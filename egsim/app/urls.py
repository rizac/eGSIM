"""eGSIM URL Configuration for the Graphical User Interface (GUI)"""
from django.urls import re_path, path
from django.views.generic.base import RedirectView

from egsim.api.views import PredictionsView, ResidualsView, ModelInfoView
from .views import (main, get_gsims_from_region, flatfile_meta_info,
                    flatfile_visualize, flatfile_validate, URLS,
                    predictions_response_tutorial,
                    residuals_response_tutorial,
                    predictions_visualize, residuals_visualize,
                    plots_image, img_ext, data_ext, error_test_response)

# Watch out trailing slashes: https://stackoverflow.com/q/1596552

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
    path(URLS.PREDICTIONS_VISUALIZE, predictions_visualize),
    re_path(fr'{URLS.PREDICTIONS_PLOT_IMG}.(?:{"|".join(img_ext)})', plots_image),
    path(URLS.PREDICTIONS_RESPONSE_TUTORIAL, predictions_response_tutorial),

    re_path(
        r'^%s.(?:%s)$' % (URLS.RESIDUALS, "|".join(data_ext)),
        ResidualsView.as_view()
    ),  # note: `data_ext` in url is set and used only in the GUI as download filename
    path(URLS.RESIDUALS_VISUALIZE, residuals_visualize),
    re_path(fr'{URLS.RESIDUALS_PLOT_IMG}.(?:{"|".join(img_ext)})', plots_image),
    path(URLS.RESIDUALS_RESPONSE_TUTORIAL, residuals_response_tutorial),

    path(URLS.FLATFILE_VISUALIZE, flatfile_visualize),
    re_path(fr'{URLS.FLATFILE_PLOT_IMG}.(?:{"|".join(img_ext)})', plots_image),

    path(URLS.FLATFILE_VALIDATE, flatfile_validate),
    path(URLS.FLATFILE_META_INFO, flatfile_meta_info),
    path(URLS.GET_GSIMS_FROM_REGION, get_gsims_from_region),
    path(URLS.GET_GSIMS_INFO, ModelInfoView.as_view()),

    # test stuff:
    re_path(r'error_test', error_test_response)
]
