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
admin.site.register(models.GsimRegion)
admin.site.register(models.GsimWithError)
admin.site.register(models.Imt)
admin.site.register(models.Flatfile)
admin.site.register(models.FlatfileColumn)

# def get_classes(module: Union[str, "module"],
#                 class_or_tuple: Union[type, tuple[type]] = None,
#                 ignore_imported_classes: bool = True) -> dict[str, type]:
#     """Return all class(es) in a given module, matching the given criteria.
#     The returned object is a `dict[str, class]`, where values are the given
#     classes keyed by their name.
#
#     :param module: (str) the module name, usually accessible through the
#         variable `__name__`, or a Python module object
#     :param class_or_tuple: (type/class or tuple of types/classes) return only
#         classes that are the same as, or a subclass of any of the given
#         class(es). See builtin function `issubclass` for details.
#         None (the default when missing) means: no filter (take all classes)
#     :param ignore_imported_classes: bool (default True): return only those
#         classes directly implemented in the module, and not imported from some
#         other module
#     """
#     module_name = sys.modules[module] if isinstance(module, str) else module
#
#     def _filter(obj):
#         return _is_class(obj, module_name if ignore_imported_classes else None,
#                          class_or_tuple)
#
#     return {cls_name: cls for (cls_name, cls) in getmembers(module_name, _filter)}
#
#
# def _is_class(obj, module_name: str = None,
#               class_or_tuple: Union[type, tuple[type]] = None):
#     if isclass(obj):
#         if module_name is None or obj.__module__ == module_name:
#             if class_or_tuple is None or issubclass(obj, class_or_tuple):
#                 return True
#     return False
#
#
# # register for admin app all Model instances in the egsim models module:
# for name, cls in get_classes(models, Model).items():
#     if not cls._meta.abstract:  # noqa
#         admin.site.register(cls)
#         print('registering %s' % str(cls))
