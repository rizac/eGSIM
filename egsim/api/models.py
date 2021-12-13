"""
Models for the django app

Created on 5 Apr 2019

@author: riccardo
"""
from os.path import abspath, join
import json
from enum import IntEnum
from datetime import datetime

from django.db.models import (Q, Model, TextField, BooleanField, ForeignKey,
                              ManyToManyField, JSONField, UniqueConstraint,
                              CASCADE, SET_NULL, Index, SmallIntegerField,
                              DateTimeField)
from django.conf import settings
from django.db.utils import IntegrityError


# Notes: primary keys are auto added if not present ('id' of type BigInt or so).
# All models here that are not abstract will be available prefixed with 'egsim_'
# in the admin panel (https://<site_url>/admin)


# ============================================
# JSON encoders/ decoders (used in JSONFields)
# ============================================


class CompactEncoder(json.JSONEncoder):
    """JSON encoder that saves space"""
    def __init__(self, **kwargs):
        kwargs['separators'] = (',', ':')
        super(CompactEncoder, self).__init__(**kwargs)


class DateTimeEncoder(CompactEncoder):
    """Encode date times as ISO formatted strings"""

    _KEY = '__iso8601datetime__'  # DO NOT CHANGE or repopulate db

    def default(self, obj):
        try:
            # Note: from timestamp is not faster, so let's use isoformat to speed up:
            return {self._KEY: obj.isoformat()}
        except Exception:  # noqa
            return super(DateTimeEncoder, self).default(obj)  # (raise TypeError)


class DateTimeDecoder(json.JSONDecoder):

    def __init__(self, **kwargs):
        super(DateTimeDecoder, self).__init__(object_hook=DateTimeDecoder.object_hook,
                                              **kwargs)

    @staticmethod
    def object_hook(dct):
        key = DateTimeEncoder._KEY  # noqa
        if key in dct:
            return datetime.fromisoformat(dct[key])
        # return dict "normally":
        return dct


# ======
# Models
# ======

class _UniqueNameModel(Model):
    """Abstract class for models identified by a single unique name"""

    name = TextField(null=False, unique=True, help_text="Unique name")

    class Meta:
        # In subclasses, `abstract` is (re)set to False. Everything else is copied
        # (https://docs.djangoproject.com/en/3.2/topics/db/models/#meta-inheritance)
        abstract = True

    def __str__(self):
        return self.name


class FlatfileColumn(_UniqueNameModel):
    """Flat file column"""

    class CATEGORY(IntEnum):
        """Flat file category inferred from the relative Gsim attribute(s)"""
        DISTANCE_MEASURE = 0  # Gsim attr: REQUIRES_DISTANCES
        RUPTURE_PARAMETER = 1  # Gsim attr: REQUIRES_RUPTURE_PARAMETERS
        SITE_PARAMETER = 2  # Gsim attr: REQUIRES_SITES_PARAMETERS

    oq_name = TextField(null=False, help_text='The OpenQuake name of the GSIM '
                                              'property associated to this '
                                              'column (e.g., as used in '
                                              'Contexts during residuals '
                                              'computation)')
    category = SmallIntegerField(null=True,
                                 choices=[(c, c.name.replace('_', ' ').capitalize())
                                          for c in CATEGORY],
                                 help_text='The OpenQuake category of the GSIM '
                                           'property associated to this '
                                           'column')
    help = TextField(null=False, default='', help_text="Field help text")
    properties = JSONField(null=True, encoder=DateTimeEncoder,
                           decoder=DateTimeDecoder,
                           help_text=('column data properties as JSON (null: no '
                                      'properties). Optional keys: "dtype" '
                                      '("int", "bool", "datetime", "str" or '
                                      '"float", or list of possible values '
                                      'the column can have), "bounds": [min or '
                                      'null, max or null] (null means: '
                                      'unbounded), "default" (the default when '
                                      'missing)'))

    class Meta(_UniqueNameModel.Meta):
        constraints = [
            # unique constraint name must be unique across ALL db tables:
            # use `app_label` and `class` to achieve that:
            UniqueConstraint(fields=['oq_name', 'category'],
                             name='%(app_label)s_%(class)s_unique_oq_name_and_'
                                  'category'),
        ]
        indexes = [Index(fields=['name']), ]

    @classmethod
    def get_dtype_and_defaults(cls) -> tuple[dict[str, str], dict[str, str]]:
        """
        Return the tuple:
        ```
        (dtype: dict, defaults: dict)
        ```
        where each dict maps flatfile column names to its type ('float', 'int',
        'datetime') and its default. If no dtype is stored in the database, it
        defaults to 'float'. If no default is given, it is not inserted in
        `defaults`
        """
        dtype, defaults = {}, {}
        for name, props in cls.objects.filter().values_list('name', 'properties'):
            if not props:
                continue
            dtype[name] = props['dtype']
            if 'default' in props:
                defaults[name] = props['default']

        return dtype, defaults

    def __str__(self):
        categ = 'N/A' if self.category is None else \
            self.get_category_display()  # noqa
        # `get_[field]_display` is added by Django for those fields with choices
        return '%s (OpenQuake name: %s). %s required by %d Gsims' % \
               (self.name, self.oq_name, categ, self.gsims.count())  # noqa


