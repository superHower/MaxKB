from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("evaluation", "0002_quality_events")]
    operations = [
        migrations.CreateModel(
            name="EvaluationResult",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("evaluator_type", models.CharField(max_length=32, default="rule")),
                ("evaluator_version", models.CharField(max_length=32, default="1")),
                ("scores", models.JSONField(default=dict)),
                ("reasons", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("sample", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                              related_name="results", to="evaluation.evaluationsample")),
            ], options={"db_table": "evaluation_result"},
        ),
    ]
