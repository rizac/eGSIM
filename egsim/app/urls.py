"""eGSIM URL Configuration for the Graphical User Interface (GUI)"""

from django.conf.urls import url  # added by default by django
from django.views.generic.base import RedirectView

from . import URLS, TAB
from .views import (main, home, apidoc, download_request, download_response,
                    imprint, ref_and_license, get_gsims_from_region, flatfile_inspection,
                    flatfile_plot, flatfile_required_columns, main_page_init_data)

# Watch out trailing slashes: https://stackoverflow.com/q/1596552

urlpatterns = [
    url(r'^$', RedirectView.as_view(pattern_name='main', url='home',
                                    permanent=False)),

    # main page entry point, valid for all urls implemented in views.KEY:
    url(r'^(?P<selected_menu>%s)/?$' % "|".join(_.name for _ in TAB), main),
    url(r'init_data/?', main_page_init_data),

    # Imprint, refs (pages with a "normal" static django template associated):
    url(r'^%s/?$' % URLS.IMPRINT, imprint),

    # other urls called from within the page:
    url(r'^%s/?$' % URLS.HOME_NO_MENU, home),
    url(r'^%s/?$' % URLS.API, apidoc),
    url(r'^%s/?$' % URLS.REF_AND_LICENSE, ref_and_license),

    # download request data (json, yaml) urls:
    url(r'^%s/(?P<key>.+?)/(?P<filename>.+)$' % URLS.DOWNLOAD_REQUEST,
        download_request),

    # download response (json, csv, png, svg, ...) urls:
    url(r'^%s/(?P<key>.+?)/(?P<filename>.+)$' % URLS.DOWNLOAD_RESPONSE,
        download_response),

    url(r'^%s/?$' % URLS.GET_GSIMS_FROM_REGION, get_gsims_from_region),
    url(r'^%s/?$' % URLS.FLATFILE_INSPECTION, flatfile_inspection),
    url(r'^%s/?$' % URLS.FLATFILE_REQUIRED_COLUMNS, flatfile_required_columns),
    url(r'^%s/?$' % URLS.FLATFILE_PLOT, flatfile_plot),

    # test stuff: (FIXME: REMOVE)
    # url(r'_test_err', _test_err),
]
