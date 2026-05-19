from django.contrib import admin
from .models import BlogPost, JournalEntry, MediaGalleryEntry, Topic, vlog


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "key", "order", "created_at")
    list_editable = ("order",)
    search_fields = ("title", "summary")
    prepopulated_fields = {"key": ("title",)}
    ordering = ("order", "title")

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "order", "created_at")
    list_editable = ("order",)
    search_fields = ("title", "excerpt")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("topics",)
    ordering = ("order", "title")


@admin.register(MediaGalleryEntry)
class MediaGalleryEntryAdmin(admin.ModelAdmin):
    list_display = ("title", "media_type", "date", "order", "created_at")
    list_editable = ("order",)
    list_filter = ("media_type", "topics")
    search_fields = ("title", "description")
    filter_horizontal = ("topics",)
    ordering = ("order", "title")


@admin.register(vlog)
class VlogAdmin(admin.ModelAdmin):
    list_display = ("title", "channel_name", "date", "order", "created_at")
    list_editable = ("order",)
    search_fields = ("title", "channel_name", "description")
    filter_horizontal = ("topics",)
    ordering = ("order", "title")


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("title", "journal_name", "publication_year", "order", "created_at")
    list_editable = ("order",)
    search_fields = ("title", "authors", "journal_name", "citation_info", "snippet")
    filter_horizontal = ("topics",)
    ordering = ("order", "title")
