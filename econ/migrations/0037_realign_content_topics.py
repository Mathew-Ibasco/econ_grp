from django.db import migrations


BLOG_TOPICS = {
    "rail-transport-supports-economic-development": [
        "rail-transport-basics",
        "mobility-economy",
    ],
    "philippine-railway-system-latest-projects": [
        "philippine-rail-systems",
        "mobility-economy",
    ],
    "first-hand-stories-and-blogs-about-daily-train-use": [
        "rail-transport-basics",
        "philippine-rail-systems",
        "mobility-economy",
    ],
    "asean-rail-systems-vs-the-philippine-rail-system": [
        "rail-transport-basics",
        "philippine-rail-systems",
        "mobility-economy",
    ],
    "history-of-the-rail-system-in-the-philippines": [
        "rail-transport-basics",
        "philippine-rail-systems",
        "rail-history-resource",
    ],
}


JOURNAL_TOPICS = {
    "How railway stations can transform urban mobility and the public realm: The stakeholders’ perspective": [
        "rail-transport-basics",
        "mobility-economy",
    ],
    "Enhancing accessibility through rail transit in congested urban areas: A cross-regional analysis": [
        "mobility-economy",
        "world-bank-mobility-resource",
    ],
    "The Association between Urban Public Transport Infrastructure and Social Equity and Spatial Accessibility within the Urban Environment: An Investigation of Tramlink in London": [
        "mobility-economy",
    ],
    "Governing urban accessibility: moving beyond transport and mobility": [
        "mobility-economy",
        "world-bank-mobility-resource",
    ],
    "The role of railway in handling transport services of cities and agglomerations": [
        "rail-transport-basics",
        "mobility-economy",
    ],
}


MEDIA_TOPICS = {
    "Mindanao Railway Concept Art": ["philippine-rail-systems", "rail-gallery"],
    "Mindanao Railway Map": ["philippine-rail-systems", "rail-gallery"],
    "NSCR Route Map": ["philippine-rail-systems", "rail-gallery"],
    "NSCR Loan Signing": ["philippine-rail-systems", "rail-gallery"],
    "NSCR South Contract Signing": ["philippine-rail-systems", "rail-gallery"],
    "NSCR Inspection Clip": ["philippine-rail-systems", "rail-gallery"],
    "Modern City Trains": ["rail-transport-basics", "rail-gallery"],
    "Crowded Rush Hour Train": [
        "rail-transport-basics",
        "philippine-rail-systems",
        "rail-gallery",
    ],
    "Elevated Railways": [
        "rail-transport-basics",
        "mobility-economy",
        "rail-gallery",
    ],
    "Inclusive Transport": [
        "philippine-rail-systems",
        "mobility-economy",
        "rail-gallery",
        "world-bank-mobility-resource",
    ],
    "Empowering Mobility": [
        "philippine-rail-systems",
        "mobility-economy",
        "rail-gallery",
    ],
    "Sustainable Mobility": [
        "mobility-economy",
        "rail-gallery",
        "world-bank-mobility-resource",
    ],
    "Connected Systems": [
        "mobility-economy",
        "rail-gallery",
        "world-bank-mobility-resource",
    ],
    "Transit Networks": [
        "rail-transport-basics",
        "philippine-rail-systems",
        "mobility-economy",
        "rail-gallery",
    ],
    "Urban Growth": [
        "mobility-economy",
        "rail-gallery",
        "world-bank-mobility-resource",
    ],
    "Tourism Boost": [
        "philippine-rail-systems",
        "mobility-economy",
        "rail-gallery",
    ],
}


VIDEO_TOPICS = {
    "Railways Reimagined: Reliability, Automation, and Equitable Connectivity": [
        "rail-transport-basics",
        "mobility-economy",
    ],
    "Driving Inclusivity and Accessibility in Rail Transportation": [
        "mobility-economy",
        "world-bank-mobility-resource",
    ],
    "Philippine's Transportation Projects": [
        "philippine-rail-systems",
        "mobility-economy",
    ],
    "Railway Bridges over Philippines": [
        "philippine-rail-systems",
        "mobility-economy",
    ],
    "Social Innovation in Transport and Mobility": [
        "mobility-economy",
        "world-bank-mobility-resource",
    ],
}


def set_topics(item, topic_model, topic_keys):
    item.topics.set(topic_model.objects.filter(key__in=topic_keys))


def realign_content_topics(apps, schema_editor):
    Topic = apps.get_model("econ", "Topic")
    BlogPost = apps.get_model("econ", "BlogPost")
    JournalEntry = apps.get_model("econ", "JournalEntry")
    MediaGalleryEntry = apps.get_model("econ", "MediaGalleryEntry")
    Vlog = apps.get_model("econ", "vlog")

    for slug, topic_keys in BLOG_TOPICS.items():
        post = BlogPost.objects.filter(slug=slug).first()
        if post:
            set_topics(post, Topic, topic_keys)

    for title, topic_keys in JOURNAL_TOPICS.items():
        journal = JournalEntry.objects.filter(title=title).first()
        if journal:
            set_topics(journal, Topic, topic_keys)

    for title, topic_keys in MEDIA_TOPICS.items():
        media = MediaGalleryEntry.objects.filter(title=title).first()
        if media:
            set_topics(media, Topic, topic_keys)

    for title, topic_keys in VIDEO_TOPICS.items():
        video = Vlog.objects.filter(title=title).first()
        if video:
            set_topics(video, Topic, topic_keys)


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0036_blogpost_featured_image_optional"),
    ]

    operations = [
        migrations.RunPython(realign_content_topics, migrations.RunPython.noop),
    ]
