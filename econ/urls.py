from django.urls import path
from econ import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("", views.index, name="index"),
    path("admin_dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("login/", views.login, name="login"),
    path("login_process", views.login_process, name="login_process"),
    path("logout_process", views.logout_process, name="logout_process"),
    path("registration/", views.registration, name="registration"),
    path("registration_process", views.registration_process, name="registration_process"),
    path("blog/", views.blog, name="blog"),
    path("vlog/", views.vlog, name="vlog"),
    path("gallery/", views.gallery, name="gallery"),
    path("journal/", views.journal, name="journal"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)