"""
Models for the django app

Created on 5 Apr 2019

@author: riccardo
"""
import json
import re

from django.db.models import (Q, Model, TextField, BooleanField, ForeignKey,
                              ManyToManyField, JSONField, UniqueConstraint,
                              CASCADE, SET_NULL)
from django.db.models.aggregates import Count

from shapely.geometry import Point, shape, Polygon

from smtk import sm_utils


# (Note below: primary keys are auto added if not present)
# All models here that are not abstract will be available prefixed with 'egsim_'
# in the admin panel (https://<site_url>/admin)


class _SingleFieldModel(Model):
    """Abstract class for models identified by a single unique name"""

    name = TextField(null=False, unique=True, help_text="Unique name")

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Imt(_SingleFieldModel):
    """The :mod:`intensity measure types <openquake.hazardlib.imt>` that
    OpenQuake's GSIMs can calculate and that are supported in eGSIM
    """
    needs_args = BooleanField(default=False, null=False)

    # OpenQuake's Gsim attribute used to populate this table during db init:
    OQ_ATTNAME = 'DEFINED_FOR_INTENSITY_MEASURE_TYPES'


class _ModelWithFlatfileMapping(_SingleFieldModel):
    """Extend :class:`_SingleFieldModel` for models with a mapping to
    some flat file column. The mapping is between an instance field `name`
    and the column name
    """

    flatfile_column = TextField(null=True, unique=True,
                                help_text="The corresponding flat file "
                                          "column name (Null: no mapping)")

    # model `name` field name -> flatfile column. Mapping a field name to None
    # means: no corresponding flat file column. NOTE for developers: the
    # mapping below is intended to be used for informative purpose only, and
    # not in computation (e.g. to filter data), as this is too complex and
    # error prone. Two typical usages might be to warn the user on required flat
    # file columns for a selected Gsim, or to warn the admin during DB init for
    # new field names not in `__flatfile_mapping__.keys()`, as this might
    # require particular actions such as defining new flat file columns
    __flatfile_mapping__ = {}

    class Meta:
        abstract = True


class GsimSitesParam(_ModelWithFlatfileMapping):
    """The site parameters names that OpenQuake's GSIM need"""

    # OpenQuake's Gsim attribute used to populate this table during db init:
    OQ_ATTNAME = 'REQUIRES_SITES_PARAMETERS'

    # model field name -> flatfile column
    __flatfile_mapping__ = {
        "backarc": 'backarc',
        # "backarc_distance":  # now xvf:  https://github.com/gem/oq-engine/issues/6135
        "ec8": None,
        "ec8_p18": None,
        "geology": None,  # (default "UNKNOWN") should be added as a configurable param.
        "h800": None,
        "lat": "station_latitude",
        "lon": "station_longitude",
        "siteclass": None,  # not used in flatfiles
        "slope":  None,  # float (default 0.1 m/m) affects 2 models for Europe
        "vs30": "vs30",
        "vs30measured": "vs30_measured",
        "xvf": None,  # float (default 0)
        "z1pt0": "z1",
        "z1pt4": None,  # used by models with a different basin depth definition
        # from the global standards (default equal to z1pt0?)
        "z2pt5": "z2pt5"
    }


class GsimRuptureParam(_ModelWithFlatfileMapping):
    """The rupture parameters names (excluding distance information) required
    by OpenQuake's GSIMs
    """

    # OpenQuake's Gsim attribute used to populate this table during db init:
    OQ_ATTNAME = 'REQUIRES_RUPTURE_PARAMETERS'

    # model field name -> flatfile column:
    __flatfile_mapping__ = {
        "dip": None,  # no 1-1-mapping in flatfiles
        "hypo_depth": "hypocenter_depth",
        "mag": "magnitude",
        "rake": None,  # no 1-1-mapping in flatfiles
        "strike": None,  # no 1-1-mapping in flatfiles
        "width": "rupture_width",
        # NOTE: in flatfiles, missing values are handled in the code
        "ztor": "depth_top_of_rupture",
        "ev_lat": "event_latitude",
        "ev_lon": "event_longitude",
    }


class GsimDistance(_ModelWithFlatfileMapping):
    """The types of distance measures between rupture and sites required by
    OpenQuake's GSIMs
    """

    # OpenQuake's Gsim attribute used to populate this table during db init:
    OQ_ATTNAME = 'REQUIRES_DISTANCES'

    # model field name -> flatfile column:
    __flatfile_mapping__ = {
        "azimuth":  "azimuth",
        "rcdpp": None,  # not used in flatfiles
        "repi":  "repi",
        "rhypo":  "rhypo",
        "rjb": "rjb",
        "rrup": "rrup",
        "rvolc": None,  # not used in flatfiles
        "rx": "rx",
        "ry0": "ry0"
    }


class GsimAttribute(_SingleFieldModel):
    """The attributes required by OpenQuake's GSIMs"""

    # OpenQuake's Gsim attribute used to populate this table during db init:
    OQ_ATTNAME = 'REQUIRES_ATTRIBUTES'


