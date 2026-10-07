# coding=utf-8
"""Persistent application evaluation datasets and asynchronous runs."""
import uuid
from django.db import models


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
