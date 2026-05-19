from django.contrib import admin
from .models import BlogPost, MediaGalleryEntry

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "order", "created_at")
    list_editable = ("order",)
    search_fields = ("title", "excerpt")
    prepopulated_fields = {"slug": ("title",)}
    ordering = ("order", "title")


@admin.register(MediaGalleryEntry)
class MediaGalleryEntryAdmin(admin.ModelAdmin):
    list_display = ("title", "media_type", "date", "order", "created_at")
    list_editable = ("order",)
    list_filter = ("media_type",)
    search_fields = ("title", "description")
    ordering = ("order", "title")
