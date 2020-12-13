"""
Module to show the django app in the admin interface (address "<URL>/admin")
For info see:
https://stackoverflow.com/questions/1694259/django-app-not-showing-up-in-admin-interface

Created on Oct 7, 2020

@author: rizac
"""
import inspect

from django.contrib import admin
from django.db.models import Model

# from .models import (Gsim, Imt, Trt, TectonicRegion, Error)
from . import models as egsim_models_module


def _filter_func(obj):
    """filter function used below"""
    return inspect.isclass(obj) and issubclass(obj, Model) \
        and obj.__module__ == egsim_models_module.__name__


# register for admin app all Model instances in the egsim models module:
for name, cls in inspect.getmembers(egsim_models_module, _filter_func):
    # print(cls)
    admin.site.register(cls)
