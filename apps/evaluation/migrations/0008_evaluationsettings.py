# coding=utf-8
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("evaluation", "0007_releasedeployment_releaseaudit_productionpointer")]
    operations = [migrations.CreateModel(
        name="EvaluationSettings",
        fields=[("application_id", models.UUIDField(primary_key=True, serialize=False)),
                ("workspace_id", models.CharField(max_length=64)), ("judge", models.JSONField(default=dict))],
    )]
