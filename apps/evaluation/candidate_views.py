# coding=utf-8
"""Application-scoped candidate lifecycle, optimistic edits and approval audit."""
import copy

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from application.models import Application, ApplicationVersion
from common.auth import TokenAuth
from common.result import result
from .badcases import CATEGORIES
from .candidates import (audit, build_spec, candidate_artifact, candidate_data, digest, identifier,
                         model_fingerprint, text, validate_candidate)
from .models import Badcase, CapabilityVersion, CandidateValidation, ImprovementCandidate, Run
from .views import access, scope


def scoped_candidate(workspace_id, application_id, candidate_id, lock=False):
    query = ImprovementCandidate.objects.select_for_update() if lock else ImprovementCandidate.objects
    return get_object_or_404(query, id=candidate_id, workspace_id=workspace_id, application_id=application_id)


def check_revision(item, data):
    if data.get("revision") != item.revision:
        raise ValidationError("候选已被修改，请刷新后重试")


def save_candidate(item, data, workspace_id, application_id, actor):
    if item.status in {"validating", "approved", "withdrawn"}:
        raise ValidationError("当前状态不能修改；请等待验证或创建新候选")
    baseline = get_object_or_404(Run, id=identifier(data.get("baseline_id"), "基线"), workspace_id=workspace_id,
                                 application_id=application_id)
    source_ids = data.get("badcase_ids", [])
    if not isinstance(source_ids, list) or len(source_ids) > 50:
        raise ValidationError("最多关联 50 条 Badcase")
    source_ids = [identifier(value, "Badcase") for value in source_ids]
    sources = list(Badcase.objects.filter(id__in=source_ids, sample__workspace_id=workspace_id,
                                         sample__application_id=application_id).select_related("sample__source_event"))
    if len(sources) != len(set(source_ids)):
        raise ValidationError("来源 Badcase 不存在或不属于当前应用")
    category = data.get("category", "other")
    if category not in CATEGORIES:
        raise ValidationError("问题类别无效")
    source = data.get("source", "manual")
    if source not in {"manual", "template"}:
        raise ValidationError("仅支持人工或模板候选")
    item.title, item.kind = text(data.get("title"), "标题", 128), data.get("kind")
    item.category, item.source = category, source
    item.spec = build_spec(data, baseline, sources)
    item.status = "draft"
    item.save()
    audit(item, actor, "saved", {"spec": item.spec, "sha256": digest(item.spec)})


class Candidates(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id):
        scope(workspace_id, application_id)
        query = ImprovementCandidate.objects.filter(workspace_id=workspace_id, application_id=application_id)
        for field in ("status", "category", "source", "kind"):
            if request.query_params.get(field):
                query = query.filter(**{field: request.query_params[field]})
        if request.query_params.get("version"):
            query = query.filter(spec__base_version_id=request.query_params["version"])
        if request.query_params.get("search"):
            query = query.filter(title__icontains=request.query_params["search"][:128])
        return result.success([candidate_data(c) for c in query.order_by("-updated_at")[:100]])

    @access
    def post(self, request, workspace_id, application_id):
        with transaction.atomic():
            scope(workspace_id, application_id)
            item = ImprovementCandidate(workspace_id=workspace_id, application_id=application_id,
                                         created_by=request.user.id)
            save_candidate(item, request.data, workspace_id, application_id, request.user.id)
        return result.success(candidate_data(item, True))


class CandidateDetail(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id, candidate_id):
        scope(workspace_id, application_id)
        return result.success(candidate_data(scoped_candidate(workspace_id, application_id, candidate_id), True))

    @access
    def put(self, request, workspace_id, application_id, candidate_id):
        with transaction.atomic():
            scope(workspace_id, application_id)
            item = scoped_candidate(workspace_id, application_id, candidate_id, True)
            check_revision(item, request.data)
            item.revision += 1
            save_candidate(item, request.data, workspace_id, application_id, request.user.id)
        return result.success(candidate_data(item, True))


