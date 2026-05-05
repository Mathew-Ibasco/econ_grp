import re
from datetime import datetime, date
from django.shortcuts import render
from pathlib import Path
from django.conf import settings
from django.http import JsonResponse, FileResponse, HttpResponse
from django.db.models import Count, F, Q, Value, Case, When, IntegerField, BooleanField, TextField, Prefetch
from django.db import models
import calendar
from decimal import Decimal
from django.http import HttpResponse

def index(request):
    return render(
        request,
        'econ/index.html',
        {
            'date': datetime.now()
        }
    )
