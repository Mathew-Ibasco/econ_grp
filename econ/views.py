from datetime import datetime, date, time
from types import SimpleNamespace

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import URLValidator, validate_email
from django.db.models import Count, F, Prefetch, Q
from django.http import JsonResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.text import slugify

import os, re, sys, html, calendar, json, subprocess, sqlite3

try:
    import pymysql
except ImportError:  # Optional dependency; only needed for MySQL support.
    pymysql = None

from .forms import ForumReplyForm, ForumThreadCreateForm
from .models import BlogPost, Bookmark, ForumReply, ForumReplyImage, ForumThread, ForumThreadImage, ItemNote, ItemQuizAttempt, ItemQuizProgress, ItemQuizQuestion, JournalEntry, MediaGalleryEntry, QuizAttempt, StudyItemProgress, Topic, TopicNote, User, vlog as VlogEntry


DEFAULT_RECOMMENDATION_IMAGE = "https://cdn.britannica.com/16/123116-050-5D3AC998/Light-rail-Changchun-transit-Jilin-China.jpg"
JOURNAL_RECOMMENDATION_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Manila_LRT-MRT_map.png/1280px-Manila_LRT-MRT_map.png"
VIDEO_RECOMMENDATION_IMAGE = "https://media.philstar.com/images/articles/met2-mrt-3_2018-04-02_20-32-49.jpg"


def _topic_study_items(topic):
    items = []
    for blog_post in topic.blog_posts.all():
        items.append({
            "type": "blog",
            "id": blog_post.id,
            "title": blog_post.title,
            "url": reverse("blog_detail", args=[blog_post.slug]),
            "kind": "Blog",
        })
    for journal_entry in topic.journal_entries.all():
        items.append({
            "type": "journal",
            "id": journal_entry.id,
            "title": journal_entry.title,
            "url": journal_entry.journal_url,
            "kind": "Journal",
        })
    for media_entry in topic.media_entries.all():
        items.append({
            "type": "media",
            "id": media_entry.id,
            "title": media_entry.title,
            "url": reverse("gallery"),
            "kind": "Media",
        })
    for video_entry in topic.vlog_entries.all():
        items.append({
            "type": "video",
            "id": video_entry.vlogID,
            "title": video_entry.title,
            "url": reverse("vlog_detail", args=[video_entry.vlogID]),
            "kind": "Video",
        })
    return items


def _topic_recommendation_candidates(topic):
    candidates = []

    for post in topic.blog_posts.order_by("order", "id"):
        candidates.append(
            SimpleNamespace(
                topic=topic,
                title=post.title,
                summary=post.excerpt,
                kind="Blog",
                kind_key="blog",
                icon="fa-newspaper",
                url=reverse("blog_detail", args=[post.slug]),
                preview_image=post.featured_image_url or DEFAULT_RECOMMENDATION_IMAGE,
                cta_label="Open blog",
            )
        )

    for entry in topic.journal_entries.order_by("order", "id"):
        preview_image = JOURNAL_RECOMMENDATION_IMAGE
        if "history" in topic.key:
            preview_image = DEFAULT_RECOMMENDATION_IMAGE
        elif "mobility" in topic.key or "economy" in topic.key or "world-bank" in topic.key:
            preview_image = JOURNAL_RECOMMENDATION_IMAGE

        candidates.append(
            SimpleNamespace(
                topic=topic,
                title=entry.title,
                summary=entry.snippet,
                kind="Journal",
                kind_key="journal",
                icon="fa-book-open",
                url=reverse("journal_detail", args=[entry.id]),
                preview_image=preview_image,
                cta_label="Open journal",
            )
        )

    for entry in topic.vlog_entries.order_by("order", "vlogID"):
        preview_image = entry.thumbnail_url or _youtube_thumbnail_url(entry.video_url) or VIDEO_RECOMMENDATION_IMAGE
        candidates.append(
            SimpleNamespace(
                topic=topic,
                title=entry.title,
                summary=entry.description or "Watch a short rail mobility highlight from this topic.",
                kind="Video",
                kind_key="video",
                icon="fa-circle-play",
                url=reverse("vlog_detail", args=[entry.vlogID]),
                preview_image=preview_image,
                cta_label="Watch video",
            )
        )

    return candidates


def _dashboard_recommendations(dashboard_topics, saved_item_keys, limit=6):
    buckets = {
        "blog": [],
        "journal": [],
        "video": [],
    }
    seen_urls = set()

    for topic in dashboard_topics:
        if topic.key in saved_item_keys:
            continue

        for recommendation in _topic_recommendation_candidates(topic):
            if recommendation.kind_key not in buckets:
                continue
            if recommendation.url in seen_urls:
                continue
            buckets[recommendation.kind_key].append(recommendation)
            seen_urls.add(recommendation.url)

    recommended_items = []
    ordered_kinds = ("blog", "journal", "video")

    while len(recommended_items) < limit:
        added_any = False
        for kind in ordered_kinds:
            if buckets[kind]:
                recommended_items.append(buckets[kind].pop(0))
                added_any = True
                if len(recommended_items) == limit:
                    break
        if not added_any:
            break

    return recommended_items

def _forum_thread_queryset(topic=None):
    queryset = ForumThread.objects.select_related("topic", "author").annotate(
        reply_count=Count("replies", distinct=True),
    ).prefetch_related(
        Prefetch("additional_topics", queryset=Topic.objects.order_by("order", "title")),
        Prefetch("images", queryset=ForumThreadImage.objects.order_by("order", "id")),
    )
    if topic is not None:
        queryset = queryset.filter(Q(topic=topic) | Q(additional_topics=topic))
    return queryset.distinct().order_by("-created_at", "-id")


def _forum_page_context(thread_form=None, thread_modal_open=False):
    forum_threads = list(_forum_thread_queryset())
    forum_stats = {
        "thread_count": ForumThread.objects.count(),
        "reply_count": ForumReply.objects.count(),
    }
    forum_feed_title = "Latest Discussions"
    forum_feed_description = "Open threads across blogs, journals, media, and rail projects."
    forum_feed_summary = f"{forum_stats['reply_count']} replies across {forum_stats['thread_count']} discussions"

    if thread_form is None:
        thread_form = ForumThreadCreateForm()

    thread_form.fields["tags"].queryset = Topic.objects.order_by("order", "title")

    return {
        "date": datetime.now(),
        "forum_threads": forum_threads,
        "forum_stats": forum_stats,
        "thread_form": thread_form,
        "forum_feed_title": forum_feed_title,
        "forum_feed_description": forum_feed_description,
        "forum_feed_summary": forum_feed_summary,
        "thread_modal_open": thread_modal_open,
    }


def _forum_thread_panel_context(context):
    return {
        "forum_threads": context["forum_threads"],
    }


def _forum_fragment_response(request, thread_form=None, thread_modal_open=False):
    context = _forum_page_context(
        thread_form=thread_form,
        thread_modal_open=thread_modal_open,
    )
    return JsonResponse({
        "forum_feed_title": context["forum_feed_title"],
        "forum_feed_description": context["forum_feed_description"],
        "forum_feed_summary": context["forum_feed_summary"],
        "forum_thread_panel_html": render_to_string(
            "econ/forum_thread_panel.html",
            _forum_thread_panel_context(context),
            request=request,
        ),
    })


