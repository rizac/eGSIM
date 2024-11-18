"""eGSIM URL Configuration for the Graphical User Interface (GUI)"""
from django.http import HttpResponse
from django.urls import re_path, path
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import RedirectView

from egsim.api.views import (PredictionsView, ResidualsView, GsimInfoView, NotFound,
                             APIFormView)
from egsim.api.forms import GsimFromRegionForm
from egsim.api.forms.flatfile import FlatfileValidationForm, FlatfileMetadataInfoForm
from .forms import (PredictionsVisualizeForm, ResidualsVisualizeForm,
                    FlatfileVisualizeForm)
from .views import (main, URLS, img_ext, data_ext, PlotsImgDownloader,
                    PredictionsHtmlTutorial, ResidualsHtmlTutorial)


# IMPORTANT: ALL VIEWS (except HTML pages) SHOULD INHERIT FROM api.views.EgsimView
# (also, watch out trailing slashes in url paths: https://stackoverflow.com/q/1596552)


urlpatterns = [
    re_path(r'^$', RedirectView.as_view(pattern_name='main', url='home',
                                        permanent=False)),
    re_path((r'^(?P<page>' +
             '|'.join([URLS.HOME_PAGE, URLS.PREDICTIONS_PAGE, URLS.RESIDUALS_PAGE,
                       URLS.FLATFILE_INSPECTION_PLOT_PAGE, URLS.FLATFILE_META_INFO_PAGE,
                       URLS.IMPRINT_PAGE, URLS.REF_AND_LICENSE_PAGE]) +
             ')/?$'), main),

    re_path(
        fr'^{URLS.PREDICTIONS}.(?:{"|".join(data_ext)})$',
        PredictionsView.as_view()
    ),  # note: `data_ext` in url is set and used only in the GUI as download filename
    path(
        URLS.PREDICTIONS_VISUALIZE,
        APIFormView.as_view(formclass=PredictionsVisualizeForm)
    ),
    re_path(
        fr'{URLS.PREDICTIONS_PLOT_IMG}.(?:{"|".join(img_ext)})',
        PlotsImgDownloader.as_view()
    ),
    path(
        URLS.PREDICTIONS_RESPONSE_TUTORIAL,
        xframe_options_exempt(PredictionsHtmlTutorial.as_view())
    ),

    re_path(  # (`data_ext` below is set and used only in the GUI as download filename)
        r'^%s.(?:%s)$' % (URLS.RESIDUALS, "|".join(data_ext)),
        ResidualsView.as_view()
    ),
    path(
        URLS.RESIDUALS_VISUALIZE,
        APIFormView.as_view(formclass=ResidualsVisualizeForm)
    ),
    re_path(
        fr'{URLS.RESIDUALS_PLOT_IMG}.(?:{"|".join(img_ext)})',
        PlotsImgDownloader.as_view()
    ),
    path(
        URLS.RESIDUALS_RESPONSE_TUTORIAL,
        xframe_options_exempt(ResidualsHtmlTutorial.as_view())
    ),

    path(
        URLS.FLATFILE_VISUALIZE,
        APIFormView.as_view(formclass=FlatfileVisualizeForm)
    ),
    re_path(
        fr'{URLS.FLATFILE_PLOT_IMG}.(?:{"|".join(img_ext)})',
        PlotsImgDownloader.as_view()
    ),

    path(
        URLS.FLATFILE_VALIDATE,
        APIFormView.as_view(formclass=FlatfileValidationForm)
    ),
    path(
        URLS.FLATFILE_META_INFO,
        APIFormView.as_view(formclass=FlatfileMetadataInfoForm)
    ),
    path(
        URLS.GET_GSIMS_FROM_REGION,
        APIFormView.as_view(formclass=GsimFromRegionForm)
    ),
    path(URLS.GET_GSIMS_INFO, GsimInfoView.as_view()),

    # test code returning specific response (in this case, no EgsimView required):
    path("test_response/<int:code>",
         csrf_exempt(lambda req, code: HttpResponse(b'test response msg', status=code))),

    # Fallback: return a 404 not-found HttpResponse (unlike Django, with empty content):
    re_path(r".*", csrf_exempt(NotFound.as_view()))
]
