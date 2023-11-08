"""
Models for the django app

Created on 5 Apr 2019

@author: riccardo
"""
from django.db.models import (Model as DjangoDbModel, TextField, BooleanField,
                              Index, URLField, Manager, QuerySet)
from django.db.models.options import Options
from os.path import abspath, join, isabs, relpath


# Notes: primary keys are auto added if not present ('id' of type BigInt or so).
# All models here that are not abstract will be available prefixed with 'api_'
# in the admin panel (https://<site_url>/admin)


class EgsimDbModel(DjangoDbModel):
    """Abstract base class of Egsim Db models"""

    # attrs dynamically set by Django. declare them here just to silent lint warnings:
    objects: Manager  # https://docs.djangoproject.com/en/stable/topics/db/managers
    _meta: Options  # https://docs.djangoproject.com/en/stable/ref/models/options/

    name = TextField(null=False, unique=True, help_text="Unique name")
    hidden = BooleanField(default=False, null=False,
                          help_text="Hide this item, i.e. make it publicly "
                                    "unavailable through the `names` property "
                                    "and as such, to the whole API. This field "
                                    "is intended to hide/show items quickly from "
                                    "the admin panel without executing management "
                                    "scrips")
    class Meta:
        abstract = True
        # does this speed up searches?:
        indexes = [Index(fields=['name']), Index(fields=['hidden'])]

    @property
    def names(self) -> QuerySet[str]:
        """Return all the names of the items (db rows) of this model, filtering out
        hidden rows"""
        return self.objects.only('name').filter(hidden=False).\
            values_list('name', flat=True)

    def hidden_elements(self, names: list[str]) -> QuerySet[str]:
        """Return which of the given name(s) is hidden"""
        return self.objects.filter(name__in=names).filter(hidden=True).\
            only('name').values_list('name', flat=True)

    def __str__(self):
        return self.name


class Gsim(EgsimDbModel):
    """The Ground Shaking Intensity Models (GSIMs) available in eGSIM. This table
    is populated with valid OpenQuake models only (`passing valid.gsim` or not
    deprecated)
    """

    unverified = BooleanField(default=False, help_text="not independently verified")
    experimental = BooleanField(default=False, help_text="experimental, may "
                                                         "change in future versions")
    adapted = BooleanField(default=False, help_text="not intended for general use, "
                                                    "the behaviour may not be "
                                                    "as expected")
    # Note: `superseded_by` is not used (we do not save deprecated Gsims)


class Reference(DjangoDbModel):
    """Abstract class for Table rows representing a reference, with any info
    such as URL, license, bib. citation"""

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
    media_root_path = TextField(unique=True, null=False,
                                help_text="the file path, relative to the media "
                                          "root directory defined in the settings"
                                          "file")

    @property
    def filepath(self):
        """Return the absolute file path of this data file"""
        from django.conf import settings
        return abspath(join(settings.MEDIA_ROOT, self.media_root_path))  # noqa

    def save(self, *a, **kw):
        """Assure `media_root_path` is relative to the current settings
        MEDIA_ROOT and save instance calling super method"""
        from django.conf import settings
        if isabs(self.media_root_path):  # noqa
            self.media_root_path = relpath(self.media_root_path,  # noqa
                                           settings.MEDIA_ROOT)
        super().save(*a, **kw)

    class Meta:
        abstract = True

    def __str__(self):
        """string representation of this object"""
        return f'{self.name} ({self.filepath})'


class Flatfile(MediaFile, Reference):
    """Class handling flatfiles stored in the file system"""


class Regionalization(MediaFile, Reference):
    """Class handling regionalizations stored in the file system"""
