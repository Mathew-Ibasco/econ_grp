from django.db import migrations


BLOG_SLUG = "asean-rail-systems-vs-the-philippine-rail-system"
OLD_EXCERPT = "Rail transport has long been a cornerstone of mobility in Southeast Asia."
NEW_EXCERPT = (
    "By comparing ASEAN rail systems with the Philippines, this blog shows how better "
    "rail networks can improve daily mobility, tourism, and long-term growth."
)


def update_blog_excerpt(apps, schema_editor):
    BlogPost = apps.get_model("econ", "BlogPost")

    blog = BlogPost.objects.get(slug=BLOG_SLUG)
    blog.excerpt = NEW_EXCERPT
    blog.save(update_fields=["excerpt"])


def revert_blog_excerpt(apps, schema_editor):
    BlogPost = apps.get_model("econ", "BlogPost")

    blog = BlogPost.objects.get(slug=BLOG_SLUG)
    blog.excerpt = OLD_EXCERPT
    blog.save(update_fields=["excerpt"])


class Migration(migrations.Migration):

    dependencies = [
        ("econ", "0030_forumthread_additional_topics"),
    ]

    operations = [
        migrations.RunPython(update_blog_excerpt, revert_blog_excerpt),
    ]
