'''
Created on 29 Jan 2018

@author: riccardo
'''
import warnings
from collections import OrderedDict

from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import __all__ as AVAL_IMTS  # FIXME: isn't there a nicer way?
from smtk.trellis.trellis_plots import DistanceIMTTrellis, DistanceSigmaIMTTrellis, MagnitudeIMTTrellis,\
    MagnitudeSigmaIMTTrellis, MagnitudeDistanceSpectraTrellis, MagnitudeDistanceSpectraSigmaTrellis
from openquake.hazardlib.scalerel import get_available_magnitude_scalerel


def get_menus():
    '''returns an OrderedDict of (menu_key, menuname) tuples. Each tuple represents a menu
    in the home web page'''
    return OrderedDict([('home', 'Home'), ('trellis', 'Trellis plots'),
                        ('residuals', 'Residuals'), ('loglikelihood', 'Log-likelihood analysis')])


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


class Gsims(object):

    def __init__(self):
        ret = OrderedDict()
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore')
            for key, gsim in get_available_gsims().items():
                try:
                    gsim_inst = gsim()
                except (TypeError, OSError, NotImplementedError) as exc:
                    gsim_inst = gsim
                ret[key] = (set(imt.__name__
                                for imt in gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES),
                            gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE,
                            tuple(n for n in gsim_inst.REQUIRES_RUPTURE_PARAMETERS))
        self._data = ret

    def aval_gsims(self):
        return list(self._data.keys())

    def aval_imts(self):
        return list(AVAL_IMTS)

    def imtsof(self, gsim):
        '''Returns a set of the imts defined for the given gsim. If the gsim is not defined,
        returns an empty set. Otherwise, manipulation ot the returned set will modify the internal
        object and subsequent calls to this method
        :param gsim: string denoting the gsim name
        '''
        return self._data.get(gsim, [set()])[0]

    def shared_imts(self, *gsims):
        '''returns the shared imt(s) of the given gsims, ie. the intersection of all imt(s)
        defined for the given gsims
        :param gsims: (string) variable length argument of the gsim names whose shared imt(s)
            have to be returned
        '''
        ret = None
        for gsim in gsims:
            if ret is None:
                ret = self.imtsof(gsim)
            else:
                ret &= self.imtsof(gsim)
            if not ret:
                break
        return ret

    def jsonlist(self):
        '''Returns a json serialized version of this object, as a list of tuples of the form:
        [
        ...
        (gsim, imts, trt)
        ...
        ]
        where:
         - gsim: (string) the gsim name
         - imts (list of strings) the imt(s) defined for the given gsim
         - trt (string): the tectonic region type defined for the given gsim
        '''
        return [(gsim, list(self._data[gsim][0]), self._data[gsim][1]) for gsim in self._data]
