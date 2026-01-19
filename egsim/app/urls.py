"""eGSIM URL Configuration for the Graphical User Interface (GUI)"""
from django.http import HttpResponse
from django.urls import re_path, path
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import RedirectView

from egsim.api.views import (
    PredictionsView, ResidualsView, GsimInfoView, NotFound, APIFormView
)
from egsim.api.forms.flatfile import FlatfileValidationForm, FlatfileMetadataInfoForm
from .forms import (
    PredictionsVisualizeForm, ResidualsVisualizeForm, FlatfileVisualizeForm
)
from .views import (
    main, URLS, img_ext, data_ext, PlotsImgDownloader, GsimFromRegion,
    PredictionsHtmlTutorial, ResidualsHtmlTutorial
)


# IMPORTANT: ALL VIEWS (except HTML pages) SHOULD INHERIT FROM api.views.EgsimView
# (also, watch out trailing slashes in url paths: https://stackoverflow.com/q/1596552)


urlpatterns = [
    re_path(
        r'^$',
        RedirectView.as_view(pattern_name='main', url='home', permanent=False)
    ),
    re_path(
        (r'^(?P<page>' +
         '|'.join([
             URLS.WEBPAGE_HOME, URLS.WEBPAGE_PREDICTIONS,
             URLS.WEBPAGE_RESIDUALS,
             URLS.WEBPAGE_FLATFILE_INSPECTION_PLOT,
             URLS.WEBPAGE_FLATFILE_COMPILATION_INFO,
             URLS.WEBPAGE_API_DOC,
             URLS.WEBPAGE_IMPRINT, URLS.WEBPAGE_CITATIONS_AND_LICENSE
         ]) + ')/?$'),
        main
    ),

    re_path(
        fr'^{URLS.DOWNLOAD_PREDICTIONS_DATA}.(?:{"|".join(data_ext)})$',
        PredictionsView.as_view()
    ),  # note: `data_ext` in url is set and used only in the GUI as download filename
    path(
        URLS.SUBMIT_PREDICTIONS_VISUALIZATION,
        APIFormView.as_view(formclass=PredictionsVisualizeForm)
    ),
    re_path(
        fr'{URLS.DOWNLOAD_PREDICTIONS_PLOT}.(?:{"|".join(img_ext)})',
        PlotsImgDownloader.as_view()
    ),
    path(
        URLS.PREDICTIONS_DOWNLOADED_DATA_TUTORIAL,
        xframe_options_exempt(PredictionsHtmlTutorial.as_view())
    ),

    re_path(  # (`data_ext` below is set and used only in the GUI as download filename)
        r'^%s.(?:%s)$' % (URLS.DOWNLOAD_RESIDUALS_DATA, "|".join(data_ext)),
        ResidualsView.as_view()
    ),
    path(
        URLS.SUBMIT_RESIDUALS_VISUALIZATION,
        APIFormView.as_view(formclass=ResidualsVisualizeForm)
    ),
    re_path(
        fr'{URLS.DOWNLOAD_RESIDUALS_PLOT}.(?:{"|".join(img_ext)})',
        PlotsImgDownloader.as_view()
    ),
    path(
        URLS.RESIDUALS_DOWNLOADED_DATA_TUTORIAL,
        xframe_options_exempt(ResidualsHtmlTutorial.as_view())
    ),

    path(
        URLS.SUBMIT_FLATFILE_COMPILATION_INFO,
        APIFormView.as_view(formclass=FlatfileMetadataInfoForm)
    ),
    path(
        URLS.SUBMIT_FLATFILE_VISUALIZATION,
        APIFormView.as_view(formclass=FlatfileVisualizeForm)
    ),
    re_path(
        fr'{URLS.DOWNLOAD_FLATFILE_PLOT}.(?:{"|".join(img_ext)})',
        PlotsImgDownloader.as_view()
    ),

    path(
        URLS.FLATFILE_VALIDATION,
        APIFormView.as_view(formclass=FlatfileValidationForm)
    ),

    path(URLS.GSIMS_FROM_REGION, GsimFromRegion.as_view()),
    path(URLS.GSIMS_INFO, GsimInfoView.as_view()),

    # test code returning specific response (in this case, no EgsimView required):
    path("test_response/<int:code>",
         csrf_exempt(lambda req, code: HttpResponse(b'test response msg', status=code))),

    # Fallback: return a 404 not-found HttpResponse (unlike Django, with empty content):
    re_path(r".*", csrf_exempt(NotFound.as_view()))
]
