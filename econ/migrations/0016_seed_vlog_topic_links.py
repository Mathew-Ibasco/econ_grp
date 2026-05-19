from datetime import date

from django.db import migrations


VLOG_ENTRIES = [
    {
        "title": "Railways Reimagined: Reliability, Automation, and Equitable Connectivity",
        "date": date(2026, 1, 6),
        "video_url": "https://www.youtube.com/watch?v=1idZRXTlo48",
        "thumbnail_url": "https://img.youtube.com/vi/1idZRXTlo48/hqdefault.jpg",
        "description": "Rail systems can improve urban-suburban connectivity by making transport more frequent, reliable, and efficient. It emphasizes technology, governance, and equitable access.",
        "topics": ["rail-transport-basics", "mobility-economy"],
        "order": 1,
    },
    {
        "title": "Driving Inclusivity and Accessibility in Rail Transportation",
        "date": date(2023, 7, 12),
        "video_url": "https://www.youtube.com/watch?v=NF6xMiH_Lt4",
        "thumbnail_url": "https://img.youtube.com/vi/NF6xMiH_Lt4/hqdefault.jpg",
        "description": "Nancy Chan's project audits 2,572 stations to improve accessibility data, helping decision-makers invest where needed. It highlights diversity and inclusivity in engineering.",
        "topics": ["mobility-economy", "world-bank-mobility-resource"],
        "order": 2,
    },
    {
        "title": "Philippine's Transportation Projects",
        "date": date(2024, 1, 23),
        "video_url": "https://www.youtube.com/watch?v=yGTiJ8gXc60",
        "thumbnail_url": "https://img.youtube.com/vi/yGTiJ8gXc60/hqdefault.jpg",
        "description": "Major investments in railways, roads, and sustainable technologies aim to improve mobility, reduce congestion, and support economic growth across the Philippines.",
        "topics": ["philippine-rail-systems", "mobility-economy"],
        "order": 3,
    },
    {
        "title": "Railway Bridges over Philippines",
        "date": date(2024, 4, 21),
        "video_url": "https://www.youtube.com/watch?v=U3x86Hcr1R8",
        "thumbnail_url": "https://img.youtube.com/vi/U3x86Hcr1R8/hqdefault.jpg",
        "description": "Highlights government investments in MRT-7, North-South Commuter Railway, and Metro Manila Subway to reduce traffic and strengthen economic activity.",
        "topics": ["philippine-rail-systems", "mobility-economy"],
        "order": 4,
    },
    {
        "title": "Social Innovation in Transport and Mobility",
        "date": date(2015, 7, 3),
        "video_url": "https://www.youtube.com/watch?v=S0bAAqitw8A",
        "thumbnail_url": "https://img.youtube.com/vi/S0bAAqitw8A/hqdefault.jpg",
        "description": "Hitachi's vision for integrated door-to-door mobility using smart ticketing and data-sharing. Applied to Philippine railways, it could reduce congestion and improve commuter life.",
        "topics": ["mobility-economy", "world-bank-mobility-resource"],
        "order": 5,
    },
]


def seed_vlogs(apps, schema_editor):
    Topic = apps.get_model("econ", "Topic")
    Vlog = apps.get_model("econ", "vlog")

    for entry in VLOG_ENTRIES:
        vlog, _ = Vlog.objects.update_or_create(
            title=entry["title"],
            defaults={
                "filename": entry["thumbnail_url"],
                "description": entry["description"],
                "video_url": entry["video_url"],
                "thumbnail_url": entry["thumbnail_url"],
                "date": entry["date"],
                "order": entry["order"],
            },
        )
        vlog.topics.set(Topic.objects.filter(key__in=entry["topics"]))


def unseed_vlogs(apps, schema_editor):
    Vlog = apps.get_model("econ", "vlog")
    Vlog.objects.filter(title__in=[entry["title"] for entry in VLOG_ENTRIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0015_alter_vlog_options_vlog_created_at_vlog_date_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_vlogs, unseed_vlogs),
    ]
