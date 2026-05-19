from datetime import date

from django.db import migrations, models


GALLERY_ENTRIES = [
    {
        "title": "Mindanao Railway Concept Art",
        "description": "Public-domain concept art showing an embankment section of the planned Mindanao Railway.",
        "media_type": "image",
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Mindanao%20Railway.png",
        "video_url": "",
        "thumbnail_url": "",
        "date": None,
        "order": 1,
    },
    {
        "title": "Mindanao Railway Map",
        "description": "High-level schematic map of the planned Mindanao Railway system and its future phases.",
        "media_type": "image",
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Mindanao%20Railway%20System%20Map.png",
        "video_url": "",
        "thumbnail_url": "",
        "date": None,
        "order": 2,
    },
    {
        "title": "NSCR Route Map",
        "description": "Map of the North-South Commuter Railway corridor and its station network.",
        "media_type": "image",
        "image_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Map%20of%20North-South%20Commuter%20Railway%20%282022%29.jpg",
        "video_url": "",
        "thumbnail_url": "",
        "date": None,
        "order": 3,
    },
    {
        "title": "NSCR Loan Signing",
        "description": "Ceremonial loan signing for the South Section of the Philippine North-South Commuter Railway Project.",
        "media_type": "video",
        "image_url": "",
        "video_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Ceremonial%20Loan%20Signing%20for%20the%20South%20Section%20of%20the%20Philippine%20North-South%20Commuter%20Railway%20Project%20-%2016%20June%202022.webm",
        "thumbnail_url": "",
        "date": date(2022, 6, 16),
        "order": 4,
    },
    {
        "title": "NSCR South Contract Signing",
        "description": "Contract signing for CP-S02 and S-03B on the NSCR South Commuter section.",
        "media_type": "video",
        "image_url": "",
        "video_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Contract%20Signing%20of%20the%20Philippines%20North-South%20Commuter%20Railway%20Project%20%E2%80%93%20South%20Commuter%20Section%20CP-S02%20%26%20S-03B.webm",
        "thumbnail_url": "",
        "date": date(2023, 4, 27),
        "order": 5,
    },
    {
        "title": "NSCR Inspection Clip",
        "description": "A short Department of Transportation inspection clip showing North-South Commuter Rail works.",
        "media_type": "video",
        "image_url": "",
        "video_url": "https://commons.wikimedia.org/wiki/Special:FilePath/Philippines%20Transport%20%28DOTr%29%20Secretary%20Giovanni%20Lopez%20inspection%20of%20the%20North-South%20Commuter%20Rail%20%28NSCR%29.webm",
        "thumbnail_url": "",
        "date": date(2025, 10, 23),
        "order": 6,
    },
]


def seed_gallery_entries(apps, schema_editor):
    MediaGalleryEntry = apps.get_model("econ", "MediaGalleryEntry")

    for entry in GALLERY_ENTRIES:
        MediaGalleryEntry.objects.update_or_create(
            title=entry["title"],
            media_type=entry["media_type"],
            defaults={
                "description": entry["description"],
                "date": entry["date"],
                "image_url": entry["image_url"],
                "video_url": entry["video_url"],
                "thumbnail_url": entry["thumbnail_url"],
                "order": entry["order"],
            },
        )


def unseed_gallery_entries(apps, schema_editor):
    MediaGalleryEntry = apps.get_model("econ", "MediaGalleryEntry")
    MediaGalleryEntry.objects.filter(title__in=[entry["title"] for entry in GALLERY_ENTRIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0004_seed_blogposts"),
    ]

    operations = [
        migrations.CreateModel(
            name="MediaGalleryEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField()),
                ("media_type", models.CharField(choices=[("image", "Image"), ("video", "Video")], max_length=10)),
                ("date", models.DateField(blank=True, null=True)),
                ("image_url", models.URLField(blank=True, max_length=500)),
                ("video_url", models.URLField(blank=True, max_length=500)),
                ("thumbnail_url", models.URLField(blank=True, max_length=500)),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "media_gallery_entry",
                "ordering": ["order", "id"],
            },
        ),
        migrations.RunPython(seed_gallery_entries, unseed_gallery_entries),
    ]
