# coding=utf-8
"""Improvement closure: apply a reviewed draft to the editable workflow, verify the published
version against the baseline plus the source Badcase questions, then close Badcases by evidence.

Applying never publishes; publishing stays a human action in the application editor.
"""
import copy
import hashlib
import json

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from application.models import ApplicationVersion
from .candidates import audit
from .models import Badcase, ImprovementCandidate, Run

PASS_SCORE = 0.6


def _node_value(kind, field, data):
    return data if kind == "workflow_patch" else (data or {}).get(field, "")


def _same(kind, value, text):
    if kind != "workflow_patch":
        return value == text
    try:
        return value == json.loads(text)
    except (TypeError, ValueError):
        return False


def _target(application_type, holder, node_id):
    """Return the mutable dict that owns the patched field (model_setting or node_data)."""
    if application_type == "SIMPLE":
        return holder
    node = next((n for n in (holder or {}).get("nodes", []) or [] if n.get("id") == node_id), None)
    if node is None:
        raise ValidationError("编排中找不到候选修改的节点，可能已被删除")
    return node.setdefault("properties", {}).setdefault("node_data", {})


def _contains(version, item):
    patch = item.spec["patch"]
    try:
        holder = version.model_setting if version.type == "SIMPLE" else version.work_flow
        data = _target(version.type, copy.deepcopy(holder or {}), patch["node_id"])
    except ValidationError:
        return False
    return _same(item.kind, _node_value(item.kind, patch["field"], data), patch["content"])


def apply_draft(item, application, actor):
    spec = item.spec
    if not spec.get("draft_only"):
        raise ValidationError("只有修改草稿可以应用到编排")
    if item.status not in {"draft", "rejected", "applied", "verify_failed", "needs_review"}:
        raise ValidationError("当前状态不能应用到编排")
    patch, kind = spec["patch"], item.kind
    if application.type == "SIMPLE" and kind != "prompt_patch":
        raise ValidationError("简单应用只支持提示词修改")
    holder = copy.deepcopy((application.model_setting if application.type == "SIMPLE" else application.work_flow) or {})
    data = _target(application.type, holder, patch["node_id"])
    current = _node_value(kind, patch["field"], data)
    previous = (spec.get("closure") or {}).get("applied_content")
    already = _same(kind, current, patch["content"])
    if not already and not _same(kind, current, patch["before"]) and not (previous and _same(kind, current, previous)):
        raise ValidationError("编排草稿中该节点已被改动，与候选记录的原配置不一致，请到应用编排中手动合并")
    if not already:
        if kind == "workflow_patch":
            data.clear()
            data.update(json.loads(patch["content"]))
        else:
            data[patch["field"]] = patch["content"]
        if application.type == "SIMPLE":
            application.model_setting = holder
        else:
            application.work_flow = holder
        application.save()
    item.spec = {**spec, "closure": {"applied_at": timezone.now().isoformat(), "applied_by": str(actor),
                                     "applied_content": patch["content"]}}
    item.status = "applied"
    Badcase.objects.filter(id__in=[s["id"] for s in spec.get("sources", [])], status="open").update(status="in_progress")
    audit(item, actor, "applied", {"node_id": patch["node_id"], "already_applied": already})


def _badcase_cases(item):
    """One frozen case per distinct source question; the gold answer comes from the latest annotation."""
    sources = Badcase.objects.filter(id__in=[s["id"] for s in item.spec.get("sources", [])]).select_related(
        "sample__source_event")
    cases, owners = {}, {}
    for badcase in sources:
        question = str((badcase.sample.source_event.data or {}).get("question") or "").strip()
        if not question:
            continue
        case_id = "badcase:" + hashlib.sha256(question.encode()).hexdigest()[:16]
        annotation = badcase.sample.annotations.order_by("-revision").first()
        gold = str((annotation.data if annotation else {}).get("gold_answer") or "").strip()
        case = cases.setdefault(case_id, {"id": case_id, "question": question, "ground_truth": "",
                                          "category": "badcase"})
        case["ground_truth"] = case["ground_truth"] or gold
        owners.setdefault(case_id, []).append(str(badcase.id))
    return list(cases.values()), owners


