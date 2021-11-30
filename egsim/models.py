"""
Models for the django app

Created on 5 Apr 2019

@author: riccardo
"""
import json
from enum import IntEnum
from datetime import datetime

from django.db.models import (Q, Model, TextField, BooleanField, ForeignKey,
                              ManyToManyField, JSONField, UniqueConstraint,
                              CASCADE, SET_NULL, Index, SmallIntegerField)
from django.db.models.aggregates import Count
from django.db.utils import IntegrityError

from shapely.geometry import Point, shape, Polygon


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

    _KEY = '__iso8601datetime__'  # DO NOT CHANGE!

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


class FlatfileField(_UniqueNameModel):
    """Flat file field (column of tabular CSV / HDF file)"""

    class CATEGORY(IntEnum):
        """Flat file category inferred from the relative Gsim attribute(s)"""
        DISTANCE_MEASURE = 0  # Gsim attr: REQUIRES_DISTANCES
        RUPTURE_PARAMETER = 1  # Gsim attr: REQUIRES_RUPTURE_PARAMETERS
        SITE_PARAMETER = 2  # Gsim attr: REQUIRES_SITES_PARAMETERS

    category = SmallIntegerField(null=True,
                                 choices=[(c, c.name.replace('_', ' ').capitalize())
                                          for c in CATEGORY],
                                 help_text="The field category")
    oq_name = TextField(null=False, help_text='The OpenQuake name (e.g., as used '
                                              'in Contexts during residuals '
                                              'computation)')
    help = TextField(null=False, default='', help_text="Field help text")
    properties = JSONField(null=True, encoder=DateTimeEncoder,
                           decoder=DateTimeDecoder,
                           help_text=('data properties as JSON (null: no '
                                      'properties). Optional keys: "dtype" '
                                      '("int", "bool", "datetime", "str" or '
                                      '"float"), "bounds": [min or null, max '
                                      'or null] (null means: unbounded), '
                                      '"default" (the default when missing) '
                                      'and "choices" (list of possible values '
                                      'the field can have)'))

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
        where each dict maps flatfile field names to its type ('float', 'int',
        'datetime') and its default. If no dtype is stored in the database, it
        defaults to 'float'. If no default is given, it is not inserted in
        `defaults`
        """
        dtype, defaults = {}, {}
        for name, props in cls.objects.filter().values_list('name', 'properties'):
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
    # src_path = TextField(unique=True, null=False)
    url = TextField(null=False, default='')
    display_name = TextField(null=True, default='')

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


class GsimTrt(_UniqueNameModel):
    """The :class:`tectonic region types <openquake.hazardlib.const.TRT>` that
    OpenQuake's GSIMs are defined for"""

    # OpenQuake's Gsim attribute used to populate this table during db init:
    OQ_ATTNAME = 'DEFINED_FOR_TECTONIC_REGION_TYPE'


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
    trt = ForeignKey(GsimTrt, on_delete=SET_NULL, null=True,
                     related_name='gsims', help_text='Tectonic Region type')
    required_flatfile_fields = ManyToManyField(FlatfileField,
                                               related_name='gsims',
                                               help_text='Required flatfile '
                                                         'field(s)')
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

    def asjson(self):
        """Convert this object as a JSON-serializable tuple of strings:
        (gsim, imts, tectonic_region_type, warning) where arguments are all
        strings except 'imts' which is a tuple of strings
        """
        # FIXME: remove trt from the json, not needed anymore!
        imts = (_.name for _ in self.imts.all())  # noqa
        return self.name, tuple(imts), self.warning or ''


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


# =============================================================================
# Utilities:
# =============================================================================


def aval_gsims(asjsonlist=False):
    """Returns a list of available gsims.

    If asjsonlist=False (the default), the list elements are strings denoting
    the Gsim names (Model's attribute `gsim.key`).

    If asjsonlist is True, the list elements are json serializable tuples:
        (gsim.key, [gsim.imt1.key, .. gsim.imtN.key], gsim.trt, gsim.warning)
    where all tuple elements are strings.

    The gsims are returned sorted alphabetically
    """
    if not asjsonlist:
        return list(gsim_names())

    manager = Gsim.objects  # noqa
    # https://docs.djangoproject.com/en/2.2/ref/models/querysets/#select-related:
    queryset = manager.prefetch_related('imts').select_related('trt').\
        order_by('key')
    return [_.asjson() for _ in queryset.all()]


def aval_imts():
    """Returns a QuerySet of strings denoting the available imts"""
