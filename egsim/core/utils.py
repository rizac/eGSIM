'''
Created on 29 Jan 2018

@author: riccardo
'''
from os import listdir
from os.path import join, dirname, isdir
from itertools import chain
import warnings
from collections import OrderedDict
from datetime import datetime
from dateutil import parser as dateparser
from dateutil.tz import tzutc

import json

from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import registry as hazardlib_imts_dict
from smtk import load_database
from smtk.strong_motion_selector import SMRecordSelector
from openquake.hazardlib.scalerel import get_available_magnitude_scalerel


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


def unique(*iterables):
    '''returns a list of unique values in any iterable, whilst preserving the order
    of each element of iterables'''
    odict = OrderedDict()
    for val in chain(*iterables):
        odict[val] = None
    return list(odict.keys())


def _get_gsims():
    '''Returns all openquake-available gsim data in an Ordered dict keyed with the gsim
    names mapped to a tuples of the form: (imts, trt, rupt_param)
    where imts is a set of strings denoting the IMTs defined for the given gsim,
    trt is a string denoting the tectonic region type, and
    rupt_params (not used in the current implementation) is a tuple of parameter names
        required for calculating a the rupture with the given gsim (FIXME: check)
    '''
    ret = OrderedDict()
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        for key, gsim in get_available_gsims().items():
            try:
                gsim_inst = gsim()
            except (TypeError, OSError, NotImplementedError) as exc:
                gsim_inst = gsim
            gsim_imts = gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES
            if not hasattr(gsim_imts, '__iter__'):
                continue
            if gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES:
                ret[key] = (set(imt.__name__
                                for imt in gsim_imts),
                            gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE,
                            tuple(n for n in gsim_inst.REQUIRES_RUPTURE_PARAMETERS))
    return ret


def _get_tr_projects():  # https://stackoverflow.com/a/6798042
    '''Load all tectonic region projects as a dict of project name (string) mapped to its
    geojson dict'''
    ret = {}
    for project in ['share']:  # FIXME: better handling
        filepath = join(dirname(dirname(__file__)), 'data', '%s.geojson' % project)
        with open(filepath) as fpt:  # https://stackoverflow.com/a/14870531
            # filepath.seek(0)
            ret[project] = json.load(fpt)
    return ret


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
    '''This class is basically a namespace container which does not need to be instantiated
    but can be referenced as a global variable and holds global data fetched from Openquake
    primarily'''
    _data = _get_gsims()
    _aval_imts = set(hazardlib_imts_dict.keys())
    _aval_trts = None  # set (will lazily populated on demand)
    _tr_projects = None  # dict (will be lazily created)
    _gmdbs = {}  # ground motion databases: name (str) -> [file_path, ground motion db obj
    _gmdbs_selections = {}
    _aval_msr = None  # An OrderedDict with the available Magnitude ScaleRel (lazily created)

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
            root = ("/Users/riccardo/work/gfz/projects/sources/"
                    "python/egsim/tmp/data/flatfiles/output")
            cls._gmdbs = {f: [join(root, f), None] for f in listdir(root)
                          if isdir(join(root, f))}
        return list(cls._gmdbs.keys())

    @classmethod
    def gmdb(cls, name):
        '''Returns a GroundMotionDatabase from the given file name (not path, just the name)'''
        entry = cls._gmdbs.get(name, None)
        if entry is None:
            return entry
        if entry[1] is None:
            entry[1] = load_database(entry[0])
        return entry[1]

    @classmethod
    def tr_projects(cls):
        '''Returns a list of all available GSIM names (string)'''
        if cls._tr_projects is None:
            cls._tr_projects = _get_tr_projects()
        return cls._tr_projects

    @classmethod
    def aval_gsims(cls):
        '''Returns a list of all available GSIM names (string)'''
        return list(cls._data.keys())

    @classmethod
    def aval_imts(cls):
        '''Returns a list of all available IMT names (string)'''
        return list(cls._aval_imts)

    @classmethod
    def aval_msr(cls):
        '''Returns an Ordered dict of the available Magnitude ScaleRel'''
        if cls._aval_msr is None:
            cls._aval_msr = get_available_magnitude_scalerel()
        return cls._aval_msr

    @classmethod
    def aval_trts(cls):
        '''Returns a list of all available tectonic region types (strings)'''
        # lazy load:
        if cls._aval_trts is None:
            ret = cls._aval_trts = set()
            for data in cls._data.values():
                ret.add(data[1])
        return cls._aval_trts

    @classmethod
    def imtsof(cls, gsim):
        '''Returns a set of the imts defined for the given gsim. If the gsim is not defined,
        returns an empty set. NOTE: if the `gsim` is defined,  **manipulating the returned set
        will modify the internal object and subsequent calls to this method**

        :param gsim: string denoting the gsim name
        '''
        return cls._data.get(gsim, [set()])[0]

    @classmethod
    def trtof(cls, gsim):
        '''Returns a string defining the tectonic region type of the given gsim. If the gsim is
        not defined, returns an empty string

        :param gsim: string denoting the gsim name
        '''
        return cls._data.get(gsim, [''])[1]

    @classmethod
    def invalid_imts(cls, gsims, imts):
        '''returns a *set* of all invalid imt(s) from the given selected gsims and imts

        :param gsims: iterable of strings denoting the selected gsims
        :param gsims: iterable of strings denoting the selected imts
        :return: a set of invalid imts
        '''
        if not isinstance(imts, set):
            imts = set(imts)
        imts_count = len(cls._aval_imts)
        invalid_imts = set()
        for gsim in gsims:
            invalid_ = imts - cls.imtsof(gsim)
            if not invalid_:
                continue
            invalid_imts |= invalid_
            if len(invalid_imts) == imts_count:
                break
        return invalid_imts

    @classmethod
    def invalid_gsims(cls, gsims, imts):
        '''returns a *list* of all invalid gsim(s) from the given selected gsims and imts

        :param gsims: iterable of strings denoting the selected gsims
        :param gsims: iterable of strings denoting the selected imts
        :return: a list of invalid gsims
        '''
        if not isinstance(imts, set):
            imts = set(imts)
#         if imts == cls._aval_imts:  # as no gsim is defined for all imts, thus return the list
#             return list(gsims)
        return [gsim for gsim in gsims if imts - cls.imtsof(gsim)]

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

    @classmethod
    def jsonlist(cls):
        '''Returns a json-serializable version of this object, as a list of tuples of the form:
        ```
        [ ... , (gsim, imts, trt) , ... ]
        ```
        where:
         - gsim: (string) is the gsim name
         - imts (list of strings) are the imt(s) defined for the given gsim
         - trt (string) is the tectonic region type defined for the given gsim
        '''
        return [(gsim, list(cls._data[gsim][0]), cls._data[gsim][1]) for gsim in cls._data]


def strptime(obj):
    """
        Converts `obj` to a `datetime` object **in UTC without tzinfo**. This function should be
        used within this program as the opposite of `datetime.isoformat()` for parsing date times
        from, e.g. web service queries or command line inputs, under the assumption that no
        time zone means UTC.
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
