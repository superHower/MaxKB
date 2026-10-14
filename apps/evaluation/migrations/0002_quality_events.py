from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("evaluation", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="EvaluationEvent",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("workspace_id", models.CharField(max_length=64, db_index=True)),
                ("application_id", models.UUIDField(db_index=True)),
                ("chat_id", models.UUIDField(db_index=True)),
                ("chat_record_id", models.UUIDField(unique=True)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ], options={"db_table": "evaluation_event"},
        ),
        migrations.CreateModel(
            name="EvaluationSample",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("workspace_id", models.CharField(max_length=64, db_index=True)),
                ("application_id", models.UUIDField(db_index=True)),
                ("sampling_reason", models.CharField(max_length=32, default="manual")),
                ("status", models.CharField(max_length=20, default="pending_review")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("source_event", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                                    related_name="samples", to="evaluation.evaluationevent")),
            ], options={"db_table": "evaluation_sample"},
        ),
        migrations.AddConstraint(model_name="evaluationsample", constraint=models.UniqueConstraint(
            fields=("source_event",), name="evaluation_sample_source_unique")),
        migrations.CreateModel(
            name="EvaluationAnnotation",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("revision", models.PositiveIntegerField()),
                ("reviewer_id", models.UUIDField()),
                ("data", models.JSONField(default=dict)),
                ("reviewed_at", models.DateTimeField(auto_now_add=True)),
                ("sample", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="annotations", to="evaluation.evaluationsample")),
            ], options={"db_table": "evaluation_annotation"},
        ),
        migrations.AddConstraint(model_name="evaluationannotation", constraint=models.UniqueConstraint(
            fields=("sample", "revision"), name="evaluation_annotation_revision")),
    ]
