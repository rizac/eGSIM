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
    url(r'^(?P<selected_menu>[a-zA-Z]+)/?$', views.main, name='main'),

    # other urls called from within the page:
    url(r'^pages/home/?$', views.home, name='home'),
    url(r'^pages/apidoc/?$', views.apidoc, name='apidoc'),
    url(r'^data/tr_models', views.get_tr_models),

    # download request urls:
    url(r'^data/%s/downloadrequest/(?P<filename>.+)/?$' %
        views.api_url(views.KEY.TRELLIS),
        views.download_request, {'formclass': views.TrellisView.formclass}),
    url(r'^data/query/%s/downloadrequest/(?P<filename>.+)/?$' %
        views.api_url(views.KEY.TEST),
        views.download_request,  {'formclass': views.TestingView.formclass}),
    url(r'^data/query/%s/downloadrequest/(?P<filename>.+)/?$' %
        views.api_url(views.KEY.RES),
        views.download_request,  {'formclass': views.ResidualsView.formclass}),

    # REST APIS:
    url(r'^%s/?$' % views.api_url(views.KEY.GSIMS),
        views.GsimsView.as_view()),
    url(r'^%s/?$' % views.api_url(views.KEY.TRELLIS),
        views.TrellisView.as_view()),
    url(r'^%s/?$' % views.api_url(views.KEY.RES),
        views.ResidualsView.as_view()),
    url(r'^%s/?$' % views.api_url(views.KEY.TEST),
        views.TestingView.as_view()),

    # test stuff: (FIXME: REMOVE)
    url(r'test_err', views.test_err),
]
