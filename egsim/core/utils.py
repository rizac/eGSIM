'''
Created on 29 Jan 2018

@author: riccardo
'''
from os import listdir
from os.path import join, dirname, isdir, splitext, isfile
from itertools import chain
import warnings
from collections import OrderedDict
from datetime import datetime
from dateutil import parser as dateparser
from dateutil.tz import tzutc

import json

from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import registry as hazardlib_imt_registry, IMT
from smtk import load_database
from smtk.strong_motion_selector import SMRecordSelector
from openquake.hazardlib.scalerel import get_available_magnitude_scalerel
from openquake.hazardlib.const import TRT
from copy import deepcopy
from collections.abc import Mapping
from openquake.hazardlib import imt


def vectorize(value):
    '''Returns value if it is an iterable, otherwise [value]. This method is primarily called from
    request/responses parameters where strings are considered scalars, i.e. not iterables
    (although they are in Python). Thus `vectorize('abc') = ['abc']` '''
    return [value] if isscalar(value) else value


def isscalar(value):
    '''Returns True if value is a scalr object, i.e. not having the attribute '__iter__'
    Note that strings and bytes are the only exceptions as they are considered scalars
    '''
    return not hasattr(value, '__iter__') or isinstance(value, (str, bytes))


class Egsim:
    '''wrapper around a gsim name in string format: it subclasses str and adds two methods,
    `imts` (set of gsim intensioty measure types) and `trt`
    (string denoting the openquake tectonic region type)'''
    def __init__(self, name, imts, trt):
        '''Initializes a new Egsim
        :param gsim: string, name of the gsim
        :param imts: iterable of strings denoting the gsim intensoty measure types
        :pram trt: string, tectonic region type defined for the gsim
        '''
        self.name = name
        self.imts = frozenset(imts)
        self.trt = trt

    def __str__(self):
        return self.name

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name.__eq__(other)

#     # the deepcopy method is called by django. the copy method is implemented for
#     # compatibility. see https://stackoverflow.com/a/15774013/3526777
#     def __deepcopy__(self, memo):
#         result = self.__class__(self, self.imts, self.trt)
#         result.imts = deepcopy(self.imts, memo)
#         result.trt = deepcopy(self.trt, memo)  # this is catually no-op
#         memo[id(self)] = result
#         return result

    def asjson(self):
        '''Converts this object as a json-serializable tuple of strings:
        (gsim, imts, tectonic_region_type) where the first and last arguments
        are strings, and the second is a list of strings'''
        return self.name, list(self.imts), self.trt


def _get_data():
    '''Returns a tuple of three elements:
    1) all openquake-available gsim data in an Ordered dict keyed with the gsim
        names mapped to a Egsim object
    2) all openquake available imts (set of strings)
    3) all openquake available tectonic region types (set of strings)
    '''

    _aval_imts = OrderedDict()  # this should be a set of strings, but we want it ordered ...

    def sanitycheck(imt_objs):
        '''filters out the elements of `imt_obj` which require additional
           argument (except SA, which is fine) because we do not know how to deal with them,
           and populates the keys of _aval_imts representing all imts passed here, with no
           repetitions'''
        for imt_obj in imt_objs:
            imt_s = imt_obj.__name__
            if imt_s not in _aval_imts:
                imt_v = hazardlib_imt_registry.get(imt_s, None)
                if imt_v is None:
                    continue
                if imt_v != imt.SA:  # test we di not need arguments if imt is not SA
                    try:
                        # this creates an instance of the class. If the instance needs argument,
                        # it fails (except below)
                        imt.from_string(imt_s)
                    except:  # @IgnorePep8 pylint: disable=bare-except
                        continue
                _aval_imts[imt_s] = None  # whatever value is fine, None is just the one chosen ...
            yield imt_s

    # get all TRTs: use the TRT class of openquake and get all attributes without a leading
    # underscore and mapped to a string:
    _aval_trts = set(getattr(TRT, a) for a in dir(TRT) if a[:1] != '_'
                     and isinstance(getattr(TRT, a), str))

    # get all gsims:
    _aval_gsims = OrderedDict()
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        for key, gsim in get_available_gsims().items():
            try:
                gsim_inst = gsim()
            except (TypeError, OSError, NotImplementedError) as exc:
                gsim_inst = gsim
            gsim_imts = gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES
            if gsim_imts and hasattr(gsim_imts, '__iter__'):
                _aval_gsims[key] = Egsim(key, (_ for _ in sanitycheck(gsim_imts)),
                                         gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE)
#             if gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES:
#                 ret[key] = (set(imt.__name__ for imt in gsim_imts),
#                             gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE,
#                             tuple(n for n in gsim_inst.REQUIRES_RUPTURE_PARAMETERS))
    return _aval_gsims, list(_aval_imts.keys()), _aval_trts


