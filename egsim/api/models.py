"""
Models for the django app

Created on 5 Apr 2019

@author: riccardo
"""
from enum import IntFlag, auto

from django.db.models import (Model as DjangoModel, TextField, BooleanField,
                              Index, URLField, Manager, QuerySet, IntegerField)
from django.db.models.options import Options


# Notes: primary keys are auto added if not present ('id' of type BigInt or so).
# All models here that are not abstract will be available prefixed with 'api_'
# in the admin panel (https://<site_url>/admin)


class Model(DjangoModel):
    """Abstract base class of all Django Models of this module"""

    # these two attributes are set by Django (see metaclass for details) and are here
    # only to silent lint warnings
    objects: Manager
    _meta: Options

    class Meta:
        # this attr makes this class abstract but note it's not inherited in subclasses,
        # where it will be False by default:
        abstract = True


class _UniqueName(Model):
    """Abstract class for Table entries identified by a single unique name"""

    name = TextField(null=False, unique=True, help_text="Unique name")

    class Meta:
        abstract = True
        # index the name attr:
        indexes = [Index(fields=['name']), ]

    @property
    def names(self) -> QuerySet[str]:
        return self.objects.only('name').values_list('name', flat=True)

    def __str__(self):
        return self.name


class _Citable(Model):
    """Abstract class for Table rows which can be cited, e.g. with any info
    such as URL, license, bib. citation"""

    display_name = TextField(default=None, null=True)
    url = URLField(default=None, null=True)
    license = TextField(default=None, null=True)
    citation = TextField(default=None, null=True,
                         help_text="Bibliographic citation, as text")
    doi = TextField(default=None, null=True)

    class Meta:
        abstract = True


class _DataFile(_UniqueName):
    """Class handling any data file used by eGSIM"""
    # Note: the unique name is usually used as display name in GUIs
    filepath = TextField(unique=True, null=False)

    class Meta:
        abstract = True

    def __str__(self):
        """string representation of this object"""
        return f'{self.name} ({self.filepath})'


class Flatfile(_UniqueName, _Citable, _DataFile):
    """Class handling flatfiles stored in the file system
    (predefined flatfiles)
    """

class Regionalization(_UniqueName, _Citable, _DataFile):
    """Class handling flatfiles stored in the file system
    (predefined flatfiles)
    """


class Gsim(_UniqueName):
    """The Ground Shaking Intensity Models (GSIMs) available in eGSIM"""
    # Note: we use a DB table to check beforehand which models can be initialized
    # and made available, saving up to 1-2 sec of time for each request

    class Attr(IntFlag):
        # superseded_by = auto()
        unverified = auto()
        experimental = auto()
        adapted = auto()

    special_attributes = \
        IntegerField(default=0, null=False,
                     choices=[(0, '')] + [(Attr(a), Attr(a).name.replace('|', ', '))
                                          for a in range(1, 2 ** len(Attr))],
                     help_text='Model special attribute(s)')

    class Meta(_UniqueName.Meta):
        indexes = [Index(fields=['name']), ]

