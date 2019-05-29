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
from . import views


# for infor with trailing slashes:
# https://stackoverflow.com/questions/1596552/django-urls-without-a-trailing-slash-do-not-redirect

urlpatterns = [  # pylint: disable=invalid-name
    url(r'^admin/', admin.site.urls),  # added by default by django
    url(r'^$', RedirectView.as_view(pattern_name='main', url='home',
                                    permanent=False)),
    # main page entry point:
    url(r'^(?P<selected_menu>[a-zA-Z]+)/?$', views.main),

    # other urls called from within the page:
    url(r'^%s/?$' % views.URLS.HOME_PAGE, views.home),
    url(r'^%s/?$' % views.URLS.DOC_PAGE, views.apidoc),
    url(r'^%s/?$' % views.URLS.GSIMS_TR, views.get_tr_models),

    # download request urls:
    url(r'^%s/(?P<filename>.+)/?$' % views.URLS.TRELLIS_DOWNLOAD_REQ,
        views.download_request, {'formclass': views.TrellisView.formclass}),
    url(r'^%s/(?P<filename>.+)/?$' % views.URLS.TESTING_DOWNLOAD_REQ,
        views.download_request,  {'formclass': views.TestingView.formclass}),
    url(r'^%s/(?P<filename>.+)/?$' % views.URLS.RESIDUALS_DOWNLOAD_REQ,
        views.download_request,  {'formclass': views.ResidualsView.formclass}),

    # REST APIS:
    url(r'^%s/?$' % views.URLS.GSIMS_RESTAPI, views.GsimsView.as_view()),
    url(r'^%s/?$' % views.URLS.TRELLIS_RESTAPI, views.TrellisView.as_view()),
    url(r'^%s/?$' % views.URLS.RESIDUALS_RESTAPI, views.ResidualsView.as_view()),
    url(r'^%s/?$' % views.URLS.TESTING_RESTAPI, views.TestingView.as_view()),
    # this is not documented but used from frontend:
    url(r'^%s/?$' % views.URLS.GMDBPLOT_RESTAPI, views.GmdbPlotView.as_view()),

    # download as text:
    url(r'^%s/(?P<filename>.+)/?$' % views.URLS.TRELLIS_DOWNLOAD_ASTEXT,
        views.download_astext,
        {'viewclass': views.TrellisView}),
    url(r'^%s/(?P<filename>.+)/?$' % views.URLS.RESIDUALS_DOWNLOAD_ASTEXT,
        views.download_astext,
        {'viewclass': views.ResidualsView}),
    url(r'^%s/(?P<filename>.+)/?$' % views.URLS.TESTING_DOWNLOAD_ASTEXT,
        views.download_astext,
        {'viewclass': views.TestingView}),
    url(r'^%s/(?P<filename>.+)/?$' % views.URLS.TRELLIS_DOWNLOAD_ASTEXT_EU,
        views.download_astext,
        {'viewclass': views.TrellisView, 'text_sep': ';', 'text_dec': ','}),
    url(r'^%s/(?P<filename>.+)/?$' % views.URLS.RESIDUALS_DOWNLOAD_ASTEXT_EU,
        views.download_astext,
        {'viewclass': views.ResidualsView, 'text_sep': ';', 'text_dec': ','}),
    url(r'^%s/(?P<filename>.+)/?$' % views.URLS.TESTING_DOWNLOAD_ASTEXT_EU,
        views.download_astext,
        {'viewclass': views.TestingView, 'text_sep': ';', 'text_dec': ','}),

    # test stuff: (FIXME: REMOVE)
    url(r'___test_err', views.test_err),
]
