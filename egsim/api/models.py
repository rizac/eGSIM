"""
Models for the django app

Created on 5 Apr 2019

@author: riccardo
"""
from os.path import abspath, join
import json
from datetime import datetime, date
from typing import Any

from django.db.models import (Model as DjangoModel, Q, TextField, BooleanField,
                              ForeignKey, ManyToManyField, JSONField, UniqueConstraint,
                              CASCADE, SET_NULL, Index, SmallIntegerField,
                              DateTimeField, URLField, Manager)
from django.db.models.options import Options
from django.conf import settings
from django.db.utils import IntegrityError


# Notes: primary keys are auto added if not present ('id' of type BigInt or so).
# All models here that are not abstract will be available prefixed with 'api_'
# in the admin panel (https://<site_url>/admin)
from egsim.smtk import flatfile


class Model(DjangoModel):
    """Abstract base class of all Django Models of this module"""

    # notify editors code inspection that these attrs exist (see metaclass for details):
    objects: Manager
    _meta: Options

    class Meta:  # make this class abstract
        abstract = True


class _UniqueNameModel(Model):
    """Abstract class for Table entries identified by a single unique name"""

    name = TextField(null=False, unique=True, help_text="Unique name")

    class Meta:
        # In subclasses, `abstract` is (re)set to False. Everything else is copied
        # (https://docs.djangoproject.com/en/3.2/topics/db/models/#meta-inheritance)
        abstract = True

    def __str__(self):
        return self.name


class _DataSource(_UniqueNameModel):
    """Abstract class for Table rows associated to source data with given
    URL, license, citation and so on"""

    display_name = TextField(default=None, null=True)
    url = URLField(default=None, null=True)
    license = TextField(default=None, null=True)
    citation = TextField(default=None, null=True,
                         help_text="Bibliographic citation, as text")
    doi = TextField(default=None, null=True)

    def __str__(self):
        """string representation of this object"""
        name = self.display_name or self.name
        url = " (%s)" % self.url if self.url else ""
        return name + url  # noqa

    class Meta:
        # In subclasses, `abstract` is (re)set to False. Everything else is copied
        # (https://docs.djangoproject.com/en/3.2/topics/db/models/#meta-inheritance)
        abstract = True


class Flatfile(_DataSource):
    """Class handling flatfiles stored in the file system
    (predefined flatfiles)
    """
    # base directory for any uploaded or created flat file:
    BASEDIR_PATH = abspath(join(settings.MEDIA_ROOT, 'flatfiles'))

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


class CompactEncoder(json.JSONEncoder):
    """Compact JSON encoder used in JSONFields of this module"""
    def __init__(self, **kwargs):
        kwargs['separators'] = (',', ':')
        super().__init__(**kwargs)


class DateTimeEncoder(CompactEncoder):
    """Encode date times as ISO formatted strings"""

    _KEY = '__iso8601datetime__'  # DO NOT CHANGE, or otherwise repopulate the db

    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            obj = {self._KEY: obj.isoformat()}
        return super(DateTimeEncoder, self).default(obj)  # (raise TypeError)


class DateTimeDecoder(json.JSONDecoder):
    """Encode date times encoded with the previous class instance"""

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


class FlatfileColumn(_UniqueNameModel):
    """Flat file column"""

    oq_name = TextField(null=True, help_text='The OpenQuake name of the GSIM '
                                             'property associated to this '
                                             'column (e.g., as used in '
                                             'Contexts during residuals '
                                             'computation)')
    category = SmallIntegerField(null=False,
                                 default=flatfile.ColumnMetadata.Category.unknown,
                                 choices=[(c.value,
                                           c.name.replace('_', ' ').capitalize())
                                          for c in flatfile.ColumnMetadata.Category],
                                 help_text='The (OpenQuake-related) category '
                                           'of the GSIM property associated '
                                           'to this column')
    help = TextField(null=False, default='', help_text="Field help text")
    data_properties = JSONField(null=True, encoder=DateTimeEncoder,
                                decoder=DateTimeDecoder,
                                help_text=('The properties of the this column data, '
                                           'as JSON (null: no properties). Optional '
                                           'keys: "dtype" ("int", "bool", "datetime", '
                                           '"str" or "float", or list of possible '
                                           'values the column data can have), "bounds": '
                                           '[min or null, max or null] (null means: '
                                           'unbounded), "default" (the default when '
                                           'missing), "required" (bool)'))

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        """Call `super.save` after checking and harmonizing the values of
        `self.properties` to be usable with flatfiles
        """
        # perform some check on the data type consistencies:
        try:
            _ = flatfile.ColumnMetadata(**(self.data_properties or {}),
                                        oq_name=self.oq_name, help=self.help, # noqa
                                        category=self.category)
        except Exception as exc:
            raise ValueError(f'Flatfile column "{self.name}" error: {exc}')

        super().save(force_insert=force_insert, force_update=force_update,
                     using=using, update_fields=update_fields)

    @classmethod
    def get_data_properties(cls) -> \
            tuple[dict[str, str], dict[str, Any], dict[str, list[Any, Any]], list[str]]:
        """
        Return the `data_properties` Field as tuples:
        `dtype` `default` `bounds` `required`
        """
        dtype, defaults, bounds, required = {}, {}, {}, []
        cols = 'name', 'data_properties'
        for name, props in cls.objects.filter().only(*cols).values_list(*cols):
            if not props:
                continue
            if props.get("dtype", None):
                dtype[name] = props["dtype"]
            if "default" in props:
                defaults[name] = props["default"]
            if "bounds" in props:
                bounds[name] = props["bounds"]
            if props.get("required", False):
                required.append(name)

        return dtype, defaults, bounds, required

    class Meta(_UniqueNameModel.Meta):
        indexes = [Index(fields=['name']), ]

    def __str__(self):
        categ = 'N/A' if self.category is None else \
            self.get_category_display()  # noqa
        # `get_[field]_display` is added by Django for those fields with choices
        return '%s (OpenQuake name: %s). %s required by %d Gsims' % \
               (self.name, self.oq_name, categ, self.gsims.count())  # noqa


class Imt(_UniqueNameModel):
    """The :mod:`intensity measure types <openquake.hazardlib.imt>` that
    OpenQuake's GSIMs can calculate and that are supported in eGSIM
    """
    needs_args = BooleanField(default=False, null=False)

    # OpenQuake's Gsim attribute used to populate this table during db init:
    OQ_ATTNAME = 'DEFINED_FOR_INTENSITY_MEASURE_TYPES'

    class Meta(_UniqueNameModel.Meta):
        indexes = [Index(fields=['name']), ]


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
    """Model representing a GSIM Region"""

    gsim = ForeignKey(Gsim, on_delete=CASCADE, null=False, related_name='regions')
    regionalization = ForeignKey("Regionalization", to_field='name',
                                 on_delete=SET_NULL, null=True,
                                 help_text="The name of the regionalization "
                                           "this region derives from")

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
        """Override save and checks if the flat file name is unique or NULL"""
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


class Regionalization(_DataSource):
    """Model representing the data source of a given Regionalization"""
    pass
