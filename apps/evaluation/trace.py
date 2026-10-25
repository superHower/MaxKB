# coding=utf-8
"""Normalized execution trace shared by offline runs and online events.

Each step names the node, its branch decision, tool call or retrieval parameters, so every failure
can be located to a concrete node, branch or retrieval setting instead of a raw details blob.
"""
import json

TOOL_TYPES = {"tool-lib-node", "tool-node", "tool-workflow-lib-node", "mcp-node", "application-node"}
RETRIEVAL_TYPES = {"search-knowledge-node", "search-document-node", "reranker-node", "search_step"}
LLM_TYPES = {"ai-chat-node", "question-node", "chat_step", "parameter-extraction-node"}
BRANCH_TYPES = {"intent-node", "condition-node"}
TRACE_VERSION = 1


def _clip(value, size=2000):
    if value is None:
        return None
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= size else text[:size] + "…"


def _kind(node_type):
    if node_type in TOOL_TYPES:
        return "tool"
    if node_type in RETRIEVAL_TYPES:
        return "retrieval"
    if node_type in BRANCH_TYPES:
        return "branch"
    if node_type in LLM_TYPES:
        return "llm"
    return "other"


def _config_nodes(workflow):
    nodes = (workflow or {}).get("nodes", []) if isinstance(workflow, dict) else []
    return {str(node.get("id")): node for node in nodes or [] if isinstance(node, dict)}


def _branch_label(data, branch_id):
    for branch in data.get("branch") or []:
        if isinstance(branch, dict) and str(branch.get("id")) == str(branch_id):
            return branch.get("content") or branch.get("type") or branch.get("name")
    return None


def build_trace(details, workflow=None, turn=None):
    """Return ordered steps; configuration comes from the executed version's workflow when available."""
    config = _config_nodes(workflow)
    rows = [row for row in (details or {}).values() if isinstance(row, dict)] if isinstance(details, dict) else []
    rows.sort(key=lambda row: (row.get("index") is None, row.get("index") or 0))
    steps = []
    for position, detail in enumerate(rows):
        node_id = str(detail.get("node_id") or "")
        node = config.get(node_id, {})
        data = (node.get("properties") or {}).get("node_data") or {}
        node_type = str(detail.get("type") or detail.get("step_type") or node.get("type") or "")
        failed = bool(detail.get("err_message")) or (detail.get("status") is not None and
                                                     str(detail.get("status")) != "200")
        step = {"index": position, "node_id": node_id or None, "runtime_node_id": detail.get("runtime_node_id"),
                "up_node_ids": list(detail.get("up_node_id_list") or []),
                "name": detail.get("name") or (node.get("properties") or {}).get("stepName") or node_type,
                "type": node_type, "kind": _kind(node_type), "status": "failed" if failed else "success",
                "error": _clip(detail.get("err_message"), 4000), "run_time": detail.get("run_time")}
        if step["kind"] == "branch":
            branch_id = detail.get("branch_id")
            step["branch"] = {"id": branch_id, "category": detail.get("category"),
                              "name": detail.get("branch_name") or _branch_label(data, branch_id) or detail.get("category")}
        elif step["kind"] == "tool":
            step["tool"] = {"id": str(data.get("tool_lib_id") or data.get("mcp_tool_id") or data.get("application_id")
                                     or "") or None,
                            "name": detail.get("mcp_tool") or data.get("mcp_tool") or step["name"],
                            "params": detail.get("params") if detail.get("params") is not None else detail.get("tool_params"),
                            "result": _clip(detail.get("result"))}
        elif step["kind"] == "retrieval":
            setting = data.get("knowledge_setting") or data.get("dataset_setting") or {}
            paragraphs = detail.get("paragraph_list")
            step["retrieval"] = {"question": _clip(detail.get("question"), 1000),
                                 "knowledge_ids": [str(i) for i in (data.get("knowledge_id_list")
                                                                    or data.get("dataset_id_list") or [])],
                                 "top_n": setting.get("top_n"), "similarity": setting.get("similarity"),
                                 "search_mode": setting.get("search_mode"),
                                 "hit_count": len(paragraphs) if isinstance(paragraphs, list) else None}
        elif step["kind"] == "llm":
            step["llm"] = {"model_id": str(data.get("model_id") or "") or None,
                           "message_tokens": detail.get("message_tokens"), "answer_tokens": detail.get("answer_tokens")}
        steps.append(step)
    failed = next((step["index"] for step in steps if step["status"] == "failed"), None)
    return {"version": TRACE_VERSION, "turn": turn, "steps": steps, "failed_step": failed,
            "branches": [{"node_id": s["node_id"], "node_name": s["name"], **s["branch"]} for s in steps if "branch" in s],
            "tool_calls": [{"node_id": s["node_id"], "status": s["status"], **s["tool"]} for s in steps if "tool" in s]}


def _identifiers(call):
    return {str(value).strip().lower() for value in (call.get("id"), call.get("name"), call.get("node_id"))
            if value}


def trace_scores(trace, case):
    """Assertions declared on a case; absent expectations produce no score rather than a zero."""
    scores = {}
    calls = trace.get("tool_calls") or []
    expected = case.get("expected_tools")
    if isinstance(expected, list):
        wanted = [str(item).strip().lower() for item in expected]
        if not wanted:
            scores["tool_call_accuracy"] = 0.0 if calls else 1.0
        else:
            called = [_identifiers(call) for call in calls]
            matched = [any(name in ids for ids in called) for name in wanted]
            scores["tool_call_accuracy"] = sum(matched) / len(wanted)
            position, ordered = 0, True
            for name in wanted:
                found = next((i for i in range(position, len(called)) if name in called[i]), None)
                if found is None:
                    ordered = False
                    break
                position = found + 1
            scores["tool_order_correct"] = float(ordered)
        if calls:
            scores["tool_error_rate"] = sum(call["status"] == "failed" for call in calls) / len(calls)
    branch = case.get("expected_branch")
    if isinstance(branch, str) and branch.strip():
        target = branch.strip().lower()
        taken = {str(value).strip().lower() for row in trace.get("branches") or []
                 for value in (row.get("id"), row.get("name"), row.get("category")) if value}
        scores["branch_correct"] = float(target in taken)
    return scores