def _forum_thread_detail_queryset():
    return ForumThread.objects.select_related("topic", "author").prefetch_related(
        Prefetch("additional_topics", queryset=Topic.objects.order_by("order", "title")),
        Prefetch("images", queryset=ForumThreadImage.objects.order_by("order", "id")),
        "likes",
        Prefetch(
            "replies",
            queryset=ForumReply.objects.select_related("author").prefetch_related(
                Prefetch("images", queryset=ForumReplyImage.objects.order_by("order", "id")),
                "likes",
            ),
        ),
    )


def _prepare_forum_like_state(thread, viewer):
    viewer_id = viewer.id if getattr(viewer, "is_authenticated", False) else None

    thread_likes = list(thread.likes.all())
    thread.like_count = len(thread_likes)
    thread.user_liked = viewer_id is not None and any(user.id == viewer_id for user in thread_likes)

    replies = list(thread.replies.all())
    for reply in replies:
        reply_likes = list(reply.likes.all())
        reply.like_count = len(reply_likes)
        reply.user_liked = viewer_id is not None and any(user.id == viewer_id for user in reply_likes)

    return replies


def _forum_thread_context(thread, viewer=None, reply_form=None):
    context = _forum_page_context()
    thread_topics = [thread.topic]
    thread_topics.extend(list(thread.additional_topics.all()))
    replies = _prepare_forum_like_state(thread, viewer)
    context.update(
        {
            "thread": thread,
            "related_threads": list(
                _forum_thread_queryset().filter(
                    Q(topic__in=thread_topics) | Q(additional_topics__in=thread_topics)
                ).exclude(pk=thread.pk).distinct()[:4]
            ),
            "replies": replies,
            "reply_form": reply_form or ForumReplyForm(),
        }
    )
    return context


def _item_topic(item_type, item_id):
    if item_type == "blog":
        item = BlogPost.objects.prefetch_related("topics").filter(id=item_id).first()
    elif item_type == "journal":
        item = JournalEntry.objects.prefetch_related("topics").filter(id=item_id).first()
    elif item_type == "video":
        item = VlogEntry.objects.prefetch_related("topics").filter(vlogID=item_id).first()
    else:
        return None
    if item is None:
        return None
    return item.topics.order_by("order", "id").first()


def _item_learning_context(user, item_type, item_id):
    if not user.is_authenticated:
        return None
    notes = ItemNote.objects.filter(user=user, item_type=item_type, item_id=item_id)
    result_attempt = None
    result_questions = []
    quiz_progress, _ = ItemQuizProgress.objects.get_or_create(
        user=user,
        item_type=item_type,
        item_id=item_id,
    )
    current_round = min(quiz_progress.perfect_rounds + 1, 3)
    questions = ItemQuizQuestion.objects.filter(
        item_type=item_type,
        item_id=item_id,
        round_number=current_round,
    ).order_by("order", "id")
    return {
        "note": notes.first(),
        "notes": notes,
        "notes_count": notes.count(),
        "questions": questions,
        "latest_attempt": ItemQuizAttempt.objects.filter(user=user, item_type=item_type, item_id=item_id).first(),
        "result_attempt": result_attempt,
        "result_questions": result_questions,
        "quiz_progress": quiz_progress,
        "current_round": current_round,
        "perfect_rounds": quiz_progress.perfect_rounds,
        "mastered": quiz_progress.mastered,
        "completed": StudyItemProgress.objects.filter(user=user, item_type=item_type, item_id=item_id).exists(),
    }


def _delete_item_learning_data(item_type, item_id):
    item_id = int(item_id)
    StudyItemProgress.objects.filter(item_type=item_type, item_id=item_id).delete()
    ItemNote.objects.filter(item_type=item_type, item_id=item_id).delete()
    ItemQuizProgress.objects.filter(item_type=item_type, item_id=item_id).delete()
    ItemQuizAttempt.objects.filter(item_type=item_type, item_id=item_id).delete()
    ItemQuizQuestion.objects.filter(item_type=item_type, item_id=item_id).delete()


def _attach_quiz_result(learning, user, item_type, item_id, attempt_id):
    if not learning or not attempt_id:
        return learning
    attempt = ItemQuizAttempt.objects.filter(
        id=attempt_id,
        user=user,
        item_type=item_type,
        item_id=item_id,
    ).first()
    if attempt is None:
        return learning

    result_questions = []
    question_ids = [int(question_id) for question_id in attempt.answers.keys() if str(question_id).isdigit()]
    questions_by_id = {
        question.id: question
        for question in ItemQuizQuestion.objects.filter(id__in=question_ids)
    }
    for question_id in question_ids:
        question = questions_by_id.get(question_id)
        if question is None:
            continue
        selected = attempt.answers.get(str(question.id), "")
        correct_text = getattr(question, f"option_{question.correct_option.lower()}")
        selected_text = getattr(question, f"option_{selected.lower()}", "") if selected in {"A", "B", "C"} else ""
        result_questions.append(SimpleNamespace(
            question=question.question,
            selected=selected,
            selected_text=selected_text,
            correct=question.correct_option,
            correct_text=correct_text,
            is_correct=selected == question.correct_option,
        ))

    learning["result_attempt"] = attempt
    learning["result_questions"] = result_questions
    learning["result_is_perfect"] = attempt.total > 0 and attempt.score == attempt.total
    return learning

def _auth_context(values=None, errors=None):
    return {
        "date": datetime.now(),
        "values": values or {},
        "errors": errors or {},
    }


YOUTUBE_EMBED_PATTERNS = (
    re.compile(r"(?:https?://)?(?:www\.)?youtu\.be/([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/embed/([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([A-Za-z0-9_-]{11})"),
)


def _youtube_video_id(video_url):
    if not video_url:
        return ""

    for pattern in YOUTUBE_EMBED_PATTERNS:
        match = pattern.search(video_url)
        if match:
            return match.group(1)

    return ""


def _youtube_embed_url(video_url):
    video_id = _youtube_video_id(video_url)
    if video_id:
        return f"https://www.youtube-nocookie.com/embed/{video_id}"
    return ""


def _youtube_thumbnail_url(video_url):
    video_id = _youtube_video_id(video_url)
    if video_id:
        return f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
    return ""

def custom_400(request, exception):
    return render(request, "econ/error/400.html", status=400)

def custom_403(request, exception):
    return render(request, "econ/error/403.html", status=403)

def custom_404(request, exception):
    return render(request, "econ/error/404.html", status=404)

def custom_500(request):
    return render(request, "econ/error/500.html", status=500)

def login_process(request):
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        next_url = request.POST.get("next", "").strip()
        values = {"username": username, "next": next_url}
        errors = {}
        account = None

        if not username:
            errors["username"] = "Username is required."
        elif len(username) > 20:
            errors["username"] = "Username cannot be more than 20 characters."
        else:
            account = User.objects.filter(username__iexact=username).first()

        if username and len(username) <= 20 and account is None:
            errors["username"] = "Account does not exist."

        if not password:
            errors["password"] = "Password is required."

        if errors:
            return render(request, "econ/login.html", _auth_context(values, errors), status=400)

        user = authenticate(request, username=account.username, password=password)
        if user is not None:
            auth_login(request, user)
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("index")
        else:
            errors["password"] = "Incorrect password."
            return render(request, "econ/login.html", _auth_context(values, errors), status=400)
    return render(request, "econ/login.html", _auth_context())

