# coding=utf-8
"""Sampling and human review of real application conversations."""
import json

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from common.auth import TokenAuth
from common.result import result
from .models import EvaluationAnnotation, EvaluationEvent, EvaluationSample
from .views import access, scope


def bounded_int(value, default, maximum):
    try:
        number = int(value)
    except (ValueError, TypeError) as error:
        raise ValidationError("数量必须为整数") from error
    if not 1 <= number <= maximum:
        raise ValidationError(f"数量必须在 1～{maximum} 之间")
    return number


def events_query(request, workspace_id, application_id):
    query = EvaluationEvent.objects.filter(workspace_id=workspace_id, application_id=application_id)
    for param, lookup in (("start", "created_at__gte"), ("end", "created_at__lte")):
        if request.query_params.get(param):
            value = parse_datetime(request.query_params[param])
            if value is None:
                raise ValidationError(f"{param} 必须为 ISO 日期时间")
            query = query.filter(**{lookup: value})
    feedback = request.query_params.get("feedback")
    if feedback is not None:
        if feedback not in ("-1", "0", "1"):
            raise ValidationError("无效的反馈条件")
        query = query.filter(data__feedback__vote=feedback)
    if request.query_params.get("no_hit") == "true":
        query = query.filter(data__retrieval_candidates=[])
    for param, lookup in (("min_latency_ms", "data__latency_ms__gte"),
                          ("min_cost", "data__estimated_cost__gte")):
        if request.query_params.get(param):
            try:
                query = query.filter(**{lookup: float(request.query_params[param])})
            except ValueError as error:
                raise ValidationError(f"{param} 必须为数字") from error
    return query


def event_data(item):
    return {"id": str(item.id), "chat_record_id": str(item.chat_record_id),
            "chat_id": str(item.chat_id), "created_at": item.created_at.isoformat(), **item.data}


def sample_data(item):
    annotation = item.annotations.order_by("-revision").first()
    return {"id": str(item.id), "source_event_id": str(item.source_event_id),
            "sampling_reason": item.sampling_reason, "status": item.status,
            "created_at": item.created_at.isoformat(), "event": event_data(item.source_event),
            "annotation": {"revision": annotation.revision, "reviewer_id": str(annotation.reviewer_id),
                           "reviewed_at": annotation.reviewed_at.isoformat(), **annotation.data} if annotation else None}


class Events(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id):
        scope(workspace_id, application_id)
        limit = bounded_int(request.query_params.get("limit", 50), 50, 200)
        query = events_query(request, workspace_id, application_id)
        return result.success([event_data(item) for item in query.order_by("-created_at")[:limit]])


class Samples(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id):
        scope(workspace_id, application_id)
        query = EvaluationSample.objects.filter(workspace_id=workspace_id, application_id=application_id)
        if request.query_params.get("status"):
            query = query.filter(status=request.query_params["status"])
        limit = bounded_int(request.query_params.get("limit", 50), 50, 200)
        return result.success([sample_data(item) for item in query.select_related("source_event").order_by(
            "-created_at")[:limit]])

    @access
    def post(self, request, workspace_id, application_id):
        scope(workspace_id, application_id)
        limit = bounded_int(request.data.get("limit", 50), 50, 200)
        reason = request.data.get("sampling_reason", "manual")
        if reason not in ("manual", "random", "negative_feedback", "no_hit", "slow", "high_cost", "follow_up"):
            raise ValidationError("无效的采样原因")
        event_ids = request.data.get("event_ids")
        if event_ids is not None and (not isinstance(event_ids, list) or len(event_ids) > 200):
            raise ValidationError("event_ids 最多 200 项")
        query = events_query(request, workspace_id, application_id)
        if event_ids is not None:
            query = query.filter(id__in=event_ids)
            if query.count() != len(set(event_ids)):
                raise ValidationError("存在不属于当前应用的事件")
        query = query.exclude(samples__isnull=False)
        query = query.order_by("?") if reason == "random" else query.order_by("-created_at")
        created = []
        for event in query[:limit]:
            sample, new = EvaluationSample.objects.get_or_create(
                source_event=event, defaults={"workspace_id": workspace_id,
                                              "application_id": application_id, "sampling_reason": reason})
            if new:
                created.append(sample_data(sample))
        return result.success(created)


class SampleDetail(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id, sample_id):
        sample = get_object_or_404(EvaluationSample, id=sample_id, workspace_id=workspace_id,
                                   application_id=application_id)
        return result.success(sample_data(sample))

    @access
    def delete(self, request, workspace_id, application_id, sample_id):
        sample = get_object_or_404(EvaluationSample, id=sample_id, workspace_id=workspace_id,
                                   application_id=application_id)
        sample.delete()
        return result.success(True)


class Annotation(APIView):
    authentication_classes = [TokenAuth]

    @access
    def post(self, request, workspace_id, application_id, sample_id):
        fields = ("answer_correct", "answer_score", "citation_relevant", "should_answer",
                  "no_answer_handling", "faithful", "needs_handoff", "badcase_category",
                  "gold_answer", "gold_context_ids", "review_note")
        data = {field: request.data[field] for field in fields if field in request.data}
        for field in ("answer_correct", "citation_relevant", "should_answer", "faithful", "needs_handoff"):
            if field in data and data[field] not in ("yes", "no", "unknown"):
                raise ValidationError(f"{field} 无效")
        if "answer_score" in data and (isinstance(data["answer_score"], bool) or
                                       not isinstance(data["answer_score"], (int, float)) or
                                       not 0 <= data["answer_score"] <= 1):
            raise ValidationError("answer_score 必须在 0～1 之间")
        if data.get("no_answer_handling") not in (None, "correct", "incorrect", "not_applicable"):
            raise ValidationError("no_answer_handling 无效")
        if data.get("badcase_category") not in (None, "data", "retrieval", "generation", "prompt",
                                                "model", "permission", "user", "other"):
            raise ValidationError("badcase_category 无效")
        if not isinstance(data.get("gold_context_ids", []), list) or any(
                not isinstance(value, str) for value in data.get("gold_context_ids", [])):
            raise ValidationError("gold_context_ids 必须为字符串列表")
        if any(not isinstance(data.get(field, ""), str) or len(data.get(field, "")) > 40960
               for field in ("gold_answer", "review_note")):
            raise ValidationError("标注文本无效或过长")
        with transaction.atomic():
            sample = get_object_or_404(EvaluationSample.objects.select_for_update(), id=sample_id,
                                       workspace_id=workspace_id, application_id=application_id)
            if sample.status == "archived":
                raise ValidationError("已归档样本不能修改")
            latest = sample.annotations.order_by("-revision").first()
            annotation = EvaluationAnnotation.objects.create(sample=sample, reviewer_id=request.user.id,
                                                             revision=latest.revision + 1 if latest else 1, data=data)
            sample.status = "reviewed"
            sample.save(update_fields=["status"])
        return result.success(sample_data(sample))


class SampleExport(APIView):
    authentication_classes = [TokenAuth]

    @access
    def get(self, request, workspace_id, application_id):
        scope(workspace_id, application_id)
        query = EvaluationSample.objects.filter(workspace_id=workspace_id, application_id=application_id)
        if request.query_params.get("status"):
            query = query.filter(status=request.query_params["status"])
        rows = [sample_data(item) for item in query.select_related("source_event").order_by("created_at")[:10000]]
        response = HttpResponse(json.dumps(rows, ensure_ascii=False), content_type="application/json; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="evaluation-samples.json"'
        return response
