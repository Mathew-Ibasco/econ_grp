from django.db import migrations


LEGACY_GALLERY_ENTRIES = [
    {
        "title": "Shinkansen, Japan",
        "description": "Urban rail systems help people travel quickly and efficiently within cities.",
        "media_type": "image",
        "image_url": "https://i0.wp.com/tokyotreatblog.wpcomstaging.com/wp-content/uploads/2023/10/bullet-train-thumbnail.png?fit=1024%2C683&ssl=1",
        "order": 7,
    },
    {
        "title": "MRT, Philippines",
        "description": "Rail transport moves thousands of passengers daily, reducing traffic congestion.",
        "media_type": "image",
        "image_url": "https://www.rappler.com/tachyon/r3-assets/612F469A6EA84F6BAE882D2B94A4B421/img/8A05DA686544457A950EEC3E0DAAF221/mrt-photo-edsa-taft.jpg",
        "order": 8,
    },
    {
        "title": "Elevated Railways",
        "description": "Improve mobility while saving valuable road space.",
        "media_type": "image",
        "image_url": "https://www.manilatimes.net/manilatimes/uploads/images/2021/05/23/1543.jpg",
        "order": 9,
    },
    {
        "title": "Inclusive Transport",
        "description": "Accessible train stations support transportation for all passengers.",
        "media_type": "image",
        "image_url": "https://www.lrta.gov.ph/wp-content/uploads/2025/07/photo_2025-07-31_12-59-03-1024x768.jpg",
        "order": 10,
    },
    {
        "title": "Empowering Mobility",
        "description": "Stations cater to people with disabilities for equitable access.",
        "media_type": "image",
        "image_url": "https://images.topgear.com.ph/topgear/images/2020/08/20/dotr-mrt-3-escalators-elevators-1597909548.jpg",
        "order": 11,
    },
    {
        "title": "Sustainable Mobility",
        "description": "Promotes eco-friendly travel by reducing fuel consumption.",
        "media_type": "image",
        "image_url": "https://www.shutterstock.com/image-vector/vector-illustration-electricpowered-mrt-train-260nw-2550253671.jpg",
        "order": 12,
    },
    {
        "title": "Connected Systems",
        "description": "Rail links with other transport modes for smoother commuting.",
        "media_type": "image",
        "image_url": "https://exclusive.multibriefs.com/images/exclusive/0427transportation.jpg",
        "order": 13,
    },
    {
        "title": "Transit Networks",
        "description": "Improve accessibility across different parts of the city.",
        "media_type": "image",
        "image_url": "https://www.urbanrail.net/as/manila/manila-metro-map.png",
        "order": 14,
    },
    {
        "title": "Urban Growth",
        "description": "Encourages development near transportation hubs.",
        "media_type": "image",
        "image_url": "https://www.railway-technology.com/wp-content/uploads/sites/13/2022/06/rail-system.jpeg",
        "order": 15,
    },
    {
        "title": "Tourism Boost",
        "description": "Rail transport enhances tourism and local economic activity.",
        "media_type": "image",
        "image_url": "https://cdn.audleytravel.com/1024/731/79/16028680-faade-of-manila-cathedral.jpg",
        "order": 16,
    },
]


def seed_legacy_gallery_entries(apps, schema_editor):
    MediaGalleryEntry = apps.get_model("econ", "MediaGalleryEntry")

    for entry in LEGACY_GALLERY_ENTRIES:
        MediaGalleryEntry.objects.update_or_create(
            title=entry["title"],
            media_type=entry["media_type"],
            defaults={
                "description": entry["description"],
                "image_url": entry["image_url"],
                "video_url": "",
                "thumbnail_url": "",
                "date": None,
                "order": entry["order"],
            },
        )


def unseed_legacy_gallery_entries(apps, schema_editor):
    MediaGalleryEntry = apps.get_model("econ", "MediaGalleryEntry")
    MediaGalleryEntry.objects.filter(title__in=[entry["title"] for entry in LEGACY_GALLERY_ENTRIES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0005_mediagalleryentry"),
    ]

    operations = [
        migrations.RunPython(seed_legacy_gallery_entries, unseed_legacy_gallery_entries),
    ]
