# coding=utf-8
"""Celery execution for application-scoped evaluations."""
import json
import time
import re
import hashlib

from django.db.models import QuerySet
from django.utils import timezone
from application.models import Application, ApplicationVersion, ChatRecord, ChatUserType
from application.serializers.common import ChatInfo
from chat.serializers.chat import ChatSerializers, OpenChatSerializers
from common.handle.impl.response.system_to_response import SystemToResponse
from models_provider.models import Model
from models_provider.tools import get_model_instance_by_model_workspace_id
from langchain_core.messages import HumanMessage
from ops import celery_app
from rag_eval.metrics import retrieval_metrics, total_score
from rag_eval.report import aggregate, compare, groups
from .models import Run
from tools.models import Tool, ToolType
from knowledge.models import File
from .evidence import node_evidence
from .candidates import validate_candidate  # noqa: F401 - register candidate Celery task


def _workflow_capabilities(version):
    workflow = version.work_flow if isinstance(version.work_flow, dict) else {}
    memory_enabled = bool(version.long_term_enable)
    skill_ids = set(str(item) for item in (version.skill_tool_ids or []))
    branches = set()
    for node in workflow.get("nodes", []) or []:
        data = (node.get("properties") or {}).get("node_data") or {}
        if node.get("type") == "base-node":
            memory_enabled = bool(data.get("long_term_enable", memory_enabled))
        skill_ids.update(str(item) for item in (data.get("skill_tool_ids") or []))
        for branch in data.get("branch") or []:
            branch_id = str(branch.get("id") or "")
            if branch_id in {"order", "after_sales", "inventory", "human"}:
                branches.add(branch_id)
    return {"memory_enabled": memory_enabled, "skill_ids": sorted(skill_ids),
            "skill_bound": bool(skill_ids), "business_branches": sorted(branches)}


