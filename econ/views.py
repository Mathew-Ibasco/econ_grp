from datetime import datetime, date
from types import SimpleNamespace

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import StreamingHttpResponse

import os, re, sys, html, calendar, json, subprocess, sqlite3

from .models import BlogPost, Bookmark, ItemNote, ItemQuizAttempt, ItemQuizProgress, ItemQuizQuestion, JournalEntry, MediaGalleryEntry, QuizAttempt, StudyItemProgress, Topic, TopicNote, User, vlog as VlogEntry


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
    candidates_by_kind = {
        "blog": [
            SimpleNamespace(
                topic=topic,
                title=post.title,
                kind="Blog",
                icon="fa-newspaper",
                url=reverse("blog_detail", args=[post.slug]),
            )
            for post in topic.blog_posts.order_by("order", "id")
        ],
        "journal": [
            SimpleNamespace(
                topic=topic,
                title=entry.title,
                kind="Journal",
                icon="fa-book-open",
                url=reverse("journal_detail", args=[entry.id]),
            )
            for entry in topic.journal_entries.order_by("order", "id")
        ],
        "video": [
            SimpleNamespace(
                topic=topic,
                title=entry.title,
                kind="Media",
                icon="fa-circle-play",
                url=reverse("vlog_detail", args=[entry.vlogID]),
            )
            for entry in topic.vlog_entries.order_by("order", "vlogID")
        ],
        "gallery": [
            SimpleNamespace(
                topic=topic,
                title=entry.title,
                kind="Gallery",
                icon="fa-images",
                url=reverse("gallery"),
            )
            for entry in topic.media_entries.order_by("order", "id")
        ],
    }

    if "gallery" in topic.key:
        priority = ["gallery", "video", "blog", "journal"]
    elif "history" in topic.key:
        priority = ["journal", "blog", "gallery", "video"]
    elif "mobility" in topic.key or "world-bank" in topic.key:
        priority = ["journal", "video", "blog", "gallery"]
    else:
        priority = ["blog", "journal", "video", "gallery"]

    candidates = []
    for kind in priority:
        candidates.extend(candidates_by_kind[kind])
    return candidates


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
        values = {"username": username}
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
        dashboard_topics = Topic.objects.prefetch_related(
            "blog_posts",
            "journal_entries",
            "media_entries",
            "vlog_entries",
            "quiz_questions",
        ).order_by("order", "id")
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

        recommended_items = []
        recommended_urls = set()
        for topic in dashboard_topics:
            if topic.key in saved_item_keys:
                continue
            for recommendation in _topic_recommendation_candidates(topic):
                if recommendation.url in recommended_urls:
                    continue
                recommended_items.append(recommendation)
                recommended_urls.add(recommendation.url)
                break
            if len(recommended_items) == 3:
                break

        context.update(
            {
                "dashboard_topics": dashboard_topics,
                "saved_bookmarks": saved_bookmarks,
                "study_boards": study_boards,
                "saved_item_keys": saved_item_keys,
                "available_topics_count": dashboard_topics.exclude(key__in=saved_item_keys).count(),
                "recommended_items": recommended_items,
            }
        )

    return context

def home(request):
    return render(request, "econ/index.html", {"date": datetime.now(), "show_dashboard": False})

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
        _auth_context()
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
    return render(request, "econ/index.html", {"date": datetime.now(), "show_dashboard": False})

@login_required
def dashboard(request):
    context = _dashboard_page_context(request)
    context["show_dashboard"] = True
    return render(request, "econ/index.html", context)

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

def gallery(request):
    return render(
        request,
        'econ/gallery.html',
        {
            'date': datetime.now(),
            'gallery_count': 10,
        }
    )

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

@login_required
@user_passes_test(lambda u: u.is_superuser)
def download_sql_dump(request):
    db_path = settings.DATABASES['default']['NAME']
    filename = f"dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"

    def stream():
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        yield f"-- SQL Dump: {os.path.basename(db_path)}\n".encode()
        yield f"-- Generated: {datetime.now()}\n\n".encode()
        yield b"PRAGMA foreign_keys = OFF;\n\n"

        # Get all user tables (exclude sqlite internal tables)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            # Table structure
            cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
            create_table = cursor.fetchone()[0]
            yield f"-- Table: {table}\n".encode()
            yield f"DROP TABLE IF EXISTS \"{table}\";\n".encode()
            yield f"{create_table};\n\n".encode()

            # Table data
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

    response = StreamingHttpResponse(stream(), content_type='application/sql')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
@user_passes_test(lambda u: u.is_superuser)
def upload_sql_process(request):
    if request.method == 'POST' and request.FILES.get('sql_file'):
        db_path = settings.DATABASES['default']['NAME']
        sql_file = request.FILES['sql_file']

        conn = sqlite3.connect(db_path)

        try:
            cursor = conn.cursor()
            sql = sql_file.read().decode('utf-8')

            # Drop all existing user tables first
            cursor.execute("PRAGMA foreign_keys = OFF;")
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            existing_tables = [row[0] for row in cursor.fetchall()]
            for table in existing_tables:
                cursor.execute(f'DROP TABLE IF EXISTS "{table}"')
            conn.commit()

            # executescript() is SQLite's native multi-statement parser —
            # it handles semicolons inside string literals and quoted identifiers
            # correctly, unlike a naive split(';').
            # It also issues a COMMIT before running, so we commit the drops above first.
            conn.executescript(sql)

            messages.success(request, "SQL dump applied successfully.")
        except Exception as e:
            conn.rollback()
            messages.error(request, f"Failed to apply dump: {str(e)}")
        finally:
            cursor.close()
            conn.close()

    return render(
        request,
        'econ/upload_sql.html',
        {'date': datetime.now()}
    )
