"""eGSIM URL Configuration"""

from django.contrib import admin  # added by default by django
from django.urls import include, path

urlpatterns = [
    path('', include('egsim.api.urls')),
    path('', include('egsim.app.urls')),
]