# coding=utf-8
"""Deterministic quality signals for reviewed or sampled chat events."""
import re


EVALUATOR_VERSION = "rule-v1"
NO_ANSWER_MARKERS = ("没有在知识库中查找到", "没有找到相关", "无法回答", "不知道", "no relevant content")


def _text(value):
    return value if isinstance(value, str) else ""


def evaluate_event(data):
    answer = _text(data.get("answer"))
    contexts = data.get("final_contexts") or []
    candidates = data.get("retrieval_candidates") or []
    citation_ids = data.get("citation_ids") or []
    token_usage = data.get("token_usage") or {}
    gold_ids = set(str(value) for value in (data.get("gold_context_ids") or []))
    context_ids = [str(row.get("id")) for row in contexts if isinstance(row, dict) and row.get("id")]
    candidate_ids = [str(row.get("id")) for row in candidates if isinstance(row, dict) and row.get("id")]
    hit_count = len(gold_ids.intersection(context_ids)) if gold_ids else None
    answer_is_refusal = any(marker.lower() in answer.lower() for marker in NO_ANSWER_MARKERS)
    supported_terms = 0
    answer_terms = [term for term in re.findall(r"[\w\u4e00-\u9fff]{2,}", answer) if term not in NO_ANSWER_MARKERS]
    context_text = " ".join(_text(row.get("content")) for row in contexts if isinstance(row, dict)).lower()
    if answer_terms and context_text:
        supported_terms = sum(term.lower() in context_text for term in answer_terms)
    scores = {
        "has_context": float(bool(contexts)),
        "retrieval_hit": (float(hit_count > 0) if gold_ids else None),
        "context_recall": (hit_count / len(gold_ids) if gold_ids else None),
        "citation_ids_complete": (float(bool(citation_ids)) if data.get("citation_ids_available") else None),
        "faithfulness_signal": (supported_terms / len(answer_terms) if answer_terms and context_text else None),
        "no_answer_response": (float(answer_is_refusal) if data.get("expected_no_answer") is not None else None),
        "latency_ms": data.get("latency_ms"),
        "input_tokens": token_usage.get("input"),
        "output_tokens": token_usage.get("output"),
    }
    reasons = {
        "context": "有最终上下文" if contexts else "没有最终上下文，无法评估引用和忠实度",
        "retrieval": (f"命中 {hit_count}/{len(gold_ids)} 个标注上下文" if gold_ids else "没有标准上下文，未计算检索命中"),
        "citation": ("已记录引用 ID" if citation_ids else "未记录引用 ID，引用准确率不可评估"),
        "faithfulness": (f"答案词项中约 {supported_terms}/{len(answer_terms)} 可在上下文找到"
                          if answer_terms and context_text else "缺少答案或上下文，忠实度不可评估"),
        "no_answer": ("检测到拒答" if answer_is_refusal else "未检测到拒答"),
    }
    return {"scores": scores, "reasons": reasons, "evaluator_version": EVALUATOR_VERSION,
            "metadata": {"candidate_count": len(candidate_ids), "context_count": len(context_ids)}}
