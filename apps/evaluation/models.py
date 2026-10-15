# coding=utf-8
"""Persistent application evaluation datasets and asynchronous runs."""
import uuid
from django.db import models
from common.encoder.encoder import SystemEncoder


class Dataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_id = models.UUIDField(db_index=True)
    workspace_id = models.CharField(max_length=64)
    name = models.CharField(max_length=128)
    version = models.CharField(max_length=64)
    cases = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evaluation_dataset"
        constraints = [models.UniqueConstraint(
            fields=["application_id", "name", "version"], name="evaluation_dataset_version")]


class Run(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_id = models.UUIDField(db_index=True)
    workspace_id = models.CharField(max_length=64)
    user_id = models.UUIDField()
    dataset = models.ForeignKey(Dataset, on_delete=models.PROTECT)
    baseline = models.ForeignKey("self", on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, default="queued")
    completed = models.IntegerField(default=0)
    config = models.JSONField(default=dict)
    results = models.JSONField(default=list)
    report = models.JSONField(default=dict)
    error = models.TextField(default="")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)


class EvaluationEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.CharField(max_length=64, db_index=True)
    application_id = models.UUIDField(db_index=True)
    chat_id = models.UUIDField(db_index=True)
    chat_record_id = models.UUIDField(unique=True)
    data = models.JSONField(default=dict, encoder=SystemEncoder)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "evaluation_event"


class EvaluationSample(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.CharField(max_length=64, db_index=True)
    application_id = models.UUIDField(db_index=True)
    source_event = models.ForeignKey(EvaluationEvent, on_delete=models.CASCADE, related_name="samples")
    sampling_reason = models.CharField(max_length=32, default="manual")
    status = models.CharField(max_length=20, default="pending_review")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evaluation_sample"
        constraints = [models.UniqueConstraint(fields=["source_event"], name="evaluation_sample_source_unique")]


class EvaluationAnnotation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sample = models.ForeignKey(EvaluationSample, on_delete=models.CASCADE, related_name="annotations")
    revision = models.PositiveIntegerField()
    reviewer_id = models.UUIDField()
    data = models.JSONField(default=dict)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evaluation_annotation"
        constraints = [models.UniqueConstraint(fields=["sample", "revision"], name="evaluation_annotation_revision")]


class EvaluationResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sample = models.ForeignKey(EvaluationSample, on_delete=models.CASCADE, related_name="results")
    evaluator_type = models.CharField(max_length=32, default="rule")
    evaluator_version = models.CharField(max_length=32, default="1")
    scores = models.JSONField(default=dict)
    reasons = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evaluation_result"


class Experiment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.CharField(max_length=64, db_index=True)
    application_id = models.UUIDField(db_index=True)
    name = models.CharField(max_length=128)
    status = models.CharField(max_length=20, default="draft")
    subject_type = models.CharField(max_length=20, default="session")
    variants = models.JSONField(default=list)
    config_snapshot = models.JSONField(default=dict)
    created_by = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    ended_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "evaluation_experiment"
        constraints = [models.UniqueConstraint(fields=["application_id", "name"], name="evaluation_experiment_name")]
