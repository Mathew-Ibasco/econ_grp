from datetime import datetime, date, time, timedelta
from types import SimpleNamespace
from urllib.parse import urlparse

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
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

from .audit import log_action
from .forms import ForumReplyForm, ForumThreadCreateForm
from .models import AuditLog, BlogPost, Bookmark, ForumReply, ForumReplyImage, ForumThread, ForumThreadImage, ItemNote, ItemQuizAttempt, ItemQuizProgress, ItemQuizQuestion, JournalEntry, MediaGalleryEntry, QuizAttempt, StudyItemProgress, Topic, TopicNote, User, vlog as VlogEntry


DEFAULT_RECOMMENDATION_IMAGE = "https://cdn.britannica.com/16/123116-050-5D3AC998/Light-rail-Changchun-transit-Jilin-China.jpg"
JOURNAL_RECOMMENDATION_IMAGE = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/83/Manila_LRT-MRT_map.png/1280px-Manila_LRT-MRT_map.png"
VIDEO_RECOMMENDATION_IMAGE = "https://media.philstar.com/images/articles/met2-mrt-3_2018-04-02_20-32-49.jpg"


def _paginate(request, queryset_or_list, per_page):
    paginator = Paginator(queryset_or_list, per_page)
    page_number = request.GET.get("page") or 1
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    return page_obj


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


def _truncate_quiz_text(value, fallback, limit=180):
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        text = fallback
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def _first_sentence(value, fallback):
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return fallback
    sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
    return _truncate_quiz_text(sentence, fallback)


def _quiz_ready_date(item):
    created_at = getattr(item, "created_at", None)
    if not created_at:
        return timezone.now()
    if timezone.is_naive(created_at):
        created_at = timezone.make_aware(created_at, timezone.get_current_timezone())
    return created_at + timedelta(days=1)


def _item_quiz_is_ready(item):
    return timezone.now() >= _quiz_ready_date(item)


def _add_generated_item_question(item_type, item_id, round_number, order, question, correct, wrong_one, wrong_two):
    correct_slots = ("A", "B", "C")
    correct_option = correct_slots[(round_number + order - 2) % len(correct_slots)]
    options = {
        "A": _truncate_quiz_text(wrong_one, "A less relevant answer."),
        "B": _truncate_quiz_text(wrong_two, "Another less relevant answer."),
        "C": _truncate_quiz_text(wrong_one, "A less relevant answer."),
    }
    options[correct_option] = _truncate_quiz_text(correct, "The content's main idea.")
    remaining = [slot for slot in correct_slots if slot != correct_option]
    options[remaining[0]] = _truncate_quiz_text(wrong_one, "A less relevant answer.")
    options[remaining[1]] = _truncate_quiz_text(wrong_two, "Another less relevant answer.")

    ItemQuizQuestion.objects.create(
        item_type=item_type,
        item_id=item_id,
        round_number=round_number,
        order=order,
        question=_truncate_quiz_text(question, "What does this content explain?", limit=280),
        option_a=options["A"],
        option_b=options["B"],
        option_c=options["C"],
        correct_option=correct_option,
    )


def _generate_blog_quiz_questions(blog_post):
    topic = blog_post.topics.order_by("order", "id").first()
    topic_title = topic.title if topic else "Rail transport and urban mobility"
    keyword = (blog_post.keywords or ["rail transport"])[0]
    highlight = (blog_post.highlights or blog_post.body_paragraphs or [blog_post.excerpt])[0]
    body_point = _first_sentence(" ".join(blog_post.body_paragraphs or []), blog_post.excerpt)
    source_label = "Original blog" if not blog_post.sources else _truncate_quiz_text(blog_post.sources[0].get("label"), "The listed source")

    question_rows = [
        (1, 1, "What is this blog mainly about?", blog_post.title, "Unrelated account security settings.", "Only private car parking."),
        (1, 2, "Which topic is connected to this blog?", topic_title, "Food service management.", "Random image formatting."),
        (1, 3, "Which idea appears in the blog excerpt or body?", body_point, "The post avoids transport issues.", "The post is only about user passwords."),
        (2, 1, "Which keyword helps classify this blog?", keyword, "dessert", "login"),
        (2, 2, "Which highlight belongs to this blog?", highlight, "Remove all public transport.", "Ignore city mobility."),
        (2, 3, "Which source context fits this blog?", source_label, "A private chat message.", "A game score table."),
        (3, 1, "What should readers connect this blog with?", topic_title, "Only website color choices.", "Only unrelated entertainment."),
        (3, 2, "Which statement best matches the blog content?", body_point, "Rail has no effect on mobility.", "The blog is only a photo caption."),
        (3, 3, "What is the strongest title-based takeaway?", blog_post.title, "The topic is unrelated to rail.", "The content is only about logging out."),
    ]
    for row in question_rows:
        _add_generated_item_question("blog", blog_post.id, *row)


def _generate_journal_quiz_questions(journal):
    topic = journal.topics.order_by("order", "id").first()
    topic_title = topic.title if topic else "Rail transport and urban mobility"
    keyword = (journal.keywords or ["rail transport"])[0]
    snippet_point = _first_sentence(journal.snippet, journal.title)
    year_text = "n.a." if "n.a." in (journal.citation_info or "").lower() else str(journal.publication_year)

    question_rows = [
        (1, 1, "What is this journal entry mainly about?", journal.title, "A password reset process.", "A restaurant menu."),
        (1, 2, "Who is listed as the author or author group?", journal.authors, "An anonymous site visitor.", "A browser extension."),
        (1, 3, "Which journal or source name is connected to this entry?", journal.journal_name, "A shopping cart.", "A profile picture."),
        (2, 1, "Which topic is connected to this journal entry?", topic_title, "Video game design.", "Unrelated account settings."),
        (2, 2, "Which idea appears in the journal snippet?", snippet_point, "The entry avoids transport research.", "The entry is only a login record."),
        (2, 3, "Which keyword helps classify this journal?", keyword, "dessert", "logout"),
        (3, 1, "What publication date value is used for this journal?", year_text, "A random phone number.", "No visible citation detail."),
        (3, 2, "Which statement best matches this journal entry?", snippet_point, "It is unrelated to the journal title.", "It only stores image thumbnails."),
        (3, 3, "What should readers connect this journal with?", topic_title, "Only button styling.", "Only upload errors."),
    ]
    for row in question_rows:
        _add_generated_item_question("journal", journal.id, *row)


