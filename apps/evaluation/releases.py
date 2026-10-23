# coding=utf-8
"""Explicit production routing and audited configuration releases.

Resource hashes are checked before serving a controlled version. Mutable external
services and business side effects are never described as reversible snapshots.
"""
import base64
import copy
import hashlib
import io
import logging
import math
import zipfile
from datetime import timedelta

from django.db import transaction
from django.forms.models import model_to_dict
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from application.models import Application, ApplicationVersion
from .candidates import candidate_artifact, digest, model_fingerprint, text, version_snapshot
from .models import CapabilityVersion, EvaluationEvent, ProductionPointer, ReleaseAudit, ReleaseDeployment

logger = logging.getLogger(__name__)
DEFAULT_POLICY = {"min_samples": 20, "window_minutes": 60, "max_error_rate": .05,
                  "max_dislike_rate": .2, "max_latency_ms": 30000, "max_mean_cost": 1,
                  "max_handoff_rate": .5, "max_safety_rate": 0, "min_quality": .8,
                  "auto_rollback": True}


def pointer_for(application_id):
    pointer = ProductionPointer.objects.filter(application_id=application_id).first()
    if pointer is not None:
        return pointer
    # One-time legacy adoption only. All writers lock the application before inserting versions.
    with transaction.atomic():
        app = Application.objects.select_for_update().get(id=application_id)
        pointer, _ = ProductionPointer.objects.get_or_create(application=app, defaults={
            "current": ApplicationVersion.objects.filter(application=app).order_by("-create_time").first()})
        return pointer


def production_version(application_id):
    return pointer_for(application_id).current


def _version_fields(snapshot):
    fields = {}
    for field in ApplicationVersion._meta.concrete_fields:
        if field.name not in {"id", "create_time", "update_time"}:
            key = field.name if field.name in snapshot else field.attname
            if key in snapshot:
                fields[field.attname] = copy.deepcopy(snapshot[key])
    return fields


def version_hash(version):
    data = version_snapshot(version)
    for key in ("id", "name", "create_time", "update_time", "publish_user_id", "publish_user_name"):
        data.pop(key, None)
    return digest(data)


def references(value):
    found = {"model": set(), "tool": set(), "knowledge": set()}

    def visit(item):
        if isinstance(item, dict):
            for key, val in item.items():
                kind = ("model" if key.endswith("model_id") else
                        "knowledge" if key in {"knowledge_id", "knowledge_ids", "knowledge_id_list"} else
                        "tool" if key in {"tool_id", "tool_ids", "tool_lib_id", "skill_tool_ids", "mcp_tool_ids"}
                        else None)
                if kind and val:
                    found[kind].update(str(i) for i in (val if isinstance(val, list) else [val]))
                visit(val)
        elif isinstance(item, list):
            for val in item:
                visit(val)
    visit(value)
    return found


