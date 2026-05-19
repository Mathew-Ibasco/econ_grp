from django.contrib import admin, messages
from .models import BlogPost, ForumReply, ForumThread, ForumThreadImage, ItemNote, ItemQuizAttempt, ItemQuizProgress, ItemQuizQuestion, JournalEntry, MediaGalleryEntry, QuizAttempt, QuizQuestion, StudyItemProgress, Topic, TopicNote, vlog


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


@admin.register(TopicNote)
class TopicNoteAdmin(admin.ModelAdmin):
    list_display = ("user", "topic", "updated_at")
    search_fields = ("user__username", "topic__title", "note")
    list_filter = ("topic",)


@admin.register(StudyItemProgress)
class StudyItemProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "topic", "item_type", "item_id", "completed_at")
    list_filter = ("topic", "item_type")
    search_fields = ("user__username", "topic__title")


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ("topic", "question", "correct_option", "order")
    list_editable = ("order",)
    list_filter = ("topic",)
    search_fields = ("question", "topic__title")


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "topic", "score", "total", "created_at")
    list_filter = ("topic",)
    search_fields = ("user__username", "topic__title")


@admin.register(ItemNote)
class ItemNoteAdmin(admin.ModelAdmin):
    list_display = ("user", "item_type", "item_id", "updated_at")
    list_filter = ("item_type",)
    search_fields = ("user__username", "note")


@admin.register(ItemQuizQuestion)
class ItemQuizQuestionAdmin(admin.ModelAdmin):
    list_display = ("item_type", "item_id", "round_number", "question", "correct_option", "order")
    list_editable = ("round_number", "order")
    list_filter = ("item_type", "round_number")
    search_fields = ("question",)


@admin.register(ItemQuizAttempt)
class ItemQuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "item_type", "item_id", "round_number", "score", "total", "created_at")
    list_filter = ("item_type", "round_number")
    search_fields = ("user__username",)


@admin.register(ItemQuizProgress)
class ItemQuizProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "item_type", "item_id", "perfect_rounds", "mastered", "updated_at")
    list_filter = ("item_type", "mastered")
    search_fields = ("user__username",)


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = ("title", "journal_name", "publication_year", "order", "created_at")
    list_editable = ("order",)
    search_fields = ("title", "authors", "journal_name", "citation_info", "snippet")
    filter_horizontal = ("topics",)
    ordering = ("order", "title")

class ForumThreadImageInline(admin.TabularInline):
    model = ForumThreadImage
    extra = 0
    fields = ("image", "order", "uploaded_at")
    readonly_fields = ("uploaded_at",)
    ordering = ("order", "id")


@admin.register(ForumThread)
class ForumThreadAdmin(admin.ModelAdmin):
    list_display = ("title", "topic", "author", "created_at", "last_activity_at")
    list_filter = ("topic", "additional_topics", "created_at")
    search_fields = ("title", "body", "author__username", "topic__title", "additional_topics__title")
    ordering = ("-last_activity_at", "-created_at")
    inlines = (ForumThreadImageInline,)
    filter_horizontal = ("additional_topics",)
    actions = ("delete_forum_threads",)

    @admin.action(description="Delete selected forum threads")
    def delete_forum_threads(self, request, queryset):
        deleted_count = queryset.count()
        queryset.delete()
        self.message_user(request, f"Deleted {deleted_count} forum thread(s).", level=messages.SUCCESS)


@admin.register(ForumReply)
class ForumReplyAdmin(admin.ModelAdmin):
    list_display = ("thread", "author", "created_at")
    list_filter = ("created_at",)
    search_fields = ("body", "author__username", "thread__title")
    ordering = ("-created_at",)
    actions = ("delete_forum_replies",)

    @admin.action(description="Delete selected forum replies")
    def delete_forum_replies(self, request, queryset):
        deleted_count = queryset.count()
        queryset.delete()
        self.message_user(request, f"Deleted {deleted_count} forum reply/replies.", level=messages.SUCCESS)