class GsimTrt(_SingleFieldModel):
    """The :class:`tectonic region types <openquake.hazardlib.const.TRT>` that
    OpenQuake's GSIMs are defined for"""

    # OpenQuake's Gsim attribute used to populate this table during db init:
    OQ_ATTNAME = 'DEFINED_FOR_TECTONIC_REGION_TYPE'


class GsimWithError(_SingleFieldModel):
    """TThe Ground Shaking Intensity Models (GSIMs) implemented in OpenQuake
    that could not be available in eGSIM due errors
    """

    error_type = TextField(help_text="Error type, usually the class name of "
                                     "the Exception raised")
    error_message = TextField(help_text="Error message")

    def __str__(self):
        return '%s. %s: %s' % (self.name, self.error_type, self.error_message)


class Gsim(_SingleFieldModel):
    """The Ground Shaking Intensity Models (GSIMs) implemented in OpenQuake and
    available in eGSIM
    """
    imts = ManyToManyField(Imt, related_name='gsims',
                           help_text='Intensity Measure Type(s)')
    trt = ForeignKey(GsimTrt, on_delete=SET_NULL, null=True,
                     related_name='gsims', help_text='Tectonic Region type')
    attributes = ManyToManyField(GsimAttribute, related_name='gsims',
                                 help_text='Required attribute(s)')
    distances = ManyToManyField(GsimDistance, related_name='gsims',
                                help_text='Required distance(s)')
    sites_parameters = ManyToManyField(GsimSitesParam, related_name='gsims',
                                       help_text='Required site parameter(s)')
    rupture_parameters = ManyToManyField(GsimRuptureParam, related_name='gsims',
                                         help_text='Required rupture parameter(s)')
    warning = TextField(default=None, null=True,
                        help_text='Optional usage warning(s)')

    def asjson(self):
        """Converts this object as a JSON-serializable tuple of strings:
        (gsim, imts, tectonic_region_type, warning) where arguments are all
        strings except 'imts' which is a tuple of strings
        """
        # FIXME: remove trt from the json, not needed anymore!
        trt = self.oq_trt.name  # noqa
        imts = (_.name for _ in self.imts.all())  # noqa
        return self.name, tuple(imts), trt, self.warning or ''


class Region(Model):
    """Geographic region uniquely identified by a two element
    tuple of strings: the parent regionalization and a the region name,
    e.g.: ("share", "active_shallow_crust"). A region geometry is given
    by a geoJSON Geometry object with at least two required fields "type"
    and "coordinates" (https://en.wikipedia.org/wiki/GeoJSON#Geometries.
    Consequently, if "type" is "MultiPolygon" a region can be composed by
    several polygons not necessarily connected)
    """

    def __init__(self, regionalization, name):
        super().__init__(regionalization=regionalization.strip().lower(),
                         name=name.strip().lower())
        self.regionalization = re.sub(r"\s", "_",  self.regionalization)
        self.name = re.sub(r"\s", "_", self.name)
        if self.regionalization != self.name:
            prefix = self.regionalization + '_'
            if self.name.startswith(prefix):
                self.name = self.name[len(prefix):]

    regionalization = TextField(null=False, help_text="The name of the parent "
                                                      "regionalization (e.g., "
                                                      "SHARE, ESHM20, germany)")
    name = TextField(null=False, help_text="The region name")
    geometry = JSONField(null=False,
                         help_text="The region coordinates as geoJSON Geometry "
                                   "object, i.e. with at least the \"type'\" "
                                   "and \"coordinates\" fields "
                                   "(https://en.wikipedia.org/wiki/GeoJSON#Geometries)")

    def __str__(self):
        return self.name if self.regionalization == self.name else \
            self.regionalization + '_' + self.name

    class Meta:
        constraints = [UniqueConstraint(fields=['regionalization', 'name'],
                                        name='unique(regionalization,name)')]


class RegionGsimMapping(Model):
    """Model representing the relationships between Gsim(s) and Region(s)"""

    gsim = ForeignKey(Gsim, on_delete=CASCADE, null=False, related_name='regions')
    region = ForeignKey(Region, on_delete=CASCADE, null=False, related_name='gsims')

    class Meta:
        constraints = [UniqueConstraint(fields=['gsim', 'region'],
                                        name='unique(gsim,region)')]

    def __str__(self):
        return "(%s, %s)" % (str(self.gsim), str(self.region))


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


def aval_trts(include_oq_name=False):
    """Returns a QuerySet of strings denoting the available Trts
    The Trts are returned sorted alphabetically by their keys"""
    trtobjects = Trt.objects  # noqa
    if include_oq_name:
        return trtobjects.order_by('key').values_list('key', 'oq_name')
    return trtobjects.order_by('key').values_list('key', flat=True)


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
    :param gsims: iterable of strings (Gsim.key) or Gsim instances, or
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


# Flatfile model (test) =====================================================


from django.db import models  # noqa


