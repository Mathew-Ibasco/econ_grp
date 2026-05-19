from django.db import migrations


BLOG_ENTRY = {
    "title": "ASEAN Rail Systems vs the Philippine Rail System",
    "slug": "asean-rail-systems-vs-the-philippine-rail-system",
    "excerpt": "Rail systems across ASEAN show how modern investment can connect cities, support tourism, and strengthen trade, while the Philippines continues to work toward a more complete and reliable network.",
    "featured_image_filename": "gallery_planning_largeR__1509364634.jpg",
    "featured_image_url": "https://cache2.travelfish.org/b/assets/2015/gallery/largeR/gallery_planning_largeR__1509364634.jpg",
    "body_paragraphs": [
        "Rail transport has long been a cornerstone of mobility in Southeast Asia. Countries like Thailand, Malaysia, and Singapore have established efficient, modern rail networks that connect urban and rural areas, facilitate trade, and support tourism.",
        "Across ASEAN, rail systems show a mix of service styles and infrastructure, but the common strengths are dense networks, modern trains, multiple service classes, integrated ticketing, and reliable passenger experiences.",
        "In contrast, the Philippines remains underdeveloped. Rail density is low, lines are concentrated in Metro Manila, and commuters still deal with aging trains, delays, and limited intercity coverage.",
        "Ongoing projects such as the North-South Commuter Railway, Mindanao Railway, and Metro Manila Subway aim to expand capacity, improve connectivity, and modernize the network.",
        "Closing the gap with ASEAN neighbors will require sustained investment, stronger planning, coordinated implementation, and a multimodal approach that links rail with buses, ferries, RORO vessels, and airports.",
    ],
    "keywords": [
        "ASEAN rail systems",
        "Philippine rail system",
        "rail modernization",
        "transport infrastructure",
        "mobility",
        "tourism",
    ],
    "highlights": [
        "ASEAN neighbors have built dense, modern rail systems that improve mobility, trade, and tourism.",
        "The Philippines still has a low rail density and limited intercity coverage outside Metro Manila.",
        "Long-term progress depends on sustained funding, coordinated planning, and faster implementation.",
    ],
    "gallery": [
        {
            "src": "https://cache2.travelfish.org/b/assets/2015/gallery/largeR/gallery_planning_largeR__1509364634.jpg",
            "alt": "ASEAN rail systems comparison",
            "caption": "Rail transport in Southeast Asia",
        }
    ],
    "sources": [
        {
            "url": "https://doi.org/10.62986/dp2024.51",
            "label": "Francisco, K. A. (2025, January 6). Transport infrastructure in the Philippines: From plans to actual allocation.",
        },
        {
            "url": "https://www.rappler.com/newsbreak/iq/167393-traveling-asean-transport-systems-southeast-asia",
            "label": "Gucilatar, T. (2017, April 20). Traveling in ASEAN: Transport systems in Southeast Asia. Rappler.",
        },
        {
            "url": "https://www.dailyguardian.com.ph/blog/ph-ranks-last-in-asean-transport-infrastructure",
            "label": "PH ranks last in ASEAN transport infrastructure. (2025, March 18). Daily Guardian.",
        },
        {
            "url": "https://www.travelfish.org/travel-planning/trains-in-southeast-asia",
            "label": "Trains in Southeast Asia. (n.d.). Travelfish.",
        },
    ],
    "topic_keys": [
        "rail-transport-basics",
        "philippine-rail-systems",
        "mobility-economy",
    ],
    "order": 4,
}


def seed_asean_blog(apps, schema_editor):
    Topic = apps.get_model("econ", "Topic")
    BlogPost = apps.get_model("econ", "BlogPost")

    blog, _ = BlogPost.objects.update_or_create(
        slug=BLOG_ENTRY["slug"],
        defaults={
            "title": BLOG_ENTRY["title"],
            "excerpt": BLOG_ENTRY["excerpt"],
            "featured_image_filename": BLOG_ENTRY["featured_image_filename"],
            "featured_image_url": BLOG_ENTRY["featured_image_url"],
            "raw_text": "\n\n".join(BLOG_ENTRY["body_paragraphs"]),
            "body_paragraphs": BLOG_ENTRY["body_paragraphs"],
            "keywords": BLOG_ENTRY["keywords"],
            "highlights": BLOG_ENTRY["highlights"],
            "gallery": BLOG_ENTRY["gallery"],
            "sources": BLOG_ENTRY["sources"],
            "order": BLOG_ENTRY["order"],
        },
    )
    blog.topics.set(Topic.objects.filter(key__in=BLOG_ENTRY["topic_keys"]))


def unseed_asean_blog(apps, schema_editor):
    BlogPost = apps.get_model("econ", "BlogPost")
    BlogPost.objects.filter(slug=BLOG_ENTRY["slug"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0016_seed_vlog_topic_links"),
    ]

    operations = [
        migrations.RunPython(seed_asean_blog, unseed_asean_blog),
    ]
