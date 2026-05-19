from django.db import migrations


TOPICS = [
    {
        "key": "rail-transport-basics",
        "title": "Rail Transport Basics",
        "summary": "Core ideas about trains, tracks, passenger movement, freight, and why rail is efficient for dense cities.",
        "icon": "fa-train",
        "source_url": "",
        "order": 1,
    },
    {
        "key": "philippine-rail-systems",
        "title": "Philippine Rail Systems",
        "summary": "MRT, LRT, PNR, subway, commuter rail, and regional railway projects that shape Philippine mobility.",
        "icon": "fa-map-location-dot",
        "source_url": "",
        "order": 2,
    },
    {
        "key": "mobility-economy",
        "title": "Accessibility, Mobility & The Economy",
        "summary": "How rail systems reduce congestion, connect people to opportunity, and support productivity, equity, and urban growth.",
        "icon": "fa-chart-simple",
        "source_url": "",
        "order": 3,
    },
    {
        "key": "rail-gallery",
        "title": "Gallery Snapshot",
        "summary": "Images and videos of Philippine rail systems, station maps, commuters, construction, and global rail references.",
        "icon": "fa-images",
        "source_url": "",
        "order": 4,
    },
    {
        "key": "rail-history-resource",
        "title": "Rail Transport History",
        "summary": "External reading on how rail transport developed and why it became central to urban and regional mobility.",
        "icon": "fa-book-open",
        "source_url": "https://www.ebsco.com/research-starters/history/rail-transport",
        "order": 5,
    },
    {
        "key": "world-bank-mobility-resource",
        "title": "World Bank: Livable Cities",
        "summary": "A source connecting urban mobility investment with more livable, accessible, and sustainable cities.",
        "icon": "fa-city",
        "source_url": "https://www.worldbank.org/en/results/2024/03/13/promoting-livable-cities-by-investing-in-urban-mobility",
        "order": 6,
    },
]

TOPIC_CONTENT = {
    "rail-gallery": {
        "blogs": [
            "rail-transport-supports-economic-development",
            "philippine-railway-system-latest-projects",
        ],
        "journals": [],
        "media": [
            "Mindanao Railway Concept Art",
            "Mindanao Railway Map",
            "NSCR Route Map",
            "NSCR Loan Signing",
            "NSCR South Contract Signing",
            "NSCR Inspection Clip",
            "Shinkansen, Japan",
            "MRT, Philippines",
            "Elevated Railways",
            "Inclusive Transport",
            "Empowering Mobility",
            "Sustainable Mobility",
            "Connected Systems",
            "Transit Networks",
            "Urban Growth",
            "Tourism Boost",
        ],
    },
    "rail-history-resource": {
        "blogs": ["rail-transport-supports-economic-development"],
        "journals": [
            "The role of railway in handling transport services of cities and agglomerations",
        ],
        "media": [
            "Shinkansen, Japan",
            "Transit Networks",
        ],
    },
    "world-bank-mobility-resource": {
        "blogs": [
            "rail-transport-supports-economic-development",
            "philippine-railway-system-latest-projects",
        ],
        "journals": [
            "Enhancing accessibility through rail transit in congested urban areas: A cross-regional analysis",
            "Governing urban accessibility: moving beyond transport and mobility",
        ],
        "media": [
            "Inclusive Transport",
            "Sustainable Mobility",
            "Connected Systems",
            "Urban Growth",
        ],
    },
}


def restore_dashboard_topics(apps, schema_editor):
    Topic = apps.get_model("econ", "Topic")
    BlogPost = apps.get_model("econ", "BlogPost")
    JournalEntry = apps.get_model("econ", "JournalEntry")
    MediaGalleryEntry = apps.get_model("econ", "MediaGalleryEntry")
    Bookmark = apps.get_model("econ", "Bookmark")

    topics_by_key = {}
    for topic_data in TOPICS:
        topic, _ = Topic.objects.update_or_create(
            key=topic_data["key"],
            defaults={
                "title": topic_data["title"],
                "summary": topic_data["summary"],
                "icon": topic_data["icon"],
                "source_url": topic_data["source_url"],
                "order": topic_data["order"],
            },
        )
        topics_by_key[topic.key] = topic

    for key, content in TOPIC_CONTENT.items():
        topic = topics_by_key[key]
        for slug in content["blogs"]:
            post = BlogPost.objects.filter(slug=slug).first()
            if post:
                post.topics.add(topic)
        for title in content["journals"]:
            journal = JournalEntry.objects.filter(title=title).first()
            if journal:
                journal.topics.add(topic)
        for title in content["media"]:
            media = MediaGalleryEntry.objects.filter(title=title).first()
            if media:
                media.topics.add(topic)

    for bookmark in Bookmark.objects.select_related("topic"):
        topic = bookmark.topic or topics_by_key.get(bookmark.item_key)
        if topic:
            bookmark.topic = topic
            bookmark.title = topic.title
            bookmark.summary = topic.summary
            bookmark.item_type = "topic"
            bookmark.url = topic.source_url
            bookmark.save(update_fields=["topic", "title", "summary", "item_type", "url"])


def remove_restored_dashboard_topics(apps, schema_editor):
    Topic = apps.get_model("econ", "Topic")
    Topic.objects.filter(
        key__in=[
            "rail-gallery",
            "rail-history-resource",
            "world-bank-mobility-resource",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0013_topic_source_url"),
    ]

    operations = [
        migrations.RunPython(restore_dashboard_topics, remove_restored_dashboard_topics),
    ]