def _ensure_item_quiz_questions(item_type, item):
    if item_type not in {"blog", "journal"} or item is None:
        return False
    item_id = item.id
    if ItemQuizQuestion.objects.filter(item_type=item_type, item_id=item_id).exists():
        return True
    if not _item_quiz_is_ready(item):
        return False
    if item_type == "blog":
        _generate_blog_quiz_questions(item)
    else:
        _generate_journal_quiz_questions(item)
    return True


def _item_learning_context(user, item_type, item_id, item=None):
    if not user.is_authenticated:
        return None
    quiz_ready = _ensure_item_quiz_questions(item_type, item)
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
        "quiz_ready": quiz_ready,
        "quiz_ready_at": _quiz_ready_date(item) if item is not None else None,
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
            log_action(
                request,
                "auth",
                "Login",
                {"Account": user.username, "Result": "Success"},
                user=user,
            )
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
    if request.user.is_authenticated:
        log_action(
            request,
            "auth",
            "Logout",
            {"Account": request.user.username, "Result": "Success"},
        )
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
            log_action(
                request,
                "update",
                "Edit Profile",
                {
                    "Changed username": username,
                    "Changed email": email,
                    "Password changed": "Yes" if wants_password_change else "No",
                },
            )
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


@login_required
@user_passes_test(lambda u: u.is_superuser)
def audit_logs(request):
    logs_queryset = AuditLog.objects.select_related("user").order_by("-created_at", "-id")
    audit_page = _paginate(request, logs_queryset, 25)
    logs = list(audit_page.object_list)
    action_counts = {}
    for action in AuditLog.objects.values_list("action", flat=True):
        action_counts[action] = action_counts.get(action, 0) + 1
    for log in logs:
        detail_rows = []
        for key, value in (log.details or {}).items():
            if isinstance(value, (list, tuple)):
                value = ", ".join(str(item) for item in value)
            elif isinstance(value, dict):
                value = "; ".join(f"{nested_key}: {nested_value}" for nested_key, nested_value in value.items())
            detail_rows.append({"label": key, "value": value})
        log.detail_rows = detail_rows

    return render(
        request,
        "econ/audit_logs.html",
        {
            "date": datetime.now(),
            "audit_logs": logs,
            "page_obj": audit_page,
            "pagination_label": "audit logs",
            "audit_total": AuditLog.objects.count(),
            "shown_total": len(logs),
            "action_counts": action_counts,
        },
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
        log_action(
            request,
            "auth",
            "Create Account",
            {"Account": user.username, "Email": user.email, "Result": "Success"},
            user=user,
        )
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
        log_action(request, "toggle", "Remove Saved Topic", {"Topic": topic.title})
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
        log_action(request, "toggle", "Save Topic", {"Topic": topic.title})

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
        log_action(
            request,
            "create",
            "Add Forum Thread",
            {
                "Thread": thread.title,
                "Tags": ", ".join(tag.title for tag in selected_tags),
                "Pictures": len(uploaded_images),
            },
        )
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
        log_action(
            request,
            "create",
            "Add Forum Reply",
            {
                "Thread": thread.title,
                "Reply": reply.body[:120],
                "Pictures": len(uploaded_images),
            },
        )
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
    log_action(request, "delete", "Delete Forum Thread", {"Thread": title})
    return redirect("forum")


@login_required
def forum_delete_reply(request, reply_id):
    if request.method != "POST":
        return redirect("forum")

    reply = get_object_or_404(ForumReply.objects.select_related("thread"), pk=reply_id)
    if not _can_manage_forum_reply(request.user, reply):
        raise PermissionDenied
    thread = reply.thread
    reply_body = reply.body
    reply.delete()
    _refresh_forum_thread_activity(thread)
    messages.success(request, "Deleted reply.")
    log_action(request, "delete", "Delete Forum Reply", {"Thread": thread.title, "Reply": reply_body[:120]})
    return redirect(f"{reverse('forum_thread', args=[thread.id])}#replies")

def blog(request):
    unlinked_blog_ids = list(
        BlogPost.objects.annotate(topic_count=Count("topics"))
        .filter(topic_count=0)
        .values_list("id", flat=True)
    )
    if unlinked_blog_ids:
        fallback_topic = Topic.objects.order_by("order", "id").first()
        if fallback_topic is not None:
            for blog_post in BlogPost.objects.filter(id__in=unlinked_blog_ids):
                blog_post.topics.add(fallback_topic)

    all_blog_posts = list(BlogPost.objects.prefetch_related("topics").order_by("order", "id"))
    blog_page = _paginate(request, all_blog_posts, 4)
    blog_posts = list(blog_page.object_list)
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
            'blog_count': len(all_blog_posts),
            'page_obj': blog_page,
            'pagination_label': 'blogs',
        }
    )


def _blog_edit_values(blog_post):
    return {
        "title": blog_post.title,
        "date": _content_date_value(blog_post.created_at),
        "excerpt": blog_post.excerpt,
        "featured_image_url": blog_post.featured_image_url,
        "body_paragraphs": "\n\n".join(blog_post.body_paragraphs or []),
        "keywords": ", ".join(blog_post.keywords or []),
        "highlights": "\n\n".join(blog_post.highlights or []),
        "gallery": "\n\n".join((item.get("src") or "") for item in (blog_post.gallery or [])),
        "sources": "\n\n".join(
            (
                source.get("label", "")
                if not source.get("url") or source.get("url") in source.get("label", "")
                else f"{source.get('label', '')} {source.get('url', '')}"
            ).strip()
            for source in (blog_post.sources or [])
        ),
    }


