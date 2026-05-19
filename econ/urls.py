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
    path("bookmark/toggle/", views.toggle_bookmark, name="toggle_bookmark"),
    path("registration/", views.registration, name="registration"),
    path("registration_process", views.registration_process, name="registration_process"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("blog/", views.blog, name="blog"),
    path("blog/<slug:slug>/", views.blog_detail, name="blog_detail"),
    path("vlog/", views.vlog, name="vlog"),
    path("vlog/<int:vlog_id>/", views.vlog_detail, name="vlog_detail"),
    path("gallery/", views.gallery, name="gallery"),
    path("journal/", views.journal, name="journal"),
    path("journal/<int:journal_id>/", views.journal_detail, name="journal_detail"),
    path('download_sql_dump', views.download_sql_dump, name='download_sql_dump'),
    path('upload_sql_process', views.upload_sql_process, name='upload_sql_process'),
    path('upload_sql', views.upload_sql, name='upload_sql'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
