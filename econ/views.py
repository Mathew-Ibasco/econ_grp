from datetime import datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import BlogPost, Bookmark, MediaGalleryEntry, User

DASHBOARD_ITEMS = [
    {
        "key": "rail-transport-basics",
        "type": "topic",
        "title": "Rail Transport Basics",
        "summary": "Core ideas about trains, tracks, passenger movement, freight, and why rail is efficient for dense cities.",
        "url": "#rail-transport",
        "icon": "fa-train",
    },
    {
        "key": "philippine-rail-systems",
        "type": "topic",
        "title": "Philippine Rail Systems",
        "summary": "A quick guide to MRT, LRT, and PNR, including how these systems serve Metro Manila and Luzon commuters.",
        "url": "#philippine-rail",
        "icon": "fa-map-location-dot",
    },
    {
        "key": "mobility-economy",
        "type": "topic",
        "title": "Accessibility, Mobility & The Economy",
        "summary": "How rail systems reduce congestion, connect people to opportunity, and support economic productivity.",
        "url": "#mobility-economy",
        "icon": "fa-chart-simple",
    },
    {
        "key": "rail-gallery",
        "type": "media",
        "title": "Gallery Snapshot",
        "summary": "Images of Philippine rail systems, station maps, commuters, construction, and global rail references.",
        "url": "#rail-gallery",
        "icon": "fa-images",
    },
    {
        "key": "rail-history-resource",
        "type": "resource",
        "title": "Rail Transport History",
        "summary": "External reading on how rail transport developed and why it became central to urban and regional mobility.",
        "url": "https://www.ebsco.com/research-starters/history/rail-transport",
        "icon": "fa-book-open",
    },
    {
        "key": "world-bank-mobility-resource",
        "type": "resource",
        "title": "World Bank: Livable Cities",
        "summary": "A source connecting urban mobility investment with more livable, accessible, and sustainable cities.",
        "url": "https://www.worldbank.org/en/results/2024/03/13/promoting-livable-cities-by-investing-in-urban-mobility",
        "icon": "fa-city",
    },
]

BOOKMARK_ITEMS_BY_KEY = {item["key"]: item for item in DASHBOARD_ITEMS}

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
    item = BOOKMARK_ITEMS_BY_KEY.get(item_key)
    if item is None:
        messages.error(request, "That bookmark item is no longer available.")
        return redirect("index")

    existing = Bookmark.objects.filter(user=request.user, item_key=item_key).first()
    if existing:
        existing.delete()
        messages.success(request, f"Removed {item['title']} from your saved items.")
    else:
        Bookmark.objects.create(
            user=request.user,
            item_key=item["key"],
            title=item["title"],
            summary=item["summary"],
            item_type=item["type"],
            url=item["url"],
        )
        messages.success(request, f"Saved {item['title']} to your dashboard.")

    return redirect("index")

def index(request):
    context = {
        'date': datetime.now(),
        'dashboard_items': DASHBOARD_ITEMS,
        'saved_bookmarks': [],
        'saved_item_keys': set(),
    }

    if request.user.is_authenticated:
        saved_bookmarks = list(request.user.bookmarks.all())
        saved_item_keys = {bookmark.item_key for bookmark in saved_bookmarks}
        context.update({
            'saved_bookmarks': saved_bookmarks,
            'saved_item_keys': saved_item_keys,
            'recommended_items': [
                item for item in DASHBOARD_ITEMS if item["key"] not in saved_item_keys
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
            'date': datetime.now()
        }
    )

def vlog(request):
    return render(
        request,
        'econ/vlog.html',
        {
            'date': datetime.now()
        }
    )

def gallery(request):
    return render(
        request,
        'econ/gallery.html',
        {
            'date': datetime.now(),
            'gallery_entries': MediaGalleryEntry.objects.order_by("order", "id"),
        }
    )