def _blog_detail_context(request, blog_post, extra=None):
    learning = _item_learning_context(request.user, "blog", blog_post.id, blog_post)
    learning = _attach_quiz_result(
        learning,
        request.user,
        "blog",
        blog_post.id,
        request.GET.get("quiz_attempt"),
    )
    context = {
        "date": datetime.now(),
        "blog_post": blog_post,
        "blog_edit_values": _blog_edit_values(blog_post),
        "learning": learning,
        "learning_item_type": "blog",
        "learning_item_id": blog_post.id,
    }
    if extra:
        context.update(extra)
    return context


def blog_detail(request, slug):
    blog_post = get_object_or_404(BlogPost, slug=slug)
    return render(request, "econ/blog_detail.html", _blog_detail_context(request, blog_post))


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_blog(request, slug):
    blog_post = get_object_or_404(BlogPost, slug=slug)
    if request.method != "POST":
        return redirect("blog_detail", slug=blog_post.slug)

    original_values = _blog_edit_values(blog_post)
    values = {key: request.POST.get(key, "").strip() for key in original_values}
    errors = {}

    _validate_edit_text(values["title"], original_values, "title", "Title", errors)
    if values["title"] and BlogPost.objects.filter(title__iexact=values["title"]).exclude(pk=blog_post.pk).exists():
        errors["title"] = "A blog with this title already exists."

    _validate_edit_text(values["excerpt"], original_values, "excerpt", "Excerpt", errors)
    _validate_edit_text(values["body_paragraphs"], original_values, "body_paragraphs", "Body paragraphs", errors)
    _validate_edit_text(values["highlights"], original_values, "highlights", "Highlights", errors)
    _validate_edit_text(values["keywords"], original_values, "keywords", "Keywords", errors)
    _validate_edit_text(values["gallery"], original_values, "gallery", "Gallery URLs", errors)
    _validate_edit_text(values["sources"], original_values, "sources", "Sources", errors)

    _validate_edit_url(values["featured_image_url"], original_values, "featured_image_url", "Featured image URL", errors)
    _validate_keywords_format(values["keywords"], "keywords", errors)
    _validate_gallery_urls(values["gallery"], errors)
    _validate_sources_format(values["sources"], errors)
    parsed_date = _parse_edit_date(values["date"], original_values, errors)

    body_list = [p.strip() for p in re.split(r"\n\s*\n", values["body_paragraphs"]) if p.strip()]
    keyword_list = [k.strip() for k in values["keywords"].split(",") if k.strip()]
    highlight_list = [h.strip() for h in re.split(r"\n\s*\n", values["highlights"]) if h.strip()]
    gallery_urls = [g.strip() for g in re.split(r"\n\s*\n", values["gallery"]) if g.strip()]
    gallery_list = [
        {"src": url, "alt": f"Gallery image {index + 1}", "caption": f"Gallery image {index + 1}"}
        for index, url in enumerate(gallery_urls)
    ]
    source_list = _parse_blog_sources(values["sources"], values["title"], parsed_date)

    comparable_current = {
        "title": blog_post.title,
        "date": _content_date_value(blog_post.created_at),
        "excerpt": blog_post.excerpt,
        "featured_image_url": blog_post.featured_image_url,
        "body_paragraphs": blog_post.body_paragraphs or [],
        "keywords": blog_post.keywords or [],
        "highlights": blog_post.highlights or [],
        "gallery": blog_post.gallery or [],
        "sources": _parse_blog_sources(_blog_edit_values(blog_post)["sources"], values["title"], parsed_date),
    }
    comparable_new = {
        "title": values["title"],
        "date": values["date"],
        "excerpt": values["excerpt"],
        "featured_image_url": values["featured_image_url"],
        "body_paragraphs": body_list,
        "keywords": keyword_list,
        "highlights": highlight_list,
        "gallery": gallery_list,
        "sources": source_list,
    }
    if not errors and comparable_current == comparable_new:
        errors["global"] = "Change at least one field before saving."

    if errors:
        return render(
            request,
            "econ/blog_detail.html",
            _blog_detail_context(
                request,
                blog_post,
                {"blog_edit_values": values, "blog_edit_errors": errors, "blog_edit_open": True},
            ),
            status=400,
        )

    blog_post.title = values["title"]
    blog_post.slug = slugify(values["title"])
    original_slug = blog_post.slug
    counter = 1
    while BlogPost.objects.filter(slug=blog_post.slug).exclude(pk=blog_post.pk).exists():
        blog_post.slug = f"{original_slug}-{counter}"
        counter += 1
    blog_post.excerpt = values["excerpt"]
    blog_post.featured_image_filename = generate_filename(values["title"])
    blog_post.featured_image_url = values["featured_image_url"]
    blog_post.body_paragraphs = body_list
    blog_post.keywords = keyword_list
    blog_post.highlights = highlight_list
    blog_post.gallery = gallery_list
    blog_post.sources = source_list
    blog_post.raw_text = "\n\n".join([f"BLOG: {blog_post.title}", values["excerpt"], *body_list])
    blog_post.save()
    if parsed_date is not None:
        BlogPost.objects.filter(pk=blog_post.pk).update(created_at=_content_created_at(parsed_date))
    messages.success(request, f"Updated blog: {blog_post.title}")
    log_action(request, "update", "Edit Blog", {"Blog": blog_post.title, "Slug": blog_post.slug})
    return redirect("blog_detail", slug=blog_post.slug)


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
    log_action(request, "delete", "Delete Blog", {"Blog": title, "Item ID": item_id})
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
        log_action(request, "toggle", "Mark Study Item Done", {"Item type": item_type, "Item ID": item_id, "Topic": topic.title})
    else:
        progress.delete()
        messages.success(request, "Marked as not done.")
        log_action(request, "toggle", "Unmark Study Item Done", {"Item type": item_type, "Item ID": item_id, "Topic": topic.title})

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
    log_action(request, "create", "Add Study Note", {"Item type": item_type, "Item ID": item_id, "Note": note_text})
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
    log_action(
        request,
        "submit",
        "Submit Quiz",
        {"Item type": item_type, "Item ID": item_id, "Score": f"{score}/{len(questions)}", "Round": current_round},
    )
    next_url = request.POST.get("next") or reverse("index")
    separator = "&" if "?" in next_url else "?"
    return redirect(f"{next_url}{separator}quiz_attempt={attempt.id}")

