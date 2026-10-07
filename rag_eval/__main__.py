# coding=utf-8
"""CLI and bounded asynchronous evaluation runner."""
import argparse
import asyncio
import json
import math
import sys
import uuid
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path

from .client import MaxKBClient
from .dataset import canonical, load_cases
from .metrics import retrieval_metrics, total_score
from .report import aggregate, compare, groups, markdown
from .store import Store, now


def validate_config(config):
    for name in ("concurrency", "judge_concurrency"):
        value = config.get(name, 2 if name == "concurrency" else 1)
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 64:
            raise ValueError(f"{name} must be an integer between 1 and 64")
    snapshot = config["snapshot"]
    for name in ("embedding_model", "llm_model", "top_k", "similarity_threshold", "rerank",
                 "knowledge_version", "model_version", "rag_config_version"):
        if name not in snapshot or snapshot[name] is None:
            raise ValueError(f"snapshot.{name} is required")
    if not isinstance(snapshot["rerank"], bool):
        raise TypeError("snapshot.rerank must be boolean")
    if isinstance(snapshot["top_k"], bool) or not isinstance(snapshot["top_k"], int) or snapshot["top_k"] < 1:
        raise ValueError("snapshot.top_k must be a positive integer")
    maxkb = config["maxkb"]
    if any(key not in {"base_url", "api_key_env", "timeout", "retries", "body"} for key in maxkb):
        raise ValueError("Unknown maxkb setting (credentials must use api_key_env)")
    if maxkb.get("timeout", 120) <= 0:
        raise ValueError("timeout must be positive")
    retries = maxkb.get("retries", 2)
    if isinstance(retries, bool) or not isinstance(retries, int) or not 0 <= retries <= 10:
        raise ValueError("retries must be an integer between 0 and 10")
    if config.get("retrieval_source", "log") not in ("log", "response", "none"):
        raise ValueError("retrieval_source must be log, response or none")
    judge = config.get("judge")
    for section in (judge or {}, (judge or {}).get("embedding", {})):
        if any(key in section for key in ("api_key", "token", "authorization", "headers")):
            raise ValueError("Judge credentials must use api_key_env")
    if judge:
        strictness = judge.get("completeness_strictness", 3)
        if isinstance(strictness, bool) or not isinstance(strictness, int) or strictness < 1:
            raise ValueError("completeness_strictness must be a positive integer")
    wait = config.get("context_wait_seconds", 5)
    if isinstance(wait, bool) or not isinstance(wait, (int, float)) or not math.isfinite(wait) or wait < 0:
        raise ValueError("context_wait_seconds must be a nonnegative finite number")
    dimensions = {"context_precision", "context_recall", "hit_rate", "mrr", "precision_at_k"}
    if judge:
        reserved = dimensions | {"faithfulness", "answer_relevancy", "completeness", "keypoint_coverage", "total_score"}
        if set(judge.get("dimensions", {})) & reserved:
            raise ValueError("Custom judge dimensions must not override built-in metrics")
        if any(not isinstance(text, str) or not text.strip() for text in judge.get("dimensions", {}).values()):
            raise ValueError("Custom rubrics must be nonempty text")
        dimensions |= {"faithfulness", "answer_relevancy", "completeness", "keypoint_coverage"}
        dimensions |= set(judge.get("dimensions", {}))
    weights = config["weights"]
    if not weights or any(key not in dimensions for key in weights):
        raise ValueError("weights must reference enabled metrics")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0
           for v in weights.values()):
        raise ValueError("weights must be positive finite numbers")
    if config.get("regression_threshold", 0.05) < 0:
        raise ValueError("regression_threshold must be nonnegative")


def config_snapshot(config):
    snapshot = json.loads(canonical(config))
    snapshot["snapshot_source"] = "operator_supplied"
    snapshot["metric_definitions_version"] = "1"
    snapshot["packages"] = {}
    for name in ("ragas", "langchain-openai"):
        try:
            snapshot["packages"][name] = package_version(name)
        except PackageNotFoundError:
            snapshot["packages"][name] = None
    return snapshot


