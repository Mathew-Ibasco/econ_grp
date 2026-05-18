import re
from datetime import datetime, date
from django.shortcuts import render, redirect
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse, FileResponse, HttpResponse
from django.db.models import Count, F, Q, Value, Case, When, IntegerField, BooleanField, TextField, Prefetch
from django.db import models
import calendar
from decimal import Decimal
from django.http import HttpResponse
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages

from .models import User

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
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            if user.is_staff:
                return redirect("admin_dashboard") # admin goes here
            return redirect("index") # regular user goes here
        else:
            messages.error(request, "Invalid credentials.")
            return render(request, "econ/login.html")
    return render(request, "econ/login.html")

def logout_process(request):
    logout(request)
    return redirect("login")

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
        {
            'date': datetime.now()
        }
    )

def registration(request):
    return render(request, "econ/registration.html")

def registration_process(request):
    if request.method == "POST":
        alldata = request.POST
        username = alldata.get("username", "").strip()
        password = alldata.get("password", "")
        confirm = alldata.get("confirm", "")
        email = alldata.get("email", "").strip()
        bio = alldata.get("bio", "").strip()

        # empty fields
        if not username or not password or not confirm:
            messages.error(request, "All fields are required.")
            return redirect("registration")

        # password length
        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return redirect("registration")

        # password match
        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return redirect("registration")

        # duplicate username
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect("registration")

        # duplicate email
        if email and User.objects.filter(email=email).exists():
            messages.error(request, "Email already in use.")
            return redirect("registration")

        user = User.objects.create_user(username=username, password=password, email=email)
        user.bio = bio
        user.save()

        auth_login(request, user)
        return redirect("index")

    return redirect("registration")

def index(request):
    return render(
        request,
        'econ/index.html',
        {
            'date': datetime.now()
        }
    )
