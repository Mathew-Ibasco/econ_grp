from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser

# Create your models here.
# Default local setup uses SQLite (db_local.sqlite3).
# If you switch ECON_DB_ENGINE=mysql, make sure the econdb database exists first.
# Generate migration files with: python manage.py makemigrations
# Apply migrations with: python manage.py migrate

class User(AbstractUser):
    # AbstractUser already has: username, email, password, is_staff, is_superuser
    # add extra fields here if needed
    bio = models.TextField(blank=True)

    class Meta:
        db_table = "user"

class vlog (models.Model):
    vlogID = models.AutoField(primary_key=True)
    title = models.CharField(max_length=300)
    filename = models.CharField(max_length=300)
    channel_name = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True)
    video_url = models.URLField(max_length=500, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    date = models.DateField(null=True, blank=True)
    topics = models.ManyToManyField("Topic", blank=True, related_name="vlog_entries")
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    class Meta:
        db_table = "vlog"
        ordering = ["order", "vlogID"]

class caption (models.Model):
    captionID = models.AutoField(primary_key=True)
    title = models.CharField(max_length=300)
    caption = models.CharField(max_length=300)
    filename = models.CharField(max_length=300)

    class Meta:
        db_table = "caption"

class Topic(models.Model):
    key = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=160)
    summary = models.TextField()
    icon = models.CharField(max_length=80, default="fa-train")
    source_url = models.URLField(max_length=500, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "topic"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

class ForumThread(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="forum_threads")
    additional_topics = models.ManyToManyField(
        Topic,
        blank=True,
        related_name="forum_additional_threads",
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="forum_threads")
    title = models.CharField(max_length=220)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "forum_thread"
        ordering = ["-last_activity_at", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def all_topics(self):
        topics = [self.topic]
        seen = {self.topic_id}
        for topic in self.additional_topics.all():
            if topic.pk not in seen:
                topics.append(topic)
                seen.add(topic.pk)
        return topics

    @property
    def topic_titles(self):
        return ", ".join(topic.title for topic in self.all_topics)


class ForumThreadImage(models.Model):
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="forum_threads/%Y/%m/%d/")
    order = models.PositiveSmallIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "forum_thread_image"
        ordering = ["order", "id"]

    def __str__(self):
        return f"Image for {self.thread_id}"


@receiver(post_delete, sender=ForumThreadImage)
def delete_forum_thread_image_file(sender, instance, **kwargs):
    if instance.image:
        instance.image.delete(save=False)


class ForumReply(models.Model):
    thread = models.ForeignKey(ForumThread, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="forum_replies")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "forum_reply"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"Reply on {self.thread_id} by {self.author_id}"


@receiver(post_delete, sender=ForumReply)
def refresh_forum_thread_activity_after_reply_delete(sender, instance, **kwargs):
    thread = instance.thread
    if thread is None or not ForumThread.objects.filter(pk=thread.pk).exists():
        return

    latest_reply = thread.replies.order_by("-created_at", "-id").first()
    latest_activity = latest_reply.created_at if latest_reply is not None else thread.created_at
    if thread.last_activity_at != latest_activity:
        thread.last_activity_at = latest_activity
        thread.save(update_fields=["last_activity_at"])

class BlogPost(models.Model):
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=320, unique=True)
    excerpt = models.TextField()
    featured_image_filename = models.CharField(max_length=300)
    featured_image_url = models.URLField(max_length=500)
    raw_text = models.TextField(blank=True)
    body_paragraphs = models.JSONField(default=list, blank=True)
    keywords = models.JSONField(default=list, blank=True)
    highlights = models.JSONField(default=list, blank=True)
    gallery = models.JSONField(default=list, blank=True)
    sources = models.JSONField(default=list, blank=True)
    topics = models.ManyToManyField(Topic, blank=True, related_name="blog_posts")
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "blog_post"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

class MediaGalleryEntry(models.Model):
    MEDIA_TYPES = [
        ("image", "Image"),
        ("video", "Video"),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField()
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES)
    date = models.DateField(null=True, blank=True)
    image_url = models.URLField(max_length=500, blank=True)
    video_url = models.URLField(max_length=500, blank=True)
    thumbnail_url = models.URLField(max_length=500, blank=True)
    topics = models.ManyToManyField(Topic, blank=True, related_name="media_entries")
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "media_gallery_entry"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

