from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [("evaluation", "0004_experiment")]
    operations = [
        migrations.CreateModel(
            name="Badcase",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("category", models.CharField(max_length=32, default="other")),
                ("status", models.CharField(max_length=20, default="open")),
                ("reason", models.TextField(default="")),
                ("suggested_fix", models.TextField(default="")),
                ("resolution", models.TextField(default="")),
                ("created_by", models.UUIDField(null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(null=True)),
                ("sample", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                 related_name="badcase", to="evaluation.evaluationsample")),
            ], options={"db_table": "evaluation_badcase"},
        ),
    ]
