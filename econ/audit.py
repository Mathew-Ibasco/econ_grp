from django.urls import resolve

from .models import AuditLog


def audit_role(user):
    if not getattr(user, "is_authenticated", False):
        return "Guest"
    if user.is_superuser:
        return "Admin"
    return "Member"


def audit_username(user):
    if not getattr(user, "is_authenticated", False):
        return "Guest"
    return user.get_username()


def request_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR") or None


def page_title_for_request(request):
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is None:
        try:
            resolver_match = resolve(request.path_info)
        except Exception:
            resolver_match = None

    if resolver_match is None:
        return request.path.strip("/") or "Home"

    names = {
        "index": "Home",
        "dashboard": "Dashboard",
        "forum": "Forum",
        "forum_thread": "Forum Thread",
        "blog": "Blogs",
        "blog_detail": "Blog Detail",
        "journal": "Journals",
        "journal_detail": "Journal Detail",
        "vlog": "Media",
        "vlog_detail": "Video Detail",
        "gallery": "Gallery",
        "profile": "Profile",
        "login": "Login",
        "registration": "Registration",
        "upload_sql": "Upload SQL Dump",
        "add_blog": "Add Blog",
        "add_journal": "Add Journal",
        "add_image": "Add Image",
        "add_video": "Add Video",
        "audit_logs": "Audit Logs",
    }
    return names.get(resolver_match.url_name, resolver_match.url_name or request.path.strip("/") or "Home")


def log_action(
    request,
    action,
    label,
    details=None,
    user=None,
    page_title=None,
    status_code=None,
):
    actor = user if user is not None else getattr(request, "user", None)
    AuditLog.objects.create(
        user=actor if getattr(actor, "is_authenticated", False) else None,
        username=audit_username(actor),
        role=audit_role(actor),
        action=action,
        label=label,
        method=getattr(request, "method", ""),
        path=getattr(request, "get_full_path", lambda: "")(),
        page_title=page_title or page_title_for_request(request),
        details=details or {},
        ip_address=request_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "") or "")[:300],
        status_code=status_code,
    )
