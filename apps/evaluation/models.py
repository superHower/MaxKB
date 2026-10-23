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


class Badcase(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sample = models.OneToOneField(EvaluationSample, on_delete=models.CASCADE, related_name="badcase")
    category = models.CharField(max_length=32, default="other")
    status = models.CharField(max_length=20, default="open")
    reason = models.TextField(default="")
    suggested_fix = models.TextField(default="")
    resolution = models.TextField(default="")
    created_by = models.UUIDField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "evaluation_badcase"


class ImprovementCandidate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace_id = models.CharField(max_length=64, db_index=True)
    application_id = models.UUIDField(db_index=True)
    title = models.CharField(max_length=128)
    kind = models.CharField(max_length=32)
    category = models.CharField(max_length=32, default="other")
    source = models.CharField(max_length=32, default="manual")
    status = models.CharField(max_length=32, default="draft")
    revision = models.PositiveIntegerField(default=1)
    spec = models.JSONField(default=dict, encoder=SystemEncoder)
    created_by = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CandidateValidation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(ImprovementCandidate, on_delete=models.PROTECT, related_name="validations")
    revision = models.PositiveIntegerField()
    status = models.CharField(max_length=20, default="queued")
    snapshot = models.JSONField(default=dict, encoder=SystemEncoder)
    report = models.JSONField(default=dict, encoder=SystemEncoder)
    error = models.TextField(default="")
    created_by = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)


class CandidateAudit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(ImprovementCandidate, on_delete=models.PROTECT, related_name="audits")
    revision = models.PositiveIntegerField()
    action = models.CharField(max_length=32)
    actor_id = models.UUIDField()
    data = models.JSONField(default=dict, encoder=SystemEncoder)
    created_at = models.DateTimeField(auto_now_add=True)


class CapabilityVersion(models.Model):
    """Approval artifact only: deliberately absent from ApplicationVersion's production lookup."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(ImprovementCandidate, on_delete=models.PROTECT, related_name="capability_versions")
    validation = models.OneToOneField(CandidateValidation, on_delete=models.PROTECT)
    status = models.CharField(max_length=32, default="pending_release")
    manifest = models.JSONField(default=dict, encoder=SystemEncoder)
    approved_by = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)


class ProductionPointer(models.Model):
    application = models.OneToOneField('application.Application', on_delete=models.CASCADE, primary_key=True)
    current = models.ForeignKey('application.ApplicationVersion', on_delete=models.SET_NULL, related_name='+', null=True)
    previous = models.ForeignKey('application.ApplicationVersion', on_delete=models.SET_NULL, related_name='+', null=True)
    rollout = models.ForeignKey('ReleaseDeployment', on_delete=models.SET_NULL, null=True, related_name='+')
    frozen = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)


class ReleaseDeployment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey('application.Application', on_delete=models.CASCADE)
    capability = models.ForeignKey(CapabilityVersion, on_delete=models.PROTECT, null=True, related_name='deployments')
    version = models.OneToOneField('application.ApplicationVersion', on_delete=models.CASCADE)
    previous = models.ForeignKey('application.ApplicationVersion', on_delete=models.SET_NULL, null=True, related_name='+')
    status = models.CharField(max_length=24, default='prepared')
    percentage = models.PositiveIntegerField(default=0)
    subject_type = models.CharField(max_length=16, default='session')
    manifest = models.JSONField(default=dict, encoder=SystemEncoder)
    policy = models.JSONField(default=dict)
    created_by = models.UUIDField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    ended_at = models.DateTimeField(null=True)


class ReleaseAudit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey('application.Application', on_delete=models.CASCADE)
    deployment = models.ForeignKey(ReleaseDeployment, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=32)
    actor_id = models.UUIDField(null=True)
    reason = models.TextField(default='')
    data = models.JSONField(default=dict, encoder=SystemEncoder)
    created_at = models.DateTimeField(auto_now_add=True)