class JournalEntry(models.Model):
    title = models.CharField(max_length=350)
    journal_url = models.URLField(max_length=500)
    authors = models.CharField(max_length=500)
    publication_year = models.PositiveSmallIntegerField()
    journal_name = models.CharField(max_length=255)
    citation_info = models.CharField(max_length=300, blank=True, default="")
    snippet = models.TextField()
    keywords = models.JSONField(default=list, blank=True)
    topics = models.ManyToManyField(Topic, blank=True, related_name="journal_entries")
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "journal_entry"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

class Bookmark(models.Model):
    BOOKMARK_TYPES = [
        ("topic", "Topic"),
        ("resource", "Resource"),
        ("media", "Media"),
    ]

    bookmarkID = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookmarks")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="bookmarks", null=True, blank=True)
    item_key = models.CharField(max_length=80)
    title = models.CharField(max_length=160)
    summary = models.TextField(blank=True)
    item_type = models.CharField(max_length=20, choices=BOOKMARK_TYPES)
    url = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bookmark"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "item_key"], name="unique_user_bookmark")
        ]

class TopicNote(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="topic_notes")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="user_notes")
    note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "topic_note"
        constraints = [
            models.UniqueConstraint(fields=["user", "topic"], name="unique_user_topic_note")
        ]

class StudyItemProgress(models.Model):
    ITEM_TYPES = [
        ("blog", "Blog"),
        ("journal", "Journal"),
        ("media", "Media"),
        ("video", "Video"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="study_progress")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="study_progress")
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    item_id = models.PositiveIntegerField()
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "study_item_progress"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "topic", "item_type", "item_id"],
                name="unique_user_topic_study_item",
            )
        ]

class QuizQuestion(models.Model):
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="quiz_questions")
    question = models.CharField(max_length=300)
    option_a = models.CharField(max_length=200)
    option_b = models.CharField(max_length=200)
    option_c = models.CharField(max_length=200)
    correct_option = models.CharField(
        max_length=1,
        choices=[("A", "A"), ("B", "B"), ("C", "C")],
    )
    explanation = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "quiz_question"
        ordering = ["topic__order", "order", "id"]

    def __str__(self):
        return self.question

class QuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_attempts")
    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name="quiz_attempts")
    score = models.PositiveSmallIntegerField(default=0)
    total = models.PositiveSmallIntegerField(default=0)
    answers = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "quiz_attempt"
        ordering = ["-created_at"]

class ItemNote(models.Model):
    ITEM_TYPES = [
        ("blog", "Blog"),
        ("journal", "Journal"),
        ("video", "Video"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="item_notes")
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    item_id = models.PositiveIntegerField()
    note = models.CharField(max_length=50)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "item_note"
        ordering = ["-updated_at"]

class ItemQuizQuestion(models.Model):
    ITEM_TYPES = [
        ("blog", "Blog"),
        ("journal", "Journal"),
        ("video", "Video"),
    ]

    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    item_id = models.PositiveIntegerField()
    question = models.CharField(max_length=300)
    option_a = models.CharField(max_length=200)
    option_b = models.CharField(max_length=200)
    option_c = models.CharField(max_length=200)
    correct_option = models.CharField(
        max_length=1,
        choices=[("A", "A"), ("B", "B"), ("C", "C")],
    )
    explanation = models.TextField(blank=True)
    round_number = models.PositiveSmallIntegerField(default=1)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "item_quiz_question"
        ordering = ["item_type", "item_id", "round_number", "order", "id"]

    def __str__(self):
        return self.question

class ItemQuizAttempt(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="item_quiz_attempts")
    item_type = models.CharField(max_length=20)
    item_id = models.PositiveIntegerField()
    round_number = models.PositiveSmallIntegerField(default=1)
    score = models.PositiveSmallIntegerField(default=0)
    total = models.PositiveSmallIntegerField(default=0)
    answers = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "item_quiz_attempt"
        ordering = ["-created_at"]

class ItemQuizProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="item_quiz_progress")
    item_type = models.CharField(max_length=20)
    item_id = models.PositiveIntegerField()
    perfect_rounds = models.PositiveSmallIntegerField(default=0)
    mastered = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "item_quiz_progress"
        constraints = [
            models.UniqueConstraint(fields=["user", "item_type", "item_id"], name="unique_user_item_quiz_progress")
        ]
