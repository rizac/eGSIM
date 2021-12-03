"""eGSIM RESTAPI URL Configuration"""
from django.conf.urls import url  # added by default by django
# from django.contrib import admin  # added by default by django
# from django.views.generic.base import RedirectView
# from django.shortcuts import render
from re import escape as esc

# from egsim.gui import (URLS, TABS)
from .views import TrellisView, ResidualsView, TestingView
# from egsim.gui.views import (main, home, apidoc, download_request,
                             # download_astext, download_asimage, imprint)

# Watch out trailing slashes:
# https://stackoverflow.com/questions/1596552/django-urls-without-a-trailing-slash-do-not-redirect


urlpatterns = [
    *[url(r'^%s/?$' % esc(_), TrellisView.as_view()) for _ in TrellisView.urls],
    *[url(r'^%s/?$' % esc(_), ResidualsView.as_view()) for _ in ResidualsView.urls],
    *[url(r'^%s/?$' % esc(_), TestingView.as_view()) for _ in TestingView.urls],

    # *[
    #     url(r'^%s/?$' % re.escape(_), cls.as_view())
    #     for cls in (TrellisView, ResidualsView, TestingView) for _ in cls.urls
    # ],

    # FIXME REMOVE
    # # GUI URLs:
    # url(r'^admin/', admin.site.urls),  # added by default by django
    # url(r'^$', RedirectView.as_view(pattern_name='main', url='home',
    #                                 permanent=False)),
    #
    # # main page entry point, valid for all urls implemented in views.KEY:
    # url(r'^(?P<selected_menu>%s)/?$' % "|".join(_.name for _ in TABS), main),
    #
    # # Imprint, refs (pages with a "normal" static django template associated):
    # url(r'imprint', imprint),
    #
    # # other urls called from within the page:
    # url(r'^%s/?$' % URLS.HOME_PAGE, home),
    # url(r'^%s/?$' % URLS.DOC_PAGE, apidoc),
    #
    # # download config (=request) urls:
    # url(r'^%s/(?P<key>.+?)/(?P<filename>.+)/?$' % URLS.DOWNLOAD_CFG,
    #     download_request),
    # # download as text:
    # url(r'^%s/(?P<key>.+?)/(?P<filename>.+)/?$' % URLS.DOWNLOAD_ASTEXT,
    #     download_astext),
    # url(r'^%s/(?P<key>.+?)/(?P<filename>.+)/?$' % URLS.DOWNLOAD_ASTEXT_EU,
    #     download_astext, {'text_sep': ';', 'text_dec': ','}),
    # # donwload as image:
    # url(r'^%s/(?P<filename>.+)/?$' % URLS.DOWNLOAD_ASIMG, download_asimage)
    #
    # # test stuff: (FIXME: REMOVE)
    # # url(r'_test_err', _test_err),
]
