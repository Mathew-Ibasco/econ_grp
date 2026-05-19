from django.db import migrations


BLOG_SLUG = "asean-rail-systems-vs-the-philippine-rail-system"

SOURCES = [
    {
        "url": "https://doi.org/10.62986/dp2024.51",
        "label": "Francisco, K. A. (2025, January 6). Transport infrastructure in the Philippines: From plans to actual allocation [Discussion paper].",
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
]


def restore_blog_sources(apps, schema_editor):
    BlogPost = apps.get_model("econ", "BlogPost")

    blog = BlogPost.objects.get(slug=BLOG_SLUG)
    blog.sources = SOURCES
    blog.save(update_fields=["sources"])


def revert_restore_blog_sources(apps, schema_editor):
    BlogPost = apps.get_model("econ", "BlogPost")

    blog = BlogPost.objects.get(slug=BLOG_SLUG)
    blog.sources = []
    blog.save(update_fields=["sources"])


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0019_cleanup_asean_rail_blog_content"),
    ]

    operations = [
        migrations.RunPython(restore_blog_sources, revert_restore_blog_sources),
    ]