class FlatfileField:

    @property
    def dtype(self):
        dtyp = None
        if isinstance(self, models.IntegerField):
            dtyp = int
        if isinstance(self, models.BooleanField):
            dtyp = bool
        if isinstance(self, models.FloatField):
            dtyp = float
        if isinstance(self, models.DateTimeField):
            dtyp = 'datetime64[ns]'
        if isinstance(self, (models.CharField, models.TextField)):
            dtyp = str
        if dtyp is None:
            raise ValueError('Cannot infer dtype for ' + str(self.__class__))
        if self.choices is not None:
            import pandas as pd
            return pd.DategoricalDtype([_[0] for _ in self.choices])
        return dtyp


class TextCol(models.TextField, FlatfileField):
   pass


class IntCol(models.IntegerField, FlatfileField):

    def __init__(self, **kwargs):
        # compatibility with pandas, which cannot handle Null/NaN with ints:
        kwargs.setdefault('default', 0)
        kwargs.setdefault('null', False)
        models.IntegerField.__init__(self, **kwargs)


class FloatCol(models.FloatField, FlatfileField):
    pass


class DateTimeCol(models.DateTimeField, FlatfileField):
    pass


class BoolCol(models.BooleanField, FlatfileField):
    pass


class Flatfile(models.Model):
    """Abstract :class:`_SingleFieldModel` class for models with a mapping to
    some flat file column (the mapping is optional in that instances can also
    have no corresponding flat file column)
    """
    event_name = TextCol()
    event_country = TextCol()
    event_time = DateTimeCol()
    event_latitude = FloatCol(help_text='event latitude (deg)')  # bounds: [-90, 90]
    event_longitude = FloatCol(help_text='event longitude (deg)')  # bounds: [-180, 180]
    hypocenter_depth = FloatCol(help_text='Hypocentral depth (Km)')  # FIXME unit
    magnitude = FloatCol()
    magnitude_type = TextCol()
    magnitude_uncertainty = FloatCol()
    tectonic_environment = TextCol()
    strike_1 = FloatCol()
    strike_2 = FloatCol()
    dip_1 = FloatCol()
    dip_2 = FloatCol()
    rake_1 = FloatCol()
    rake_2 = FloatCol()
    style_of_faulting = TextCol(choices=[(_, _) for _ in sm_utils.MECHANISM_TYPE.keys()])
    depth_top_of_rupture = FloatCol(help_text='Top of Rupture Depth (km)')
    rupture_length = FloatCol()
    rupture_width = FloatCol()
    station_name = TextCol()
    station_country = TextCol()
    station_latitude = FloatCol(help_text="station latitude (deg)")  # bounds: [-90, 90]
    station_longitude = FloatCol(help_text="station longitude (deg)")  # bounds: [-180, 180]
    station_elevation = FloatCol(help_text="station elevation (Km)")  # FIXME unit
    vs30 = FloatCol(help_text="Average shear wave velocity in the top 30 "
                              "meters, in m/s")
    vs30_measured = BoolCol(help_text="whether or not the Vs30 is measured "
                                      "(default true)", default=True)
    vs30_sigma = FloatCol()
    depth_to_basement = FloatCol()
    z1 = FloatCol(help_text="Depth of the layer where seismic waves start to "
                            "propagate with a speed above 1.0 km/s, in meters")
    z2pt5 = FloatCol(help_text="Depth of the layer where seismic waves start "
                               "to propagate with a speed above 2.5 km/s, in km")
    repi = FloatCol(help_text="Epicentral distance (Km)")  # FIXME: unit
    rrup = FloatCol(help_text="Rupture_distance (Km)")  # FIXME: unit
    rjb = FloatCol(help_text="Joyner - Boore distance (Km)")  # FIXME: unit
    rhypo = FloatCol(help_text="Hypocentral distance (Km)")  # FIXME: unit
    rx = FloatCol()
    ry0 = FloatCol()
    azimuth = FloatCol()
    digital_recording = BoolCol(default=True)
    type_of_filter = TextCol()
    npass = IntCol(default=0)
    nroll = FloatCol()
    hp_h1 = FloatCol()
    hp_h2 = FloatCol()
    lp_h1 = FloatCol()
    lp_h2 = FloatCol()
    factor = FloatCol()
    lowest_usable_frequency_h1 = FloatCol()
    lowest_usable_frequency_h2 = FloatCol()
    lowest_usable_frequency_avg = FloatCol()
    highest_usable_frequency_h1 = FloatCol()
    highest_usable_frequency_h2 = FloatCol()
    highest_usable_frequency_avg = FloatCol()
    backarc = BoolCol(default=False)

    @classmethod
    def dtypes(cls) -> dict[str, "dtype"]:
        """"dict of all columns data types (pandas compatible)"""
        return {_: cls.fields[_].dtype for _ in cls.fields}

    @classmethod
    def to_dataframe(cls):
        import pandas as pd
        return pd.DataFrame({k: pd.Series(dtype=v) for k, v in cls.dtypes().items()})

    @classmethod
    def normalize_dataframe(cls, dataframe) -> "pd.DataFrame":
        dtypes = cls.dtypes()
        import pandas as pd
        return pd.DataFrame({c: dataframe[c].astype(dtypes[c], copy=True)
                             for c in dataframe.columns if c in dtypes})

    class Meta:
        abstract = True

