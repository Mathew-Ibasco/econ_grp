from datetime import datetime, date

from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import StreamingHttpResponse

import os, re, sys, html, calendar, json, subprocess, sqlite3

from .models import BlogPost, Bookmark, JournalEntry, MediaGalleryEntry, Topic, User, vlog as VlogEntry

def _auth_context(values=None, errors=None):
    return {
        "date": datetime.now(),
        "values": values or {},
        "errors": errors or {},
    }

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
            if user.is_staff:
                return redirect("admin_dashboard") # admin goes here
            return redirect("index") # regular user goes here
        else:
            errors["password"] = "Incorrect password."
            return render(request, "econ/login.html", _auth_context(values, errors), status=400)
    return render(request, "econ/login.html", _auth_context())

def logout_process(request):
    logout(request)
    return redirect("index")

# regular users only
@login_required
def home(request):
    return render(
        request, 
        "econ/home.html",
        {
            'date': datetime.now()
        }
    )

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
    dashboard_topics = Topic.objects.prefetch_related(
        "blog_posts",
        "journal_entries",
        "media_entries",
        "vlog_entries",
    ).order_by("order", "id")
    context = {
        'date': datetime.now(),
        'dashboard_topics': dashboard_topics,
        'saved_bookmarks': [],
        'saved_item_keys': set(),
        'available_topics_count': dashboard_topics.count(),
        'recommended_topics': dashboard_topics[:3],
    }

    if request.user.is_authenticated:
        saved_bookmarks = list(
            request.user.bookmarks.select_related("topic").prefetch_related(
                "topic__blog_posts",
                "topic__journal_entries",
                "topic__media_entries",
                "topic__vlog_entries",
            )
        )
        saved_item_keys = {bookmark.item_key for bookmark in saved_bookmarks}
        context.update({
            'saved_bookmarks': saved_bookmarks,
            'saved_item_keys': saved_item_keys,
            'available_topics_count': dashboard_topics.exclude(key__in=saved_item_keys).count(),
            'recommended_topics': [
                topic for topic in dashboard_topics if topic.key not in saved_item_keys
            ][:3],
        })

    return render(
        request,
        'econ/index.html',
        context
    )

def blog(request):
    return render(
        request,
        'econ/blog.html',
        {
            'date': datetime.now(),
            'blog_posts': BlogPost.objects.order_by("order", "id"),
        }
    )

def blog_detail(request, slug):
    blog_post = get_object_or_404(BlogPost, slug=slug)

    return render(
        request,
        "econ/blog_detail.html",
        {
            "date": datetime.now(),
            "blog_post": blog_post,
        }
    )

def journal(request):
    return render(
        request,
        'econ/journal.html',
        {
            'date': datetime.now(),
            'journal_entries': JournalEntry.objects.order_by("order", "id"),
        }
    )

def vlog(request):
    return render(
        request,
        'econ/vlog.html',
        {
            'date': datetime.now(),
            'vlog_entries': VlogEntry.objects.prefetch_related("topics").order_by("order", "vlogID"),
        }
    )

def gallery(request):
    return render(
        request,
        'econ/gallery.html',
        {
            'date': datetime.now(),
            'gallery_entries': MediaGalleryEntry.objects.prefetch_related("topics").order_by("order", "id"),
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
