"""eGSIM RESTAPI URL Configuration"""
from django.urls import re_path
from django.contrib import admin
from re import escape as esc

from .views import TrellisView, ResidualsView, TestingView

# Watch out trailing slashes:
# https://stackoverflow.com/questions/1596552/django-urls-without-a-trailing-slash-do-not-redirect

urlpatterns = [
    re_path(r'^admin/', admin.site.urls),  # added by default by django
    *[re_path(r'^%s/?$' % esc(_), TrellisView.as_view()) for _ in TrellisView.urls],
    *[re_path(r'^%s/?$' % esc(_), ResidualsView.as_view()) for _ in ResidualsView.urls],
    *[re_path(r'^%s/?$' % esc(_), TestingView.as_view()) for _ in TestingView.urls],
]
