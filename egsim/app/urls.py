"""eGSIM URL Configuration for the Graphical User Interface (GUI)"""

from django.urls import re_path
from django.views.generic.base import RedirectView

from egsim.api.views import TrellisView, ResidualsView
from .views import (main, get_gsims_from_region, flatfile_inspection,
                    flatfile_plot, flatfile_required_columns, URLS, test_request,
                    get_predictions_response_tutorial, get_residuals_response_tutorial)

# Watch out trailing slashes: https://stackoverflow.com/q/1596552

urlpatterns = [
    re_path(r'^$', RedirectView.as_view(pattern_name='main', url='home',
                                        permanent=False)),

    # html pages:
    re_path((r'^(?P<page>' +
             '|'.join([URLS.HOME_PAGE, URLS.PREDICTIONS_PAGE, URLS.RESIDUALS_PAGE,
                       URLS.FLATFILE_VISUALIZER_PAGE, URLS.FLATFILE_INFO_PAGE,
                       URLS.IMPRINT_PAGE, URLS.REF_AND_LICENSE_PAGE]) +
             ')/?$'), main),

    re_path(r'^%s/?$' % URLS.RESIDUALS_RESPONSE_TUTORIAL_HTML,
            get_residuals_response_tutorial),
    re_path(r'^%s/?$' % URLS.PREDICTIONS_RESPONSE_TUTORIAL_HTML,
            get_predictions_response_tutorial),

    # FIXME REMOVE CLEANUP
    # re_path(r'%s/?' % URLS.MAIN_PAGE_INIT_DATA, main_page_init_data),

    # Imprint, refs (pages with a "normal" static django template associated):
    # re_path(r'^%s/?$' % URLS.IMPRINT, imprint),

    # other urls called from within the page:
    # re_path(r'^%s/?$' % URLS.HOME_NO_MENU, home),
    # re_path(r'^%s/?$' % URLS.API, apidoc),
    # re_path(r'^%s/?$' % URLS.REF_AND_LICENSE, ref_and_license),

    # download request data (json, yaml) urls:
    # re_path(r'^%s/(?P<key>.+?)/(?P<filename>.+)$' % URLS.DOWNLOAD_REQUEST,
    #         download_request),

    # download response (json, csv, png, svg, ...) urls:
    # re_path(r'^%s/(?P<key>.+?)/(?P<filename>.+)$' % URLS.DOWNLOAD_RESPONSE,
    #         download_response),
    re_path(r'^%s/?$' % URLS.DOWNLOAD_PREDICTIONS, TrellisView.as_view()),
    re_path(r'^%s/?$' % URLS.DOWNLOAD_RESIDUALS, ResidualsView.as_view()),

    re_path(r'^%s/?$' % URLS.GET_GSIMS_FROM_REGION, get_gsims_from_region),
    re_path(r'^%s/?$' % URLS.FLATFILE_INSPECTION, flatfile_inspection),
    # re_path(r'^%s/?$' % URLS.FLATFILE_REQUIRED_COLUMNS, flatfile_required_columns),
    # re_path(r'^%s/?$' % URLS.FLATFILE_PLOT, flatfile_plot),

    # test stuff: (FIXME: REMOVE)
    # url(r'_test_err', _test_err),
    re_path(r'test_request', test_request)
]
