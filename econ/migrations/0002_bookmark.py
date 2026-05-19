# Generated for user bookmarks on 2026-05-19

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Bookmark",
            fields=[
                ("bookmarkID", models.AutoField(primary_key=True, serialize=False)),
                ("item_key", models.CharField(max_length=80)),
                ("title", models.CharField(max_length=160)),
                ("summary", models.TextField(blank=True)),
                (
                    "item_type",
                    models.CharField(
                        choices=[
                            ("topic", "Topic"),
                            ("resource", "Resource"),
                            ("media", "Media"),
                        ],
                        max_length=20,
                    ),
                ),
                ("url", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bookmarks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "bookmark",
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "item_key"), name="unique_user_bookmark"
                    )
                ],
            },
        ),
    ]
