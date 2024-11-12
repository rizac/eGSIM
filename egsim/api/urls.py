"""eGSIM RESTAPI URL Configuration"""
from django.urls import re_path
from django.contrib import admin
from django.views.decorators.csrf import csrf_exempt
from http.client import responses

from .views import PredictionsView, ResidualsView, error_response, ModelInfoView

API_PATH = 'api/query'

# these two are used for testing:
PREDICTIONS_URL_PATH = f'{API_PATH}/predictions'
RESIDUALS_URL_PATH = f'{API_PATH}/residuals'
MODEL_INFO = f'{API_PATH}/modelinfo'

# For trailing slashes in urls, see: https://stackoverflow.com/a/11690144
urlpatterns = [
    re_path(r'^admin/', admin.site.urls),  # added by default by django
    re_path(fr'^{PREDICTIONS_URL_PATH}/?$', csrf_exempt(PredictionsView.as_view())),
    re_path(fr'^{RESIDUALS_URL_PATH}/?$', csrf_exempt(ResidualsView.as_view())),
    re_path(fr'^{MODEL_INFO}/?$', csrf_exempt(ModelInfoView.as_view())),
    # return a 404 not-found JSON Response for all other cases
    # KEEP THIS AT THE END OF THE URL PATTERNS (see also egsim.urls for details):
    re_path("^.+/?$", csrf_exempt(lambda *a, **kw: error_response(responses[404], 404)))
]