def resource_hashes(version):
    """Hash configured resource contents, including knowledge text and retrieval index.

    Operational counters/timestamps are excluded. No model credentials are returned.
    """
    from knowledge.models import File
    from knowledge.models.knowledge import (Knowledge, Document, Paragraph, Problem, ProblemParagraphMapping,
                                           Tag, DocumentTag, Termbase, Embedding)
    from models_provider.models import Model
    from tools.models import Tool
    refs = references(version_snapshot(version))
    hashes = {"models": {}, "tools": {}, "knowledge": {}}
    for model_id in sorted(refs["model"]):
        model = Model.objects.filter(id=model_id).first()
        if model is None:
            raise ValidationError("引用的模型不存在")
        hashes["models"][model_id] = model_fingerprint(model)
    for tool_id in sorted(refs["tool"]):
        tool = Tool.objects.filter(id=tool_id).first()
        if tool is None:
            raise ValidationError("引用的工具不存在")
        data = model_to_dict(tool)
        if tool.tool_type == "SKILL":
            file = File.objects.filter(id=tool.code).first()
            if file is None:
                raise ValidationError("Skill 文件缺失")
            data["file_sha256"] = hashlib.sha256(file.get_bytes()).hexdigest()
        if tool.tool_type == "WORKFLOW":
            # Nested tool workflows currently resolve latest; controlled releases must not use that mutable path.
            raise ValidationError("受控发布暂不支持嵌套工具工作流，请先固定其版本")
        hashes["tools"][tool_id] = digest(data)
    excluded = {"create_time", "update_time", "hit_num", "status", "status_meta", "char_length"}
    for knowledge_id in sorted(refs["knowledge"]):
        if not Knowledge.objects.filter(id=knowledge_id).exists():
            raise ValidationError("知识库不存在")
        parts = {}
        for model in (Knowledge, Document, Paragraph, Problem, ProblemParagraphMapping, Tag, DocumentTag,
                      Termbase, Embedding):
            fields = [f.attname for f in model._meta.concrete_fields if f.name not in excluded]
            lookup = {"id": knowledge_id} if model is Knowledge else (
                {"document__knowledge_id": knowledge_id} if model is DocumentTag else {"knowledge_id": knowledge_id})
            if model is Embedding:
                lookup = {"knowledge_id": knowledge_id}
            # Convert vectors to exact lists; numpy's abbreviated string representation loses content.
            rows = []
            for row in model.objects.filter(**lookup).order_by("pk").values(*fields).iterator():
                rows.append({k: v.tolist() if hasattr(v, "tolist") else v for k, v in row.items()})
            parts[model._meta.db_table] = digest(rows)
        hashes["knowledge"][knowledge_id] = parts
    return hashes


def verify_deployment(item):
    if version_hash(item.version) != item.manifest.get("version_sha256"):
        raise ValidationError("版本内容已变化，已阻止受控版本接收流量")
    if resource_hashes(item.version) != item.manifest.get("resources"):
        raise ValidationError("模型、工具或知识内容已变化，请重新验证发布")


def verify_version(version):
    item = ReleaseDeployment.objects.filter(version=version).select_related("version").first()
    if item:
        verify_deployment(item)


def audit(pointer, action, actor=None, reason="", deployment=None, data=None):
    return ReleaseAudit.objects.create(application_id=pointer.application_id, deployment=deployment,
                                      action=action, actor_id=actor, reason=reason, data=data or {})


def policy_data(data):
    policy = {**DEFAULT_POLICY, **data}
    if set(data) - set(DEFAULT_POLICY):
        raise ValidationError("未知监控阈值")
    for key, value in policy.items():
        if key == "auto_rollback":
            if not isinstance(value, bool):
                raise ValidationError("自动回滚必须为布尔值")
        elif isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValidationError("监控阈值必须为非负有限数值")
    for key in ("min_samples", "window_minutes"):
        if not isinstance(policy[key], int) or not 1 <= policy[key] <= 10000:
            raise ValidationError("样本数与窗口必须为 1～10000 的整数")
    for key in ("max_error_rate", "max_dislike_rate", "max_handoff_rate", "max_safety_rate", "min_quality"):
        if policy[key] > 1:
            raise ValidationError("比例阈值必须在 0～1 之间")
    return policy


def check_capability(capability):
    candidate, validation, manifest = capability.candidate, capability.validation, capability.manifest
    if (capability.status == "withdrawn" or candidate.status != "approved"
            or candidate.revision != manifest.get("revision") or validation.revision != candidate.revision
            or digest(candidate.spec) != validation.snapshot.get("sha256")
            or digest(candidate.spec) != digest(manifest.get("spec"))
            or digest(candidate_artifact(candidate.spec, candidate.kind)) != digest(manifest.get("artifact"))
            or digest(validation.report) != digest(manifest.get("report"))):
        raise ValidationError("审批产物已失效，请重新提交候选")
    checks = validation.report.get("checks", [])
    if not checks or validation.status not in {"passed", "failed"}:
        raise ValidationError("缺少已完成的验证报告")
    for check in checks:
        if not check["passed"] and (not check.get("waivable") or
                                    not manifest.get("waivers", {}).get(check["key"], "").strip()):
            raise ValidationError("存在未通过的发布门禁")
    from models_provider.models import Model
    for model_id, expected in candidate.spec.get("model_fingerprints", {}).items():
        model = Model.objects.filter(id=model_id).first()
        if not model or model_fingerprint(model) != expected:
            raise ValidationError("验证所用模型配置已变化")


