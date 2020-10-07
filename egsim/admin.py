'''
Created on Oct 7, 2020

@author: rizac
'''
# https://stackoverflow.com/questions/1694259/django-app-not-showing-up-in-admin-interface
from django.contrib import admin
from .models import (Gsim, Imt, Trt, TectonicRegion, Error)

for _ in (Gsim, Imt, Trt, TectonicRegion, Error):
    print(_)
    admin.site.register(_)
