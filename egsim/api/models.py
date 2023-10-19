"""
Models for the django app

Created on 5 Apr 2019

@author: riccardo
"""
import json
from datetime import datetime

from django.db.models import (Model as DjangoModel, Q, TextField, BooleanField,
                              ForeignKey, ManyToManyField, JSONField, UniqueConstraint,
                              CASCADE, SET_NULL, Index,
                              DateTimeField, URLField, Manager, CharField)
from django.db.models.options import Options

from egsim.smtk.flatfile.columns import ColumnType

# Notes: primary keys are auto added if not present ('id' of type BigInt or so).
# All models here that are not abstract will be available prefixed with 'api_'
# in the admin panel (https://<site_url>/admin)


class Model(DjangoModel):
    """Abstract base class of all Django Models of this module"""

    # these two attributes are set by Django (see metaclass for details) and are here
    # only to silent lint warnings
    objects: Manager
    _meta: Options

    class Meta:  # make this class abstract
        abstract = True


class _UniqueName(Model):
    """Abstract class for Table entries identified by a single unique name"""

    name = TextField(null=False, unique=True, help_text="Unique name")

    class Meta:
        # In subclasses, `abstract` is (re)set to False. Everything else is copied
        # (https://docs.djangoproject.com/en/3.2/topics/db/models/#meta-inheritance)
        abstract = True

    @property
    def names(self):
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
        # In subclasses, `abstract` is (re)set to False. Everything else is copied
        # (https://docs.djangoproject.com/en/3.2/topics/db/models/#meta-inheritance)
        abstract = True


class Flatfile(_UniqueName, _Citable):
    """Class handling flatfiles stored in the file system
    (predefined flatfiles)
    """
    filepath = TextField(unique=True, null=False)
    hidden = BooleanField(null=False, default=False,
                          help_text="if true, the flatfile is hidden in browsers "
                                    "(users can still access it via API requests, "
                                    "if not expired)")
    expiration = DateTimeField(null=True, default=None,
                               help_text="expiration date(time). If null, the "
                                         "flatfile has no expiration date")

    @classmethod
    def get_flatfiles(cls, hidden=False, expired=False):
        qry = cls.objects  # noqa
        if not expired:
            qry = qry.filter(Q(expiration__isnull=True) |
                                     Q(expiration__lt=datetime.utcnow()))
        if not hidden:
            qry = qry.filter(hidden=False)
        return qry

    def __str__(self):
        """string representation of this object"""
        return f'{self.name} ({self.filepath})'


class CompactEncoder(json.JSONEncoder):
    """Compact JSON encoder used in JSONFields of this module"""
    def __init__(self, **kwargs):
        kwargs['separators'] = (',', ':')
        super().__init__(**kwargs)


class FlatfileColumn(_UniqueName):
    """Flat file column"""
    alias_of = TextField(null=True, help_text=('The alias, or null (meaning this'
                                               'is the primary name for the column'))
    description = JSONField(null=False, default='', help_text="Field description")

    class Meta(_UniqueName.Meta):
        indexes = [Index(fields=['name']), ]

    def __str__(self):
        return f'Column "{self.name}" ({self.get_type_display()} type)'  # noqa


class Imt(_UniqueName):
    """The :mod:`intensity measure types <openquake.hazardlib.imt>` that
    OpenQuake's GSIMs can calculate and that are supported in eGSIM
    """
    needs_args = BooleanField(default=False, null=False)

    # OpenQuake's Gsim attribute used to populate this table during db init:
    OQ_ATTNAME = 'DEFINED_FOR_INTENSITY_MEASURE_TYPES'

    class Meta(_UniqueName.Meta):
        indexes = [Index(fields=['name']), ]


class Gsim(_UniqueName):
    """The Ground Shaking Intensity Models (GSIMs) implemented in OpenQuake and
    available in eGSIM
    """
    imts = ManyToManyField(Imt, related_name='gsims',
                           help_text='Intensity Measure Type(s)')
    required_flatfile_columns = ManyToManyField(FlatfileColumn,
                                                related_name='gsims',
                                                help_text='Required flatfile '
                                                          'column(s)')
    warning = TextField(default=None, null=True,
                        help_text='Optional usage warning(s) to be reported '
                                  'before usage (e.g., in GUIs)')

    class Meta(_UniqueName.Meta):
        indexes = [Index(fields=['name']), ]


class _GeoJsonRegion(Model):
    """Abstract class representing a db model with an associated Region
    in GeoJSON coordinates"""

    geometry = JSONField(null=False, encoder=CompactEncoder,
                         help_text="The region area as geoJSON Geometry object, "
                                   "with at least the keys \"coordinates\""
                                   f"and \"type'\" (usually 'Polygon', 'MultiPolygon')."
                                   f" For details see: "
                                   "https://en.wikipedia.org/wiki/GeoJSON#Geometries)")

    class Meta:  # make this class abstract
        abstract = True

class GsimRegion(_GeoJsonRegion):
    """Model representing a GSIM Region"""

    gsim = ForeignKey(Gsim, on_delete=CASCADE, null=False, related_name='regions')
    regionalization = ForeignKey("Regionalization", to_field='name',
                                 on_delete=SET_NULL, null=True,
                                 help_text="The name of the seismic hazard source "
                                           "regionalization that defines and includes "
                                           "this region")
    class Meta:
        constraints = [UniqueConstraint(fields=['gsim', 'regionalization'],
                                        name='%(app_label)s_%(class)s_unique_'
                                             'gsim_and_regionalization')]

    def __str__(self):
        typ = self.geometry.get('type', "unknown")  # noqa
        return f'Region (type {typ}), model: {str(self.gsim)}, ' \
               f'regionalization: {self.regionalization}'


class Regionalization(_UniqueName, _Citable, _GeoJsonRegion):
    """Model representing a Regionalization, which is basically a collection
    of `GsimRegion`s. As such, each regionalization `geometry`
    attribute should be the union of all `geometry`s of its `GsimRegion`s (to
    be computed beforehand for performance reasons)
    """
    pass
