"""eGSIM URL Configuration for the Graphical User Interface (GUI)"""
from django.urls import re_path
from django.views.generic.base import RedirectView

from egsim.api.views import TrellisView, ResidualsView
from .views import (main, get_gsims_from_region, flatfile_meta_info,
                    flatfile_visualize, flatfile_validate, URLS, test_request,
                    get_predictions_response_tutorial,
                    get_residuals_response_tutorial,
                    predictions_visualize, residuals_visualize,
                    download_plots_as_image, img_ext, data_ext)

# Watch out trailing slashes: https://stackoverflow.com/q/1596552

urlpatterns = [
    re_path(r'^$', RedirectView.as_view(pattern_name='main', url='home',
                                        permanent=False)),
    re_path((r'^(?P<page>' +
             '|'.join([URLS.HOME_PAGE, URLS.PREDICTIONS_PAGE, URLS.RESIDUALS_PAGE,
                       URLS.FLATFILE_INSPECTION_PLOT_PAGE, URLS.FLATFILE_META_INFO_PAGE,
                       URLS.IMPRINT_PAGE, URLS.REF_AND_LICENSE_PAGE]) +
             ')/?$'), main),

    re_path(r'^%s.(?:%s)$' % (URLS.PREDICTIONS, "|".join(data_ext)),
            TrellisView.as_view()),
    re_path(r'^%s$' % URLS.PREDICTIONS_VISUALIZE, predictions_visualize),
    *[re_path(r'^%s.%s$' % (URLS.PREDICTIONS_PLOT_IMG, ext), download_plots_as_image)
      for ext in img_ext],
    re_path(r'^%s/?$' % URLS.PREDICTIONS_RESPONSE_TUTORIAL,
            get_predictions_response_tutorial),

    re_path(r'^%s.(?:%s)$' % (URLS.RESIDUALS, "|".join(data_ext)),
            ResidualsView.as_view()),
    re_path(r'^%s$' % URLS.RESIDUALS_VISUALIZE, residuals_visualize),
    *[re_path(r'^%s.%s$' % (URLS.RESIDUALS_PLOT_IMG, ext), download_plots_as_image)
      for ext in img_ext],
    re_path(r'^%s/?$' % URLS.RESIDUALS_RESPONSE_TUTORIAL,
            get_residuals_response_tutorial),

    re_path(r'^%s/?$' % URLS.FLATFILE_VISUALIZE, flatfile_visualize),
    *[re_path(r'^%s.%s$' % (URLS.FLATFILE_PLOT_IMG, ext), download_plots_as_image)
      for ext in img_ext],

    re_path(r'^%s/?$' % URLS.FLATFILE_VALIDATE, flatfile_validate),
    re_path(r'^%s/?$' % URLS.FLATFILE_META_INFO, flatfile_meta_info),
    re_path(r'^%s/?$' % URLS.GET_GSIMS_FROM_REGION, get_gsims_from_region),

    # test stuff: (FIXME: REMOVE)
    # url(r'_test_err', _test_err),
    re_path(r'test_request', test_request)
]
