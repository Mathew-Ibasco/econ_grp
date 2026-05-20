from datetime import timedelta
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import ForumReply, ForumReplyImage, ForumThread, Topic, User
from PIL import Image


def _sample_png_upload(name="sample.png"):
    buffer = BytesIO()
    image = Image.new("RGB", (1, 1), color="white")
    image.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()
    return SimpleUploadedFile(name, png_bytes, content_type="image/png")


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

    def test_reply_like_can_be_toggled(self):
        self.client.force_login(self.user)
        reply = ForumReply.objects.create(thread=self.thread, author=self.user, body="Reply body")

        response = self.client.post(reverse("forum_toggle_reply_like", args=[reply.id]))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(reply.likes.filter(pk=self.user.pk).exists())

        response = self.client.post(reverse("forum_toggle_reply_like", args=[reply.id]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(reply.likes.filter(pk=self.user.pk).exists())

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

    def test_forum_thread_form_uses_tags_language(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("forum"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tags")
        self.assertNotContains(response, "Topics")

    def test_mobility_economy_topic_uses_chart_line_icon(self):
        economy_topic = Topic.objects.get(key="mobility-economy")

        self.assertEqual(economy_topic.icon, "fa-chart-line")
