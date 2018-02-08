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
from . import views

urlpatterns = [
    url(r'^admin/', admin.site.urls),  # added by default by django
    url(r'^$', views.index, name = 'index'), # main page entry point
    url(r'get_init_params', views.get_init_params),  #, name = 'index'), # main page entry point
    url(r'validate_trellis_input', views.validate_trellis_input),  #, name = 'index'), # main page entry point
    url(r'get_trellis_plots', views.get_trellis_plots),  #, name = 'index'), # main page entry point
    
]