def _resource_snapshot(version):
    workflow = version.work_flow or {}
    workflow_text = json.dumps(workflow, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    prompt_parts = []
    for node in workflow.get("nodes", []) or []:
        node_data = (node.get("properties") or {}).get("node_data") or {}
        for key in ("system", "prompt"):
            value = node_data.get(key)
            if isinstance(value, str) and value.strip():
                prompt_parts.append(value)
    if version.type == "SIMPLE":
        for key in ("system", "prompt", "no_references_prompt"):
            value = (version.model_setting or {}).get(key)
            if isinstance(value, str) and value.strip():
                prompt_parts.append(value)
        if version.problem_optimization:
            prompt_parts.append(version.problem_optimization_prompt or "")
    prompt_text = json.dumps(prompt_parts, ensure_ascii=False, separators=(",", ":"))
    skill_ids = set(str(item) for item in (version.skill_tool_ids or []))
    model_ids = {str(version.model_id)} if version.model_id else set()
    model_ids.update(str(setting["model_id"]) for setting in (version.default_model_setting or {}).values()
                     if isinstance(setting, dict) and setting.get("model_id"))
    tool_ids = {str(item) for item in
                (getattr(version, "tool_ids", []) or []) + (getattr(version, "mcp_tool_ids", []) or [])}
    for node in workflow.get("nodes", []) or []:
        node_data = (node.get("properties") or {}).get("node_data") or {}
        skill_ids.update(str(item) for item in (node_data.get("skill_tool_ids") or []))
        model_ids.update(str(value) for key, value in node_data.items() if key.endswith("model_id") and value)
        for key in ("tool_ids", "mcp_tool_ids"):
            tool_ids.update(str(item) for item in (node_data.get(key) or []))
        for key in ("tool_id", "mcp_tool_id"):
            if node_data.get(key):
                tool_ids.add(str(node_data[key]))
    skills = {}
    skill_tools = list(Tool.objects.filter(id__in=skill_ids, tool_type=ToolType.SKILL))
    skill_files = {str(item.id): item.sha256_hash for item in File.objects.filter(
        id__in=[skill.code for skill in skill_tools if skill.code])}
    for skill in skill_tools:
        skills[str(skill.id)] = {"name": skill.name, "version": skill.version,
                                 "content_id": str(skill.code), "sha256": skill_files.get(str(skill.code))}
    return {
        "application_version_id": str(version.id),
        "workflow_sha256": hashlib.sha256(workflow_text.encode("utf-8")).hexdigest(),
        "prompt_sha256": hashlib.sha256(prompt_text.encode("utf-8")).hexdigest(),
        "llm_model_id": str(version.model_id) if version.model_id else None,
        "model_ids": sorted(model_ids),
        "tool_ids": sorted(tool_ids),
        "knowledge_ids": sorted({str(item) for item in (version.knowledge_ids or [])} | {
            str(item) for node in (version.work_flow or {}).get("nodes", []) or []
            for item in (((node.get("properties") or {}).get("node_data") or {}).get("knowledge_id_list") or [])
        }),
        "skill_ids": sorted(skill_ids),
        "skills": skills,
    }


def snapshot(version, judge_id=None, embedding_id=None, dimensions=None):
    return {
        "application_version": str(version.id), "llm_model": str(version.model_id) if version.model_id else None,
        "embedding_model": str(embedding_id) if embedding_id else None, "judge_model": str(judge_id) if judge_id else None,
        "top_k": version.knowledge_setting.get("top_n"), "similarity_threshold": version.knowledge_setting.get("similarity"),
        "rerank": any(n.get("type") == "reranker-node" for n in version.work_flow.get("nodes", [])),
        "knowledge_version": None, "model_version": None,
        "rag_config_version": str(version.id), "dimensions": dimensions or {},
        "weights": {"context_precision": 1, "context_recall": 1, "hit_rate": 1, "mrr": 1},
        "evaluator_version": "rule-v1",
        "capabilities": _workflow_capabilities(version),
        "resource_snapshot": _resource_snapshot(version),
    }


def _response_text(response):
    chunks = response.streaming_content if hasattr(response, "streaming_content") else [response.content]
    answer, record_id = [], None
    for raw in chunks:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        for frame in raw.split("data: ")[1:]:
            try:
                payload = json.loads(frame.strip())
            except (TypeError, ValueError):
                continue
            answer.append(payload.get("content", ""))
            record_id = payload.get("chat_record_id") or record_id
    return "".join(answer), record_id


def _chat(application, question, user_id, application_version_id):
    source = {"type": "evaluation", "application_version_id": str(application_version_id)}
    chat_id = OpenChatSerializers(data={
        "workspace_id": application.workspace_id, "application_id": str(application.id),
        "chat_user_id": str(user_id), "chat_user_type": ChatUserType.PLATFORM_USER, "debug": False,
        "source": source, "application_version_id": str(application_version_id), "ip_address": "127.0.0.1",
    }).open()
    response = ChatSerializers(data={
        "chat_id": chat_id, "chat_user_id": str(user_id), "chat_user_type": ChatUserType.PLATFORM_USER,
        "application_id": str(application.id), "debug": False, "source": source,
        "application_version_id": str(application_version_id),
        "ip_address": "127.0.0.1",
    }).chat(
        {"message": question, "stream": True, "re_chat": False}, SystemToResponse())
    answer, record_id = _response_text(response)
    record = QuerySet(ChatRecord).filter(id=record_id, chat_id=chat_id).first()
    contexts = []
    if record:
        for detail in record.details.values():
            if isinstance(detail, dict):
                contexts.extend(detail.get("paragraph_list", []) or [])
    return answer, contexts, node_evidence(record.details) if record else {}, time.time()


def _content(response):
    value = getattr(response, "content", response)
    if isinstance(value, list):
        return "".join(str(item.get("text", item)) if isinstance(item, dict) else str(item) for item in value)
    return str(value)


def _judge(model, question, answer, contexts, ground_truth):
    context_text = "\n\n".join(str(row.get("content", "")) for row in contexts if isinstance(row, dict))
    prompt = f'''You are an evaluation judge. Return JSON only, with numeric scores from 0 to 1 and short reasons.
Keys: answer_correctness, citation_relevance, no_answer_correctness, faithfulness, reason.
Question: {question}
Reference answer: {ground_truth}
Answer: {answer}
Retrieved context:\n{context_text[:24000]}'''
    messages = [HumanMessage(content=prompt)]
    options = {}
    if "qwen" in str(getattr(model, "model_name", "")).lower():
        options["extra_body"] = {"enable_thinking": False}
    raw = _content(model.invoke(messages, **options))
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("Judge 未返回 JSON")
    payload = json.loads(match.group(0))
    scores = {}
    for key in ("answer_correctness", "citation_relevance", "no_answer_correctness", "faithfulness"):
        value = payload.get(key)
        if isinstance(value, bool):
            value = float(value)
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise ValueError(f"Judge 指标 {key} 无效")
        scores[key] = float(value)
    scores["judge_score"] = sum(scores.values()) / len(scores)
    return scores, str(payload.get("reason", ""))[:4000]


@celery_app.task(name="evaluation.evaluate", queue="celery")
def evaluate(run_id):
    run = Run.objects.select_related("dataset", "baseline").get(id=run_id)
    run.status = "running"
    run.save(update_fields=["status"])
    results = []
    try:
        application = Application.objects.get(id=run.application_id, workspace_id=run.workspace_id)
        judge = None
        if run.config.get("judge_model"):
            judge = get_model_instance_by_model_workspace_id(run.config["judge_model"], run.workspace_id,
                                                             temperature=0, max_tokens=800)
        snapshot_cases = run.config.get("dataset_snapshot", {}).get("cases")
        cases = run.dataset.cases if snapshot_cases is None else snapshot_cases
        application_version_id = run.config.get("application_version")
        if not application_version_id:
            application_version_id = str(ApplicationVersion.objects.filter(
                application_id=application.id).order_by("-create_time").values_list("id", flat=True).first())
        for case in cases:
            started = time.perf_counter()
            answer, contexts, node_details, timestamp = _chat(application, case["question"], run.user_id, application_version_id)
            scores = retrieval_metrics(contexts, case.get("relevant_doc_ids"))
            row = {**case, "answer": answer, "contexts": contexts, "node_details": node_details, "timestamp": timestamp,
                   "response_time": time.perf_counter() - started, "scores": scores, "token_usage": None,
                   "metric_errors": {}}
            if judge:
                try:
                    judge_scores, judge_reason = _judge(judge, case["question"], answer, contexts,
                                                        case.get("ground_truth", ""))
                    row["scores"].update(judge_scores)
                    row["judge"] = {"reason": judge_reason, "model": run.config["judge_model"]}
                except Exception as error:  # noqa: BLE001 - retain per-case judge failure
                    row["metric_errors"]["judge"] = str(error)
            row["total_score"] = total_score(row["scores"], run.config.get("weights", {}))
            results.append(row)
            run.completed, run.results = len(results), results
            run.save(update_fields=["completed", "results"])
        baseline = run.baseline.report if run.baseline_id else None
        comparison = compare(results, baseline, run.config, run.config.get("regression_threshold", 0.05))
        regression_passed = not run.config.get("regression") or bool(comparison and not comparison["regressions"])
        dataset_snapshot = run.config.get("dataset_snapshot", {})
        report = {"id": str(run.id), "dataset": dataset_snapshot.get("name", run.dataset.name),
                  "dataset_version": dataset_snapshot.get("version", run.dataset.version),
                  "status": "completed", "failed_cases": sum(r["total_score"] is None for r in results),
                  "config": run.config, "results": results, "summary": aggregate(results),
                  "groups": groups(results), "comparison": comparison,
                  "regression_passed": regression_passed}
        run.status, run.report, run.finished_at = ("completed" if regression_passed else "partial"), report, timezone.now()
        run.save(update_fields=["status", "report", "finished_at"])
    except Exception as error:  # noqa: BLE001
        run.status, run.error, run.finished_at = "failed", str(error), timezone.now()
        run.save(update_fields=["status", "error", "finished_at"])
        raise