def journal(request):
    all_journal_entries = list(JournalEntry.objects.prefetch_related("topics").order_by("order", "id"))
    journal_page = _paginate(request, all_journal_entries, 6)
    journal_entries = list(journal_page.object_list)
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
            'journal_count': len(all_journal_entries),
            'page_obj': journal_page,
            'pagination_label': 'journals',
        }
    )


def _journal_edit_values(journal):
    return {
        "title": journal.title,
        "date": _content_date_value(journal.created_at),
        "journal_url": journal.journal_url,
        "authors": journal.authors,
        "publication_year": str(journal.publication_year),
        "journal_name": journal.journal_name,
        "citation_info": journal.citation_info,
        "snippet": journal.snippet,
        "keywords": ", ".join(journal.keywords or []),
    }


def _journal_detail_context(request, journal, extra=None):
    learning = _item_learning_context(request.user, "journal", journal.id, journal)
    learning = _attach_quiz_result(
        learning,
        request.user,
        "journal",
        journal.id,
        request.GET.get("quiz_attempt"),
    )
    context = {
        "date": datetime.now(),
        "journal": journal,
        "journal_edit_values": _journal_edit_values(journal),
        "learning": learning,
        "learning_item_type": "journal",
        "learning_item_id": journal.id,
    }
    if extra:
        context.update(extra)
    return context


def journal_detail(request, journal_id):
    journal = get_object_or_404(
        JournalEntry.objects.prefetch_related("topics"),
        pk=journal_id,
    )
    return render(request, "econ/journal_detail.html", _journal_detail_context(request, journal))


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_journal(request, journal_id):
    journal = get_object_or_404(JournalEntry, pk=journal_id)
    if request.method != "POST":
        return redirect("journal_detail", journal_id=journal.id)

    original_values = _journal_edit_values(journal)
    values = {key: request.POST.get(key, "").strip() for key in original_values}
    errors = {}
    for field, label in (
        ("title", "Title"),
        ("journal_url", "Journal URL"),
        ("authors", "Authors"),
        ("journal_name", "Journal name"),
        ("citation_info", "Citation info"),
        ("snippet", "Snippet"),
        ("keywords", "Keywords"),
    ):
        if field == "journal_url":
            _validate_edit_url(values[field], original_values, field, label, errors)
        else:
            _validate_edit_text(values[field], original_values, field, label, errors)

    if values["title"] and JournalEntry.objects.filter(title__iexact=values["title"]).exclude(pk=journal.pk).exists():
        errors["title"] = "A journal with this title already exists."
    if original_values["publication_year"] and not values["publication_year"]:
        errors["publication_year"] = "Publication year cannot be left blank."
    elif values["publication_year"] and not values["publication_year"].isdigit():
        errors["publication_year"] = "Publication year must be a number."
    _validate_keywords_format(values["keywords"], "keywords", errors)
    parsed_date = _parse_edit_date(values["date"], original_values, errors)
    keyword_list = [keyword.strip() for keyword in values["keywords"].split(",") if keyword.strip()]

    comparable_current = _journal_edit_values(journal)
    comparable_new = dict(values)
    if not errors and comparable_current == comparable_new:
        errors["global"] = "Change at least one field before saving."

    if errors:
        return render(
            request,
            "econ/journal_detail.html",
            _journal_detail_context(
                request,
                journal,
                {"journal_edit_values": values, "journal_edit_errors": errors, "journal_edit_open": True},
            ),
            status=400,
        )

    journal.title = values["title"]
    journal.journal_url = values["journal_url"]
    journal.authors = values["authors"]
    journal.publication_year = int(values["publication_year"])
    journal.journal_name = values["journal_name"]
    journal.citation_info = values["citation_info"]
    journal.snippet = values["snippet"]
    journal.keywords = keyword_list
    journal.save()
    if parsed_date is not None:
        JournalEntry.objects.filter(pk=journal.pk).update(created_at=_content_created_at(parsed_date))
    messages.success(request, f"Updated journal: {journal.title}")
    log_action(request, "update", "Edit Journal", {"Journal": journal.title, "Item ID": journal.id})
    return redirect("journal_detail", journal_id=journal.id)


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
    log_action(request, "delete", "Delete Journal", {"Journal": title, "Item ID": item_id})
    return redirect("journal")


def vlog(request):
    all_vlog_entries = list(
        VlogEntry.objects.prefetch_related("topics").order_by("order", "vlogID")
    )

    vlog_page = _paginate(request, all_vlog_entries, 6)
    vlog_entries = list(vlog_page.object_list)

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
            'vlog_count': len(all_vlog_entries),
            'page_obj': vlog_page,
            'pagination_label': 'media',
        }
    )

