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