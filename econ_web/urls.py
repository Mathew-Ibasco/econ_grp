from django.contrib import admin
from django.urls import include, path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.conf import settings
from django.conf.urls.static import static

from econ import views 
from django.views.generic.base import RedirectView

from django.shortcuts import render

handler400 = "econ.views.custom_400"
handler403 = "econ.views.custom_403"
handler404 = "econ.views.custom_404"
handler500 = "econ.views.custom_500"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(url="/econ/", permanent=False)),
    path("accounts/login/", views.login, name="accounts_login"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("econ/", include("econ.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
