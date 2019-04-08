'''
Models for the django app

Currently they represent only read-only data from Tectonic Regionalisations
(provided by custom input files) and OpenQuake Imts, Gsims and Trt

Created on 5 Apr 2019

@author: riccardo
'''
import json

from django.db import models
from django.db.models import Q
from django.db.models.aggregates import Count
# primary keys are auto added if not present

from shapely.geometry import Point, shape, Polygon


ENTITIES = (('gsim', 'Ground Shaking Intensity Model'),
            ('imt', 'Intensity Measure Type'),
            ('trt', 'Tectonic Region Type'))


class Error(models.Model):
    '''Model representing the Errors table. The table stores information
    during the creation of the database for diagnistic purposes only'''

    entity_key = models.TextField(unique=True)
    entity_type = models.CharField(max_length=4, choices=ENTITIES)
    type = models.TextField()
    message = models.TextField()

    def __str__(self):
        return '%s "%s": %s (%s)' % (self.entity_type,
                                     self.entity_key,
                                     self.type,
                                     self.message)


class Trt(models.Model):
    '''Model representing the db table of the (OpenQuake) Tectonic region types
    '''
    key = models.TextField(unique=True)  # no need to set it (see below)
    oq_att = models.CharField(max_length=100, unique=True)
    oq_name = models.TextField(unique=True)

    def save(self, *args, **kwargs):  # pylint: disable=arguments-differ
        # Django does not have hybrid attributes. Workaround is to set the key
        # from the oq_name (https://stackoverflow.com/a/7558665)
        if not self.key:  # it might be empty string (the def.)
            self.key = self.oq_name.replace(' ', '_').lower()  # pylint: disable=no-member
        super(Trt, self).save(*args, **kwargs)

    def __str__(self):
        return self.key


class TectonicRegion(models.Model):
    '''Model representing the db table of Tectonic regions used for gsim
    selection
    '''

    model = models.TextField(null=False)
    geojson = models.TextField(blank=True)
    type = models.ForeignKey(Trt, on_delete=models.CASCADE, null=False)

    def __str__(self):
        return "Tr %d (model: %s, type: %s)" \
            % (self.id, self.model, self.trt.key)  # pylint: disable=no-member


class Imt(models.Model):
    '''Model representing the db table of the (OpenQuake) Intensity Measure
    Types
    '''

    key = models.CharField(max_length=100, unique=True)
    needs_args = models.BooleanField(default=False, null=False)

    def __str__(self):
        return self.key


class Gsim(models.Model):
    '''Model representing the db table of the (OpenQuake) Ground Shaking
    Intensity Models, or GMPE
    '''

    # currently, the max length of the OQ gsims is 43 ...
    key = models.TextField(null=False, unique=True)
    trt = models.ForeignKey(Trt, on_delete=models.CASCADE, null=False)
    imts = models.ManyToManyField(Imt, related_name='gsims')
    needs_args = models.BooleanField(default=False, null=False)
    warning = models.TextField(default=None, null=True)

    def asjson(self):
        '''Converts this object as a json-serializable tuple of strings:
        (gsim, imts, tectonic_region_type, warning) where arguments are all
        strings except 'imts' which is a tuple of strings'''
        trt = self.trt.key  # pylint: disable=no-member
        imts = (_.key for _ in self.imts.all())  # pylint: disable=no-member
        return self.key, tuple(imts), trt, self.warning or ''

    def __str__(self):
        return self.key


# utilities:

def empty_all():
    '''Emtpies all tables'''
    Error.objects.all().delete()  # pylint: disable=no-member
    Gsim.objects.all().delete()  # pylint: disable=no-member
    Imt.objects.all().delete()  # pylint: disable=no-member
    TectonicRegion.objects.all().delete()  # pylint: disable=no-member
    Trt.objects.all().delete()  # pylint: disable=no-member


# def get_gsims_asjson(sort=True):
#     '''
#         Returns a tuple of Gsims in json serializable format:
#         (gsim.key, [gsim.imt1.key, .. gsim.imtN.key], gsim.trt, gsim.warning)
#         where all tuple elements are strings.
#
#         :param sort: returns the Gsim sorted according to their key (Gsim
#             unique name)
#     '''
#     ret = {}  # in python 3.7+ dicts preserve insertion order
#     manager = Gsim.objects  # pylint: disable=no-member
#     # https://docs.djangoproject.com/en/2.2/ref/models/querysets/#select-related:
#     queryset = manager.prefetch_related('imts').select_related('trt')
#     if sort:
#         queryset = queryset.order_by('key')
#     for gsim in queryset.all():
#         if gsim.key in ret:  # should not happen, but for safety ...
#             continue
#         ret[gsim.key] = gsim.asjson()
#     return tuple(ret.values())


def aval_gsims(asjsonlist=False):
    '''Returns a list of available gsims.

    If asjsonlist=False (the default), the list elements are strings denoting
    the Gsim names (attribute gsim.key).

    If asjsonlist is True, the list elements are json serializable tuples:
        (gsim.key, [gsim.imt1.key, .. gsim.imtN.key], gsim.trt, gsim.warning)
    where all tuple elements are strings.

    The gsims are returned sorted alphabetically
    '''
    if not asjsonlist:
        return list(gsim_names())

    manager = Gsim.objects  # pylint: disable=no-member
    # https://docs.djangoproject.com/en/2.2/ref/models/querysets/#select-related:
    queryset = manager.prefetch_related('imts').select_related('trt').\
        order_by('key')
    return [_.asjson() for _ in queryset.all()]