def materialize_skill(version, capability):
    """Clone the approved ZIP; replace only SKILL.md and keep auxiliary files."""
    from knowledge.models import File
    from tools.models import Tool, ToolFolder
    spec = capability.manifest["artifact"]
    patch = spec["patch"]
    original_id = patch.get("skill_id")
    frozen = capability.manifest["spec"].get("skills", {}).get(original_id, {})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
        skill_path = "SKILL.md"
        if frozen:
            raw = base64.b64decode(frozen["zip_base64"], validate=True)
            if hashlib.sha256(raw).hexdigest() != frozen["sha256"]:
                raise ValidationError("冻结 Skill 校验失败")
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                paths = sorted((e.filename for e in entries if e.filename.rsplit("/", 1)[-1] == "SKILL.md"),
                               key=lambda p: (p.count("/"), p))
                if not paths or sum(e.file_size for e in entries) > 30 * 1024 * 1024:
                    raise ValidationError("Skill 压缩包无效或过大")
                skill_path = paths[0]
                for entry in entries:
                    name = entry.filename.replace("\\", "/")
                    if name.startswith("/") or ".." in name.split("/") or ":" in name:
                        raise ValidationError("Skill 压缩包含不安全路径")
                    if entry.filename != skill_path:
                        output.writestr(entry, archive.read(entry))
        output.writestr(skill_path, patch["content"].encode("utf-8"))
    original = Tool.objects.filter(id=original_id).first() if original_id else None
    fields = model_to_dict(original) if original else {}
    fields.pop("id", None)
    fields.pop("user", None)
    fields.pop("folder", None)
    folder = original.folder if original else ToolFolder.objects.filter(workspace_id=version.workspace_id).first()
    if folder is None:
        raise ValidationError("请先创建当前工作空间的工具目录")
    tool = Tool(**fields, folder=folder, user_id=version.publish_user_id)
    tool.name = (frozen.get("name") or "Candidate Skill")[:64]
    tool.workspace_id, tool.tool_type, tool.version = version.workspace_id, "SKILL", str(capability.id)
    file = File(file_name="skill.zip", source_type="TOOL", source_id=str(tool.id))
    file.save(buffer.getvalue())
    tool.code = str(file.id)
    tool.save()
    target = version if version.type == "SIMPLE" else next(
        n["properties"]["node_data"] for n in version.work_flow["nodes"] if n["id"] == patch["node_id"])
    ids = list(target.skill_tool_ids or []) if isinstance(target, ApplicationVersion) else list(target.get("skill_tool_ids", []))
    ids = [str(tool.id) if str(i) == original_id else i for i in ids]
    if not original_id:
        ids.append(str(tool.id))
    if isinstance(target, ApplicationVersion):
        target.skill_tool_ids = ids
    else:
        target["skill_tool_ids"] = ids


