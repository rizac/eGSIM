"""eGSIM RESTAPI URL Configuration"""
from django.urls import re_path
from django.contrib import admin
from django.views.decorators.csrf import csrf_exempt
from re import escape as esc

from .views import TrellisView, ResidualsView

# Watch out trailing slashes:
# https://stackoverflow.com/questions/1596552/django-urls-without-a-trailing-slash-do-not-redirect

urlpatterns = [
    re_path(r'^admin/', admin.site.urls),  # added by default by django
    *[re_path(r'^%s/?$' % esc(_), csrf_exempt(TrellisView.as_view()))
      for _ in TrellisView.urls],
    *[re_path(r'^%s/?$' % esc(_), csrf_exempt(ResidualsView.as_view()))
      for _ in ResidualsView.urls],
]
