'''
Created on 29 Jan 2018

@author: riccardo
'''
from itertools import chain
import warnings
from collections import OrderedDict

from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import __all__ as AVAL_IMTS


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


def get_gsims():
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


def _create_gsims(name, types, attrs):
    cls = type(name, types, attrs)
    cls._data = get_gsims()  # pylint: disable=protected-access
    return cls


class EGSIM(metaclass=_create_gsims):
    '''This class is basically a namespace container which does not need to be instantiated
    but can be referenced as a global variable and holds global data fetched from openquake
    primarily'''
    _data = {}  # will be populated when creating the class (note: the class, not the object)

    @classmethod
    def aval_gsims(cls):
        '''Returns a list of all available GSIM names (string)'''
        return list(cls._data.keys())

    @staticmethod
    def aval_imts():
        '''Returns a list of all available IMT names (string)'''
        return list(AVAL_IMTS)

    @classmethod
    def imtsof(cls, gsim):
        '''Returns a set of the imts defined for the given gsim. If the gsim is not defined,
        returns an empty set. Otherwise, manipulation ot the returned set will modify the internal
        object and subsequent calls to this method
        :param gsim: string denoting the gsim name
        '''
        return cls._data.get(gsim, [set()])[0]

    @classmethod
    def shared_imts(cls, *gsims):
        '''returns the shared imt(s) of the given gsims, ie. the intersection of all imt(s)
        defined for the given gsims
        :param gsims: (string) variable length argument of the gsim names whose shared imt(s)
            have to be returned
        '''
        ret = set()
        for gsim in gsims:
            if not ret:
                ret = cls.imtsof(gsim)
            else:
                ret &= cls.imtsof(gsim)
            if not ret:
                break
        return ret

    @classmethod
    def jsonlist(cls):
        '''Returns a json-serialized version of this object, as a list of tuples of the form:
        ```
        [ ... , (gsim, imts, trt) , ... ]
        ```
        where:
         - gsim: (string) is the gsim name
         - imts (list of strings) are the imt(s) defined for the given gsim
         - trt (string) is the tectonic region type defined for the given gsim
        '''
        return [(gsim, list(cls._data[gsim][0]), cls._data[gsim][1]) for gsim in cls._data]
