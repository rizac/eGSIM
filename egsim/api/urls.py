"""eGSIM RESTAPI URL Configuration"""
from django.conf.urls import url  # added by default by django
from django.contrib import admin  # added by default by django
from re import escape as esc

from .views import TrellisView, ResidualsView, TestingView

# Watch out trailing slashes:
# https://stackoverflow.com/questions/1596552/django-urls-without-a-trailing-slash-do-not-redirect

urlpatterns = [
    url(r'^admin/', admin.site.urls),  # added by default by django
    *[url(r'^%s/?$' % esc(_), TrellisView.as_view()) for _ in TrellisView.urls],
    *[url(r'^%s/?$' % esc(_), ResidualsView.as_view()) for _ in ResidualsView.urls],
    *[url(r'^%s/?$' % esc(_), TestingView.as_view()) for _ in TestingView.urls],
]
