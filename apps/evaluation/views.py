# coding=utf-8
"""Authenticated, application-scoped evaluation API."""
import tempfile
from pathlib import Path

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from application.models import Application, ApplicationVersion
from common.auth import TokenAuth
from common.auth.authentication import has_permissions
from common.constants.permission_constants import PermissionConstants, RoleConstants, ViewPermission, CompareConstants
from common.result import result
from models_provider.models import Model
from rag_eval.dataset import load_cases, version
from .models import Dataset, Run

access = has_permissions(
    PermissionConstants.APPLICATION_EDIT.get_workspace_application_permission(),
    PermissionConstants.APPLICATION_EDIT.get_workspace_permission_workspace_manage_role(),
    ViewPermission([RoleConstants.USER.get_workspace_role()],
                   [PermissionConstants.APPLICATION.get_workspace_application_permission()], CompareConstants.AND),
    RoleConstants.WORKSPACE_MANAGE.get_workspace_role(),
)


def scope(workspace_id, application_id):
    return get_object_or_404(Application, id=application_id, workspace_id=workspace_id)


def dataset_data(item):
    return {"id": str(item.id), "name": item.name, "version": item.version,
            "count": len(item.cases), "created_at": item.created_at.isoformat(),
            "categories": sorted({row.get("category", "unclassified") for row in item.cases})}


def dataset_detail(item):
    return {**dataset_data(item), "cases": item.cases}


def run_data(item, detail=False):
    data = {"id": str(item.id), "status": item.status, "completed": item.completed,
            "total": len(item.dataset.cases), "dataset_name": item.dataset.name,
            "dataset_version": item.dataset.version, "created_at": item.created_at.isoformat(),
            "error": item.error, "summary": item.report.get("summary", {}),
            "baseline_id": str(item.baseline_id) if item.baseline_id else None,
            "regression": bool(item.config.get("regression")),
            "regression_passed": item.report.get("regression_passed")}
    if detail:
        data.update(config=item.config, results=item.results, report=item.report)
    return data


class Datasets(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id):
        scope(workspace_id, application_id)
        return result.success([dataset_data(item) for item in Dataset.objects.filter(
            workspace_id=workspace_id, application_id=application_id).order_by("-created_at")])

    @access
    def post(self, request, workspace_id, application_id):
        scope(workspace_id, application_id)
        name, upload = str(request.data.get("name", "")).strip(), request.FILES.get("file")
        if not name or len(name) > 128 or upload is None:
            raise ValidationError("请输入测试集名称并上传 JSON/CSV 文件")
        suffix = Path(upload.name).suffix.lower()
        if suffix not in (".json", ".csv") or upload.size > 5 * 1024 * 1024:
            raise ValidationError("请上传不超过 5MB 的 JSON/CSV 文件")
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / ("dataset" + suffix)
                path.write_bytes(upload.read())
                cases = load_cases(path)
            if len(cases) > 1000:
                raise ValueError("每个测试集最多 1000 条")
        except (ValueError, TypeError, UnicodeError) as error:
            raise ValidationError(str(error)) from error
        item, _ = Dataset.objects.get_or_create(
            application_id=application_id, workspace_id=workspace_id, name=name, version=version(cases),
            defaults={"cases": cases})
        return result.success(dataset_data(item))


class DatasetDetail(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id, dataset_id):
        scope(workspace_id, application_id)
        item = get_object_or_404(Dataset, id=dataset_id, workspace_id=workspace_id,
                                 application_id=application_id)
        return result.success(dataset_detail(item))