async def execute(store, dataset_name, digest, cases, config, baseline=None):
    validate_config(config)
    client = MaxKBClient(config["maxkb"])
    judge = None
    if config.get("judge"):
        from .judge import Judge
        judge = Judge(config["judge"])
    snapshot = config_snapshot(config)
    run_id = str(uuid.uuid4())
    started = now()
    store.start(run_id, dataset_name, digest, snapshot)
    chat_limit = asyncio.Semaphore(config.get("concurrency", 2))
    judge_limit = asyncio.Semaphore(config.get("judge_concurrency", 1))

    async def one(case):
        async with chat_limit:
            result = await asyncio.to_thread(client.ask, case["question"])
        contexts = result.get("contexts")
        try:
            if config.get("retrieval_source", "log") == "log" and not result.get("error"):
                deadline = asyncio.get_running_loop().time() + config.get("context_wait_seconds", 5)
                while True:
                    contexts = store.contexts(result.get("chat_id"), result.get("chat_record_id"))
                    if contexts is not None or asyncio.get_running_loop().time() >= deadline:
                        break
                    await asyncio.sleep(0.2)
            elif config.get("retrieval_source") == "none":
                contexts = None
            if contexts is not None:
                if not isinstance(contexts, list):
                    raise ValueError("retrieval contexts must be an array")
                for row in contexts:
                    if (not isinstance(row, dict) or not row.get("document_id") or
                            not isinstance(row.get("content"), str)):
                        raise ValueError("invalid context schema")
        except Exception as error:  # noqa: BLE001 - isolate malformed context per case
            contexts = None
            result["context_error"] = type(error).__name__
        result = {**case, **result, "contexts": contexts}
        result["scores"] = retrieval_metrics(contexts, case.get("relevant_doc_ids"))
        result["metric_errors"] = {}
        result["judge_reasons"] = {}
        if contexts is None and config.get("retrieval_source", "log") != "none" and not result.get("error"):
            result["metric_errors"]["retrieval"] = result.get("context_error", "Missing final-context log")
        if judge and not result.get("error"):
            async with judge_limit:
                scores, reasons, errors = await judge.score(case, result["answer"], contexts)
            result["scores"].update(scores)
            result["judge_reasons"] = reasons
            result["metric_errors"].update(errors)
        result["total_score"] = total_score(result["scores"], config["weights"])
        if not case.get("knowledge_ids") and contexts:
            result["knowledge_ids"] = sorted({str(row["knowledge_id"]) for row in contexts if row.get("knowledge_id")})
        if not case.get("document_tags") and contexts:
            result["document_tags"] = sorted({tag for row in contexts for tag in row.get("document_tags", [])})
        store.save_result(run_id, result)
        return result

    queue = asyncio.Queue()
    for index, case in enumerate(cases):
        queue.put_nowait((index, case))
    results = [None] * len(cases)

    async def worker():
        while not queue.empty():
            index, case = queue.get_nowait()
            results[index] = await one(case)

    try:
        await asyncio.gather(*(worker() for _ in range(config.get("concurrency", 2))))
        failed = sum(bool(r.get("error") or r["metric_errors"] or r["total_score"] is None) for r in results)
        report = {"id": run_id, "dataset": dataset_name, "dataset_version": digest, "started_at": started,
                  "finished_at": now(), "status": "completed" if not failed else "partial",
                  "failed_cases": failed, "config": snapshot, "results": results,
                  "summary": aggregate(results), "groups": groups(results),
                  "comparison": compare(results, baseline, snapshot, config.get("regression_threshold", 0.05))}
    except BaseException:
        available = [row for row in results if row is not None]
        store.finish(run_id, {"id": run_id, "status": "failed", "results": available, "config": snapshot,
                              "dataset": dataset_name, "dataset_version": digest})
        raise
    store.finish(run_id, report)
    return report


def export(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{report['id']}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / f"{report['id']}.md").write_text(markdown(report), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description="MaxKB RAG regression evaluation")
    parser.add_argument("--db", default="data/rag_eval.sqlite3")
    sub = parser.add_subparsers(dest="command", required=True)
    importer = sub.add_parser("import")
    importer.add_argument("name")
    importer.add_argument("file")
    runner = sub.add_parser("run")
    runner.add_argument("name")
    runner.add_argument("--version")
    runner.add_argument("--config", required=True)
    runner.add_argument("--baseline")
    runner.add_argument("--output", default="data/rag_eval_reports")
    runner.add_argument("--fail-on-regression", action="store_true")
    logger = sub.add_parser("log-context")
    logger.add_argument("file", help="JSON: chat_id, chat_record_id, contexts (final LLM input order)")
    exporter = sub.add_parser("export")
    exporter.add_argument("run_id")
    exporter.add_argument("--output", default="data/rag_eval_reports")
    args = parser.parse_args(argv)
    store = Store(args.db)
    try:
        if args.command == "import":
            cases = load_cases(args.file)
            print(store.import_dataset(args.name, cases))
            print("categories:", ", ".join(sorted({c.get("category", "unclassified") for c in cases})))
            return 0
        if args.command == "log-context":
            payload = json.loads(Path(args.file).read_text(encoding="utf-8-sig"))
            store.log_context(payload["chat_id"], payload["chat_record_id"], payload["contexts"])
            return 0
        if args.command == "export":
            report = store.baseline("", "", args.run_id)
            if "summary" not in report:
                raise ValueError("Failed run has no complete report")
            export(report, args.output)
            return 0
        config = json.loads(Path(args.config).read_text(encoding="utf-8-sig"))
        digest, cases = store.dataset(args.name, args.version)
        baseline = store.baseline(args.name, digest, args.baseline)
        report = asyncio.run(execute(store, args.name, digest, cases, config, baseline))
        export(report, args.output)
        print(json.dumps({"run_id": report["id"], "status": report["status"], "summary": report["summary"]},
                         ensure_ascii=False))
        if report["status"] != "completed":
            return 2
        if args.fail_on_regression and report["comparison"] and report["comparison"]["regressions"]:
            return 3
        return 0
    finally:
        store.close()


if __name__ == "__main__":
    sys.exit(main())
