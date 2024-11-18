"""eGSIM URL Configuration"""

from django.contrib import admin  # added by default by django  # noqa
from django.urls import include, path

urlpatterns = [
    # Note: 1st path arg should be empty otherwise it messes up csrf exempt in API views
    path('', include('egsim.api.urls')),
    path('', include('egsim.app.urls')),
]