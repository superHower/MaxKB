# coding=utf-8
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(name="Dataset", fields=[
            ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ("application_id", models.UUIDField(db_index=True)),
            ("workspace_id", models.CharField(max_length=64)),
            ("name", models.CharField(max_length=128)),
            ("version", models.CharField(max_length=64)),
            ("cases", models.JSONField(default=list)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
        ], options={"db_table": "evaluation_dataset"}),
        migrations.AddConstraint(model_name="dataset", constraint=models.UniqueConstraint(
            fields=("application_id", "name", "version"), name="evaluation_dataset_version")),
        migrations.CreateModel(name="Run", fields=[
            ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
            ("application_id", models.UUIDField(db_index=True)),
            ("workspace_id", models.CharField(max_length=64)),
            ("user_id", models.UUIDField()),
            ("status", models.CharField(max_length=20, default="queued")),
            ("completed", models.IntegerField(default=0)),
            ("config", models.JSONField(default=dict)),
            ("results", models.JSONField(default=list)),
            ("report", models.JSONField(default=dict)),
            ("error", models.TextField(default="")),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("finished_at", models.DateTimeField(null=True)),
            ("dataset", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="evaluation.dataset")),
            ("baseline", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to="evaluation.run")),
        ]),
    ]
