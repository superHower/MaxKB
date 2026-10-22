# coding=utf-8
"""Capture the evidence available when a chat record is saved."""
from application.models import ApplicationVersion
from .models import EvaluationEvent


def _workflow_capabilities(application):
    """Return the configured memory/skill/business branch facts for trace display.

    These are configuration facts, not proof that a business operation succeeded.
    """
    workflow = application.work_flow if isinstance(getattr(application, "work_flow", None), dict) else {}
    memory_enabled = bool(getattr(application, "long_term_enable", False))
    skill_ids = set(str(item) for item in (getattr(application, "skill_tool_ids", None) or []))
    business_branches = set()
    for node in workflow.get("nodes", []) or []:
        node_data = (node.get("properties") or {}).get("node_data") or {}
        if node.get("type") == "base-node":
            memory_enabled = bool(node_data.get("long_term_enable", memory_enabled))
        skill_ids.update(str(item) for item in (node_data.get("skill_tool_ids") or []))
        for branch in node_data.get("branch") or []:
            branch_id = str(branch.get("id") or "")
            if branch_id in {"order", "after_sales", "inventory", "human"}:
                business_branches.add(branch_id)
    return {"memory_enabled": memory_enabled, "skill_ids": sorted(skill_ids),
            "skill_bound": bool(skill_ids), "business_branches": sorted(business_branches)}


def capture_chat_record(record, application):
    details = record.details if isinstance(record.details, dict) else {}
    candidates, contexts = [], []
    prompts = []
    model_ids = set()
    intent_categories = []
    tool_call_count = 0
    confirmation_requested = False
    confirmation_confirmed = False
    for detail in details.values():
        if not isinstance(detail, dict):
            continue
        if detail.get("category"):
            intent_categories.append(str(detail["category"]))
        if detail.get("type") in {"tool-node", "tool-lib-node", "tool-workflow-lib-node", "mcp-node"}:
            tool_call_count += 1
        if detail.get("type") == "form-node":
            confirmation_requested = True
            confirmation_confirmed = confirmation_confirmed or detail.get("is_submit") is True
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
    capabilities = _workflow_capabilities(application)
    memory_used = any(
        isinstance(field, dict) and field.get("key") == "memory" and bool(field.get("value"))
        for detail in details.values() if isinstance(detail, dict)
        for field in detail.get("global_fields", []) or []
    )
    intent_category = intent_categories[-1] if intent_categories else None
    configured_business_branch = intent_category in set(capabilities["business_branches"])
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
        "intent_category": intent_category,
        "capabilities": {**capabilities, "memory_used": memory_used,
                          "business_branch_configured": configured_business_branch,
                          "business_tool_call_present": bool(tool_call_count) if configured_business_branch else None},
        "tool_call_count": tool_call_count,
        "confirmation_required": confirmation_requested if confirmation_requested else None,
        "confirmation_confirmed": confirmation_confirmed if confirmation_requested else None,
        # These fields are intentionally nullable until a business system or reviewer supplies ground truth.
        "task_success": (record.source or {}).get("task_success") if isinstance(record.source, dict) else None,
        "tool_call_accuracy": (record.source or {}).get("tool_call_accuracy") if isinstance(record.source, dict) else None,
        "experiment_id": (record.source or {}).get("experiment_id") if isinstance(record.source, dict) else None,
        "experiment_variant": (record.source or {}).get("experiment_variant") if isinstance(record.source, dict) else None,
        "evaluable": bool(contexts),
    }
    EvaluationEvent.objects.update_or_create(
        chat_record_id=record.id,
        defaults={"workspace_id": application.workspace_id, "application_id": application.id,
                  "chat_id": record.chat_id, "data": data},
    )