class Flatfile(_UniqueNameModel):

    path = TextField(unique=True, null=False)
    url = TextField(null=False, default='')
    display_name = TextField(null=True, default='')
    hidden_in_browser = BooleanField(null=False, default=False,
                                     help_text="if true, the flatfile is hidden "
                                               "in browsers (users can still "
                                               "access it via API requests, if "
                                               "not expired)")
    expires_at = DateTimeField(null=True, default=None,
                               help_text="expiration date(time) after which the "
                                         "flatfile is not visible or accessible "
                                         "to any request. If null, the flatfile "
                                         "has no expiration date")

    # base directory for any uploaded or created flat file:
    BASEDIR_PATH = abspath(join(settings.MEDIA_ROOT, 'flatfiles'))

    @classmethod
    def get_flatfiles(cls, for_browser=False):
        qry = cls.objects.filter(Q(expires_at__isnull=True) |
                                 Q(expires_at__lt=datetime.utcnow()))
        if for_browser:
            qry = qry.filter(hidden_in_browser=False)
        return qry

    def __str__(self):
        """string representation of this object"""
        name = self.display_name or self.name
        url = " (%s)" % self.url if self.url else ""
        return name + url


class Imt(_UniqueNameModel):
    """The :mod:`intensity measure types <openquake.hazardlib.imt>` that
    OpenQuake's GSIMs can calculate and that are supported in eGSIM
    """
    needs_args = BooleanField(default=False, null=False)

    # OpenQuake's Gsim attribute used to populate this table during db init:
    OQ_ATTNAME = 'DEFINED_FOR_INTENSITY_MEASURE_TYPES'

    class Meta(_UniqueNameModel.Meta):
        indexes = [Index(fields=['name']), ]


# class GsimTrt(_UniqueNameModel):
#     """The :class:`tectonic region types <openquake.hazardlib.const.TRT>` that
#     OpenQuake's GSIMs are defined for"""
#
#     # OpenQuake's Gsim attribute used to populate this table during db init:
#     OQ_ATTNAME = 'DEFINED_FOR_TECTONIC_REGION_TYPE'


class GsimWithError(_UniqueNameModel):
    """The Ground Shaking Intensity Models (GSIMs) implemented in OpenQuake
    that could not be available in eGSIM due errors
    """

    error_type = TextField(help_text="Error type, usually the class name of "
                                     "the Exception raised")
    error_message = TextField(help_text="Error message")

    def __str__(self):
        return '%s. %s: %s' % (self.name, self.error_type, self.error_message)