class Runs(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id):
        scope(workspace_id, application_id)
        return result.success([run_data(item) for item in Run.objects.filter(
            workspace_id=workspace_id, application_id=application_id).select_related("dataset").order_by("-created_at")[:100]])

    @access
    def post(self, request, workspace_id, application_id):
        dataset = get_object_or_404(Dataset, id=request.data.get("dataset_id"),
                                   workspace_id=workspace_id, application_id=application_id)
        judge_id = request.data.get("judge_model_id")
        embedding_id = request.data.get("embedding_model_id")
        if judge_id:
            get_object_or_404(Model, id=judge_id, workspace_id=workspace_id, model_type="LLM", status="SUCCESS")
            get_object_or_404(Model, id=embedding_id, workspace_id=workspace_id,
                             model_type="EMBEDDING", status="SUCCESS")
        elif embedding_id:
            raise ValidationError("请选择 Judge 模型")
        rubrics = request.data.get("dimensions", {})
        if not isinstance(rubrics, dict) or len(rubrics) > 10 or any(
                not isinstance(k, str) or not k or not isinstance(v, str) or not v.strip() or len(v) > 4000
                for k, v in rubrics.items()):
            raise ValidationError("自定义维度需为名称到评分标准的映射，最多 10 项")
        reserved = {"faithfulness", "answer_relevancy", "completeness", "keypoint_coverage",
                    "context_precision", "context_recall", "mrr", "hit_rate", "precision_at_k", "total_score"}
        if reserved.intersection(rubrics):
            raise ValidationError("自定义维度名称不能与内置指标重复")
        if rubrics and not judge_id:
            raise ValidationError("自定义评分需要 Judge 模型")
        baseline = None
        if request.data.get("baseline_id"):
            baseline = get_object_or_404(Run, id=request.data["baseline_id"], workspace_id=workspace_id,
                                         application_id=application_id, status__in=["completed", "partial"])
        regression = bool(request.data.get("regression", False))
        try:
            regression_threshold = float(request.data.get("regression_threshold", 0.05))
        except (TypeError, ValueError) as error:
            raise ValidationError("回归阈值必须为数字") from error
        if not 0 < regression_threshold <= 1:
            raise ValidationError("回归阈值必须在 0～1 之间")
        if regression and baseline is None:
            raise ValidationError("回归评测必须指定基线运行")
        with transaction.atomic():
            application = Application.objects.select_for_update().get(id=application_id, workspace_id=workspace_id)
            if Run.objects.filter(application_id=application_id, status__in=["queued", "running"]).exists():
                raise ValidationError("此应用已有评测正在执行，请等待完成")
            published = ApplicationVersion.objects.filter(application_id=application_id).order_by("-create_time").first()
            if published is None:
                raise ValidationError("请先发布应用，再评测发布版本")
            if baseline is None:
                baseline = Run.objects.filter(application_id=application_id, dataset=dataset,
                                              status="completed").order_by("-created_at").first()
            from .tasks import snapshot
            config = snapshot(published, judge_id, embedding_id, rubrics)
            config.update({"regression": regression, "regression_threshold": regression_threshold})
            item = Run.objects.create(application_id=application.id, workspace_id=workspace_id,
                                      user_id=request.user.id, dataset=dataset, baseline=baseline, config=config)
        from .tasks import evaluate
        try:
            evaluate.delay(str(item.id))
        except Exception as error:  # noqa: BLE001 - report broker failure to the user
            item.status, item.error = "failed", "任务提交失败，请检查任务服务后重试"
            item.save(update_fields=["status", "error"])
            raise ValidationError(item.error) from error
        return result.success(run_data(item))


class RunDetail(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id, run_id):
        scope(workspace_id, application_id)
        item = get_object_or_404(Run.objects.select_related("dataset"), id=run_id,
                                workspace_id=workspace_id, application_id=application_id)
        format_name = request.query_params.get("format")
        if format_name:
            if not item.report.get("summary"):
                raise ValidationError("评测尚未生成报告")
            import json
            from rag_eval.report import markdown
            if format_name not in ("json", "md"):
                raise ValidationError("仅支持 JSON 和 Markdown")
            body = markdown(item.report) if format_name == "md" else json.dumps(
                item.report, ensure_ascii=False, indent=2)
            response = HttpResponse(body, content_type="text/markdown" if format_name == "md" else "application/json")
            response["Content-Disposition"] = f'attachment; filename="evaluation-{item.id}.{format_name}"'
            return response
        return result.success(run_data(item, True))