#     imtobjects = Imt.objects  # pylint: disable=no-member
#     # return imts mapped to at least one gsim
#     # (https://stackoverflow.com/a/12101599)
#     # for values_list, see: https://stackoverflow.com/a/37205928
#     return imtobjects.annotate(c=Count('gsims')).filter(c__gt=0).\
#         values_list('key', flat=True)
    return shared_imts(None)


# def aval_trts(include_oq_name=False):
#     """Returns a QuerySet of strings denoting the available Trts
#     The Trts are returned sorted alphabetically by their keys"""
#     trtobjects = Trt.objects  # noqa
#     if include_oq_name:
#         return trtobjects.order_by('key').values_list('key', 'oq_name')
#     return trtobjects.order_by('key').values_list('key', flat=True)


def aval_trmodels(asjsonlist=False):
    """Returns the QueryList of models (strings) if asjsonlist is missing or
    False. Otherwise, returns QueryList of sub-lists:
        [model, type, geojson]
    where all list elements are strings (type is the associated Trt key.
    Geojson can be converted to a dict by calling as usual:
    `json.dumps(geojson)`)
    """
    trobjects = GeographicRegion.objects  # noqa
    if asjsonlist is True:
        return trobjects.values_list('model', 'type__key', 'geojson')
    return trobjects.order_by('model').values_list('model', flat=True).distinct()


def shared_imts(gsims):
    """Returns a QuerySet of strings with the the keys (=unique names) of the
    imts shared by all supplied gsims

    :param gsims: list of integers (gsim id), gsims instances, or
        strings denoting a Gsim key
    """
    # Do not expose publicly the fact that passing None returns all imts
    # defined for at least one gsim, as the user should use `aval_imts()`
    # instead
    imtobjects = Imt.objects  # noqa
    min_required_gsims = 1
    if gsims is not None:
        min_required_gsims = len(gsims)
        if not any(isinstance(_, str) for _ in gsims):
            imtobjects = imtobjects.filter(gsims__in=gsims)
        else:
            expr = or_(Q(gsims__key=_) if isinstance(_, str) else Q(gsims=_)
                       for _ in gsims)
            imtobjects = imtobjects.filter(expr)

    # return imts mapped to at least `min_required_gsims` gsim
    # (https://stackoverflow.com/a/12101599)
    # for values_list, see: https://stackoverflow.com/a/37205928
    # This assures that, if gsims is given, we return imts matching at
    # least all supplied gsims
    # (https://stackoverflow.com/a/8637972)
    return imtobjects.annotate(kount=Count('gsims')).\
        filter(kount__gte=min_required_gsims).values_list('key', flat=True)


def sharing_gsims(imts):
    """Returns a QuerySet of strings with the keys (=unique names)
    of the gsims defined for all supplied imts

    :param imts: list of integers (imt id), imts instances, or
        strings denoting an Imt key
    """
    return gsim_names(imts=imts, imts_match_all=True)


