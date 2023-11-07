"""
Models for the django app

Created on 5 Apr 2019

@author: riccardo
"""
from django.db.models import (Model as DjangoDbModel, TextField, BooleanField,
                              Index, URLField, Manager, QuerySet)
from django.db.models.options import Options


# Notes: primary keys are auto added if not present ('id' of type BigInt or so).
# All models here that are not abstract will be available prefixed with 'api_'
# in the admin panel (https://<site_url>/admin)


class EgsimManager(Manager):
    """Defines a base custom manager filtering out hidden elements. Details here:
    https://docs.djangoproject.com/en/stable/topics/db/managers
    """
    def get_queryset(self):
        return super().get_queryset().filter(hidden=False)


class EgsimDbModel(DjangoDbModel):
    """Abstract base class of Egsim Db models"""

    # Explicitly set the `objects` `Manager` that does not return hidden elements:
    objects = EgsimManager()
    # _meta is dynamically set by Django. declare it here just to silent lint warnings:
    _meta: Options

    name = TextField(null=False, unique=True, help_text="Unique name")
    hidden = BooleanField(default=False,
                          help_text="Hide this item. This will make the item publicly "
                                    "unavailable through the `names`"
                                    "and `items` properties (which are supposed to be "
                                    "used to publicly expose API). This field is "
                                    "intended to temporarily hide/show items quickly "
                                    "from the admin panel without executing management "
                                    "scrips")
    class Meta:
        abstract = True
        # index the name attr:
        indexes = [Index(fields=['name']), ]

    @property
    def names(self) -> QuerySet[str]:
        """Return all the names of the items (db rows) of this model, filtering out
        hidden rows."""
        return self.objects.only('name').values_list('name', flat=True)

    def __str__(self):
        return self.name


class Gsim(EgsimDbModel):
    """The Ground Shaking Intensity Models (GSIMs) available in eGSIM. This table
    simply makes responses faster when querying all available and valid models"""

    unverified = BooleanField(default=False, help_text="not independently verified")
    experimental = BooleanField(default=False, help_text="experimental, may "
                                                         "change in future versions")
    adapted = BooleanField(default=False, help_text="not intended for general use, "
                                                    "the behaviour may not be "
                                                    "as expected")
    # Note: `superseded_by` is not used (we do not save deprecated Gsims)


class Citable(DjangoDbModel):
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


class DataFile(EgsimDbModel):
    """Abstract class handling any data file used by eGSIM"""
    # Note: the unique name is usually used as display name in GUIs
    filepath = TextField(unique=True, null=False)

    class Meta:
        abstract = True

    def __str__(self):
        """string representation of this object"""
        return f'{self.name} ({self.filepath})'


class Flatfile(DataFile, Citable):
    """Class handling flatfiles stored in the file system
    (predefined flatfiles)
    """
    pass


class Regionalization(DataFile, Citable):
    """Class handling flatfiles stored in the file system
    (predefined flatfiles)
    """
    pass