def logout_process(request):
    logout(request)
    return redirect("index")

@login_required
def profile(request):
    user = request.user
    edit_mode = request.GET.get("edit") == "1"
    role_label = "ADMINISTRATOR" if user.is_superuser else "STAFF MEMBER" if user.is_staff else "MEMBER"
    access_label = "System Admin Access" if user.is_superuser or user.is_staff else "Standard Member Access"
    values = {
        "username": user.username,
        "email": user.email,
        "bio": user.bio,
    }
    errors = {}
    bio_limit = 250

    if request.method == "POST":
        edit_mode = True
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        bio = request.POST.get("bio", "").strip()
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")
        wants_password_change = bool(new_password or confirm_password)
        values = {
            "username": username,
            "email": email,
            "bio": bio,
        }

        if not username:
            errors["username"] = "Username cannot be blank."
        elif len(username) > 20:
            errors["username"] = "Username cannot be more than 20 characters."
        elif User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
            errors["username"] = "Username already exists."

        if not email:
            errors["email"] = "Email cannot be blank."
        else:
            try:
                validate_email(email)
            except ValidationError:
                errors["email"] = "Enter a valid email address with @."
            else:
                if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
                    errors["email"] = "Email already exists."

        if not bio:
            errors["bio"] = "Bio cannot be blank."
        elif len(bio) > bio_limit:
            errors["bio"] = f"Bio cannot be more than {bio_limit} characters."

        if wants_password_change:
            if not new_password:
                errors["new_password"] = "New password cannot be blank."
            elif len(new_password) < 8:
                errors["new_password"] = "New password must be at least 8 characters."
            elif user.check_password(new_password):
                errors["new_password"] = "New password cannot be the same as your current password."

            if not confirm_password:
                errors["confirm_password"] = "Confirm password cannot be blank."
            elif new_password and new_password != confirm_password:
                errors["confirm_password"] = "New password and confirm password must match."

        profile_changed = (
            username != user.username
            or email != user.email
            or bio != user.bio
        )
        if not errors and not profile_changed and not wants_password_change:
            errors["form"] = "No changes were made."

        if not errors:
            user.username = username
            user.email = email
            user.bio = bio
            if wants_password_change:
                user.set_password(new_password)
            user.save()
            if wants_password_change:
                update_session_auth_hash(request, user)
            messages.success(request, "Profile updated successfully.")
            return redirect("profile")

    return render(
        request,
        "econ/profile.html",
        {
            "date": datetime.now(),
            "edit_mode": edit_mode,
            "profile_role_label": role_label,
            "profile_access_label": access_label,
            "values": values,
            "errors": errors,
            "bio_limit": bio_limit,
        },
        status=400 if errors else 200,
    )

def _dashboard_page_context(request):
    context = {
        "date": datetime.now(),
    }

    if request.user.is_authenticated:
        dashboard_topics = list(Topic.objects.prefetch_related(
            "blog_posts",
            "journal_entries",
            "media_entries",
            "vlog_entries",
            "quiz_questions",
        ).order_by("order", "id"))
        saved_bookmarks = list(
            request.user.bookmarks.select_related("topic").prefetch_related(
                "topic__blog_posts",
                "topic__journal_entries",
                "topic__media_entries",
                "topic__vlog_entries",
                "topic__quiz_questions",
            )
        )
        saved_item_keys = {bookmark.item_key for bookmark in saved_bookmarks}
        saved_topics = [bookmark.topic for bookmark in saved_bookmarks if bookmark.topic_id]
        topic_ids = [topic.id for topic in saved_topics]
        progress_rows = StudyItemProgress.objects.filter(
            user=request.user,
            topic_id__in=topic_ids,
        )
        completed_keys = {
            (row.topic_id, row.item_type, row.item_id)
            for row in progress_rows
        }

        study_boards = []
        for bookmark in saved_bookmarks:
            topic = bookmark.topic
            if topic is None:
                continue
            items = []
            for item in _topic_study_items(topic):
                item["completed"] = (topic.id, item["type"], item["id"]) in completed_keys
                items.append(SimpleNamespace(**item))
            total_items = len(items)
            completed_items = sum(1 for item in items if item.completed)
            progress_percent = round((completed_items / total_items) * 100) if total_items else 0
            study_boards.append(SimpleNamespace(
                bookmark=bookmark,
                topic=topic,
                items=items,
                blog_items=[item for item in items if item.type == "blog"],
                journal_items=[item for item in items if item.type == "journal"],
                media_items=[item for item in items if item.type == "media"],
                video_items=[item for item in items if item.type == "video"],
                total_items=total_items,
                completed_items=completed_items,
                progress_percent=progress_percent,
            ))

        recommended_items = _dashboard_recommendations(dashboard_topics, saved_item_keys)

        context.update(
            {
                "dashboard_topics": dashboard_topics,
                "saved_bookmarks": saved_bookmarks,
                "study_boards": study_boards,
                "saved_item_keys": saved_item_keys,
                "available_topics_count": sum(1 for topic in dashboard_topics if topic.key not in saved_item_keys),
                "recommended_items": recommended_items,
            }
        )

    return context

def _public_home_context():
    homepage_topics = list(
        Topic.objects.prefetch_related(
            "blog_posts",
            "journal_entries",
            "vlog_entries",
        ).order_by("order", "id")
    )
    return {
        "date": datetime.now(),
        "show_dashboard": False,
        "recommended_items": _dashboard_recommendations(homepage_topics, set()),
    }


def home(request):
    return render(request, "econ/index.html", _public_home_context())

# staff/admin only
@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
    return render(
        request, 
        "econ/admin_dashboard.html",
        {
            'date': datetime.now()
        }
    )

def login(request):
    return render(
        request,
        'econ/login.html',
        _auth_context({"next": request.GET.get("next", "")})
    )

def registration(request):
    return render(request, "econ/registration.html", _auth_context())

def registration_process(request):
    if request.method == "POST":
        alldata = request.POST
        username = alldata.get("username", "").strip()
        password = alldata.get("password", "")
        confirm = alldata.get("confirm", "")
        email = alldata.get("email", "").strip()
        bio = alldata.get("bio", "").strip()
        values = {
            "username": username,
            "email": email,
            "bio": bio,
        }
        errors = {}

        if not username:
            errors["username"] = "Username is required."
        elif len(username) > 20:
            errors["username"] = "Username cannot be more than 20 characters."
        elif User.objects.filter(username__iexact=username).exists():
            errors["username"] = "Username already exists."

        if not email:
            errors["email"] = "Email is required."
        else:
            try:
                validate_email(email)
            except ValidationError:
                errors["email"] = "Enter a valid email address."
            else:
                if User.objects.filter(email__iexact=email).exists():
                    errors["email"] = "Email already exists."

        if not password:
            errors["password"] = "Password is required."
        elif len(password) < 8:
            errors["password"] = "Password must be at least 8 characters."

        if not confirm:
            errors["confirm"] = "Confirm password is required."
        elif password and password != confirm:
            errors["confirm"] = "Passwords do not match."

        if errors:
            return render(request, "econ/registration.html", _auth_context(values, errors), status=400)

        user = User.objects.create_user(username=username, password=password, email=email)
        user.bio = bio
        user.save()

        messages.success(request, "Registration successful. Please log in.")
        return redirect("login")

    return redirect("registration")

