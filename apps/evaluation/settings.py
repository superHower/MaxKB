# coding=utf-8
"""Validated Judge settings and published retrieval configuration for evaluation."""
import math

from rest_framework.exceptions import ValidationError


DEFAULT_JUDGE_SETTINGS = {"max_tokens": 4096, "temperature": 0, "thinking": "auto", "json_mode": False}


def judge_settings(value):
    if not isinstance(value, dict) or set(value) - set(DEFAULT_JUDGE_SETTINGS):
        raise ValidationError("Judge 参数包含不支持的字段")
    settings = {**DEFAULT_JUDGE_SETTINGS, **value}
    tokens, temperature = settings["max_tokens"], settings["temperature"]
    if isinstance(tokens, bool) or not isinstance(tokens, int) or not 256 <= tokens <= 32768:
        raise ValidationError("Judge 输出 token 上限必须是 256～32768 的整数")
    if (isinstance(temperature, bool) or not isinstance(temperature, (int, float))
            or not math.isfinite(temperature) or not 0 <= temperature <= 1):
        raise ValidationError("Judge 温度必须在 0～1 之间")
    if settings["thinking"] not in ("auto", "disabled", "enabled"):
        raise ValidationError("Judge 思考模式无效")
    if not isinstance(settings["json_mode"], bool):
        raise ValidationError("Judge JSON 模式必须为布尔值")
    return settings


def retrieval_settings(version):
    if version is None:
        return {"version_id": None, "nodes": [], "edges": []}
    workflow = version.work_flow or {}
    nodes = []
    for node in workflow.get("nodes", []):
        properties = node.get("properties") or {}
        data = properties.get("node_data") or {}
        if node.get("type") not in {"search-knowledge-node", "search-document-node", "reranker-node",
                                    "condition-node", "reply-node", "intent-node", "ai-chat-node"}:
            continue
        nodes.append({"id": node["id"], "name": properties.get("stepName", node["id"]), "type": node["type"],
                      "knowledge_ids": data.get("knowledge_id_list", []),
                      "settings": data.get("knowledge_setting", data.get("reranker_setting", {})),
                      "branches": data.get("branch", []) if node.get("type") in {
                          "intent-node", "condition-node"} else [],
                      "reply": data.get("content") if node.get("type") == "reply-node" else None,
                      "exception_enabled": properties.get("enableException", False)})
    return {"version_id": str(version.id), "type": version.type, "nodes": nodes,
            "knowledge_ids": version.knowledge_ids or [], "settings": version.knowledge_setting or {},
            "no_references": (version.knowledge_setting or {}).get("no_references_setting", {}),
            "edges": [{"source": e.get("sourceNodeId"), "target": e.get("targetNodeId")}
                      for e in workflow.get("edges", [])]}
