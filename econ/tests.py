from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import AuditLog, BlogPost, ForumReply, ForumReplyImage, ForumThread, ItemQuizQuestion, JournalEntry, MediaGalleryEntry, Topic, User, vlog as VlogEntry
from PIL import Image


def _sample_png_upload(name="sample.png"):
    buffer = BytesIO()
    image = Image.new("RGB", (1, 1), color="white")
    image.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()
    return SimpleUploadedFile(name, png_bytes, content_type="image/png")


class SecuritySettingsTests(TestCase):
    def test_sessions_expire_after_fifteen_minutes_but_refresh_while_active(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 15 * 60)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertFalse(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)


class ForumThreadDeleteModalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lucygars", password="secret123")
        self.topic = Topic.objects.create(
            key="mobility",
            title="Mobility",
            summary="Mobility discussions",
            icon="fa-train",
        )
        self.thread = ForumThread.objects.create(
            topic=self.topic,
            author=self.user,
            title="Sample thread",
            body="Thread body",
        )

    def test_thread_author_sees_delete_modal(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("forum_thread", args=[self.thread.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-forum-delete-trigger')
        self.assertContains(response, 'id="forumDeleteModal"')

    def test_thread_page_renders_image_modal(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("forum_thread", args=[self.thread.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="forumImageModal"')
        self.assertContains(response, 'data-forum-image-trigger')
        self.assertContains(response, 'data-forum-thread-like-trigger')
        self.assertContains(response, "0 replies")
        self.assertContains(response, "0 likes")
        self.assertNotContains(response, "replys")
        self.assertNotContains(response, "forum-post-rail")

    def test_reply_can_include_images(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("forum_reply", args=[self.thread.id]),
            {
                "body": "Reply with an image",
                "images": _sample_png_upload(),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(ForumReply.objects.count(), 1)
        self.assertEqual(ForumReplyImage.objects.count(), 1)

        response = self.client.get(reverse("forum_thread", args=[self.thread.id]))
        self.assertContains(response, 'data-forum-image-trigger')
        self.assertContains(response, 'data-forum-reply-like-trigger')

    def test_thread_like_can_be_toggled(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("forum_toggle_thread_like", args=[self.thread.id]))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.thread.likes.filter(pk=self.user.pk).exists())

        response = self.client.post(reverse("forum_toggle_thread_like", args=[self.thread.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.thread.likes.filter(pk=self.user.pk).exists())

    def test_thread_like_can_be_toggled_via_ajax(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("forum_toggle_thread_like", args=[self.thread.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["like_count"], 1)
        self.assertTrue(response.json()["liked"])
        self.assertEqual(response.json()["aria_label"], "1 like")

        response = self.client.post(
            reverse("forum_toggle_thread_like", args=[self.thread.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["like_count"], 0)
        self.assertFalse(response.json()["liked"])
        self.assertEqual(response.json()["aria_label"], "0 likes")

    def test_reply_like_can_be_toggled(self):
        self.client.force_login(self.user)
        reply = ForumReply.objects.create(thread=self.thread, author=self.user, body="Reply body")

        response = self.client.post(reverse("forum_toggle_reply_like", args=[reply.id]))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(reply.likes.filter(pk=self.user.pk).exists())

        response = self.client.post(reverse("forum_toggle_reply_like", args=[reply.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(reply.likes.filter(pk=self.user.pk).exists())

    def test_reply_like_can_be_toggled_via_ajax(self):
        self.client.force_login(self.user)
        reply = ForumReply.objects.create(thread=self.thread, author=self.user, body="Reply body")

        response = self.client.post(
            reverse("forum_toggle_reply_like", args=[reply.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["like_count"], 1)
        self.assertTrue(response.json()["liked"])
        self.assertEqual(response.json()["aria_label"], "1 like")

        response = self.client.post(
            reverse("forum_toggle_reply_like", args=[reply.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            HTTP_ACCEPT="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["like_count"], 0)
        self.assertFalse(response.json()["liked"])
        self.assertEqual(response.json()["aria_label"], "0 likes")

    def test_forum_page_orders_latest_threads_first(self):
        older_thread = ForumThread.objects.create(
            topic=self.topic,
            author=self.user,
            title="Older thread",
            body="Older body",
        )
        newer_thread = ForumThread.objects.create(
            topic=self.topic,
            author=self.user,
            title="Newer thread",
            body="Newer body",
        )

        now = timezone.now()
        ForumThread.objects.filter(pk=older_thread.pk).update(created_at=now - timedelta(days=2))
        ForumThread.objects.filter(pk=newer_thread.pk).update(created_at=now - timedelta(days=1))

        response = self.client.get(reverse("forum"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertLess(content.index("Newer thread"), content.index("Older thread"))

    def test_forum_page_omits_topic_sidebar_and_filters(self):
        response = self.client.get(reverse("forum"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Latest Discussions")
        self.assertNotContains(response, 'class="forum-topic-chips"')
        self.assertNotContains(response, "active topics")
        self.assertNotContains(response, "?topic=")

    def test_forum_thread_form_uses_topics_language(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("forum"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Topics")
        self.assertContains(response, "Select one or more topics that fit this thread.")
        self.assertNotContains(response, "Select one or more tags that fit this thread.")

    def test_mobility_economy_topic_uses_chart_line_icon(self):
        economy_topic = Topic.objects.get(key="mobility-economy")

        self.assertEqual(economy_topic.icon, "fa-chart-line")


class AdminContentTopicTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="secret123",
        )
        self.topic = Topic.objects.create(
            key="rail-policy",
            title="Rail Policy",
            summary="Rail policy resources",
            icon="fa-train",
        )
        self.second_topic = Topic.objects.create(
            key="station-access",
            title="Station Access",
            summary="Station access resources",
            icon="fa-universal-access",
        )
        self.client.force_login(self.admin)

    def test_add_content_pages_render_topic_dropdown(self):
        for url_name in ("add_blog", "add_journal", "add_video", "add_image"):
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'name="topic_choice"')
                self.assertContains(response, "Rail Policy")
                self.assertContains(response, "Other")

    def test_add_topic_page_renders_edit_and_delete_controls(self):
        response = self.client.get(reverse("add_topic"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-content-edit-target="topicEditModal')
        self.assertContains(response, 'data-content-delete-trigger')
        self.assertContains(response, reverse("edit_topic", args=[self.topic.id]))
        self.assertContains(response, reverse("delete_topic", args=[self.topic.id]))

    def test_edit_topic_rejects_no_changes_inline(self):
        response = self.client.post(
            reverse("edit_topic", args=[self.topic.id]),
            {
                "title": self.topic.title,
                "summary": self.topic.summary,
                "icon": self.topic.icon,
                "source_url": self.topic.source_url,
                "order": str(self.topic.order),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Make at least one change before saving.", status_code=400)
        self.assertContains(response, f'id="topicEditModal{self.topic.id}"', status_code=400)
        self.assertContains(response, "is-open", status_code=400)

    def test_edit_topic_rejects_duplicate_title(self):
        response = self.client.post(
            reverse("edit_topic", args=[self.topic.id]),
            {
                "title": self.second_topic.title,
                "summary": self.topic.summary,
                "icon": self.topic.icon,
                "source_url": self.topic.source_url,
                "order": str(self.topic.order),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "A topic with this title already exists.", status_code=400)

    def test_edit_topic_rejects_clearing_original_value(self):
        self.topic.source_url = "https://example.com/source"
        self.topic.save(update_fields=["source_url"])

        response = self.client.post(
            reverse("edit_topic", args=[self.topic.id]),
            {
                "title": self.topic.title,
                "summary": self.topic.summary,
                "icon": self.topic.icon,
                "source_url": "",
                "order": str(self.topic.order),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "source cannot be left blank.", status_code=400)

    def test_edit_topic_allows_originally_blank_source_to_remain_blank(self):
        response = self.client.post(
            reverse("edit_topic", args=[self.topic.id]),
            {
                "title": "Updated Rail Policy",
                "summary": self.topic.summary,
                "icon": self.topic.icon,
                "source_url": "",
                "order": str(self.topic.order),
            },
        )

        self.assertEqual(response.status_code, 302)
        self.topic.refresh_from_db()
        self.assertEqual(self.topic.title, "Updated Rail Policy")
        self.assertEqual(self.topic.source_url, "")

    def test_delete_topic_blocks_linked_content(self):
        blog = BlogPost.objects.create(
            title="Linked Topic Blog",
            slug="linked-topic-blog",
            excerpt="A linked topic blog",
            featured_image_filename="linked-topic-blog.jpg",
            body_paragraphs=["Body"],
            order=1,
        )
        blog.topics.add(self.topic)

        response = self.client.post(reverse("delete_topic", args=[self.topic.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Topic.objects.filter(pk=self.topic.pk).exists())
        self.assertContains(response, "cannot be deleted because it is linked", status_code=200)

    def test_delete_topic_removes_unlinked_topic(self):
        response = self.client.post(reverse("delete_topic", args=[self.second_topic.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Topic.objects.filter(pk=self.second_topic.pk).exists())

    def test_add_content_pages_disable_date_until_url_is_entered(self):
        expected_sources = {
            "add_blog": "featured_image_url",
            "add_journal": "journal_url",
            "add_video": "video_url",
            "add_image": "image_url",
        }

        for url_name, field_name in expected_sources.items():
            with self.subTest(url_name=url_name):
                response = self.client.get(reverse(url_name))

                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'data-content-date-input disabled')
                self.assertContains(response, f'name="{field_name}"')
                self.assertContains(response, 'data-content-url-source')

    def test_add_blog_allows_blank_featured_image_url(self):
        response = self.client.post(
            reverse("add_blog"),
            {
                "title": "Blog Without Featured Image",
                "excerpt": "Rail planning summary",
                "body_paragraphs": "Rail planning improves access.",
                "keywords": "rail, planning",
                "highlights": "Better access",
                "gallery": "https://example.com/gallery.jpg",
                "sources": "Source\nhttps://example.com/source",
                "topic_choices": [str(self.topic.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        blog = BlogPost.objects.get(title="Blog Without Featured Image")
        self.assertEqual(response["Location"], reverse("blog_detail", args=[blog.slug]))
        self.assertEqual(blog.featured_image_url, "")
        self.assertTrue(blog.topics.filter(pk=self.topic.pk).exists())

    def test_add_blog_allows_blank_keywords(self):
        response = self.client.post(
            reverse("add_blog"),
            {
                "title": "Blog Without Keywords",
                "excerpt": "Rail planning summary",
                "body_paragraphs": "Rail planning improves access.",
                "keywords": "",
                "highlights": "Better access",
                "gallery": "https://example.com/gallery.jpg",
                "topic_choices": [str(self.topic.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        blog = BlogPost.objects.get(title="Blog Without Keywords")
        self.assertEqual(response["Location"], reverse("blog_detail", args=[blog.slug]))
        self.assertEqual(blog.keywords, [])

    def test_add_blog_accepts_apa_source_text_without_url(self):
        source_text = "Smith, J. A. (2020). Understanding modern society. Academic Press."
        response = self.client.post(
            reverse("add_blog"),
            {
                "title": "Blog With Citation Text",
                "excerpt": "Rail planning summary",
                "body_paragraphs": "Rail planning improves access.",
                "keywords": "rail, planning",
                "highlights": "Better access",
                "gallery": "https://example.com/gallery.jpg",
                "sources": source_text,
                "topic_choices": [str(self.topic.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        blog = BlogPost.objects.get(title="Blog With Citation Text")
        self.assertEqual(blog.sources, [{"label": source_text, "url": ""}])

    def test_add_blog_generates_apa_source_for_url(self):
        response = self.client.post(
            reverse("add_blog"),
            {
                "title": "Blog With URL Source",
                "excerpt": "Rail planning summary",
                "featured_image_url": "https://example.com/featured.jpg",
                "date": "2026-05-20",
                "body_paragraphs": "Rail planning improves access.",
                "keywords": "rail, planning",
                "highlights": "Better access",
                "gallery": "https://example.com/gallery.jpg",
                "sources": "https://example.com/source",
                "topic_choices": [str(self.topic.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        blog = BlogPost.objects.get(title="Blog With URL Source")
        self.assertEqual(blog.sources[0]["url"], "https://example.com/source")
        self.assertIn("Blog With URL Source. (2026, May 20). Example.", blog.sources[0]["label"])

    def test_add_blog_uses_no_date_in_generated_apa_source(self):
        response = self.client.post(
            reverse("add_blog"),
            {
                "title": "Blog With Unknown Source Date",
                "excerpt": "Rail planning summary",
                "featured_image_url": "https://example.com/featured.jpg",
                "no_date": "1",
                "body_paragraphs": "Rail planning improves access.",
                "keywords": "rail, planning",
                "highlights": "Better access",
                "gallery": "https://example.com/gallery.jpg",
                "sources": "https://example.com/source",
                "topic_choices": [str(self.topic.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        blog = BlogPost.objects.get(title="Blog With Unknown Source Date")
        self.assertIn("Blog With Unknown Source Date. (n.a.). Example.", blog.sources[0]["label"])

    def test_add_blog_requires_date_only_for_valid_featured_image_url(self):
        response = self.client.post(
            reverse("add_blog"),
            {
                "title": "Blog With Featured Image Date",
                "excerpt": "Rail planning summary",
                "featured_image_url": "https://example.com/featured.jpg",
                "body_paragraphs": "Rail planning improves access.",
                "keywords": "rail, planning",
                "highlights": "Better access",
                "gallery": "https://example.com/gallery.jpg",
                "sources": "Source\nhttps://example.com/source",
                "topic_choices": [str(self.topic.id)],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Date is required when this content comes from a URL.", status_code=400)

    def test_add_journal_uses_no_date_in_generated_apa_citation(self):
        response = self.client.post(
            reverse("add_journal"),
            {
                "title": "Journal With Unknown Date",
                "journal_url": "https://example.com/journal",
                "no_date": "1",
                "authors": "Rail Author",
                "publication_year": "",
                "journal_name": "Rail Journal",
                "citation_info": "",
                "snippet": "Rail planning improves access.",
                "keywords": "rail, planning",
                "topic_choices": [str(self.topic.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        journal = JournalEntry.objects.get(title="Journal With Unknown Date")
        self.assertEqual(response["Location"], reverse("journal_detail", args=[journal.id]))
        self.assertEqual(
            journal.citation_info,
            "Rail Author. (n.a.). Journal With Unknown Date. Rail Journal. https://example.com/journal",
        )

    def test_add_journal_allows_blank_keywords(self):
        response = self.client.post(
            reverse("add_journal"),
            {
                "title": "Journal Without Keywords",
                "journal_url": "https://example.com/journal-without-keywords",
                "date": "2026-05-20",
                "authors": "Rail Author",
                "publication_year": "2026",
                "journal_name": "Rail Journal",
                "citation_info": "",
                "snippet": "Rail planning improves access.",
                "keywords": "",
                "topic_choices": [str(self.topic.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        journal = JournalEntry.objects.get(title="Journal Without Keywords")
        self.assertEqual(response["Location"], reverse("journal_detail", args=[journal.id]))
        self.assertEqual(journal.keywords, [])

    def test_add_video_allows_numeric_channel_name(self):
        response = self.client.post(
            reverse("add_video"),
            {
                "title": "Numeric Channel Video",
                "channel_name": "12345",
                "description": "A video from a numeric channel",
                "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "date": "2026-05-20",
                "topic_choices": [str(self.topic.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        video = VlogEntry.objects.get(title="Numeric Channel Video", channel_name="12345")
        self.assertEqual(response["Location"], reverse("vlog_detail", args=[video.vlogID]))

    def test_blog_page_paginates_after_four_cards(self):
        for index in range(5):
            BlogPost.objects.create(
                title=f"Paged Blog {index}",
                slug=f"paged-blog-{index}",
                excerpt="A blog excerpt",
                featured_image_filename=f"paged-blog-{index}.jpg",
                featured_image_url="https://example.com/paged.jpg",
                body_paragraphs=["Body"],
                keywords=["rail", "policy"],
                highlights=["Highlight"],
                gallery=[],
                sources=[],
                order=index,
            )

        response = self.client.get(reverse("blog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 1 of")
        self.assertContains(response, "Paged Blog 0")
        self.assertNotContains(response, "Paged Blog 4")

    def test_journal_page_paginates_after_six_cards(self):
        for index in range(7):
            JournalEntry.objects.create(
                title=f"Paged Journal {index}",
                journal_url="https://example.com/journal",
                authors="Rail Author",
                publication_year=2026,
                journal_name="Rail Journal",
                citation_info="Rail Author. (2026). Paged Journal. Rail Journal.",
                snippet="Journal snippet",
                keywords=["rail", "journal"],
                order=index,
            )

        response = self.client.get(reverse("journal"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 1 of 2")
        self.assertContains(response, "Paged Journal 0")
        self.assertNotContains(response, "Paged Journal 6")

    def test_media_pages_paginate_at_requested_card_counts(self):
        for index in range(9):
            MediaGalleryEntry.objects.create(
                title=f"Paged Image {index}",
                description="Gallery description",
                media_type="image",
                date=timezone.localdate(),
                image_url="https://example.com/image.jpg",
                order=index,
            )
            VlogEntry.objects.create(
                title=f"Paged Video {index}",
                filename=f"paged-video-{index}.mp4",
                channel_name="Rail Channel",
                description="Video description",
                video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                date=timezone.localdate(),
                order=index,
            )

        gallery_response = self.client.get(reverse("gallery"))
        media_response = self.client.get(reverse("vlog"))

        self.assertContains(gallery_response, "Page 1 of")
        self.assertContains(media_response, "Page 1 of")
        self.assertContains(media_response, "Paged Video 0")
        self.assertNotContains(media_response, "Paged Video 6")

    def test_gallery_cards_keep_normal_width_when_page_has_few_items(self):
        response = self.client.get(reverse("gallery"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "repeat(auto-fill, minmax(280px, 360px))")
        self.assertContains(response, "justify-content: center")

    def test_media_cards_keep_normal_width_when_page_has_few_items(self):
        response = self.client.get(reverse("vlog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "repeat(auto-fill, minmax(320px, 380px))")
        self.assertContains(response, "justify-content: center")

    def test_blog_and_journal_cards_keep_normal_width_when_page_has_few_items(self):
        css_path = Path(settings.BASE_DIR) / "econ" / "static" / "econ" / "css" / "main.css"
        css = css_path.read_text(encoding="utf-8")

        self.assertIn("repeat(auto-fill, minmax(320px, 560px))", css)
        self.assertIn(".blogs-page .blog-list-grid", css)
        self.assertIn("justify-content: center", css)

    def test_add_image_requires_topic(self):
        response = self.client.post(
            reverse("add_image"),
            {
                "title": "Station Platform",
                "description": "Platform accessibility improvements",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "At least one topic is required.", status_code=400)
        self.assertFalse(MediaGalleryEntry.objects.filter(title="Station Platform").exists())

    def test_add_image_links_existing_topics(self):
        response = self.client.post(
            reverse("add_image"),
            {
                "title": "Station Platform",
                "description": "Platform accessibility improvements",
                "topic_choices": [str(self.topic.id), str(self.second_topic.id)],
            },
        )

        self.assertEqual(response.status_code, 302)
        image = MediaGalleryEntry.objects.get(title="Station Platform")
        self.assertTrue(response["Location"].startswith(f"{reverse('gallery')}?page="))
        self.assertTrue(response["Location"].endswith(f"#gallery-item-{image.id}"))
        self.assertTrue(image.topics.filter(pk=self.topic.pk).exists())
        self.assertTrue(image.topics.filter(pk=self.second_topic.pk).exists())

    def test_other_topic_is_created_in_proper_case(self):
        response = self.client.post(
            reverse("add_image"),
            {
                "title": "Ticket Hall",
                "description": "Ticket hall crowd flow",
                "topic_choices": [str(self.topic.id)],
                "topic_choice": "__other__",
                "topic_other": "urban fare systems",
            },
        )

        self.assertEqual(response.status_code, 302)
        topic = Topic.objects.get(title="Urban Fare Systems")
        image = MediaGalleryEntry.objects.get(title="Ticket Hall")
        self.assertTrue(response["Location"].startswith(f"{reverse('gallery')}?page="))
        self.assertTrue(response["Location"].endswith(f"#gallery-item-{image.id}"))
        self.assertTrue(image.topics.filter(pk=topic.pk).exists())
        self.assertTrue(image.topics.filter(pk=self.topic.pk).exists())

    def test_other_topic_rejects_duplicate_numbers_and_symbols(self):
        cases = [
            ("rail policy", "Topic cannot match an existing topic."),
            ("12345", "Topic cannot be only numbers."),
            ("!!!", "Topic cannot be only symbols."),
        ]

        for value, message in cases:
            with self.subTest(value=value):
                response = self.client.post(
                    reverse("add_image"),
                    {
                        "title": f"Image {value}",
                        "description": "A valid description",
                        "topic_choice": "__other__",
                        "topic_other": value,
                    },
                )

                self.assertEqual(response.status_code, 400)
                self.assertContains(response, message, status_code=400)

    def test_blog_page_links_and_displays_topic_for_unlinked_blog(self):
        blog = BlogPost.objects.create(
            title="Unlinked Blog",
            slug="unlinked-blog",
            excerpt="A blog that needs a topic",
            featured_image_filename="unlinked-blog.jpg",
            featured_image_url="https://example.com/unlinked.jpg",
            body_paragraphs=["Body"],
            keywords=["rail"],
            highlights=["Highlight"],
            gallery=[],
            sources=[],
        )

        response = self.client.get(reverse("blog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rail Policy")
        self.assertTrue(blog.topics.filter(pk=self.topic.pk).exists())

    def test_old_blog_auto_generates_content_quiz(self):
        blog = BlogPost.objects.create(
            title="Rail Access And City Growth",
            slug="rail-access-and-city-growth",
            excerpt="Rail access can connect commuters to work and services.",
            featured_image_filename="rail-access.jpg",
            featured_image_url="https://example.com/rail.jpg",
            body_paragraphs=["Rail stations improve mobility and support nearby economic activity."],
            keywords=["mobility"],
            highlights=["Stations connect people to opportunity."],
            gallery=[],
            sources=[],
        )
        blog.topics.add(self.topic)
        BlogPost.objects.filter(pk=blog.pk).update(created_at=timezone.now() - timedelta(days=1, minutes=5))

        response = self.client.get(reverse("blog_detail", args=[blog.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Answer Quiz")
        self.assertEqual(ItemQuizQuestion.objects.filter(item_type="blog", item_id=blog.id).count(), 9)
        self.assertTrue(
            ItemQuizQuestion.objects.filter(
                item_type="blog",
                item_id=blog.id,
                question__icontains="mainly about",
                option_a__icontains="Rail Access",
            ).exists()
            or ItemQuizQuestion.objects.filter(
                item_type="blog",
                item_id=blog.id,
                question__icontains="mainly about",
                option_b__icontains="Rail Access",
            ).exists()
            or ItemQuizQuestion.objects.filter(
                item_type="blog",
                item_id=blog.id,
                question__icontains="mainly about",
                option_c__icontains="Rail Access",
            ).exists()
        )

    def test_new_blog_waits_one_day_before_quiz(self):
        blog = BlogPost.objects.create(
            title="New Blog Waiting For Quiz",
            slug="new-blog-waiting-for-quiz",
            excerpt="A new blog should wait before quiz generation.",
            featured_image_filename="new-blog.jpg",
            featured_image_url="https://example.com/new.jpg",
            body_paragraphs=["New content is still processing."],
            keywords=["rail"],
            highlights=["Processing window"],
            gallery=[],
            sources=[],
        )
        blog.topics.add(self.topic)

        response = self.client.get(reverse("blog_detail", args=[blog.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Quiz processing completes after")
        self.assertNotContains(response, "Answer Quiz")
        self.assertFalse(ItemQuizQuestion.objects.filter(item_type="blog", item_id=blog.id).exists())

    def test_old_journal_auto_generates_content_quiz(self):
        journal = JournalEntry.objects.create(
            title="Rail Equity Journal",
            journal_url="https://example.com/rail-equity",
            authors="Rail Researcher",
            publication_year=2026,
            journal_name="Urban Mobility Review",
            citation_info="Rail Researcher. (2026). Rail Equity Journal. Urban Mobility Review.",
            snippet="The journal studies how rail access affects social equity and commuting.",
            keywords=["equity"],
        )
        journal.topics.add(self.topic)
        JournalEntry.objects.filter(pk=journal.pk).update(created_at=timezone.now() - timedelta(days=1, minutes=5))

        response = self.client.get(reverse("journal_detail", args=[journal.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Answer Quiz")
        self.assertEqual(ItemQuizQuestion.objects.filter(item_type="journal", item_id=journal.id).count(), 9)
        self.assertTrue(
            ItemQuizQuestion.objects.filter(
                item_type="journal",
                item_id=journal.id,
                question__icontains="author",
                option_a__icontains="Rail Researcher",
            ).exists()
            or ItemQuizQuestion.objects.filter(
                item_type="journal",
                item_id=journal.id,
                question__icontains="author",
                option_b__icontains="Rail Researcher",
            ).exists()
            or ItemQuizQuestion.objects.filter(
                item_type="journal",
                item_id=journal.id,
                question__icontains="author",
                option_c__icontains="Rail Researcher",
            ).exists()
        )

    def test_admin_detail_pages_render_edit_buttons(self):
        blog = BlogPost.objects.create(
            title="Edit Button Blog",
            slug="edit-button-blog",
            excerpt="A blog excerpt",
            featured_image_filename="edit-button-blog.jpg",
            featured_image_url="https://example.com/edit-button.jpg",
            body_paragraphs=["Body"],
            keywords=["rail", "policy"],
            highlights=["Highlight"],
            gallery=[{"src": "https://example.com/gallery.jpg", "alt": "Gallery image 1", "caption": "Gallery image 1"}],
            sources=[{"label": "Source", "url": "https://example.com/source"}],
        )
        journal = JournalEntry.objects.create(
            title="Edit Button Journal",
            journal_url="https://example.com/journal",
            authors="Rail Author",
            publication_year=2026,
            journal_name="Rail Journal",
            citation_info="Vol. 1",
            snippet="Journal snippet",
            keywords=["rail", "journal"],
        )
        media = MediaGalleryEntry.objects.create(
            title="Edit Button Image",
            description="Gallery description",
            media_type="image",
            date=timezone.localdate(),
            image_url="https://example.com/image.jpg",
        )
        video = VlogEntry.objects.create(
            title="Edit Button Video",
            filename="edit-button-video.mp4",
            channel_name="Rail Channel",
            description="Video description",
            video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            thumbnail_url="https://example.com/thumb.jpg",
            date=timezone.localdate(),
        )

        blog_response = self.client.get(reverse("blog_detail", args=[blog.slug]))
        journal_response = self.client.get(reverse("journal_detail", args=[journal.id]))
        gallery_response = self.client.get(reverse("gallery"))
        video_response = self.client.get(reverse("vlog_detail", args=[video.vlogID]))

        self.assertContains(blog_response, "Edit Blog")
        self.assertContains(journal_response, "Edit Journal")
        self.assertContains(gallery_response, "Edit")
        self.assertContains(gallery_response, reverse("edit_gallery_entry", args=[media.id]))
        self.assertContains(video_response, "Edit Media")

    def test_edit_blog_rejects_no_changes_inline(self):
        blog = BlogPost.objects.create(
            title="No Change Blog",
            slug="no-change-blog",
            excerpt="A blog excerpt",
            featured_image_filename="no-change-blog.jpg",
            featured_image_url="https://example.com/no-change.jpg",
            body_paragraphs=["Body"],
            keywords=["rail", "policy"],
            highlights=["Highlight"],
            gallery=[{"src": "https://example.com/gallery.jpg", "alt": "Gallery image 1", "caption": "Gallery image 1"}],
            sources=[{"label": "Source", "url": "https://example.com/source"}],
        )

        response = self.client.post(
            reverse("edit_blog", args=[blog.slug]),
            {
                "title": blog.title,
                "date": timezone.localtime(blog.created_at).date().isoformat(),
                "excerpt": blog.excerpt,
                "featured_image_url": blog.featured_image_url,
                "body_paragraphs": "Body",
                "keywords": "rail, policy",
                "highlights": "Highlight",
                "gallery": "https://example.com/gallery.jpg",
                "sources": "Source\nhttps://example.com/source",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Change at least one field before saving.", status_code=400)
        self.assertContains(response, "content-edit-modal is-open", status_code=400)

    def test_edit_journal_rejects_duplicate_title(self):
        JournalEntry.objects.create(
            title="Existing Journal",
            journal_url="https://example.com/existing",
            authors="Author One",
            publication_year=2026,
            journal_name="Rail Journal",
            citation_info="Vol. 1",
            snippet="Snippet",
            keywords=["rail", "policy"],
        )
        journal = JournalEntry.objects.create(
            title="Editable Journal",
            journal_url="https://example.com/editable",
            authors="Author Two",
            publication_year=2025,
            journal_name="Mobility Journal",
            citation_info="Vol. 2",
            snippet="Editable snippet",
            keywords=["mobility", "rail"],
        )

        response = self.client.post(
            reverse("edit_journal", args=[journal.id]),
            {
                "title": "Existing Journal",
                "date": timezone.localtime(journal.created_at).date().isoformat(),
                "journal_url": journal.journal_url,
                "authors": journal.authors,
                "publication_year": str(journal.publication_year),
                "journal_name": journal.journal_name,
                "citation_info": journal.citation_info,
                "snippet": journal.snippet,
                "keywords": "mobility, rail",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "A journal with this title already exists.", status_code=400)

    def test_edit_gallery_entry_requires_fields_inline(self):
        media = MediaGalleryEntry.objects.create(
            title="Editable Image",
            description="Gallery description",
            media_type="image",
            date=timezone.localdate(),
            image_url="https://example.com/image.jpg",
        )

        response = self.client.post(
            reverse("edit_gallery_entry", args=[media.id]),
            {
                "title": "",
                "description": "",
                "date": "",
                "image_url": "",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Title cannot be left blank.", status_code=400)
        self.assertContains(response, "Description cannot be left blank.", status_code=400)
        self.assertContains(response, "Image URL cannot be left blank.", status_code=400)

    def test_edit_gallery_entry_allows_originally_blank_date_to_stay_blank(self):
        media = MediaGalleryEntry.objects.create(
            title="Undated Image",
            description="Gallery description",
            media_type="image",
            image_url="https://example.com/image.jpg",
        )

        response = self.client.post(
            reverse("edit_gallery_entry", args=[media.id]),
            {
                "title": media.title,
                "description": "Updated gallery description",
                "date": "",
                "image_url": media.image_url,
            },
        )

        self.assertEqual(response.status_code, 302)
        media.refresh_from_db()
        self.assertEqual(media.description, "Updated gallery description")
        self.assertIsNone(media.date)


class AuditLogTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="auditadmin",
            email="auditadmin@example.com",
            password="secret123",
        )
        self.member = User.objects.create_user(username="auditmember", password="secret123")

    def test_admin_dropdown_contains_audit_logs_link(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("add_blog"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Audit Logs")
        self.assertContains(response, reverse("audit_logs"))

    def test_audit_page_is_admin_only(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("audit_logs"))

        self.assertNotEqual(response.status_code, 200)

    def test_audit_page_displays_roles_details_and_date_format(self):
        log = AuditLog.objects.create(
            user=self.admin,
            username=self.admin.username,
            role="Admin",
            action="auth",
            label="Login",
            method="POST",
            path="/econ/login_process",
            page_title="Login",
            details={"Account": self.admin.username, "Result": "Success"},
            status_code=302,
        )
        AuditLog.objects.create(
            username="Guest",
            role="Guest",
            action="visit",
            label="Page Visit",
            method="GET",
            path="/econ/blog/",
            page_title="Blogs",
            details={"Page": "Blogs"},
            status_code=200,
        )
        AuditLog.objects.create(
            user=self.member,
            username=self.member.username,
            role="Member",
            action="create",
            label="Create Account",
            method="POST",
            path="/econ/registration_process",
            page_title="Registration",
            details={"Account": self.member.username},
            status_code=302,
        )
        created_at = timezone.make_aware(
            datetime(2026, 5, 4, 13, 8),
            timezone.get_current_timezone(),
        )
        AuditLog.objects.filter(pk=log.pk).update(created_at=created_at)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("audit_logs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "May 04, 2026 1:08PM")
        self.assertContains(response, "Admin")
        self.assertContains(response, "Member")
        self.assertContains(response, "Guest")
        self.assertNotContains(response, "Type of Action")
        self.assertContains(response, "Login")
        self.assertContains(response, "Create Account")
        self.assertContains(response, "Account")
        self.assertContains(response, "Result")

    def test_guest_page_visit_is_logged_as_guest(self):
        response = self.client.get(reverse("blog"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AuditLog.objects.filter(role="Guest", action="visit", page_title="Blogs").exists()
        )

    def test_audit_logs_paginate_after_twenty_five_logs(self):
        for index in range(26):
            AuditLog.objects.create(
                username="Guest",
                role="Guest",
                action="visit",
                label=f"Page Visit {index}",
                method="GET",
                path=f"/econ/page-{index}/",
                page_title="Page",
                status_code=200,
            )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("audit_logs"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Page 1 of 2")
        self.assertContains(response, "audit logs")