# def _get_tr_models():  # https://stackoverflow.com/a/6798042
#     '''Load all tectonic region models as a dict of project name (string) mapped to its
#     geojson dict'''
#     ret = {}
#     for project in ['share']:  # FIXME: better handling
#         filepath = join(dirname(dirname(__file__)), 'data', '%s.geojson' % project)
#         with open(filepath) as fpt:  # https://stackoverflow.com/a/14870531
#             # filepath.seek(0)
#             ret[project] = json.load(fpt)
#     return ret


def _convert(func):
    '''function acting as decorator returning None if the input is None, otherwise calling
    func(input). Example: _convert(float)('5.5')
    '''
    def wrapper(string):
        '''wrapping function'''
        if not string or string is None:
            return None
        return func(string)
    return wrapper


class EGSIM:  # For metaclasses (not used anymore): https://stackoverflow.com/a/6798042
    '''Namespace container for Openquake related data used in this program'''
    _aval_gsims, _aval_imts, _aval_trts = _get_data()
#     _aval_imts = set(hazardlib_imts_dict.keys())
#     _aval_trts = None
    _trmodels = None  # dict of names mapped to a geojson colleciton (will be lazily created)
    _gmdbs = {}  # ground motion databases: name (str) -> [file_path, ground motion db obj
    _gmdbs_selections = {}
    # _aval_msr = None  # An OrderedDict with the available Magnitude ScaleRel (lazily created)

    @classmethod
    def gmdb_selections(cls):
        '''Returns a dict of strings mapped to the conversion function'''
        if not cls._gmdbs_selections:
            cls._gmdbs_selections = {'distance': _convert(float), 'vs30': _convert(float),
                                     'magnitude': _convert(float), 'time': _convert(strptime),
                                     'depth': _convert(float)}
        return cls._gmdbs_selections

    @classmethod
    def gmdb_names(cls):
        if not cls._gmdbs:
            # FIXME: hardcoded, change it!
            root = join(dirname(dirname(dirname(__file__))),
                        'tmp', 'data', 'flatfiles', 'output')
#             root = ("/Users/riccardo/work/gfz/projects/sources/"
#                     "python/egsim/tmp/data/flatfiles/output")
            cls._gmdbs = {f: [join(root, f), None] for f in listdir(root)
                          if isdir(join(root, f))}
        return list(cls._gmdbs.keys())

    @classmethod
    def gmdb(cls, name):
        '''Returns a GroundMotionDatabase from the given file name (not path, just the name)'''
        entry = cls._gmdbs[name]
        if entry[1] is None:
            entry[1] = load_database(entry[0])
        return entry[1]

#     @classmethod
#     def trmodel_names(cls):
#         '''Returns a list of all available tectonic region model names (string)'''
#         if not cls._trmodels:
#             # FIXME: hardcoded, change it!
#             root = join(dirname(dirname(__file__)), 'data')
#             cls._trmodels = {splitext(f)[0]: [join(root, f), None] for f in listdir(root)
#                              if splitext(f)[1].lower() == '.geojson'}
#         return list(cls._trmodels.keys())
# 
#     @classmethod
#     def trmodel(cls, name):
#         '''Returns a dict representing a geojson collection from the given tectonic region
#         model name'''
#         entry = cls._trmodels[name]
#         if entry[1] is None:
#             with open(entry[0]) as fpt:  # https://stackoverflow.com/a/14870531
#                 # filepath.seek(0)
#                 entry[1] = json.load(fpt)
#         return entry[1]

    @classmethod
    def trmodels(cls):
        '''Returns a list of all available tectonic region model names (string)'''

        def loadjson(filepath):
            '''loads json from file'''
            with open(filepath) as fpt:  # https://stackoverflow.com/a/14870531
                return json.load(fpt)

        if not cls._trmodels:
            # FIXME: hardcoded, change it!
            root = join(dirname(dirname(__file__)), 'data')
            cls._trmodels = {splitext(f)[0]: loadjson(join(root, f)) for f in listdir(root)
                             if splitext(f)[1].lower() == '.geojson'}
        return cls._trmodels
#     for project in ['share']:
#         filepath = join(dirname(dirname(__file__)), 'data', '%s.geojson' % project)
#         with open(filepath) as fpt:  # https://stackoverflow.com/a/14870531
#             # filepath.seek(0)
#             ret[project] = json.load(fpt)
#     return ret

#     @classmethod
#     def tr_models(cls):
#         '''Returns a list of all available GSIM names (string)'''
#         if cls._tr_projects is None:
#             cls._tr_projects = _get_tr_models()
#         return cls._tr_projects

    @classmethod
    def aval_gsims(cls):
        '''Returns a dict of all available GSIM names (string) mapped to their Egsim object'''
        return cls._aval_gsims

    @classmethod
    def aval_imts(cls):
        '''Returns a list of all available IMT names (strings)'''
        return list(cls._aval_imts)

#     @classmethod
#     def aval_msr(cls):
#         '''Returns an Ordered dict of the available Magnitude ScaleRel'''
#         if cls._aval_msr is None:
#             cls._aval_msr = get_available_magnitude_scalerel()
#         return cls._aval_msr

    @classmethod
    def aval_trts(cls):
        '''Returns a list of all available tectonic region types (strings)'''
        return list(cls._aval_trts)