def prepare(pointer, capability, actor, policy):
    if pointer.frozen:
        raise ValidationError("发布已冻结")
    if pointer.rollout_id:
        raise ValidationError("请先结束当前灰度")
    if capability.candidate.application_id != pointer.application_id:
        raise ValidationError("能力版本不属于当前应用")
    check_capability(capability)
    if capability.candidate.kind == "knowledge_task":
        raise ValidationError("知识维护提案需先人工维护知识库，再建立新基线验证；不能作为配置直接发布")
    if capability.deployments.exists():
        raise ValidationError("该能力版本已准备，请使用已有发布记录")
    if str(pointer.current_id) != capability.manifest["spec"]["base_version_id"]:
        raise ValidationError("生产版本已偏离验证基线，请重新验证")
    if str(pointer.current_id) != str(capability.manifest["rollback_version"]["id"]):
        raise ValidationError("审批回滚点必须为当前生产版本")
    artifact = capability.manifest["artifact"]["base_version"]
    fields = _version_fields(artifact)
    fields.update(application_id=pointer.application_id, publish_user_id=actor,
                  name=f"受控发布 {str(capability.id)[:8]}")
    version = ApplicationVersion(**fields)
    if capability.candidate.kind == "skill_version":
        materialize_skill(version, capability)
    version.save()
    resources = resource_hashes(version)
    # Freeze the rollback dependency hashes too; rollback never silently adopts changed resources.
    rollback_resources = resource_hashes(pointer.current)
    item = ReleaseDeployment.objects.create(application_id=pointer.application_id, capability=capability,
        version=version, previous=pointer.current, created_by=actor, policy=policy_data(policy), manifest={
            "capability_sha256": digest(capability.manifest), "version_sha256": version_hash(version),
            "resources": resources, "rollback_resources": rollback_resources,
            "rollback_sha256": version_hash(pointer.current), "dataset_sha256": digest(capability.manifest["spec"]["dataset"]),
            "validation_id": str(capability.validation_id), "approved_by": str(capability.approved_by),
            "impact_scope": capability.manifest.get("impact_scope"), "diff": capability.manifest["spec"].get("diff"),
            "external_effects_reversed": False})
    audit(pointer, "prepared", actor, deployment=item, data={"manifest": item.manifest})
    return item


def save_pointer(pointer):
    pointer.revision += 1
    pointer.save()


def restore(pointer, item):
    if not item.previous_id:
        raise ValidationError("没有可恢复版本")
    if (version_hash(item.previous) != item.manifest.get("rollback_sha256") or
            resource_hashes(item.previous) != item.manifest.get("rollback_resources")):
        raise ValidationError("回滚点资源已变化，无法安全恢复；请冻结发布并人工修复")
    pointer.current, pointer.previous = item.previous, item.version
    pointer.rollout = None


def transition(pointer, item, action, actor, reason, data):
    reason = text(reason, "操作原因", 4000)
    if action in {"start", "promote"}:
        if pointer.frozen:
            raise ValidationError("发布已冻结")
        if item.status not in {"prepared", "running"}:
            raise ValidationError("仅准备中或灰度中的版本可以发布")
        if pointer.current_id != item.previous_id or pointer.rollout_id not in (None, item.id):
            raise ValidationError("生产指针已变化，请刷新或建立新候选")
        check_capability(item.capability)
        if digest(item.capability.manifest) != item.manifest["capability_sha256"]:
            raise ValidationError("审批产物校验失败")
        verify_deployment(item)
        if action == "start":
            percent = data.get("percentage")
            subject = data.get("subject_type", "session")
            if isinstance(percent, bool) or not isinstance(percent, int) or not 1 <= percent <= 99:
                raise ValidationError("灰度比例必须为 1～99 的整数")
            if subject not in {"application", "user", "session"}:
                raise ValidationError("无效的分组方式")
            if item.started_at and subject != item.subject_type:
                raise ValidationError("开始灰度后不能更改分组方式")
            item.percentage, item.subject_type, item.status = percent, subject, "running"
            pointer.rollout = item
        else:
            pointer.previous, pointer.current, pointer.rollout = pointer.current, item.version, None
            item.percentage, item.status = 100, "promoted"
        item.started_at = item.started_at or timezone.now()
    elif action in {"stop", "rollback"}:
        if item.status not in {"running", "promoted"}:
            raise ValidationError("该版本没有接收线上流量")
        if pointer.current_id == item.version_id:
            restore(pointer, item)
        elif pointer.rollout_id == item.id:
            pointer.rollout = None
        else:
            raise ValidationError("该版本已不在当前生产指针中")
        item.status = "stopped" if action == "stop" else "rolled_back"
        item.ended_at = timezone.now()
    else:
        raise ValidationError("未知发布操作")
    item.save()
    save_pointer(pointer)
    audit(pointer, action, actor, reason, item, {"current_version": str(pointer.current_id),
                                               "percentage": item.percentage, "external_effects_reversed": False})