class CandidateAction(APIView):
    authentication_classes = [TokenAuth]

    @access
    def post(self, request, workspace_id, application_id, candidate_id):
        validation_id = None
        with transaction.atomic():
            get_object_or_404(Application.objects.select_for_update(), id=application_id, workspace_id=workspace_id)
            item = scoped_candidate(workspace_id, application_id, candidate_id, True)
            check_revision(item, request.data)
            action = request.data.get("action")
            if action == "validate":
                if item.status not in {"draft", "rejected", "validation_failed", "pending_review"}:
                    raise ValidationError("当前状态不能开始验证")
                if CandidateValidation.objects.filter(candidate__application_id=application_id,
                                                       status__in=["queued", "running"]).exists():
                    raise ValidationError("当前应用已有候选验证，请等待完成")
                validation = CandidateValidation.objects.create(
                    candidate=item, revision=item.revision, created_by=request.user.id,
                    snapshot={"spec": copy.deepcopy(item.spec), "kind": item.kind,
                              "sha256": digest(item.spec), "revision": item.revision})
                item.status, validation_id = "validating", str(validation.id)
                audit(item, request.user.id, "validation_started", {"validation_id": validation_id})
            elif action == "cancel_validation":
                if item.status != "validating":
                    raise ValidationError("当前没有进行中的验证")
                reason = text(request.data.get("reason"), "取消原因", 4000)
                item.validations.filter(status__in=["queued", "running"]).update(
                    status="cancelled", error=reason, finished_at=timezone.now())
                item.status = "validation_failed"
                audit(item, request.user.id, action, {"reason": reason})
            elif action in {"reject", "withdraw"}:
                if item.status in {"validating", "withdrawn"} or (action == "reject" and item.status == "approved"):
                    raise ValidationError("当前状态不能执行该操作")
                reason = text(request.data.get("reason"), "原因", 4000)
                item.status = "rejected" if action == "reject" else "withdrawn"
                if action == "withdraw":
                    item.capability_versions.update(status="withdrawn")
                audit(item, request.user.id, action, {"reason": reason})
            elif action == "approve":
                if item.status not in {"pending_review", "validation_failed"}:
                    raise ValidationError("请先完成当前修订的验证")
                validation = item.validations.order_by("-created_at").first()
                if (not validation or validation.revision != item.revision
                        or validation.snapshot.get("sha256") != digest(item.spec)
                        or validation.status not in {"passed", "failed"} or not validation.report.get("checks")):
                    raise ValidationError("验证记录缺失或已过期，请重新验证")
                from models_provider.models import Model
                for model_id, fingerprint in item.spec.get("model_fingerprints", {}).items():
                    current = Model.objects.filter(id=model_id, workspace_id=workspace_id, status="SUCCESS").first()
                    if current is None or model_fingerprint(current) != fingerprint:
                        raise ValidationError("模型配置已变化，请修改候选后重新验证")
                waivers = request.data.get("waivers", {})
                if not isinstance(waivers, dict):
                    raise ValidationError("豁免必须为类别与原因的映射")
                failed = [c for c in validation.report["checks"] if not c["passed"]]
                allowed = {c["key"] for c in failed if c["waivable"]}
                if set(waivers) - allowed:
                    raise ValidationError("只能豁免报告中退化的业务类别")
                for check in failed:
                    if not check["waivable"]:
                        raise ValidationError("硬门禁未通过或缺少数据，不能批准")
                    text(waivers.get(check["key"]), "关键类别退化豁免原因", 4000)
                impact = text(request.data.get("impact_scope"), "影响范围", 4000)
                rollback_id = identifier(request.data.get("rollback_version_id"), "回滚点")
                rollback = get_object_or_404(ApplicationVersion, id=rollback_id,
                                             application_id=application_id, workspace_id=workspace_id)
                from .candidates import version_snapshot
                manifest = {"candidate_id": str(item.id), "revision": item.revision,
                            "kind": item.kind, "spec": copy.deepcopy(item.spec),
                            "artifact": candidate_artifact(item.spec, item.kind),
                            "validation_id": str(validation.id), "report": copy.deepcopy(validation.report),
                            "approved_by": str(request.user.id), "impact_scope": impact,
                            "rollback_version": version_snapshot(rollback), "waivers": waivers,
                            "production_changed": False}
                CapabilityVersion.objects.create(candidate=item, validation=validation, manifest=manifest,
                                                  approved_by=request.user.id)
                item.status = "approved"
                audit(item, request.user.id, "approved", {"impact_scope": impact, "waivers": waivers,
                                                          "rollback_version_id": str(rollback.id),
                                                          "validation_id": str(validation.id)})
            else:
                raise ValidationError("未知候选操作")
            item.save(update_fields=["status", "updated_at"])
        if validation_id:
            try:
                validate_candidate.delay(validation_id)
            except Exception as exc:
                with transaction.atomic():
                    CandidateValidation.objects.filter(id=validation_id, status="queued").update(
                        status="failed", error="任务提交失败", finished_at=timezone.now())
                    ImprovementCandidate.objects.filter(id=item.id, status="validating").update(status="validation_failed")
                    audit(item, request.user.id, "validation_submission_failed", {"validation_id": validation_id})
                raise ValidationError("任务提交失败，请检查 Celery 后重新验证") from exc
        return result.success(candidate_data(item, True))


class CandidateOptions(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id):
        scope(workspace_id, application_id)
        versions = ApplicationVersion.objects.filter(application_id=application_id, workspace_id=workspace_id)
        return result.success({"versions": [{"id": str(v.id), "name": v.name or str(v.create_time),
                                             "type": v.type, "targets": ([{"id": "", "name": "应用回答"}]
                                             if v.type == "SIMPLE" else [
                                                 {"id": n["id"], "name": (n.get("properties") or {}).get("node_name", n["id"])}
                                                 for n in (v.work_flow or {}).get("nodes", [])
                                                 if n.get("type") == "ai-chat-node"])} for v in versions.order_by("-create_time")[:100]]})