class Gsim(_UniqueNameModel):
    """The Ground Shaking Intensity Models (GSIMs) implemented in OpenQuake and
    available in eGSIM
    """
    imts = ManyToManyField(Imt, related_name='gsims',
                           help_text='Intensity Measure Type(s)')
    # trt = ForeignKey(GsimTrt, on_delete=SET_NULL, null=True,
    #                  related_name='gsims', help_text='Tectonic Region type')
    required_flatfile_columns = ManyToManyField(FlatfileColumn,
                                                related_name='gsims',
                                                help_text='Required flatfile '
                                                          'column(s)')
    init_parameters = JSONField(null=True, encoder=CompactEncoder,
                                help_text="The parameters used to "
                                          "initialize this GSIM in "
                                          "Python, as JSON object of "
                                          "names mapped to their "
                                          "default value. Included "
                                          "here are only parameters "
                                          "whose default value type "
                                          "is a Python int, float, "
                                          "bool or str")
    warning = TextField(default=None, null=True,
                        help_text='Optional usage warning(s) to be reported '
                                  'before usage (e.g., in GUIs)')

    class Meta(_UniqueNameModel.Meta):
        indexes = [Index(fields=['name']), ]


class GsimRegion(Model):
    """Model representing the relationships between Gsim(s) and Region(s)"""

    gsim = ForeignKey(Gsim, on_delete=CASCADE, null=False, related_name='regions')
    regionalization = TextField(null=False, help_text="The name of the "
                                                      "regionalization defining "
                                                      "the mapping Gsim <-> "
                                                      "Geographic region")

    GEOM_TYPES = ('Polygon', 'MultiPolygon')

    geometry = JSONField(null=False, encoder=CompactEncoder,
                         help_text="The region as geoJSON Geometry object, "
                                   "with at least the keys \"coordinates\""
                                   "and \"type'\" in %s only. For details see: "
                                   "https://en.wikipedia.org/wiki/GeoJSON"
                                   "#Geometries)" % str(GEOM_TYPES))

    class Meta:
        constraints = [UniqueConstraint(fields=['gsim', 'regionalization'],
                                        name='%(app_label)s_%(class)s_unique_'
                                             'gsim_and_regionalization')]

    def save(self, *args, **kwargs):
        """Overrides save and checks if the flat file name is unique or NULL"""
        # WARNING: DO NOT set Breakpoints in PyCharm 2021.1.1 and Python 3.9
        # as it seems that the program crashes in debug mode (but it works actually)
        key = 'geometry'
        val = getattr(self, key)
        if val is not None:
            if not val:  # force empty fields to be NULL:
                setattr(self, key, None)
            else:
                key2 = 'type'
                val2 = val.get(key2, '')
                if val2 not in self.GEOM_TYPES:
                    raise IntegrityError('%s["%s"]="%s" must be in %s' %
                                         (key, key2, val2, self.GEOM_TYPES))

        super(GsimRegion, self).save(*args, **kwargs)

    @staticmethod
    def num_polygons(geometry: dict):
        """Return the number of Polygons from the given geometry goJSON geometry"""
        geom_type = geometry['type']
        if geom_type != GsimRegion.GEOM_TYPES[0]:
            return len(geometry['coordinates'])
        return 1

    def __str__(self):
        npoly = self.num_polygons(self.geometry)  # noqa
        poly = 'polygon' if npoly == 1 else 'polygons'
        return 'Region "%s", %d %s, regionalization: %s' % \
               (str(self.gsim), npoly, poly, self.regionalization)


# UNUSED Legacy functions ====================================================


def _is_field_value_unique(instance: Model, field_name: str, ignore_nulls=True):
    """Return True if the instance field value is unique by querying the db table

    :param instance: a Model instance
    :param field_name: the instance field name to check
    :param ignore_nulls: boolean (default True): ignore null. I.e., allow
        multiple null values
    """
    # Rationale: apparently a Django Field(... unique=True, null=True,...) will
    # force also uniqueness on NULLs (only one NULL can be saved). This is
    # probably because not all DBs support unique with multiple NULLs
    # (postgres does). Implement here a function that allows that
    field_val = getattr(instance, field_name)
    if field_val is None and ignore_nulls:
        return True
    filter_cond = {field_name + '__exact': field_val}  # works for None as well
    return not instance.__class__.objects.filter(**filter_cond).exists()  # noqa
