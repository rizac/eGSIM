"""eGSIM URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.conf.urls import url  # added by default by django
from django.contrib import admin  # added by default by django
from django.views.generic.base import RedirectView
# from django.shortcuts import render

from egsim.views import (URLS, KEY, main, home, apidoc, get_tr_models,
                         download_request, download_astext, download_asimage,
                         TrellisView, GsimsView, ResidualsView, GmdbPlotView,
                         TestingView, imprint, refs)

# for infor with trailing slashes:
# https://stackoverflow.com/questions/1596552/django-urls-without-a-trailing-slash-do-not-redirect

urlpatterns = [  # pylint: disable=invalid-name
    url(r'^admin/', admin.site.urls),  # added by default by django
    url(r'^$', RedirectView.as_view(pattern_name='main', url='home',
                                    permanent=False)),

    # main page entry point, valid for all urls implemented in views.KEY:
    url(r'^(?P<selected_menu>%s)/?$' %
        "|".join(getattr(KEY, _) for _ in dir(KEY) if _[:1] != '_'), main),

    # Imprint, refs (pages with a "normal" static django template associated):
    url(r'imprint', imprint),
    url(r'references', refs),

    # other urls called from within the page:
    url(r'^%s/?$' % URLS.HOME_PAGE, home),
    url(r'^%s/?$' % URLS.DOC_PAGE, apidoc),
    url(r'^%s/?$' % URLS.GSIMS_TR, get_tr_models),

    # REST APIS:
    url(r'^%s/?$' % URLS.GSIMS_RESTAPI, GsimsView.as_view()),
    url(r'^%s/?$' % URLS.TRELLIS_RESTAPI, TrellisView.as_view()),
    url(r'^%s/?$' % URLS.RESIDUALS_RESTAPI, ResidualsView.as_view()),
    url(r'^%s/?$' % URLS.TESTING_RESTAPI, TestingView.as_view()),
    # this is not documented but used from frontend:
    url(r'^%s/?$' % URLS.GMDBPLOT_RESTAPI, GmdbPlotView.as_view()),

    # download config (=request) urls:
    url(r'^%s/(?P<key>.+?)/(?P<filename>.+)/?$' % URLS.DOWNLOAD_CFG,
        download_request),
    # download as text:
    url(r'^%s/(?P<key>.+?)/(?P<filename>.+)/?$' % URLS.DOWNLOAD_ASTEXT,
        download_astext),
    url(r'^%s/(?P<key>.+?)/(?P<filename>.+)/?$' % URLS.DOWNLOAD_ASTEXT_EU,
        download_astext, {'text_sep': ';', 'text_dec': ','}),
    # donwload as image:
    url(r'^%s/(?P<filename>.+)/?$' % URLS.DOWNLOAD_ASIMG, download_asimage)

    # test stuff: (FIXME: REMOVE)
    # url(r'_test_err', _test_err),
]
