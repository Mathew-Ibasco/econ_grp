from django.contrib import admin
from django.urls import include, path
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

from django.conf.urls.i18n import i18n_patterns
from econ import views 
from django.views.i18n import set_language
from django.views.generic.base import RedirectView

from django.conf.urls import handler404
from django.shortcuts import render

def custom_400(request, exception):
    return render(request, "econ/error/400.html", status=400)

def custom_404(request, exception):
    return render(request, "econ/error/404.html", status=404)

def custom_500(request):
    return render(request, "econ/error/500.html", status=500)

def custom_403(request, exception):
    return render(request, "econ/error/403.html", status=403)

handler400 = custom_400
handler403 = custom_403
handler404 = custom_404
handler500 = custom_500

urlpatterns = [
    path('', RedirectView.as_view(url='/econ/', permanent=False)),
    path("econ/", include("econ.urls")),
    path('i18n/', include('django.conf.urls.i18n')),
]

urlpatterns += i18n_patterns(
    path("econ/", include("econ.urls")),
) 