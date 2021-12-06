"""eGSIM URL Configuration"""

from django.urls import include, path

urlpatterns = [
    path('', include('egsim.api.urls')),
    path('', include('egsim.gui.urls')),
]