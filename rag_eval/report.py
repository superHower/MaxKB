# coding=utf-8
"""Coverage-aware reports and matched-case regression."""
import json
from collections import defaultdict


def aggregate(results):
    names = set().union(*(row["scores"] for row in results)) if results else set()
    summary = {}
    for name in sorted(names | {"total_score", "response_time"}):
        values = [(row.get(name) if name in ("total_score", "response_time") else row["scores"].get(name))
                  for row in results]
        values = [value for value in values if value is not None]
        summary[name] = {"mean": sum(values) / len(values) if values else None,
                         "count": len(values), "total": len(results)}
    return summary


def groups(results):
    grouped = defaultdict(list)
    for row in results:
        for field in ("knowledge_ids", "document_tags"):
            for value in set(row.get(field, [])):
                grouped[f"{field}:{value}"].append(row)
        grouped["category:" + row.get("category", "unclassified")].append(row)
    return {key: aggregate(rows) for key, rows in sorted(grouped.items())}


def compare(results, baseline, config, threshold):
    if not baseline:
        return None
    old = {row["id"]: row for row in baseline["results"]}
    pairs = []
    for row in results:
        previous = old.get(row["id"])
        if previous and all(row.get(key) == previous.get(key) for key in
                            ("question", "ground_truth", "relevant_doc_ids")):
            pairs.append((row, previous))
    dimensions = set().union(*(row["scores"] for row, _ in pairs)) | {"total_score"} if pairs else set()
    delta, regressions = {}, []
    for name in sorted(dimensions):
        values = []
        for row, previous in pairs:
            current = row["total_score"] if name == "total_score" else row["scores"].get(name)
            before = previous["total_score"] if name == "total_score" else previous["scores"].get(name)
            if current is not None and before is not None:
                values.append(current - before)
        delta[name] = {"delta": sum(values) / len(values) if values else None, "count": len(values)}
    for row, previous in pairs:
        drops = {}
        for name in dimensions:
            current = row["total_score"] if name == "total_score" else row["scores"].get(name)
            before = previous["total_score"] if name == "total_score" else previous["scores"].get(name)
            if current is not None and before is not None and before - current > threshold:
                drops[name] = {"before": before, "after": current, "delta": current - before}
        if drops or row.get("error") or row.get("metric_errors"):
            regressions.append({"id": row["id"], "question": row["question"], "answer": row["answer"],
                                "previous_answer": previous["answer"], "drops": drops,
                                "errors": row.get("metric_errors", {}), "error": row.get("error")})
    return {"baseline_run_id": baseline["id"], "matched_cases": len(pairs),
            "added_cases": [row["id"] for row in results if row["id"] not in old],
            "removed_cases": [key for key in old if key not in {row["id"] for row in results}],
            "config_changes": {key: {"before": baseline["config"].get(key), "after": config.get(key)}
                               for key in set(config) | set(baseline["config"])
                               if baseline["config"].get(key) != config.get(key)},
            "dimensions": delta, "regressions": regressions}


def markdown(report):
    def fmt(value):
        return "N/A" if value is None else f"{value:.4f}"

    def safe(value):
        return str(value).replace("|", "\\|").replace("\n", "<br>")

    lines = [f"# MaxKB RAG evaluation {report['id']}", "",
             f"Dataset: {report['dataset']} / {report['dataset_version']}",
             f"Status: {report['status']} | Failed cases: {report['failed_cases']}", "",
             "## Metrics", "", "| Dimension | Mean | Valid / Total | Delta |",
             "| --- | ---: | ---: | ---: |"]
    comparison = report.get("comparison") or {}
    for name, item in report["summary"].items():
        delta = comparison.get("dimensions", {}).get(name, {}).get("delta")
        lines.append(f"| {name} | {fmt(item['mean'])} | {item['count']}/{item['total']} | {fmt(delta)} |")
    fence = chr(96) * 3
    lines.extend(["", "## Configuration snapshot", "", fence + "json",
                  json.dumps(report["config"], ensure_ascii=False, indent=2), fence])
    for group, summary in report["groups"].items():
        lines.extend(["", f"## Group: {safe(group)}", "", "| Dimension | Mean | Valid / Total |",
                      "| --- | ---: | ---: |"])
        for name, item in summary.items():
            lines.append(f"| {name} | {fmt(item['mean'])} | {item['count']}/{item['total']} |")
    lines.extend(["", "## Case scores", "", "| Case | Question | Total | Scores | Errors |",
                  "| --- | --- | ---: | --- | --- |"])
    for row in report["results"]:
        lines.append(f"| {safe(row['id'])} | {safe(row['question'])} | {fmt(row['total_score'])} | "
                     f"{safe(json.dumps(row['scores'], ensure_ascii=False))} | "
                     f"{safe(row.get('error') or row.get('metric_errors', {}))} |")
    if comparison:
        lines.extend(["", f"## Regression vs {comparison['baseline_run_id']}", "",
                      f"Matched cases: {comparison['matched_cases']}"])
        for row in comparison["regressions"]:
            lines.extend(["", f"### {safe(row['id'])}", "", f"Question: {safe(row['question'])}",
                          "", f"Previous answer: {safe(row['previous_answer'])}",
                          "", f"Current answer: {safe(row['answer'])}",
                          "", f"Drops: {safe(json.dumps(row['drops']))}",
                          f"Errors: {safe(row.get('error') or row['errors'])}"])
    return "\n".join(lines) + "\n"
