# coding=utf-8
"""Application publish permission is required for every production mutation."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from application.models import Application
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants, ViewPermission, CompareConstants
from common.result import result
from .models import CapabilityVersion, EvaluationEvent, ProductionPointer, ReleaseAudit, ReleaseDeployment
from .releases import (audit, check_capability, monitor_metrics, pointer_for, prepare, save_pointer,
                       text, transition)
from .views import access, scope

publish_access = has_permissions(
    PermissionConstants.APPLICATION_PUBLISH.get_workspace_application_permission(),
    PermissionConstants.APPLICATION_PUBLISH.get_workspace_permission_workspace_manage_role(),
    ViewPermission([RoleConstants.USER.get_workspace_role()],
                   [PermissionConstants.APPLICATION.get_workspace_application_permission()], CompareConstants.AND),
    RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
)


def state(application_id):
    pointer = pointer_for(application_id)
    rows = list(EvaluationEvent.objects.filter(application_id=application_id).order_by("-created_at")[:10000])
    groups = {}
    for row in rows:
        key = (row.data.get("application_version"), row.data.get("experiment_id"),
               row.data.get("experiment_variant"))
        groups.setdefault(key, []).append(row.data)
    releases = []
    for item in ReleaseDeployment.objects.filter(application_id=application_id).order_by("-created_at")[:100]:
        releases.append({"id": str(item.id), "capability_id": str(item.capability_id),
            "version_id": str(item.version_id), "previous_id": str(item.previous_id), "status": item.status,
            "percentage": item.percentage, "subject_type": item.subject_type, "manifest": item.manifest,
            "policy": item.policy, "created_at": item.created_at.isoformat(),
            "metrics": monitor_metrics([r.data for r in rows if r.data.get("release_id") == str(item.id)])})
    capabilities = []
    for item in CapabilityVersion.objects.filter(candidate__application_id=application_id,
            status="pending_release").select_related("candidate", "validation").order_by("-created_at")[:100]:
        if item.deployments.exists():
            continue
        capabilities.append({"id": str(item.id), "title": item.candidate.title,
            "kind": item.candidate.kind, "approved_by": str(item.approved_by),
            "impact_scope": item.manifest.get("impact_scope"), "diff": item.manifest.get("spec", {}).get("diff"),
            "report": item.manifest.get("report"), "limitations": item.manifest.get("spec", {}).get("limitations")})
    return {"revision": pointer.revision, "current_version_id": str(pointer.current_id) if pointer.current_id else None,
        "previous_version_id": str(pointer.previous_id) if pointer.previous_id else None, "frozen": pointer.frozen,
        "rollout_id": str(pointer.rollout_id) if pointer.rollout_id else None,
        "capabilities": capabilities, "releases": releases,
        "traffic": [{"version_id": key[0], "experiment_id": key[1], "variant": key[2],
                     **monitor_metrics(values)} for key, values in groups.items()],
        "traffic_limit": 10000,
        "audits": [{"id": str(a.id), "action": a.action, "reason": a.reason, "actor_id": str(a.actor_id),
                    "deployment_id": str(a.deployment_id) if a.deployment_id else None,
                    "data": a.data, "created_at": a.created_at.isoformat()} for a in
                   ReleaseAudit.objects.filter(application_id=application_id).order_by("-created_at")[:100]]}


class Releases(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id):
        scope(workspace_id, application_id)
        return result.success(state(application_id))

    @publish_access
    def post(self, request, workspace_id, application_id):
        with transaction.atomic():
            get_object_or_404(Application.objects.select_for_update(), id=application_id, workspace_id=workspace_id)
            pointer_for(application_id)
            pointer = ProductionPointer.objects.select_for_update().get(application_id=application_id)
            if request.data.get("revision") != pointer.revision:
                raise ValidationError("发布状态已变化，请刷新后重试")
            action = request.data.get("action")
            if action in {"freeze", "unfreeze"}:
                reason = text(request.data.get("reason"), "冻结或解冻原因", 4000)
                pointer.frozen = action == "freeze"
                save_pointer(pointer)
                audit(pointer, action, request.user.id, reason)
            elif action == "prepare":
                capability = get_object_or_404(CapabilityVersion.objects.select_related("candidate", "validation"),
                    id=request.data.get("capability_id"), candidate__application_id=application_id,
                    candidate__workspace_id=workspace_id)
                check_capability(capability)
                prepare(pointer, capability, request.user.id, request.data.get("policy", {}))
                save_pointer(pointer)
            else:
                item = get_object_or_404(ReleaseDeployment.objects.select_for_update(),
                    id=request.data.get("deployment_id"), application_id=application_id)
                transition(pointer, item, action, request.user.id, request.data.get("reason"), request.data)
        return result.success(state(application_id))
