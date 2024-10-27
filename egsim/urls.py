"""eGSIM URL Configuration"""

from django.contrib import admin  # added by default by django  # noqa
from django.urls import include, path

urlpatterns = [
    path('', include('egsim.api.urls')),
    path('', include('egsim.app.urls')),
]

# in api.urls, the last url pattern (urlpatterns[0][-1]) is a fallback returning
# a 404 in JSON format: to have the same behaviour here, we need to move it to the end:
urlpatterns[1].url_patterns.append(urlpatterns[0].url_patterns.pop())
