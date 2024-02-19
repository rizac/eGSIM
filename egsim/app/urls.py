"""eGSIM URL Configuration for the Graphical User Interface (GUI)"""

from django.urls import re_path
from django.views.generic.base import RedirectView

from .views import (main, home, apidoc, download_request, download_response,
                    imprint, ref_and_license, get_gsims_from_region, flatfile_inspection,
                    flatfile_plot, flatfile_required_columns, URLS, TAB)

# Watch out trailing slashes: https://stackoverflow.com/q/1596552

urlpatterns = [
    re_path(r'^$', RedirectView.as_view(pattern_name='main', url='home',
                                        permanent=False)),

    # main page entry point, valid for all urls implemented in views.KEY:
    re_path(r'^(?P<selected_menu>%s)/?$' % "|".join(_.name for _ in TAB), main),
    # FIXME REMOVE BELOW
    # re_path(r'%s/?' % URLS.MAIN_PAGE_INIT_DATA, main_page_init_data),

    # Imprint, refs (pages with a "normal" static django template associated):
    re_path(r'^%s/?$' % URLS.IMPRINT, imprint),

    # other urls called from within the page:
    re_path(r'^%s/?$' % URLS.HOME_NO_MENU, home),
    re_path(r'^%s/?$' % URLS.API, apidoc),
    re_path(r'^%s/?$' % URLS.REF_AND_LICENSE, ref_and_license),

    # download request data (json, yaml) urls:
    re_path(r'^%s/(?P<key>.+?)/(?P<filename>.+)$' % URLS.DOWNLOAD_REQUEST,
            download_request),

    # download response (json, csv, png, svg, ...) urls:
    re_path(r'^%s/(?P<key>.+?)/(?P<filename>.+)$' % URLS.DOWNLOAD_RESPONSE,
            download_response),

    re_path(r'^%s/?$' % URLS.GET_GSIMS_FROM_REGION, get_gsims_from_region),
    re_path(r'^%s/?$' % URLS.FLATFILE_INSPECTION, flatfile_inspection),
    re_path(r'^%s/?$' % URLS.FLATFILE_REQUIRED_COLUMNS, flatfile_required_columns),
    re_path(r'^%s/?$' % URLS.FLATFILE_PLOT, flatfile_plot),

    # test stuff: (FIXME: REMOVE)
    # url(r'_test_err', _test_err),
]