def vlog_detail(request, vlog_id):
    video = get_object_or_404(VlogEntry.objects.prefetch_related("topics"), pk=vlog_id)
    video.embed_url = _youtube_embed_url(video.video_url)
    video.preview_url = video.thumbnail_url or _youtube_thumbnail_url(video.video_url)
    return render(request, "econ/vlog_detail.html", _video_detail_context(request, video))


def _video_edit_values(video):
    return {
        "title": video.title,
        "channel_name": video.channel_name,
        "description": video.description,
        "video_url": video.video_url,
        "thumbnail_url": video.thumbnail_url,
        "date": _content_date_value(video.date),
    }


def _video_detail_context(request, video, extra=None):
    video.embed_url = _youtube_embed_url(video.video_url)
    video.preview_url = video.thumbnail_url or _youtube_thumbnail_url(video.video_url)
    learning = _item_learning_context(request.user, "video", video.vlogID, video)
    learning = _attach_quiz_result(
        learning,
        request.user,
        "video",
        video.vlogID,
        request.GET.get("quiz_attempt"),
    )
    context = {
        "date": datetime.now(),
        "video": video,
        "video_edit_values": _video_edit_values(video),
        "learning": learning,
        "learning_item_type": "video",
        "learning_item_id": video.vlogID,
    }
    if extra:
        context.update(extra)
    return context


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_vlog(request, vlog_id):
    video = get_object_or_404(VlogEntry, pk=vlog_id)
    if request.method != "POST":
        return redirect("vlog_detail", vlog_id=video.vlogID)

    original_values = _video_edit_values(video)
    values = {key: request.POST.get(key, "").strip() for key in original_values}
    errors = {}
    for field, label in (
        ("title", "Title"),
        ("channel_name", "Channel"),
        ("description", "Description"),
    ):
        _validate_edit_text(values[field], original_values, field, label, errors)

    if values["title"] and VlogEntry.objects.filter(title__iexact=values["title"]).exclude(pk=video.pk).exists():
        errors["title"] = "A video with this title already exists."
    _validate_edit_url(values["video_url"], original_values, "video_url", "Video URL", errors)
    _validate_edit_url(values["thumbnail_url"], original_values, "thumbnail_url", "Thumbnail URL", errors)
    parsed_date = _parse_edit_date(values["date"], original_values, errors)

    comparable_current = _video_edit_values(video)
    comparable_new = dict(values)
    if not errors and comparable_current == comparable_new:
        errors["global"] = "Change at least one field before saving."

    if errors:
        return render(
            request,
            "econ/vlog_detail.html",
            _video_detail_context(
                request,
                video,
                {"video_edit_values": values, "video_edit_errors": errors, "video_edit_open": True},
            ),
            status=400,
        )

    video.title = values["title"]
    video.filename = f"{slugify(values['title'])}.mp4"
    video.channel_name = values["channel_name"]
    video.description = values["description"]
    video.video_url = values["video_url"]
    video.thumbnail_url = values["thumbnail_url"]
    video.date = parsed_date
    video.save()
    messages.success(request, f"Updated video: {video.title}")
    log_action(request, "update", "Edit Video", {"Video": video.title, "Item ID": video.vlogID})
    return redirect("vlog_detail", vlog_id=video.vlogID)


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
    log_action(request, "delete", "Delete Video", {"Video": title, "Item ID": item_id})
    return redirect("vlog")


def gallery(request):
    all_gallery_entries = list(MediaGalleryEntry.objects.order_by("order", "id"))
    gallery_page = _paginate(request, all_gallery_entries, 8)
    gallery_entries = list(gallery_page.object_list)
    for entry in gallery_entries:
        entry.edit_values = _media_edit_values(entry)
    return render(
        request,
        'econ/gallery.html',
        {
            'date': datetime.now(),
            'gallery_entries': gallery_entries,
            'gallery_count': len(all_gallery_entries),
            'page_obj': gallery_page,
            'pagination_label': 'gallery items',
        }
    )