def resolve(application_id, session_id, user_id=None):
    pointer = pointer_for(application_id)
    item = pointer.rollout
    version, variant = pointer.current, "control"
    if item and item.status == "running":
        subject = (str(application_id) if item.subject_type == "application" else
                   str(user_id or session_id) if item.subject_type == "user" else str(session_id))
        bucket = int(hashlib.sha256(f"{application_id}:{item.id}:{subject}".encode()).hexdigest()[:16], 16) % 10000
        if bucket < item.percentage * 100:
            version, variant = item.version, "treatment"
    if version is None:
        raise ValidationError("应用尚未发布")
    verify_version(version)
    deployed = ReleaseDeployment.objects.filter(version=version).first()
    return version, {"application_version_id": str(version.id),
                     "release_id": str(deployed.id) if deployed else None,
                     "experiment_id": str(item.id) if item else None,
                     "experiment_variant": variant if item else "production"}


def monitor_metrics(rows):
    from .online_metrics import summarize
    summary = summarize(rows)
    def mean(field):
        values = [r[field] for r in rows if isinstance(r.get(field), (int, float, bool))]
        return sum(values) / len(values) if values else None
    return {"count": len(rows), "error_rate": mean("execution_error"),
            "dislike_rate": summary["dislike_rate"], "latency_ms": summary["latency_ms"]["p95"],
            "mean_cost": mean("estimated_cost"), "handoff_rate": mean("human_handoff"),
            "safety_rate": mean("safety_incident"), "quality": mean("quality_score")}


def monitor(deployment_id):
    item = ReleaseDeployment.objects.filter(id=deployment_id).first()
    if not item or item.status not in {"running", "promoted"}:
        return
    rows = list(EvaluationEvent.objects.filter(application_id=item.application_id,
        data__release_id=str(item.id), created_at__gte=max(item.started_at, timezone.now() - timedelta(
            minutes=item.policy["window_minutes"]))).values_list("data", flat=True))
    metrics = monitor_metrics(rows)
    if metrics["count"] < item.policy["min_samples"]:
        return
    limits = {"error_rate": "max_error_rate", "dislike_rate": "max_dislike_rate", "latency_ms": "max_latency_ms",
              "mean_cost": "max_mean_cost", "handoff_rate": "max_handoff_rate", "safety_rate": "max_safety_rate"}
    breached = {k: v for k, v in metrics.items() if k != "count" and v is not None and (
        v < item.policy["min_quality"] if k == "quality" else v > item.policy[limits[k]])}
    if not breached:
        return
    with transaction.atomic():
        Application.objects.select_for_update().get(id=item.application_id)
        pointer = ProductionPointer.objects.select_for_update().get(application_id=item.application_id)
        item = ReleaseDeployment.objects.select_for_update().select_related("previous", "version").get(id=item.id)
        if item.status not in {"running", "promoted"}:
            return
        if pointer.rollout_id == item.id:
            pointer.rollout = None
        elif pointer.current_id == item.version_id:
            if not item.policy["auto_rollback"]:
                pointer.frozen = True
                audit(pointer, "alert", reason="全量监控超阈值，自动回滚未启用，已冻结发布", deployment=item,
                      data={"breached": breached, "metrics": metrics})
                save_pointer(pointer)
                return
            try:
                restore(pointer, item)
            except ValidationError:
                # Quarantine unsafe configuration instead of continuing to serve it.
                pointer.current, pointer.rollout, pointer.frozen = None, None, True
        else:
            return
        item.status, item.ended_at = "auto_stopped", timezone.now()
        item.save()
        save_pointer(pointer)
        audit(pointer, "auto_stopped", reason="监控超阈值，已停止新流量", deployment=item,
              data={"breached": breached, "metrics": metrics, "external_effects_reversed": False})
        logger.error("Release %s automatically stopped: %s", item.id, breached)