def start_verification(item, actor):
    if not item.spec.get("draft_only") or item.status not in {"applied", "verify_failed", "needs_review", "verified"}:
        raise ValidationError("请先把修改应用到编排")
    if Run.objects.filter(application_id=item.application_id, status__in=["queued", "running"]).exists():
        raise ValidationError("此应用已有评测正在执行，请等待完成")
    published = ApplicationVersion.objects.filter(application_id=item.application_id).order_by("-create_time").first()
    if published is None or str(published.id) == item.spec.get("base_version_id") or not _contains(published, item):
        raise ValidationError("最新发布版本还不包含这项修改，请先到应用编排发布")
    baseline = Run.objects.filter(id=item.spec.get("baseline_id"), application_id=item.application_id,
                                  status__in=["completed", "partial"]).select_related("dataset").first()
    if baseline is None or "cases" not in baseline.config.get("dataset_snapshot", {}):
        raise ValidationError("基线测评不存在或缺少冻结题目，无法回归")
    extra, owners = _badcase_cases(item)
    from .settings import retrieval_settings
    from .tasks import snapshot
    source = baseline.config
    config = snapshot(published, source.get("judge_model"), source.get("embedding_model"), source.get("dimensions"))
    frozen = source["dataset_snapshot"]
    known = {case["id"] for case in frozen["cases"]}
    config["dataset_snapshot"] = {**frozen, "name": f"{frozen.get('name', baseline.dataset.name)} + Badcase",
                                  "cases": copy.deepcopy(frozen["cases"]) + [c for c in extra if c["id"] not in known]}
    config.update({"regression": True, "regression_threshold": source.get("regression_threshold", 0.05),
                   "verification": {"candidate_id": str(item.id), "badcases": owners}})
    for key in ("judge_prompt", "judge_settings"):
        if key in source:
            config[key] = copy.deepcopy(source[key])
    config["retrieval_settings"] = retrieval_settings(published)
    run = Run.objects.create(application_id=item.application_id, workspace_id=item.workspace_id, user_id=actor,
                             dataset=baseline.dataset, baseline=baseline, config=config)
    closure = {**(item.spec.get("closure") or {}), "run_id": str(run.id), "version_id": str(published.id),
               "started_at": timezone.now().isoformat()}
    closure.pop("result", None)
    item.spec = {**item.spec, "closure": closure}
    item.status = "verifying"
    audit(item, actor, "verification_started", {"run_id": str(run.id), "version_id": str(published.id)})
    return run


def case_verdict(row):
    """passed / failed / needs_review from the evidence the run captured for this question."""
    trace = row.get("trace") or {}
    if row.get("error") or trace.get("failed_step") is not None:
        return "failed"
    scores = row.get("scores") or {}
    if any(scores.get(key) == 0 for key in ("branch_correct", "tool_order_correct")):
        return "failed"
    keys = ("answer_correctness",) if row.get("ground_truth") else ("faithfulness", "no_answer_correctness")
    values = [scores.get(key) for key in keys if scores.get(key) is not None]
    if not values:
        return "needs_review"
    return "passed" if min(values) >= PASS_SCORE else "failed"


def finish_verification(run):
    info = run.config["verification"]
    with transaction.atomic():
        item = ImprovementCandidate.objects.select_for_update().filter(id=info["candidate_id"]).first()
        if item is None or (item.spec.get("closure") or {}).get("run_id") != str(run.id):
            return
        rows = {str(row.get("id")): row for row in run.results}
        regression_ok = run.status != "failed" and bool(run.report.get("regression_passed"))
        regressions = len((run.report.get("comparison") or {}).get("regressions") or [])
        cases, closed = [], []
        for case_id, badcase_ids in info.get("badcases", {}).items():
            row = rows.get(case_id)
            verdict = case_verdict(row) if row else "failed"
            cases.append({"id": case_id, "question": (row or {}).get("question"), "verdict": verdict,
                          "answer": str((row or {}).get("answer") or "")[:4000], "badcase_ids": badcase_ids,
                          "scores": (row or {}).get("scores", {})})
            if verdict == "passed" and regression_ok:
                closed += badcase_ids
        Badcase.objects.filter(id__in=closed).exclude(status="resolved").update(
            status="resolved", resolved_at=timezone.now(),
            resolution=f"改进方案「{item.title}」应用发布后回归通过（测评 {run.id}）")
        verdicts = {case["verdict"] for case in cases}
        if run.status == "failed" or not regression_ok or "failed" in verdicts:
            item.status = "verify_failed"
        elif "needs_review" in verdicts:
            item.status = "needs_review"
        else:
            item.status = "verified"
        result = {"run_status": run.status, "run_error": run.error, "regression_passed": regression_ok,
                  "regressions": regressions, "cases": cases, "closed_badcases": closed,
                  "finished_at": timezone.now().isoformat()}
        item.spec = {**item.spec, "closure": {**item.spec["closure"], "result": result}}
        item.save(update_fields=["spec", "status", "updated_at"])
        audit(item, run.user_id, "verification_finished", {"run_id": str(run.id), "status": item.status,
                                                           "closed_badcases": closed})