def _gallery_item_page(media_id, per_page=8):
    ordered_ids = list(MediaGalleryEntry.objects.order_by("order", "id").values_list("id", flat=True))
    try:
        position = ordered_ids.index(media_id)
    except ValueError:
        return 1
    return (position // per_page) + 1


def _media_edit_values(media):
    return {
        "title": media.title,
        "description": media.description,
        "date": _content_date_value(media.date),
        "image_url": media.image_url,
        "video_url": media.video_url,
        "thumbnail_url": media.thumbnail_url,
    }


def _gallery_context(extra=None):
    all_gallery_entries = list(MediaGalleryEntry.objects.order_by("order", "id"))
    paginator = Paginator(all_gallery_entries, 8)
    page_number = (extra or {}).get("page_number") or 1
    try:
        gallery_page = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        gallery_page = paginator.page(1)
    gallery_entries = list(gallery_page.object_list)
    for entry in gallery_entries:
        entry.edit_values = _media_edit_values(entry)
    context = {
        "date": datetime.now(),
        "gallery_entries": gallery_entries,
        "gallery_count": len(all_gallery_entries),
        "page_obj": gallery_page,
        "pagination_label": "gallery items",
    }
    if extra:
        edit_item_id = extra.get("media_edit_item_id")
        edit_values = extra.get("media_edit_values")
        if edit_item_id and edit_values:
            for entry in gallery_entries:
                if entry.id == edit_item_id:
                    entry.edit_values = edit_values
                    break
        context.update(extra)
    return context


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_gallery_entry(request, media_id):
    media = get_object_or_404(MediaGalleryEntry, pk=media_id)
    if request.method != "POST":
        return redirect("gallery")

    original_values = _media_edit_values(media)
    values = {key: request.POST.get(key, "").strip() for key in original_values}
    errors = {}
    _validate_edit_text(values["title"], original_values, "title", "Title", errors)
    _validate_edit_text(values["description"], original_values, "description", "Description", errors)
    parsed_date = _parse_edit_date(values["date"], original_values, errors)

    if values["title"] and MediaGalleryEntry.objects.filter(title__iexact=values["title"]).exclude(pk=media.pk).exists():
        errors["title"] = "A gallery item with this title already exists."

    if media.media_type == "image":
        _validate_edit_url(values["image_url"], original_values, "image_url", "Image URL", errors)
    else:
        _validate_edit_url(values["video_url"], original_values, "video_url", "Video URL", errors)
        _validate_edit_url(values["thumbnail_url"], original_values, "thumbnail_url", "Thumbnail URL", errors)

    comparable_current = _media_edit_values(media)
    comparable_new = dict(values)
    if not errors and comparable_current == comparable_new:
        errors["global"] = "Change at least one field before saving."

    if errors:
        return render(
            request,
            "econ/gallery.html",
            _gallery_context(
                {
                    "media_edit_item_id": media.id,
                    "media_edit_values": values,
                    "media_edit_errors": errors,
                    "media_edit_open": True,
                    "page_number": request.GET.get("page") or 1,
                }
            ),
            status=400,
        )

    media.title = values["title"]
    media.description = values["description"]
    media.date = parsed_date
    if media.media_type == "image":
        media.image_url = values["image_url"]
        media.video_url = ""
        media.thumbnail_url = ""
    else:
        media.video_url = values["video_url"]
        media.thumbnail_url = values["thumbnail_url"]
        media.image_url = ""
    media.save()
    messages.success(request, f"Updated gallery item: {media.title}")
    log_action(request, "update", "Edit Gallery Item", {"Gallery item": media.title, "Item ID": media.id})
    page_number = request.GET.get("page")
    if page_number:
        return redirect(f"{reverse('gallery')}?page={page_number}")
    return redirect("gallery")


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
    log_action(request, "delete", "Delete Gallery Item", {"Gallery item": title, "Item ID": item_id})
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
            log_action(
                request,
                "system",
                "Upload SQL Dump",
                {"File": request.FILES["sql_file"].name, "Result": "Applied successfully"},
            )
        except Exception as e:
            messages.error(request, f"Failed to apply dump: {str(e)}")
            log_action(
                request,
                "system",
                "Upload SQL Dump Failed",
                {"File": request.FILES["sql_file"].name, "Error": str(e)},
            )

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


def _is_valid_url(value):
    if not value:
        return False
    validator = URLValidator()
    try:
        validator(value)
    except ValidationError:
        return False
    return True


def _is_number_only(value):
    clean_value = value.strip()
    return bool(re.search(r"\d", clean_value) and re.fullmatch(r"[\d\s.,+-]+", clean_value))


def _is_symbol_only(value):
    clean_value = value.strip()
    return bool(clean_value and not re.search(r"[A-Za-z0-9]", clean_value))


def _validate_text_not_number(value, field_name, label, errors):
    if value and field_name not in errors and _is_number_only(value):
        errors[field_name] = f"{label} cannot be only numbers."


def _validate_text_not_symbol(value, field_name, label, errors):
    if value and field_name not in errors and _is_symbol_only(value):
        errors[field_name] = f"{label} cannot be only symbols."


def _validate_required_text(value, field_name, label, errors):
    if not value:
        errors[field_name] = f"{label} is required."
        return
    _validate_text_not_number(value, field_name, label, errors)
    _validate_text_not_symbol(value, field_name, label, errors)


def _validate_edit_text(value, original_values, field_name, label, errors):
    original_value = str(original_values.get(field_name, "") or "").strip()
    if original_value and not value:
        errors[field_name] = f"{label} cannot be left blank."
        return
    if value:
        _validate_text_not_number(value, field_name, label, errors)
        _validate_text_not_symbol(value, field_name, label, errors)


def _validate_edit_url(value, original_values, field_name, label, errors):
    original_value = str(original_values.get(field_name, "") or "").strip()
    if original_value and not value:
        errors[field_name] = f"{label} cannot be left blank."
        return
    _validate_url(value, field_name, label, errors)


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


def _extract_urls(value):
    return re.findall(r"https?://[^\s<>()]+", value or "")


def _source_site_name(url):
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if not host:
        return "Source Website"
    name = host.split(":")[0].split(".")[0]
    return name.replace("-", " ").title()


def _apa_date(content_date, no_date=False):
    if no_date:
        return "n.a."
    if not content_date:
        return "n.a."
    return content_date.strftime("%Y, %B %-d") if os.name != "nt" else content_date.strftime("%Y, %B %#d")


def _apa_web_source(title, url, content_date, no_date=False):
    return f"{title}. ({_apa_date(content_date, no_date)}). {_source_site_name(url)}. {url}"


def _apa_journal_source(authors, year, title, journal_name, url="", no_date=False):
    authors_text = authors.strip().rstrip(".")
    title_text = title.strip().rstrip(".")
    journal_text = journal_name.strip().rstrip(".")
    year_text = "n.a." if no_date else (str(year).strip() or "n.a.")
    citation = f"{authors_text}. ({year_text}). {title_text}. {journal_text}."
    if url:
        citation = f"{citation} {url}"
    return citation


def _validate_sources_format(value, errors):
    if not value or "sources" in errors:
        return
    for source in _blank_line_blocks(value):
        if _is_number_only(source):
            errors["sources"] = "Sources cannot be only numbers."
            return
        if _is_symbol_only(source):
            errors["sources"] = "Sources cannot be only symbols."
            return
        for url in _extract_urls(source):
            _validate_url(url, "sources", "source", errors)
            if "sources" in errors:
                return


def _parse_blog_sources(value, blog_title, content_date, no_date=False):
    sources = []
    for source in _blank_line_blocks(value):
        urls = _extract_urls(source)
        if urls:
            for url in urls:
                title_part = source.replace(url, "").strip(" -\n\t.")
                citation_title = title_part or blog_title
                sources.append({
                    "label": _apa_web_source(citation_title, url, content_date, no_date),
                    "url": url,
                })
        else:
            sources.append({"label": source, "url": ""})
    return sources


def _parse_optional_content_date(value, has_url, errors, no_date=False):
    if no_date:
        return timezone.localdate()
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


def _content_date_value(value):
    if not value:
        return ""
    if hasattr(value, "date"):
        return timezone.localtime(value).date().isoformat()
    return value.isoformat()


def _parse_required_edit_date(value, errors):
    if not value:
        errors["date"] = "Date is required."
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors["date"] = "Enter a valid date."
        return None


def _parse_edit_date(value, original_values, errors):
    original_value = str(original_values.get("date", "") or "").strip()
    if original_value and not value:
        errors["date"] = "Date cannot be left blank."
        return None
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors["date"] = "Enter a valid date."
        return None


TOPIC_OTHER_VALUE = "__other__"


def _proper_case_topic_title(value):
    normalized = re.sub(r"\s+", " ", value.strip())
    return normalized.title()


def _topic_form_context(extra=None):
    values = (extra or {}).get("values")
    selected_topic_ids = []
    selected_topic_pairs = []
    if values is not None and hasattr(values, "getlist"):
        selected_topic_ids = [
            topic_id
            for topic_id in values.getlist("topic_choices")
            if str(topic_id).isdigit()
        ]
        if selected_topic_ids:
            selected_topic_labels = {
                str(topic.id): topic.title
                for topic in Topic.objects.filter(id__in=selected_topic_ids)
            }
            selected_topic_pairs = [
                {
                    "id": topic_id,
                    "title": selected_topic_labels.get(topic_id, "Selected topic"),
                }
                for topic_id in selected_topic_ids
                if topic_id in selected_topic_labels
            ]

    context = {
        "topic_options": Topic.objects.order_by("order", "title"),
        "topic_other_value": TOPIC_OTHER_VALUE,
        "selected_topic_ids": selected_topic_ids,
        "selected_topic_pairs": selected_topic_pairs,
    }
    if extra:
        context.update(extra)
    return context


def _validate_topic_selections(post_data, errors, create=True):
    topic_choices = []
    if hasattr(post_data, "getlist"):
        topic_choices = [
            choice.strip()
            for choice in post_data.getlist("topic_choices")
            if choice.strip()
        ]
    topic_choice = post_data.get("topic_choice", "").strip()
    topic_other = post_data.get("topic_other", "").strip()

    if topic_choice and topic_choice != TOPIC_OTHER_VALUE:
        topic_choices.append(topic_choice)

    seen_topic_choices = set()
    topic_ids = []
    for choice in topic_choices:
        if not choice.isdigit():
            errors["topics"] = "Select valid topics."
            return []
        if choice in seen_topic_choices:
            continue
        seen_topic_choices.add(choice)
        topic_ids.append(int(choice))

    selected_topics = list(Topic.objects.filter(pk__in=topic_ids))
    selected_by_id = {topic.pk: topic for topic in selected_topics}
    if len(selected_by_id) != len(topic_ids):
        errors["topics"] = "Select valid topics."
        return []

    if topic_choice == TOPIC_OTHER_VALUE:
        if not topic_other:
            errors["topic_other"] = "Topic is required."
            return []

        topic_title = _proper_case_topic_title(topic_other)
        if _is_number_only(topic_title):
            errors["topic_other"] = "Topic cannot be only numbers."
            return []
        if _is_symbol_only(topic_title):
            errors["topic_other"] = "Topic cannot be only symbols."
            return []
        if Topic.objects.filter(title__iexact=topic_title).exists():
            errors["topic_other"] = "Topic cannot match an existing topic."
            return []

        topic_key = slugify(topic_title)
        if not topic_key:
            errors["topic_other"] = "Enter a valid topic."
            return []
        if Topic.objects.filter(key__iexact=topic_key).exists():
            errors["topic_other"] = "Topic cannot match an existing topic."
            return []

        if create:
            selected_topics.append(
                Topic.objects.create(
                    key=topic_key,
                    title=topic_title,
                    summary="User-added topic.",
                    order=(Topic.objects.order_by("-order").values_list("order", flat=True).first() or 0) + 1,
                )
            )

    if not selected_topics and topic_choice != TOPIC_OTHER_VALUE:
        errors["topics"] = "At least one topic is required."

    return selected_topics

@login_required
@user_passes_test(superuser_required)
def add_blog(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        posted_date = request.POST.get("date", "").strip()
        excerpt = request.POST.get("excerpt", "").strip()
        featured_image_filename = generate_filename(title)
        featured_image_url = request.POST.get("featured_image_url", "").strip()
        no_date = request.POST.get("no_date") == "1"

        body_paragraphs = request.POST.get("body_paragraphs", "").strip()
        keywords = request.POST.get("keywords", "").strip()
        highlights = request.POST.get("highlights", "").strip()
        gallery = request.POST.get("gallery", "").strip()
        sources = request.POST.get("sources", "").strip()
        has_featured_image_url = _is_valid_url(featured_image_url)

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

        _validate_keywords_format(keywords, "keywords", errors)

        if not highlights:
            errors["highlights"] = "Highlights are required."
        _validate_blank_line_format(highlights, "highlights", "Highlight", errors)

        if not gallery:
            errors["gallery"] = "Gallery URLs are required."
        _validate_gallery_urls(gallery, errors)

        if sources:
            _validate_sources_format(sources, errors)

        parsed_date = _parse_optional_content_date(posted_date, has_featured_image_url, errors, no_date=no_date)

        _validate_url(featured_image_url, "featured_image_url", "featured image", errors)

        selected_topics = _validate_topic_selections(request.POST, errors, create=not errors)

        if errors:
            return render(
                request,
                "econ/add_blog.html",
                _topic_form_context({
                    "date": datetime.now(),
                    "date_value": posted_date or timezone.localdate().isoformat(),
                    "errors": errors,
                    "values": request.POST,
                }),
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

        source_list = _parse_blog_sources(sources, title, parsed_date, no_date=no_date)

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
        blog.topics.set(selected_topics)
        BlogPost.objects.filter(pk=blog.pk).update(created_at=_content_created_at(parsed_date))

        messages.success(request, f"Blog '{blog.title}' created successfully.")
        log_action(
            request,
            "create",
            "Add Blog",
            {"Blog": blog.title, "Topics": ", ".join(topic.title for topic in selected_topics), "Slug": blog.slug},
        )
        return redirect("blog_detail", slug=blog.slug)

    return render(
        request,
        "econ/add_blog.html",
        _topic_form_context({
            "date": datetime.now(),
            "date_value": timezone.localdate().isoformat(),
        })
    )


@login_required
@user_passes_test(superuser_required)
def add_journal(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        posted_date = request.POST.get("date", "").strip()
        journal_url = request.POST.get("journal_url", "").strip()
        no_date = request.POST.get("no_date") == "1"
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

        parsed_date = _parse_optional_content_date(posted_date, _is_valid_url(journal_url), errors, no_date=no_date)

        if not authors:
            errors["authors"] = "Authors are required."
        _validate_text_not_number(authors, "authors", "Authors", errors)

        if journal_url and not publication_year and not no_date:
            errors["publication_year"] = "Publication year is required."
        elif not publication_year:
            publication_year = str(timezone.localdate().year)
        elif not publication_year.isdigit():
            errors["publication_year"] = "Publication year must be a number."

        if not journal_name:
            errors["journal_name"] = "Journal name is required."
        _validate_text_not_number(journal_name, "journal_name", "Journal name", errors)

        _validate_text_not_number(citation_info, "citation_info", "Citation info", errors)

        if not snippet:
            errors["snippet"] = "Snippet is required."
        _validate_text_not_number(snippet, "snippet", "Snippet", errors)

        _validate_keywords_format(keywords, "keywords", errors)

        selected_topics = _validate_topic_selections(request.POST, errors, create=not errors)

        if errors:
            return render(
                request,
                "econ/add_journal.html",
                _topic_form_context({
                    "date": datetime.now(),
                    "date_value": posted_date or timezone.localdate().isoformat(),
                    "errors": errors,
                    "values": request.POST,
                }),
                status=400
            )

        journal = JournalEntry.objects.create(
            title=title,
            journal_url=journal_url,
            authors=authors,
            publication_year=int(publication_year),
            journal_name=journal_name,
            citation_info=citation_info or _apa_journal_source(authors, publication_year, title, journal_name, journal_url, no_date=no_date),
            snippet=snippet,
            keywords=[
                k.strip() for k in keywords.split(",") if k.strip()
            ],
           order=order,
        )
        journal.topics.set(selected_topics)
        JournalEntry.objects.filter(pk=journal.pk).update(created_at=_content_created_at(parsed_date))

        messages.success(request, f"Journal '{journal.title}' added successfully.")
        log_action(
            request,
            "create",
            "Add Journal",
            {"Journal": journal.title, "Topics": ", ".join(topic.title for topic in selected_topics), "URL": journal.journal_url},
        )
        return redirect("journal_detail", journal_id=journal.id)

    return render(
        request,
        "econ/add_journal.html",
        _topic_form_context({
            "date": datetime.now(),
            "date_value": timezone.localdate().isoformat(),
        })
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
        parsed_date = _parse_optional_content_date(date, _is_valid_url(image_url), errors)
        selected_topics = _validate_topic_selections(request.POST, errors, create=not errors)

        if errors:
            return render(
                request,
                "econ/add_media.html",
                _topic_form_context({
                    "date": datetime.now(),
                    "errors": errors,
                    "values": request.POST,
                }),
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
        media.topics.set(selected_topics)

        messages.success(request, f"Image '{media.title}' added successfully.")
        log_action(
            request,
            "create",
            "Add Image",
            {"Image": media.title, "Topics": ", ".join(topic.title for topic in selected_topics), "URL": media.image_url},
        )
        gallery_page = _gallery_item_page(media.id)
        return redirect(f"{reverse('gallery')}?page={gallery_page}#gallery-item-{media.id}")

    return render(
        request,
        "econ/add_media.html",
        _topic_form_context({
            "date": datetime.now(),
        })
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
        _validate_text_not_symbol(channel_name, "channel_name", "Channel", errors)

        if not description:
            errors["description"] = "Description is required."
        _validate_text_not_number(description, "description", "Description", errors)

        if not video_url:
            errors["video_url"] = "Video URL is required so the video can be embedded."
        _validate_url(video_url, "video_url", "video", errors)
        parsed_date = _parse_optional_content_date(date, _is_valid_url(video_url), errors)

        selected_topics = _validate_topic_selections(request.POST, errors, create=not errors)

        if errors:
            return render(
                request,
                "econ/add_vlog.html",
                _topic_form_context({
                    "date": datetime.now(),
                    "errors": errors,
                    "values": request.POST,
                }),
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
        new_vlog.topics.set(selected_topics)

        messages.success(request, f"Video '{new_vlog.title}' added successfully.")
        log_action(
            request,
            "create",
            "Add Video",
            {"Video": new_vlog.title, "Topics": ", ".join(topic.title for topic in selected_topics), "URL": new_vlog.video_url},
        )
        return redirect("vlog_detail", vlog_id=new_vlog.vlogID)

    return render(
        request,
        "econ/add_vlog.html",
        _topic_form_context({
            "date": datetime.now(),
        })
    )


def add_media(request):
    return redirect("add_image")


def add_vlog(request):
    return redirect("add_video")