def aval_imts():
    '''Returns a QuerySet of strings denoting the available imts'''
    imtobjects = Imt.objects  # pylint: disable=no-member
    # return imts mapped to at least one gsim
    # (https://stackoverflow.com/a/12101599)
    # for values_list, see: https://stackoverflow.com/a/37205928
    return imtobjects.annotate(c=Count('gsims')).filter(c__gt=0).\
        values_list('key', flat=True)


def aval_trts(include_oq_name=False):
    '''Returns a QuerySet of strings denoting the available Trts
    The Trts are returned sorted alphabetically'''
    trtobjects = Trt.objects  # pylint: disable=no-member
    if include_oq_name:
        return trtobjects.order_by('key').values_list('key', 'oq_name')
    return trtobjects.order_by('key').values_list('key', flat=True)


def aval_trmodels():
    trobjects = TectonicRegion.objects  # pylint: disable=no-member
    return trobjects.order_by('model').values_list('model', flat=True).distinct()


def gsim_names(gsims=None, imts=None, trts=None, tr_selector=None):
    '''
        Returns a QuerySet
        (https://docs.djangoproject.com/en/2.2/ref/models/querysets/)
        of Gsim names (strings) matching the given criteria.
        A Gsim name is the OpenQuake name and actually acts as a
        unique key for that Gsim (this is why it is referred as key in the
        Model).
        Note that Gsims having ANY of the provided imt(s) AND
        ANY of the provided trt(s) will be returned, where ANY stands for
        "at least one of".

        :param gsims: iterable of strings (Gsim.key) or Gsim instances, or
            both. If None (the default), no filter is applied. Otherwise,
            return Gsims whose name matches any of the provided Gsim(s)
        :param imts: iterable of strings (Imt.key) or Imt instances, or both.
            If None (the default), no filter is applied. Otherwise, return
            Gsims whose imts match any of the provided imt(s)
        :param trts: iterable of strings (Trt.key) or Trt instances, or both.
            If None (the default), no filter is applied. Otherwise, return
            only Gsims defined for any of the provided trt(s)
        :param tr_selector: a Tectonic region selector (see class
            `TrSelector`) based on any tectonic regionalisation defined on the
            database (see 'TectonicRegion' model) for filtering the search to
            a specific geographical point or rectangle. If None, nothing
            is filtered
        :param sort: when True (the default), the returned Gsims will be
            sorted ascending alphabetically
            (https://docs.djangoproject.com/en/2.2/ref/models/querysets/#order-by)
    '''
    # trt can be a trt instance, an int denoting the trt pkey,
    # or a string denoting the trt key field (unique)
    # in the expressions .filter(imts_in=[...]) the arguments in
    # list can be pkey (ints) or instances. We want to allow also
    # to pass imt keys (names). In this case we need to use
    # the Q function. For info see:
    # https://docs.djangoproject.com/en/2.2/topics/db/examples/many_to_one/
    # https://docs.djangoproject.com/en/2.2/topics/db/queries/

    gsimobjects = Gsim.objects  # pylint: disable=no-member

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
    '''Concatenates the given Q expression with an 'OR'. Returns None if
    `q_expressions` (iterable) has no items'''
    expr = None
    for expr_chunk in q_expressions:
        if expr is None:
            expr = expr_chunk
        else:
            expr |= expr_chunk
    return expr


def and_(q_expressions):
    '''Concatenates the given Q expression with an 'AND'. Returns None if
    `q_expressions` (iterable) has no items'''
    expr = None
    for expr_chunk in q_expressions:
        if expr is None:
            expr = expr_chunk
        else:
            expr &= expr_chunk
    return expr


# These are the possible combinations

# trts OK
# model+point OK
# model+point+trts OK (intersection between trts and model's trts is returned) 
# point NO (which model?)
# model NO (might be OK, but NO for simplicity)
# trts+point NO (which model?)
# trts+model NO (might be OK, but NO for simplicity)

class TrSelector:
    '''This object allows selection of Trt (tectonic region types
    from a given tectonic regionalisation (TR) and a specified point
    (or rectangle) defined on TR. The method get_trt_names will return all
    Trt(s) matching the given criteria
    '''

    def __init__(self, tr_model, lon0, lat0, lon1=None, lat1=None):
        '''Initializes this object. Call the method `get_trt_names` to return
        the Trt(s) matching this object.

        If specifiec, lon1 and lat1 will take the same values as lon0 and lat0,
        and will define a rectangle and all Trt(s) *intersecting* it will be
        returned. Otherwise, all Trt(s) *including* the point specified by
        lon0 and lat0 will be returned.

        :param tr_model: string. a tectonic regionalisation model, must be present
            int the table 'TectonicRegions' under the 'model' column
        :param lon0: float, the latitude (in degreees) of the point
        :param lon0: float, the longitude (in degrees) of the point
        '''
        self.tr_model = tr_model
        if lon1 is None or lat1 is None:
            self.shape = Point([lon0, lat0])
        else:
            self.shape = Polygon([(lon0, lat0), (lon0, lat1),
                                  (lon1, lat1), (lon1, lat0)])

    def get_trt_names(self, trts=None):
        geojsons = TectonicRegion.objects.filter(model=self.tr_model)
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

# def _or(expressions):
#     expr = expressions[0]
#     for expr_ in expressions[1:]:
#         expr |= expr_
#     return expr
# 
# 
# def _and(expressions):
#     expr = expressions[0]
#     for expr_ in expressions[1:]:
#         expr &= expr_
#     return expr
