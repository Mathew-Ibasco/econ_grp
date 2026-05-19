from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
# make sure you have 'econdb' database already made
# Generate Migration files: python manage.py makemigrations
# Apply to MySQL Database: python manage.py migrate

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

    class Meta:
        db_table = "vlog"

class caption (models.Model):
    captionID = models.AutoField(primary_key=True)
    title = models.CharField(max_length=300)
    caption = models.CharField(max_length=300)
    filename = models.CharField(max_length=300)

    class Meta:
        db_table = "caption"

class post(models.Model):
    POST_TYPES = [
        ("blog", "Blog"),
        ("journal", "Journal"),
    ]

    postID = models.AutoField(primary_key=True)
    type = models.CharField(max_length=20, choices=POST_TYPES)
    header = models.CharField(max_length=300)
    text = models.TextField()
    sources = models.TextField(blank=True)
    tags = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "post"

class post_section(models.Model):
    sectionID = models.AutoField(primary_key=True)
    post = models.ForeignKey(post, on_delete=models.CASCADE, related_name="sections")
    subheader = models.CharField(max_length=300, blank=True)
    text = models.TextField()
    order = models.PositiveIntegerField()
    # controls order

    class Meta:
        db_table = "post_section"
        ordering = ["order"]

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
    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "media_gallery_entry"
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