@login_required
def toggle_bookmark(request):
    if request.method != "POST":
        return redirect("index")

    item_key = request.POST.get("item_key", "").strip()
    topic = Topic.objects.filter(key=item_key).first()
    if topic is None:
        messages.error(request, "That topic is no longer available.")
        return redirect("index")

    existing = Bookmark.objects.filter(user=request.user, item_key=item_key).first()
    if existing:
        existing.delete()
        messages.success(request, f"Removed {topic.title} from your saved topics.")
    else:
        Bookmark.objects.create(
            user=request.user,
            topic=topic,
            item_key=topic.key,
            title=topic.title,
            summary=topic.summary,
            item_type="topic",
            url=topic.source_url,
        )
        messages.success(request, f"Saved {topic.title} to your dashboard.")

    return redirect("index")

def index(request):
    if request.user.is_authenticated:
        context = _dashboard_page_context(request)
        context["show_dashboard"] = True
        return render(request, "econ/index.html", context)
    return render(request, "econ/index.html", _public_home_context())

@login_required
def dashboard(request):
    context = _dashboard_page_context(request)
    context["show_dashboard"] = True
    return render(request, "econ/index.html", context)

def forum(request):
    if request.GET.get("fragment") == "1" or request.headers.get("x-requested-with") == "XMLHttpRequest":
        return _forum_fragment_response(request)
    context = _forum_page_context()
    return render(request, "econ/forum.html", context)


@login_required
def forum_create_thread(request):
    if request.method != "POST":
        return redirect("forum")

    form = ForumThreadCreateForm(request.POST, request.FILES)
    if form.is_valid():
        selected_tags = list(form.cleaned_data["tags"])
        primary_tag = selected_tags[0]
        secondary_tags = selected_tags[1:]
        thread = ForumThread.objects.create(
            topic=primary_tag,
            author=request.user,
            title=form.cleaned_data["title"],
            body=form.cleaned_data["body"],
        )
        thread.additional_topics.set(secondary_tags)
        uploaded_images = form.cleaned_data.get("images") or []
        for order, image in enumerate(uploaded_images):
            ForumThreadImage.objects.create(thread=thread, image=image, order=order)

        if uploaded_images:
            messages.success(request, "Your discussion and pictures were posted.")
        else:
            messages.success(request, "Your discussion was posted.")
        return redirect("forum_thread", thread_id=thread.id)

    context = _forum_page_context(thread_form=form, thread_modal_open=True)
    messages.error(request, "Please finish the thread details and try again.")
    return render(request, "econ/forum.html", context, status=400)


def _require_forum_staff(user):
    if not (user.is_staff or user.is_superuser):
        raise PermissionDenied


def _can_manage_forum_thread(user, thread):
    return user.is_staff or user.is_superuser or thread.author_id == user.id


def _can_manage_forum_reply(user, reply):
    return user.is_staff or user.is_superuser or reply.author_id == user.id


def _refresh_forum_thread_activity(thread):
    latest_reply = thread.replies.order_by("-created_at", "-id").first()
    latest_activity = latest_reply.created_at if latest_reply is not None else thread.created_at
    if thread.last_activity_at != latest_activity:
        thread.last_activity_at = latest_activity
        thread.save(update_fields=["last_activity_at"])


def forum_thread(request, thread_id):
    thread = get_object_or_404(_forum_thread_detail_queryset(), pk=thread_id)
    context = _forum_thread_context(thread, request.user)
    return render(request, "econ/forum_thread.html", context)


@login_required
def forum_reply(request, thread_id):
    if request.method != "POST":
        return redirect("forum_thread", thread_id=thread_id)

    thread = get_object_or_404(_forum_thread_detail_queryset(), pk=thread_id)
    form = ForumReplyForm(request.POST, request.FILES)
    if form.is_valid():
        reply = ForumReply.objects.create(
            thread=thread,
            author=request.user,
            body=form.cleaned_data["body"],
        )
        uploaded_images = form.cleaned_data.get("images") or []
        for order, image in enumerate(uploaded_images):
            ForumReplyImage.objects.create(reply=reply, image=image, order=order)
        thread.last_activity_at = timezone.now()
        thread.save(update_fields=["last_activity_at"])
        if uploaded_images:
            messages.success(request, "Your reply and pictures were posted.")
        else:
            messages.success(request, "Your reply was posted.")
        return redirect(f"{reverse('forum_thread', args=[thread.id])}#replies")

    context = _forum_thread_context(thread, request.user, reply_form=form)
    messages.error(request, "Please check the reply details and try again.")
    return render(request, "econ/forum_thread.html", context, status=400)


@login_required
def forum_toggle_thread_like(request, thread_id):
    if request.method != "POST":
        return redirect("forum_thread", thread_id=thread_id)

    thread = get_object_or_404(ForumThread, pk=thread_id)
    if thread.likes.filter(pk=request.user.pk).exists():
        thread.likes.remove(request.user)
    else:
        thread.likes.add(request.user)

    return redirect(f"{reverse('forum_thread', args=[thread.id])}#thread")


@login_required
def forum_toggle_reply_like(request, reply_id):
    reply = get_object_or_404(ForumReply.objects.select_related("thread"), pk=reply_id)
    if request.method != "POST":
        return redirect(f"{reverse('forum_thread', args=[reply.thread_id])}#reply-{reply.id}")

    if reply.likes.filter(pk=request.user.pk).exists():
        reply.likes.remove(request.user)
    else:
        reply.likes.add(request.user)

    return redirect(f"{reverse('forum_thread', args=[reply.thread_id])}#reply-{reply.id}")


@login_required
def forum_delete_thread(request, thread_id):
    if request.method != "POST":
        return redirect("forum_thread", thread_id=thread_id)

    thread = get_object_or_404(ForumThread.objects.select_related("author"), pk=thread_id)
    if not _can_manage_forum_thread(request.user, thread):
        raise PermissionDenied
    title = thread.title
    thread.delete()
    messages.success(request, f"Deleted thread: {title}")
    return redirect("forum")


@login_required
def forum_delete_reply(request, reply_id):
    if request.method != "POST":
        return redirect("forum")

    reply = get_object_or_404(ForumReply.objects.select_related("thread"), pk=reply_id)
    if not _can_manage_forum_reply(request.user, reply):
        raise PermissionDenied
    thread = reply.thread
    reply.delete()
    _refresh_forum_thread_activity(thread)
    messages.success(request, "Deleted reply.")
    return redirect(f"{reverse('forum_thread', args=[thread.id])}#replies")

def blog(request):
    blog_posts = list(BlogPost.objects.order_by("order", "id"))
    if request.user.is_authenticated and blog_posts:
        viewed_blog_ids = set(
            StudyItemProgress.objects.filter(
                user=request.user,
                item_type="blog",
                item_id__in=[blog.id for blog in blog_posts],
            ).values_list("item_id", flat=True)
        )
        for blog_post in blog_posts:
            blog_post.learning = SimpleNamespace(completed=blog_post.id in viewed_blog_ids)
    else:
        for blog_post in blog_posts:
            blog_post.learning = SimpleNamespace(completed=False)

    return render(
        request,
        'econ/blog.html',
        {
            'date': datetime.now(),
            'blog_posts': blog_posts,
        }
    )