def gsim_names(gsims=None, imts=None, trts=None, tr_selector=None,
               imts_match_all=False):
    """Returns a QuerySet
    (https://docs.djangoproject.com/en/2.2/ref/models/querysets/)
    of strings denoting the Gsim names matching the given criteria.
    A Gsim name is the OpenQuake unique name (attribute `Gsim.key` in the
    associated ORM Model).
    A gsim is returned when it matches ALL the conditions
    specified by the provided arguments (missing arguments are skipped),
    which are:
    :param gsims: iterable of strings (Gsim.name) or Gsim instances, or
        both. If None (the default), no filter is applied. Otherwise,
        return Gsims whose name matches any of the provided Gsim(s)
    :param imts: iterable of strings (Imt.key) or Imt instances, or both.
        If None (the default), no filter is applied. Otherwise, return
        Gsims whose imts match any of the provided imt(s). If
        `imts_match_all`=True, return Gsims defined for (at least) all
        the provided imt(s)
    :param trts: iterable of strings (Trt.key) or Trt instances, or both.
        If None (the default), no filter is applied. Otherwise, return
        only Gsims defined for any of the provided trt(s)
    :param tr_selector: a Tectonic region selector (see class
        `TrSelector`) based on any tectonic regionalization defined on the
        database (see 'TectonicRegion' model) for filtering the search to
        a specific geographical point or rectangle. If None, nothing
        is filtered
    :param imts_match_all: boolean, ignored if `imts` is None or missing.
        When False (the default), any gsim defined for at least *one*
        of the provided imts will be taken. When True, any gsim defined
        for *all* provided imts will be taken.
    """
    # trt can be a trt instance, an int denoting the trt pkey,
    # or a string denoting the trt key field (unique)
    # in the expressions .filter(imts_in=[...]) the arguments in
    # list can be pkey (ints) or instances. We want to allow also
    # to pass imt keys (names). In this case we need to use
    # the Q function. For info see:
    # https://docs.djangoproject.com/en/2.2/topics/db/examples/many_to_one/
    # https://docs.djangoproject.com/en/2.2/topics/db/queries/

    gsimobjects = Gsim.objects  # noqa

    if gsims is not None:
        # For each gsim in gsims, gsim can be a string (the gsim key),
        # an instance or, of neither of the two, it is assumed to be an int
        # denoting the gsim.id. This is translated in this set of SQL OR
        # expressions:
        expr = or_(Q(key=_) if isinstance(_, str) else
                   Q(id=getattr(_, 'id', _)) for _ in gsims)
        gsimobjects = gsimobjects.filter(expr)

    if imts is not None:
        if not any(isinstance(_, str) for _ in imts):
            gsimobjects = gsimobjects.filter(imts__in=imts)
        else:
            expr = or_(Q(imts__key=_) if isinstance(_, str) else Q(imts=_)
                       for _ in imts)
            gsimobjects = gsimobjects.filter(expr)

        if imts_match_all:
            # https://stackoverflow.com/a/8637972
            gsimobjects = gsimobjects.annotate(num_imts=Count('imts')).\
                filter(num_imts__gte=len(imts))

    if tr_selector is not None:
        trts = tr_selector.get_trt_names(trts)
        if not trts:
            # https://docs.djangoproject.com/en/dev/ref/models/querysets/#none
            return gsimobjects.none()

    if trts is not None:
        if not any(isinstance(_, str) for _ in trts):
            gsimobjects = gsimobjects.filter(trt__in=trts)
        else:
            expr = or_(Q(trt__key=_) if isinstance(_, str) else Q(trt=_)
                       for _ in trts)
            gsimobjects = gsimobjects.filter(expr)

    gsimobjects = gsimobjects.order_by('key')

    # https://stackoverflow.com/a/37205928:
    return gsimobjects.distinct().values_list('key', flat=True)


def or_(q_expressions):
    """Concatenates the given Q expression with an 'OR'. Returns None if
    `q_expressions` (iterable) has no items"""
    expr = None
    for expr_chunk in q_expressions:
        if expr is None:
            expr = expr_chunk
        else:
            expr |= expr_chunk
    return expr


# These are the possible combinations

# trts OK
# model+point OK
# model+point+trts OK (intersection between trts and model's trts is returned)
# point NO (which model?)
# model NO (might be OK, but NO for simplicity)
# trts+point NO (which model?)
# trts+model NO (might be OK, but NO for simplicity)

class TrSelector:  # FIXME: buggy, models have been renamed and geoJSON added. fix!
    """This object allows selection of Trt (tectonic region types
    from a given tectonic regionalization (TR) and a specified point
    (or rectangle) defined on TR. The method get_trt_names will return all
    Trt(s) matching the given criteria
    """

    def __init__(self, tr_model, lon0, lat0, lon1=None, lat1=None):
        """Initializes this object. Call the method `get_trt_names` to return
        the Trt(s) matching this object.

        If specified, lon1 and lat1 will take the same values as lon0 and lat0,
        and will define a rectangle and all Trt(s) *intersecting* it will be
        returned. Otherwise, all Trt(s) *including* the point specified by
        lon0 and lat0 will be returned.

        :param tr_model: string. a tectonic regionalization model, must be
            present int the table 'TectonicRegions' under the 'model' column
        :param lon0: float, the latitude (in degrees) of the point
        :param lon0: float, the longitude (in degrees) of the point
        """
        self.tr_model = tr_model
        if lon1 is None or lat1 is None:
            self.shape = Point([lon0, lat0])
        else:
            self.shape = Polygon([(lon0, lat0), (lon0, lat1),
                                  (lon1, lat1), (lon1, lat0)])

    def get_trt_names(self, trts=None):
        tecregobjects = GeographicRegion.objects  # noqa
        geojsons = tecregobjects.filter(model=self.tr_model)
        if trts is not None:
            if not any(isinstance(_, str) for _ in trts):
                geojsons = geojsons.filter(type__in=trts)
            else:
                expr = or_(Q(type__key=_) if isinstance(_, str) else Q(type=_)
                           for _ in trts)
                geojsons = geojsons.filter(expr)

        matched_trts = {}
        ispoint = isinstance(self.shape, Point)
        for (geojson, trt) in geojsons.values_list('geojson', 'type__key'):
            if trt in matched_trts:
                continue
            tr_shape = shape(json.loads(geojson)['geometry'])
            check = tr_shape.contains if ispoint else tr_shape.intersects
            if check(self.shape):
                matched_trts[trt] = None

        return list(matched_trts.keys())


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
