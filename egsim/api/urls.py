"""eGSIM RESTAPI URL Configuration"""
from django.urls import re_path
from django.contrib import admin
from django.views.decorators.csrf import csrf_exempt
from re import escape as esc
from http.client import responses

from .views import PredictionsView, ResidualsView, error_response

# For trailing slashes in urls, see: https://stackoverflow.com/a/11690144

urlpatterns = [
    re_path(r'^admin/', admin.site.urls),  # added by default by django
    *[re_path(r'^%s/?$' % esc(_), csrf_exempt(PredictionsView.as_view()))
      for _ in PredictionsView.urls],
    *[re_path(r'^%s/?$' % esc(_), csrf_exempt(ResidualsView.as_view()))
      for _ in ResidualsView.urls],
    # return a 404 not-found JSON Response for all other cases
    # KEEP THIS AT THE END OF THE URL PATTERNS (see also egsim.urls for details):
    re_path("^.+/?$", csrf_exempt(lambda *a, **kw: error_response(responses[404], 404)))
]
