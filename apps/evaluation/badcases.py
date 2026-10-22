# coding=utf-8
"""Badcase candidate detection and category suggestions."""


CATEGORIES = {"data", "retrieval", "generation", "prompt", "model", "permission", "user", "business", "other"}


def suggest(event, annotation=None, result=None):
    feedback = event.get("feedback") or {}
    if feedback.get("vote") == "1":
        return "generation", "用户点踩", "检查回答事实、引用和生成提示词"
    if event.get("human_handoff") is True:
        return "user", "该会话转人工", "检查转人工触发条件和知识覆盖"
    if not event.get("retrieval_candidates"):
        return "retrieval", "未检索到候选段落", "检查知识库内容、切片和检索参数"
    if event.get("latency_ms", 0) > 10000:
        return "model", "响应耗时超过 10 秒", "检查模型响应、重试和上下文长度"
    if event.get("estimated_cost", 0) > 0 and event.get("estimated_cost", 0) >= 100:
        return "model", "单次成本较高", "检查 Token 使用和模型配置"
    if result and result.scores.get("faithfulness_signal") is not None and result.scores["faithfulness_signal"] < .5:
        return "generation", "答案中有较多内容无法由上下文支持", "检查提示词、引用上下文和模型"
    if annotation and annotation.data.get("badcase_category") in CATEGORIES:
        return annotation.data["badcase_category"], annotation.data.get("review_note", "人工标注为 Badcase"), "按人工归因处理"
    return None