#     @classmethod
#     def imtsof(cls, gsim):
#         '''Returns a set of the imts defined for the given gsim. If the gsim is not defined,
#         returns an empty set. NOTE: if the `gsim` is defined,  **manipulating the returned set
#         will modify the internal object and subsequent calls to this method**
# 
#         :param gsim: string denoting the gsim name
#         '''
#         return cls._data.get(gsim, [set()])[0]
# 
#     @classmethod
#     def trtof(cls, gsim):
#         '''Returns a string defining the tectonic region type of the given gsim. If the gsim is
#         not defined, returns an empty string
# 
#         :param gsim: string denoting the gsim name
#         '''
#         return cls._data.get(gsim, ['', ''])[1]

#     @classmethod
#     def invalid_gsims(cls, gsims, imts):
#         '''returns a *list* of all invalid gsim(s) from the given selected gsims and imts
# 
#         :param gsims: iterable of strings denoting the selected gsims
#         :param gsims: iterable of strings denoting the selected imts
#         :return: a list of invalid gsims
#         '''
#         if not isinstance(imts, set):
#             imts = set(imts)
# #         if imts == cls._aval_imts:  # as no gsim is defined for all imts, thus return the list
# #             return list(gsims)
#         return [gsim for gsim in gsims if imts - gsim.imts]

#     @classmethod
#     def shared_imts(cls, *gsims):
#         '''returns the shared imt(s) of the given gsims, ie. the intersection of all imt(s)
#         defined for the given gsims
#         :param gsims: list of strings denoting the selected gsims
#         :param gsims: list of strings denoting the selected imts
#         '''
#         ret = set()
#         for gsim in gsims:
#             if not ret:
#                 ret = cls.imtsof(gsim)
#             else:
#                 ret &= cls.imtsof(gsim)
#             if not ret:
#                 break
#         return ret

#     @classmethod
#     def jsonlist(cls):
#         '''Returns a json-serializable version of this object, as a list of tuples of the form:
#         ```
#         [ ... , (gsim, imts, trt) , ... ]
#         ```
#         where:
#          - gsim: (string) is the gsim name
#          - imts (list of strings) are the imt(s) defined for the given gsim
#          - trt (string) is the tectonic region type defined for the given gsim
#         '''
#         return [(gsim, list(cls._data[gsim][0]), cls._data[gsim][1]) for gsim in cls._data]


def strptime(obj):
    """
        Converts `obj` to a `datetime` object **in UTC without tzinfo**.
        If `obj` is string, creates a `datetime` object by parsing it. If `obj`
        is not a date-time object, raises TypeError. Otherwise, uses `obj` as `datetime` object.
        Then, if the datetime object has a tzinfo supplied, converts it to UTC and removes the
        tzinfo attribute. Finally, returns the datetime object
        Implementation details: `datetime.strptime`does not keep time zone information in the
        parsed date-time, nor it recognizes 'Z' as 'UTC' (raises instead). The library `dateutil`,
        on the other hand, is too permissive and has too many false "positives"
        (e.g. integers or strings such as  '5-7' are succesfully parsed into date-time).
        We choose `dateutil` as the code is shorter, cleaner, and a single hack is needed:
        we simply check, after a string `obj` is succesfully parsed into `dtime`, that `obj`
        contains at least the string `dtime.strftime(format='%Y-%m-%d')` (such as e,g, '2006-01-31')
        :param obj: `datetime` object or string in ISO format (see examples below)
        :return: a datetime object in UTC, with the tzinfo removed
        :raise: TypeError or ValueError
        :Example. These are all equivalent:
        ```
            strptime("2016-06-01T00:00:00.000000Z")
            strptime("2016-06-01T00.01.00CET")
            strptime("2016-06-01 00:00:00.000000Z")
            strptime("2016-06-01 00:00:00.000000")
            strptime("2016-06-01 00:00:00")
            strptime("2016-06-01 00:00:00Z")
            strptime("2016-06-01")
            This raises ValueError:
            strptime("2016-06-01Z")
            This raises TypeError:
            strptime(45.5)
        ```
    """
    dtime = obj
    if isinstance(obj, str):
        try:
            dtime = dateparser.parse(obj, fuzzy=False, fuzzy_with_tokens=False)
            # now, dateperser is quite hacky on purpose, guessing too much.
            # datetime.strptime, on the other hand, does not parse Z as UTC (raises in case)
            # and does not include the timezone in the parsed date. The best (hacky) solution
            # is to assert the bare minimum: that %Y-%m-%d is in dtime:
            assert dtime.strftime('%Y-%m-%d') in obj
        except Exception as exc:
            raise ValueError(str(exc))

    if not isinstance(dtime, datetime):
        raise TypeError('string or datetime required, found %s' % str(type(obj)))

    if dtime.tzinfo is not None:
        # if a time zone is specified, convert to utc and remove the timezone
        dtime = dtime.astimezone(tzutc()).replace(tzinfo=None)

    # the datetime has no timezone provided AND is in UTC:
    return dtime
