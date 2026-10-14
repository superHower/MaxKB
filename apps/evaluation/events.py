# coding=utf-8
"""Capture the evidence available when a chat record is saved."""
from application.models import ApplicationVersion
from .models import EvaluationEvent


def capture_chat_record(record, application):
    details = record.details if isinstance(record.details, dict) else {}
    candidates, contexts = [], []
    prompts = []
    model_ids = set()
    for detail in details.values():
        if not isinstance(detail, dict):
            continue
        if isinstance(detail.get("paragraph_list"), list):
            candidates.extend(p for p in detail["paragraph_list"] if isinstance(p, dict))
        if detail.get("model_id"):
            model_ids.add(str(detail["model_id"]))
        for key in ("system", "question"):
            value = detail.get(key)
            if isinstance(value, str):
                prompts.append(value)
        for message in detail.get("message_list") or []:
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                prompts.append(message["content"])
    prompt_text = "\n".join(prompts)
    for paragraph in candidates:
        content = paragraph.get("content")
        if isinstance(content, str) and content and content in prompt_text:
            contexts.append(paragraph)
    version = ApplicationVersion.objects.filter(application_id=application.id).order_by("-create_time").first()
    data = {
        "chat_id": str(record.chat_id),
        "question": record.problem_text, "answer": record.answer_text,
        "retrieval_candidates": candidates, "final_contexts": contexts,
        "citation_ids": [], "citation_ids_available": False,
        "application_version": str(version.id) if version else None,
        "version_inferred": bool(version),
        "knowledge_ids": sorted({str(p["knowledge_id"]) for p in candidates if p.get("knowledge_id")}),
        "document_ids": sorted({str(p["document_id"]) for p in candidates if p.get("document_id")}),
        "model_ids": sorted(model_ids | ({str(application.model_id)} if application.model_id else set())),
        "prompt_snapshot": application.model_setting,
        "retrieval_snapshot": application.knowledge_setting,
        "latency_ms": round(record.run_time * 1000),
        "token_usage": {"input": record.message_tokens, "output": record.answer_tokens},
        "estimated_cost": record.const,
        "feedback": {"vote": record.vote_status, "reason": record.vote_reason},
        "human_handoff": None,
        "evaluable": bool(contexts),
    }
    EvaluationEvent.objects.update_or_create(
        chat_record_id=record.id,
        defaults={"workspace_id": application.workspace_id, "application_id": application.id,
                  "chat_id": record.chat_id, "data": data},
    )
