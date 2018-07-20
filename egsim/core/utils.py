'''
Created on 29 Jan 2018

@author: riccardo
'''
from os.path import join, dirname
from itertools import chain
import warnings
from collections import OrderedDict

import json

from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import __all__ as hazardlib_imts


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
            if gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES:
                ret[key] = (set(imt.__name__
                                for imt in gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES),
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


class EGSIM:  # For metaclasses (not used anymore): https://stackoverflow.com/a/6798042
    '''This class is basically a namespace container which does not need to be instantiated
    but can be referenced as a global variable and holds global data fetched from openquake
    primarily'''
    _data = _get_gsims()
    _aval_imts = set(hazardlib_imts)
    _aval_trts = None  # set (will lazily populated on demand)
    _tr_projects = None  # dict (will be lazily created)

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