def blog_detail(request, slug):
    blog_post = get_object_or_404(BlogPost, slug=slug)
    learning = _item_learning_context(request.user, "blog", blog_post.id)
    learning = _attach_quiz_result(
        learning,
        request.user,
        "blog",
        blog_post.id,
        request.GET.get("quiz_attempt"),
    )

    return render(
        request,
        "econ/blog_detail.html",
        {
            "date": datetime.now(),
            "blog_post": blog_post,
            "learning": learning,
            "learning_item_type": "blog",
            "learning_item_id": blog_post.id,
        }
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_blog(request, slug):
    if request.method != "POST":
        return redirect("blog_detail", slug=slug)

    blog_post = get_object_or_404(BlogPost, slug=slug)
    title = blog_post.title
    item_id = blog_post.id
    blog_post.delete()
    _delete_item_learning_data("blog", item_id)
    messages.success(request, f"Deleted blog: {title}")
    return redirect("blog")


@login_required
def toggle_study_progress(request):
    if request.method != "POST":
        return redirect("index")

    item_type = request.POST.get("item_type", "").strip()
    item_id = request.POST.get("item_id", "").strip()

    if item_type not in {"blog", "journal", "media", "video"} or not item_id.isdigit():
        messages.error(request, "That study item could not be updated.")
        return redirect(request.POST.get("next") or "index")

    topic = _item_topic(item_type, int(item_id))
    if topic is None:
        topic_id = request.POST.get("topic_id")
        topic = get_object_or_404(Topic, id=topic_id)

    progress, created = StudyItemProgress.objects.get_or_create(
        user=request.user,
        topic=topic,
        item_type=item_type,
        item_id=int(item_id),
    )
    if created:
        messages.success(request, "Marked as done.")
    else:
        progress.delete()
        messages.success(request, "Marked as not done.")

    return redirect(request.POST.get("next") or "index")

@login_required
def save_item_note(request):
    if request.method != "POST":
        return redirect("index")

    item_type = request.POST.get("item_type", "").strip()
    item_id = request.POST.get("item_id", "").strip()
    note_text = request.POST.get("note", "").strip()
    if item_type not in {"blog", "journal", "video"} or not item_id.isdigit():
        messages.error(request, "That note could not be saved.")
        return redirect(request.POST.get("next") or "index")

    if not note_text:
        messages.error(request, "Please enter a note before saving.")
        return redirect(request.POST.get("next") or "index")

    if len(note_text) > 50:
        messages.error(request, "Notes can only be up to 50 characters.")
        return redirect(request.POST.get("next") or "index")

    notes_count = ItemNote.objects.filter(
        user=request.user,
        item_type=item_type,
        item_id=int(item_id),
    ).count()
    if notes_count >= 5:
        messages.error(request, "You can only save up to 5 notes for this item.")
        return redirect(request.POST.get("next") or "index")

    ItemNote.objects.create(
        user=request.user,
        item_type=item_type,
        item_id=int(item_id),
        note=note_text,
    )
    messages.success(request, "Saved your note.")
    return redirect(request.POST.get("next") or "index")

@login_required
def submit_item_quiz(request):
    if request.method != "POST":
        return redirect("index")

    item_type = request.POST.get("item_type", "").strip()
    item_id = request.POST.get("item_id", "").strip()
    if item_type not in {"blog", "journal"} or not item_id.isdigit():
        messages.error(request, "That quiz could not be submitted.")
        return redirect(request.POST.get("next") or "index")

    quiz_progress, _ = ItemQuizProgress.objects.get_or_create(
        user=request.user,
        item_type=item_type,
        item_id=int(item_id),
    )
    if quiz_progress.mastered:
        messages.success(request, "You already mastered this checkpoint.")
        return redirect(request.POST.get("next") or "index")

    current_round = min(quiz_progress.perfect_rounds + 1, 3)
    questions = list(ItemQuizQuestion.objects.filter(
        item_type=item_type,
        item_id=int(item_id),
        round_number=current_round,
    ).order_by("order", "id"))
    answers = {}
    score = 0
    for question in questions:
        selected = request.POST.get(f"question_{question.id}", "").strip().upper()
        answers[str(question.id)] = selected
        if selected == question.correct_option:
            score += 1

    attempt = ItemQuizAttempt.objects.create(
        user=request.user,
        item_type=item_type,
        item_id=int(item_id),
        round_number=current_round,
        score=score,
        total=len(questions),
        answers=answers,
    )
    if questions and score == len(questions):
        quiz_progress.perfect_rounds = min(quiz_progress.perfect_rounds + 1, 3)
        quiz_progress.mastered = quiz_progress.perfect_rounds >= 3
        quiz_progress.save(update_fields=["perfect_rounds", "mastered", "updated_at"])

    messages.success(request, f"Quiz submitted: {score}/{len(questions)}.")
    next_url = request.POST.get("next") or reverse("index")
    separator = "&" if "?" in next_url else "?"
    return redirect(f"{next_url}{separator}quiz_attempt={attempt.id}")

def journal(request):
    journal_entries = list(JournalEntry.objects.prefetch_related("topics").order_by("order", "id"))
    if request.user.is_authenticated and journal_entries:
        viewed_journal_ids = set(
            StudyItemProgress.objects.filter(
                user=request.user,
                item_type="journal",
                item_id__in=[journal.id for journal in journal_entries],
            ).values_list("item_id", flat=True)
        )
        for journal_entry in journal_entries:
            journal_entry.learning = SimpleNamespace(completed=journal_entry.id in viewed_journal_ids)
    else:
        for journal_entry in journal_entries:
            journal_entry.learning = SimpleNamespace(completed=False)

    return render(
        request,
        'econ/journal.html',
        {
            'date': datetime.now(),
            'journal_entries': journal_entries,
        }
    )

def journal_detail(request, journal_id):
    journal = get_object_or_404(
        JournalEntry.objects.prefetch_related("topics"),
        pk=journal_id,
    )
    learning = _item_learning_context(request.user, "journal", journal.id)
    learning = _attach_quiz_result(
        learning,
        request.user,
        "journal",
        journal.id,
        request.GET.get("quiz_attempt"),
    )

    return render(
        request,
        "econ/journal_detail.html",
        {
            "date": datetime.now(),
            "journal": journal,
            "learning": learning,
            "learning_item_type": "journal",
            "learning_item_id": journal.id,
        }
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_journal(request, journal_id):
    if request.method != "POST":
        return redirect("journal_detail", journal_id=journal_id)

    journal = get_object_or_404(JournalEntry, pk=journal_id)
    title = journal.title
    item_id = journal.id
    journal.delete()
    _delete_item_learning_data("journal", item_id)
    messages.success(request, f"Deleted journal: {title}")
    return redirect("journal")


def vlog(request):
    vlog_entries = list(
        VlogEntry.objects.prefetch_related("topics").order_by("order", "vlogID")
    )

    for entry in vlog_entries:
        entry.embed_url = _youtube_embed_url(entry.video_url)
        entry.preview_url = entry.thumbnail_url or _youtube_thumbnail_url(entry.video_url)

    if request.user.is_authenticated and vlog_entries:
        viewed_video_ids = set(
            StudyItemProgress.objects.filter(
                user=request.user,
                item_type="video",
                item_id__in=[entry.vlogID for entry in vlog_entries],
            ).values_list("item_id", flat=True)
        )
        for entry in vlog_entries:
            entry.learning = SimpleNamespace(completed=entry.vlogID in viewed_video_ids)
    else:
        for entry in vlog_entries:
            entry.learning = SimpleNamespace(completed=False)

    return render(
        request,
        'econ/vlog.html',
        {
            'date': datetime.now(),
            'vlog_entries': vlog_entries,
        }
    )

def vlog_detail(request, vlog_id):
    video = get_object_or_404(VlogEntry.objects.prefetch_related("topics"), pk=vlog_id)
    video.embed_url = _youtube_embed_url(video.video_url)
    video.preview_url = video.thumbnail_url or _youtube_thumbnail_url(video.video_url)
    learning = _item_learning_context(request.user, "video", video.vlogID)
    learning = _attach_quiz_result(
        learning,
        request.user,
        "video",
        video.vlogID,
        request.GET.get("quiz_attempt"),
    )

    return render(
        request,
        "econ/vlog_detail.html",
        {
            "date": datetime.now(),
            "video": video,
            "learning": learning,
            "learning_item_type": "video",
            "learning_item_id": video.vlogID,
        }
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_vlog(request, vlog_id):
    if request.method != "POST":
        return redirect("vlog_detail", vlog_id=vlog_id)

    video = get_object_or_404(VlogEntry, pk=vlog_id)
    title = video.title
    item_id = video.vlogID
    video.delete()
    _delete_item_learning_data("video", item_id)
    messages.success(request, f"Deleted media: {title}")
    return redirect("vlog")


def gallery(request):
    gallery_entries = list(MediaGalleryEntry.objects.order_by("order", "id"))
    return render(
        request,
        'econ/gallery.html',
        {
            'date': datetime.now(),
            'gallery_entries': gallery_entries,
            'gallery_count': len(gallery_entries),
        }
    )


@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_gallery_entry(request, media_id):
    if request.method != "POST":
        return redirect("gallery")

    media = get_object_or_404(MediaGalleryEntry, pk=media_id)
    title = media.title
    item_id = media.id
    media.delete()
    _delete_item_learning_data("media", item_id)
    messages.success(request, f"Deleted gallery item: {title}")
    return redirect("gallery")

############################################# SQL ##############################################################################

@login_required
@user_passes_test(lambda u: u.is_superuser)
def upload_sql(request):
    return render(
        request,
        'econ/upload_sql.html',
        {
            'date': datetime.now()
        }
    )

def get_db_engine():
    return settings.DATABASES['default'].get('ENGINE', '')

def is_sqlite():
    return 'sqlite3' in get_db_engine()

def is_mysql():
    return 'mysql' in get_db_engine()

@login_required
@user_passes_test(lambda u: u.is_superuser)
def download_sql_dump(request):
    filename = f"dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"

    if is_sqlite():
        stream = _sqlite_dump_stream()
    elif is_mysql():
        stream = _mysql_dump_stream()
    else:
        raise ValueError(f"Unsupported database engine: {get_db_engine()}")

    response = StreamingHttpResponse(stream, content_type='application/sql')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def _sqlite_dump_stream():
    db_path = settings.DATABASES['default']['NAME']
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    yield f"-- SQL Dump: {os.path.basename(db_path)}\n".encode()
    yield f"-- Generated: {datetime.now()}\n\n".encode()
    yield b"PRAGMA foreign_keys = OFF;\n\n"

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
        create_table = cursor.fetchone()[0]
        yield f"-- Table: {table}\n".encode()
        yield f'DROP TABLE IF EXISTS "{table}";\n'.encode()
        yield f"{create_table};\n\n".encode()

        cursor.execute(f'SELECT * FROM "{table}"')
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                values = ', '.join(
                    'NULL' if val is None
                    else f"'{str(val).replace(chr(39), chr(39)*2)}'"
                    for val in row
                )
                yield f'INSERT INTO "{table}" VALUES ({values});\n'.encode()
            yield b"\n"

    yield b"PRAGMA foreign_keys = ON;\n"
    cursor.close()
    conn.close()


def _mysql_dump_stream():
    if pymysql is None:
        raise ImportError("PyMySQL is required for MySQL database support.")

    db = settings.DATABASES['default']
    conn = pymysql.connect(
        host=db['HOST'],
        port=int(db.get('PORT', 3306)),
        user=db['USER'],
        password=db['PASSWORD'],
        database=db['NAME'],
    )
    cursor = conn.cursor()

    yield f"-- SQL Dump: {db['NAME']}\n".encode()
    yield f"-- Generated: {datetime.now()}\n\n".encode()
    yield b"SET FOREIGN_KEY_CHECKS=0;\n\n"

    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        cursor.execute(f"SHOW CREATE TABLE `{table}`")
        create_table = cursor.fetchone()[1]
        yield f"-- Table: {table}\n".encode()
        yield f"DROP TABLE IF EXISTS `{table}`;\n".encode()
        yield f"{create_table};\n\n".encode()

        cursor.execute(f"SELECT * FROM `{table}`")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                values = ', '.join(
                    'NULL' if val is None
                    else f"'{str(val).replace(chr(39), chr(39)*2)}'"
                    for val in row
                )
                yield f"INSERT INTO `{table}` VALUES ({values});\n".encode()
            yield b"\n"

    yield b"SET FOREIGN_KEY_CHECKS=1;\n"
    cursor.close()
    conn.close()

@login_required
@user_passes_test(lambda u: u.is_superuser)
def upload_sql_process(request):
    if request.method == 'POST' and request.FILES.get('sql_file'):
        sql = request.FILES['sql_file'].read().decode('utf-8')

        try:
            if is_sqlite():
                _sqlite_upload(sql)
            elif is_mysql():
                _mysql_upload(sql)
            else:
                raise ValueError(f"Unsupported database engine: {get_db_engine()}")
            messages.success(request, "SQL dump applied successfully.")
        except Exception as e:
            messages.error(request, f"Failed to apply dump: {str(e)}")

    return render(request, 'econ/upload_sql.html', {'date': datetime.now()})


def _sqlite_upload(sql):
    db_path = settings.DATABASES['default']['NAME']
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF;")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        for (table,) in cursor.fetchall():
            cursor.execute(f'DROP TABLE IF EXISTS "{table}"')
        conn.commit()
        conn.executescript(sql)
    finally:
        cursor.close()
        conn.close()


def _mysql_upload(sql):
    if pymysql is None:
        raise ImportError("PyMySQL is required for MySQL database support.")

    db = settings.DATABASES['default']
    conn = pymysql.connect(
        host=db['HOST'],
        port=int(db.get('PORT', 3306)),
        user=db['USER'],
        password=db['PASSWORD'],
        database=db['NAME'],
    )
    try:
        cursor = conn.cursor()
        cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
        cursor.execute("SHOW TABLES")
        for (table,) in cursor.fetchall():
            cursor.execute(f"DROP TABLE IF EXISTS `{table}`")

        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
        for statement in statements:
            cursor.execute(statement)

        cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
########################################################################################################################

def superuser_required(user):
    return user.is_superuser

def generate_filename(title):
    clean = slugify(title)
    return f"{clean}.jpg"


def _validate_url(value, field_name, label, errors):
    if not value:
        return
    validator = URLValidator()
    try:
        validator(value)
    except ValidationError:
        errors[field_name] = f"Enter a valid {label} URL."


def _is_number_only(value):
    clean_value = value.strip()
    return bool(re.search(r"\d", clean_value) and re.fullmatch(r"[\d\s.,+-]+", clean_value))


def _validate_text_not_number(value, field_name, label, errors):
    if value and field_name not in errors and _is_number_only(value):
        errors[field_name] = f"{label} cannot be only numbers."


def _blank_line_blocks(value):
    return [
        block.strip()
        for block in re.split(r"\n\s*\n", value)
        if block.strip()
    ]


def _validate_keywords_format(value, field_name, errors):
    if not value or field_name in errors:
        return
    if "," not in value:
        errors[field_name] = "Use comma-separated keywords, for example: rail, mobility, economy."
        return

    keywords = [keyword.strip() for keyword in value.split(",")]
    if any(not keyword for keyword in keywords):
        errors[field_name] = "Remove empty keywords and separate each keyword with one comma."
        return
    if any(_is_number_only(keyword) for keyword in keywords):
        errors[field_name] = "Keywords cannot be only numbers."


def _validate_blank_line_format(value, field_name, label, errors):
    if not value or field_name in errors:
        return []
    if "\n" in value and not re.search(r"\n\s*\n", value):
        errors[field_name] = f"Separate each {label.lower()} with a blank line."
        return []
    blocks = _blank_line_blocks(value)
    if any(_is_number_only(block) for block in blocks):
        errors[field_name] = f"{label} cannot be only numbers."
    return blocks


def _validate_gallery_urls(value, errors):
    blocks = _validate_blank_line_format(value, "gallery", "Gallery URL", errors)
    if not blocks or "gallery" in errors:
        return
    for url in blocks:
        _validate_url(url, "gallery", "gallery image", errors)
        if "gallery" in errors:
            return


def _validate_sources_format(value, errors):
    blocks = _validate_blank_line_format(value, "sources", "Source", errors)
    if not blocks or "sources" in errors:
        return
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) != 2:
            errors["sources"] = "Use two lines per source: label on line 1, URL on line 2. Separate sources with a blank line."
            return
        if _is_number_only(lines[0]):
            errors["sources"] = "Source labels cannot be only numbers."
            return
        _validate_url(lines[1], "sources", "source", errors)
        if "sources" in errors:
            return


def _parse_optional_content_date(value, has_url, errors):
    if has_url and not value:
        errors["date"] = "Date is required when this content comes from a URL."
        return None
    if not value:
        return timezone.localdate()
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors["date"] = "Enter a valid date."
        return None


def _content_created_at(content_date):
    return timezone.make_aware(
        datetime.combine(content_date, time.min),
        timezone.get_current_timezone(),
    )

@login_required
@user_passes_test(superuser_required)
def add_blog(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        posted_date = request.POST.get("date", "").strip()
        excerpt = request.POST.get("excerpt", "").strip()
        featured_image_filename = generate_filename(title)
        featured_image_url = request.POST.get("featured_image_url", "").strip()

        body_paragraphs = request.POST.get("body_paragraphs", "").strip()
        keywords = request.POST.get("keywords", "").strip()
        highlights = request.POST.get("highlights", "").strip()
        gallery = request.POST.get("gallery", "").strip()
        sources = request.POST.get("sources", "").strip()
        has_source_url = bool(sources)

        order = (
            BlogPost.objects.order_by("-order")
            .values_list("order", flat=True)
            .first() or 0
        ) + 1

        errors = {}

        if not title:
            errors["title"] = "Title is required."
        elif BlogPost.objects.filter(title__iexact=title).exists():
            errors["title"] = "A blog with this title already exists."
        _validate_text_not_number(title, "title", "Title", errors)

        if not excerpt:
            errors["excerpt"] = "Excerpt is required."
        _validate_text_not_number(excerpt, "excerpt", "Excerpt", errors)

        if not body_paragraphs:
            errors["body_paragraphs"] = "Body paragraphs are required."
        _validate_text_not_number(body_paragraphs, "body_paragraphs", "Body paragraphs", errors)

        if not keywords:
            errors["keywords"] = "Keywords are required."
        _validate_keywords_format(keywords, "keywords", errors)

        if not highlights:
            errors["highlights"] = "Highlights are required."
        _validate_blank_line_format(highlights, "highlights", "Highlight", errors)

        if not gallery:
            errors["gallery"] = "Gallery URLs are required."
        _validate_gallery_urls(gallery, errors)

        if sources:
            _validate_sources_format(sources, errors)

        parsed_date = _parse_optional_content_date(posted_date, has_source_url, errors)

        if not featured_image_url:
            errors["featured_image_url"] = "Featured image URL is required."
        _validate_url(featured_image_url, "featured_image_url", "featured image", errors)

        if errors:
            return render(
                request,
                "econ/add_blog.html",
                {
                    "date": datetime.now(),
                    "date_value": posted_date or timezone.localdate().isoformat(),
                    "errors": errors,
                    "values": request.POST,
                },
                status=400
            )

        slug = slugify(title)

        original_slug = slug
        counter = 1

        while BlogPost.objects.filter(slug=slug).exists():
            slug = f"{original_slug}-{counter}"
            counter += 1

        body_list = [
            p.strip()
            for p in re.split(r"\n\s*\n", body_paragraphs)
            if p.strip()
        ]

        keyword_list = [
            k.strip()
            for k in keywords.split(",")
            if k.strip()
        ]

        highlight_list = [
            h.strip()
            for h in re.split(r"\n\s*\n", highlights)
            if h.strip()
        ]

        gallery_list = [
            {
                "src": g.strip(),
                "alt": f"Gallery image {index + 1}",
                "caption": f"Gallery image {index + 1}",
            }
            for index, g in enumerate(
                re.split(r"\n\s*\n", gallery)
            )
            if g.strip()
        ]

        source_list = []

        source_blocks = [
            block.strip()
            for block in re.split(r"\n\s*\n", sources)
            if block.strip()
        ]

        for block in source_blocks:
            lines = [
                line.strip()
                for line in block.splitlines()
                if line.strip()
            ]

            if len(lines) >= 2:
                source_list.append({
                    "label": lines[0],
                    "url": lines[1],
                })

        raw_text_parts = [
            f"BLOG: {title}",
            f"Picture: {featured_image_filename}\n{featured_image_url}",
        ]

        raw_text_parts.extend(body_list)

        if highlight_list:
            raw_text_parts.append(
                "Highlights:\n" + "\n".join(
                    f"- {highlight}"
                    for highlight in highlight_list
                )
            )

        if gallery_list:
            raw_text_parts.append(
                "Gallery:\n" + "\n".join(
                    image["src"]
                    for image in gallery_list
                )
            )

        if source_list:
            raw_text_parts.append(
                "Sources:\n" + "\n".join(
                    f"{source['label']}\n{source['url']}"
                    for source in source_list
                )
            )

        raw_text = "\n\n".join(raw_text_parts)

        blog = BlogPost.objects.create(
            title=title,
            slug=slug,
            excerpt=excerpt,
            featured_image_filename=featured_image_filename,
            featured_image_url=featured_image_url,
            raw_text=raw_text,
            body_paragraphs=body_list,
            keywords=keyword_list,
            highlights=highlight_list,
            gallery=gallery_list,
            sources=source_list,
            order=order,
        )
        BlogPost.objects.filter(pk=blog.pk).update(created_at=_content_created_at(parsed_date))

        messages.success(request, f"Blog '{blog.title}' created successfully.")
        return redirect("blog")

    return render(
        request,
        "econ/add_blog.html",
        {
            "date": datetime.now(),
            "date_value": timezone.localdate().isoformat(),
        }
    )


@login_required
@user_passes_test(superuser_required)
def add_journal(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        posted_date = request.POST.get("date", "").strip()
        journal_url = request.POST.get("journal_url", "").strip()
        authors = request.POST.get("authors", "").strip()
        publication_year = request.POST.get("publication_year", "").strip()
        journal_name = request.POST.get("journal_name", "").strip()
        citation_info = request.POST.get("citation_info", "").strip()
        snippet = request.POST.get("snippet", "").strip()
        keywords = request.POST.get("keywords", "").strip()
        order = (
            JournalEntry.objects.order_by("-order")
            .values_list("order", flat=True)
            .first() or 0
        ) + 1

        errors = {}

        if not title:
            errors["title"] = "Title is required."
        elif JournalEntry.objects.filter(title__iexact=title).exists():
            errors["title"] = "A journal with this title already exists."
        _validate_text_not_number(title, "title", "Title", errors)

        if journal_url:
            _validate_url(journal_url, "journal_url", "journal", errors)

        parsed_date = _parse_optional_content_date(posted_date, bool(journal_url), errors)

        if not authors:
            errors["authors"] = "Authors are required."
        _validate_text_not_number(authors, "authors", "Authors", errors)

        if journal_url and not publication_year:
            errors["publication_year"] = "Publication year is required."
        elif not publication_year:
            publication_year = str(timezone.localdate().year)
        elif not publication_year.isdigit():
            errors["publication_year"] = "Publication year must be a number."

        if not journal_name:
            errors["journal_name"] = "Journal name is required."
        _validate_text_not_number(journal_name, "journal_name", "Journal name", errors)

        if not citation_info:
            errors["citation_info"] = "Citation info is required."
        _validate_text_not_number(citation_info, "citation_info", "Citation info", errors)

        if not snippet:
            errors["snippet"] = "Snippet is required."
        _validate_text_not_number(snippet, "snippet", "Snippet", errors)

        if not keywords:
            errors["keywords"] = "Keywords are required."
        _validate_keywords_format(keywords, "keywords", errors)

        if errors:
            return render(
                request,
                "econ/add_journal.html",
                {
                    "date": datetime.now(),
                    "date_value": posted_date or timezone.localdate().isoformat(),
                    "errors": errors,
                    "values": request.POST,
                },
                status=400
            )

        journal = JournalEntry.objects.create(
            title=title,
            journal_url=journal_url,
            authors=authors,
            publication_year=int(publication_year),
            journal_name=journal_name,
            citation_info=citation_info,
            snippet=snippet,
            keywords=[
                k.strip() for k in keywords.split(",") if k.strip()
            ],
           order=order,
        )
        JournalEntry.objects.filter(pk=journal.pk).update(created_at=_content_created_at(parsed_date))

        messages.success(request, f"Journal '{journal.title}' added successfully.")
        return redirect("journal")

    return render(
        request,
        "econ/add_journal.html",
        {
            "date": datetime.now(),
            "date_value": timezone.localdate().isoformat(),
        }
    )


@login_required
@user_passes_test(superuser_required)
def add_image(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "").strip()
        date = request.POST.get("date", "").strip()
        image_url = request.POST.get("image_url", "").strip()

        order = (
            MediaGalleryEntry.objects.order_by("-order")
            .values_list("order", flat=True)
            .first() or 0
        ) + 1
        errors = {}

        if not title:
            errors["title"] = "Title is required."
        elif MediaGalleryEntry.objects.filter(title__iexact=title).exists():
            errors["title"] = "A gallery image with this title already exists."
        _validate_text_not_number(title, "title", "Title", errors)

        if not description:
            errors["description"] = "Description is required."
        _validate_text_not_number(description, "description", "Description", errors)

        _validate_url(image_url, "image_url", "image", errors)
        parsed_date = _parse_optional_content_date(date, bool(image_url), errors)

        if errors:
            return render(
                request,
                "econ/add_media.html",
                {
                    "date": datetime.now(),
                    "errors": errors,
                    "values": request.POST,
                },
                status=400
            )

        media = MediaGalleryEntry.objects.create(
            title=title,
            description=description,
            media_type="image",
            date=parsed_date,
            image_url=image_url,
            order=order,
        )

        messages.success(request, f"Image '{media.title}' added successfully.")
        return redirect("gallery")

    return render(
        request,
        "econ/add_media.html",
        {
            "date": datetime.now(),
        }
    )

@login_required
@user_passes_test(superuser_required)
def add_video(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        channel_name = request.POST.get("channel_name", "").strip()
        description = request.POST.get("description", "").strip()
        video_url = request.POST.get("video_url", "").strip()
        date = request.POST.get("date", "").strip()

        errors = {}

        if not title:
            errors["title"] = "Title is required."
        elif VlogEntry.objects.filter(title__iexact=title).exists():
            errors["title"] = "A video with this title already exists."
        _validate_text_not_number(title, "title", "Title", errors)

        if not channel_name:
            errors["channel_name"] = "Channel is required."
        _validate_text_not_number(channel_name, "channel_name", "Channel", errors)

        if not description:
            errors["description"] = "Description is required."
        _validate_text_not_number(description, "description", "Description", errors)

        if not video_url:
            errors["video_url"] = "Video URL is required so the video can be embedded."
        _validate_url(video_url, "video_url", "video", errors)
        if not date:
            errors["date"] = "Date is required for videos."
            parsed_date = None
        else:
            parsed_date = _parse_optional_content_date(date, True, errors)

        if errors:
            return render(
                request,
                "econ/add_vlog.html",
                {
                    "date": datetime.now(),
                    "errors": errors,
                    "values": request.POST,
                },
                status=400
            )

        filename = f"{slugify(title)}.mp4"

        order = (
            VlogEntry.objects.order_by("-order")
            .values_list("order", flat=True)
            .first() or 0
        ) + 1

        new_vlog = VlogEntry.objects.create(
            title=title,
            filename=filename,
            channel_name=channel_name,
            description=description,
            video_url=video_url,
            date=parsed_date,
            order=order,
        )

        messages.success(request, f"Video '{new_vlog.title}' added successfully.")
        return redirect("vlog")

    return render(
        request,
        "econ/add_vlog.html",
        {
            "date": datetime.now(),
        }
    )


def add_media(request):
    return redirect("add_image")


def add_vlog(request):
    return redirect("add_video")
