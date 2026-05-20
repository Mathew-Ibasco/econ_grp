from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0034_merge_20260520_1455"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("username", models.CharField(blank=True, default="", max_length=150)),
                ("role", models.CharField(default="Guest", max_length=20)),
                ("action", models.CharField(choices=[("visit", "Page Visit"), ("auth", "Authentication"), ("create", "Create"), ("update", "Update"), ("delete", "Delete"), ("submit", "Submit"), ("toggle", "Toggle"), ("system", "System")], max_length=20)),
                ("label", models.CharField(max_length=160)),
                ("method", models.CharField(blank=True, default="", max_length=10)),
                ("path", models.CharField(blank=True, default="", max_length=500)),
                ("page_title", models.CharField(blank=True, default="", max_length=160)),
                ("details", models.JSONField(blank=True, default=dict)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.CharField(blank=True, default="", max_length=300)),
                ("status_code", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="audit_logs", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "db_table": "audit_log",
                "ordering": ["-created_at", "-id"],
            },
        ),
    ]
