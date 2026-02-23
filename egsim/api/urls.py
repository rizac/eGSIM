"""eGSIM RESTAPI URL Configuration"""

from django.urls import re_path
from django.views.decorators.csrf import csrf_exempt

from .views import PredictionsView, ResidualsView, NotFound, GsimInfoView

# IMPORTANT: ALL VIEWS SHOULD INHERIT FROM api.views.EgsimView
# (also, watch out trailing slashes in url paths: https://stackoverflow.com/q/1596552)

API_PATH = 'api/query/'

# these two are used for testing:
PREDICTIONS_URL_PATH = f'{API_PATH}predictions'
RESIDUALS_URL_PATH = f'{API_PATH}residuals'
MODEL_INFO_URL_PATH = f'{API_PATH}models'

urlpatterns = [
    re_path(
        fr'^{PREDICTIONS_URL_PATH}/?$', csrf_exempt(PredictionsView.as_view())
    ),
    re_path(
        fr'^{RESIDUALS_URL_PATH}/?$', csrf_exempt(ResidualsView.as_view())
    ),
    re_path(
        fr'^{MODEL_INFO_URL_PATH}/?$', csrf_exempt(GsimInfoView.as_view())
    ),
    # Fallback: return a 404 not-found HttpResponse (unlike Django, with empty content):
    re_path(fr"^{API_PATH}.*$", csrf_exempt(NotFound.as_view()))
]
