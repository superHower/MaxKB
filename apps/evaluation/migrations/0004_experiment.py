from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [("evaluation", "0003_evaluationresult")]
    operations = [
        migrations.CreateModel(
            name="Experiment",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("workspace_id", models.CharField(max_length=64, db_index=True)),
                ("application_id", models.UUIDField(db_index=True)),
                ("name", models.CharField(max_length=128)),
                ("status", models.CharField(max_length=20, default="draft")),
                ("subject_type", models.CharField(max_length=20, default="session")),
                ("variants", models.JSONField(default=list)),
                ("config_snapshot", models.JSONField(default=dict)),
                ("created_by", models.UUIDField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(null=True)),
                ("ended_at", models.DateTimeField(null=True)),
            ], options={"db_table": "evaluation_experiment"},
        ),
        migrations.AddConstraint(model_name="experiment", constraint=models.UniqueConstraint(
            fields=("application_id", "name"), name="evaluation_experiment_name")),
    ]
