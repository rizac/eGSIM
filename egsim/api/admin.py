"""
Module to show the django app in the admin interface (address "<URL>/admin")
For details see:
https://stackoverflow.com/questions/1694259/django-app-not-showing-up-in-admin-interface

Created on Oct 7, 2020

@author: rizac
"""
# from typing import Union
# import sys
# from inspect import getmembers, isclass
# from django.db.models import Model

from django.contrib import admin

from ..api import models

admin.site.register(models.Gsim)
admin.site.register(models.GsimWithError)
admin.site.register(models.GsimRegion)
admin.site.register(models.Regionalization)
admin.site.register(models.Imt)
admin.site.register(models.Flatfile)
admin.site.register(models.FlatfileColumn)
