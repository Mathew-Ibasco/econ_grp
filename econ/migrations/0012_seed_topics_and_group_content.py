from django.db import migrations


TOPICS = [
    {
        "key": "rail-transport-basics",
        "title": "Rail Transport Basics",
        "summary": "Core ideas about trains, tracks, passenger movement, freight, and why rail is efficient for dense cities.",
        "icon": "fa-train",
        "order": 1,
    },
    {
        "key": "philippine-rail-systems",
        "title": "Philippine Rail Systems",
        "summary": "MRT, LRT, PNR, subway, commuter rail, and regional railway projects that shape Philippine mobility.",
        "icon": "fa-map-location-dot",
        "order": 2,
    },
    {
        "key": "mobility-economy",
        "title": "Accessibility, Mobility & The Economy",
        "summary": "How rail systems reduce congestion, connect people to opportunity, and support productivity, equity, and urban growth.",
        "icon": "fa-chart-simple",
        "order": 3,
    },
]

BLOG_TOPICS = {
    "rail-transport-supports-economic-development": [
        "rail-transport-basics",
        "mobility-economy",
    ],
    "philippine-railway-system-latest-projects": [
        "philippine-rail-systems",
        "mobility-economy",
    ],
}

JOURNAL_TOPICS = {
    "How railway stations can transform urban mobility and the public realm: The stakeholders’ perspective": [
        "rail-transport-basics",
        "mobility-economy",
    ],
    "Enhancing accessibility through rail transit in congested urban areas: A cross-regional analysis": [
        "mobility-economy",
    ],
    "The Association between Urban Public Transport Infrastructure and Social Equity and Spatial Accessibility within the Urban Environment: An Investigation of Tramlink in London": [
        "mobility-economy",
    ],
    "Governing urban accessibility: moving beyond transport and mobility": [
        "mobility-economy",
    ],
    "The role of railway in handling transport services of cities and agglomerations": [
        "rail-transport-basics",
        "mobility-economy",
    ],
}

MEDIA_TOPICS = {
    "Mindanao Railway Concept Art": ["philippine-rail-systems"],
    "Mindanao Railway Map": ["philippine-rail-systems"],
    "NSCR Route Map": ["philippine-rail-systems"],
    "NSCR Loan Signing": ["philippine-rail-systems"],
    "NSCR South Contract Signing": ["philippine-rail-systems"],
    "NSCR Inspection Clip": ["philippine-rail-systems"],
    "Shinkansen, Japan": ["rail-transport-basics"],
    "MRT, Philippines": ["rail-transport-basics", "philippine-rail-systems"],
    "Elevated Railways": ["rail-transport-basics", "mobility-economy"],
    "Inclusive Transport": ["mobility-economy"],
    "Empowering Mobility": ["mobility-economy"],
    "Sustainable Mobility": ["mobility-economy"],
    "Connected Systems": ["mobility-economy"],
    "Transit Networks": ["rail-transport-basics", "mobility-economy"],
    "Urban Growth": ["mobility-economy"],
    "Tourism Boost": ["mobility-economy"],
}


def seed_topics(apps, schema_editor):
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
                "order": topic_data["order"],
            },
        )
        topics_by_key[topic.key] = topic

    for slug, topic_keys in BLOG_TOPICS.items():
        post = BlogPost.objects.filter(slug=slug).first()
        if post:
            post.topics.set([topics_by_key[key] for key in topic_keys])

    for title, topic_keys in JOURNAL_TOPICS.items():
        journal = JournalEntry.objects.filter(title=title).first()
        if journal:
            journal.topics.set([topics_by_key[key] for key in topic_keys])

    for title, topic_keys in MEDIA_TOPICS.items():
        entry = MediaGalleryEntry.objects.filter(title=title).first()
        if entry:
            entry.topics.set([topics_by_key[key] for key in topic_keys])

    for bookmark in Bookmark.objects.filter(topic__isnull=True):
        topic = topics_by_key.get(bookmark.item_key)
        if topic:
            bookmark.topic = topic
            bookmark.title = topic.title
            bookmark.summary = topic.summary
            bookmark.item_type = "topic"
            bookmark.url = ""
            bookmark.save(update_fields=["topic", "title", "summary", "item_type", "url"])


def unseed_topics(apps, schema_editor):
    Topic = apps.get_model("econ", "Topic")
    Topic.objects.filter(key__in=[topic["key"] for topic in TOPICS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0011_topic_blogpost_topics_bookmark_topic_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_topics, unseed_topics),
    ]
