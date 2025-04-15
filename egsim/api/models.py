"""
Models for the django app

Created on 5 Apr 2019

@author: riccardo
"""
from __future__ import annotations
from typing import Any, Self

from django.db.models import (Model as DjangoDbModel, TextField, BooleanField,
                              Index, URLField, Manager, QuerySet, FloatField)
from django.db.models.options import Options


# Notes: primary keys are auto added if not present ('id' of type BigInt or so).
# All models here that are not abstract will be available prefixed with 'api_'
# in the admin panel (https://<site_url>/admin)


class EgsimDbModel(DjangoDbModel):
    """Abstract base class of Egsim Db models"""

    # attrs dynamically set by Django. declared here just to silent lint warnings:
    # (NOTE: `objects` SHOULD BE USED INTERNALLY, see `queryset` docstring for details)
    objects: Manager  # https://docs.djangoproject.com/en/stable/topics/db/managers
    _meta: Options  # https://docs.djangoproject.com/en/stable/ref/models/options/

    name = TextField(null=False, unique=True, help_text="Unique name")
    hidden = BooleanField(default=False, null=False,
                          help_text="Hide this item, i.e. make it publicly "
                                    "unavailable to the whole API. This field "
                                    "is intended to hide/show items quickly from "
                                    "the admin panel without executing management "
                                    "scrips")

    class Meta:
        abstract = True
        # does this speed up searches?:
        indexes = [Index(fields=['name']), Index(fields=['hidden'])]

    def __str__(self):
        return self.name

    @classmethod
    def queryset(cls, *only) -> QuerySet[Self]:
        """Return a QuerySet of all visible model instances. This method calls
        `cls.objects.filter(hidden=False)` and should be used to serve model data
        in the API instead of `cls.objects`. The latter should be used for internal
        operations only, e.g., in a management command where we want to empty a table
        (including hidden elements): `cls.objects.all().delete()`

        :param only: the fields to load from the DB for each instance, e.g. 'name'
            (the `str` uniquely denoting the instance). Empty (the default) will
            load all instance fields
        """
        queryset = cls.objects if not only else cls.objects.only(*only)
        return queryset.filter(hidden=False)

    @classmethod
    def names(cls) -> QuerySet[str]:
        """Return a QuerySet yielding all instance unique names (`str`)"""
        return cls.queryset('name').values_list('name', flat=True)


class Gsim(EgsimDbModel):
    """The Ground Shaking Intensity Models (GSIMs) available in eGSIM. This table
    is populated with valid OpenQuake models only (`passing valid.gsim` or not
    deprecated)
    """
    imts = TextField(null=False,
                     help_text='The intensity measure types '
                               'defined for the model, space separated '
                               '(e.g.: "PGA SA")')
    min_sa_period = FloatField(null=True,
                               help_text='The minimum SA period supported '
                                         'by the model, or None (no lower limit)')
    max_sa_period = FloatField(null=True,
                               help_text='The maximum SA period supported '
                                         'by the model, or None (no upper limit)')

    unverified = BooleanField(default=False, help_text="not independently verified")
    experimental = BooleanField(default=False, help_text="experimental: may "
                                                         "change in future versions")
    adapted = BooleanField(default=False, help_text="not intended for general use: "
                                                    "the behaviour may not be "
                                                    "as expected")
    # Note: `superseded_by` is not used (we do not save deprecated Gsims)


class Reference(DjangoDbModel):
    """Abstract class for Table rows representing a reference to some work
    (e.g. data, file, article)"""

    display_name = TextField(default=None, null=True)
    url = URLField(default=None, null=True)
    license = TextField(default=None, null=True)
    citation = TextField(default=None, null=True,
                         help_text="Bibliographic citation, as text")
    doi = TextField(default=None, null=True)

    class Meta:
        abstract = True


class MediaFile(EgsimDbModel):
    """Abstract class handling any data file in the MEDIA directory of eGSIM"""
    # for safety, do not store full file paths in the db (see `filepath` for details):
    filepath = TextField(unique=True, null=False,
                         help_text="the file absolute path (usually within the "
                                   "MEDIA_ROOT path defined in Django settings)")

    def read_from_filepath(self, **kwargs) -> Any:
        raise NotImplementedError()

    class Meta:
        abstract = True

    def __str__(self):
        """string representation of this object"""
        return f'{self.name} ({self.filepath})'


class Flatfile(MediaFile, Reference):
    """Class handling flatfiles stored in the file system. For each row of this table,
    the associated media file is an HDF file representing a valid flatfile (pandas
    DataFrame)
    """

    def read_from_filepath(self, **kwargs) -> Any:
        """Return this instance media file as flatfile (pandas DataFrame)

        @param kwargs: additional arguments to pandas `read_hdf` ('key' will
            be set in this function if not given)
        """
        from pandas import read_hdf
        kwargs.setdefault('key', self.name)
        return read_hdf(self.filepath, **kwargs)


class Regionalization(MediaFile, Reference):
    """Class handling regionalizations stored in the file system. A regionalization
    is a collection of regions, where each region is an object denoted by:
     - a geometry (e.g. a Polygon enclosed by poitns in (lat, lon) coordinates), 
     - a unique name (identifier) 
     - a list of ground shaking models selected for the region.
    For each row of this table, the associated media file is a geoJSON file where a 
    regionalization is stored as FeatureCollection object, and each region is a 
    geoJSON Feature object. E.g.:
    ```
    {
        "type": 'FeatureCollection',
        "features" : [
            {
                "type": "Feature",
                "geometry": list,
                "properties": {
                    "region": str,
                    "models": list[str],
                    ...
                }
            },
            ...
        ]
    }
    ```
    Note for developers:. See `read_from_filepath` to convert a Feature
    geometry to a shapely `shape` object
    """  # noqa

    def read_from_filepath(self, **kwargs) -> dict:
        """Return this instance media file as geoJSON FeatureCollection object (dict).
        To convert each Feature geometry to a shapely `shape` object:
        ```python
        from shapely.geometry import shape
        feature_collection = self.read_from_filepath()
        for feat in feature_collection['features']:
            feat['geometry'] = shape(feat['geometry'])
        ```

        @param kwargs: additional arguments to `json.load`
        """  # noqa
        import json
        with open(self.filepath, 'r') as _:
            return json.load(_, **kwargs)
