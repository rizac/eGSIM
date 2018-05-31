'''
Created on 29 Jan 2018

@author: riccardo
'''
from collections import OrderedDict

from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import __all__ as available_imts  # FIXME: isn't there a nicer way?


def get_menus():
    return OrderedDict([('home', 'Home'), ('trellis', 'Trellis plots'),
                        ('residuals', 'Residuals'), ('loglikelihood', 'Log-likelihood analysis')])


class InitData(object):
    '''Just a wrapper housing Initialization data stuff'''
    available_gsims = get_available_gsims()

    available_gsims_names = available_gsims.keys()

    available_imts_names = list(available_imts)

    gsims2imts = {key: set([imt.__name__ for imt in gsim.DEFINED_FOR_INTENSITY_MEASURE_TYPES])
                  for key, gsim in available_gsims.items()}

    gsim2trts = {key: gsim.DEFINED_FOR_TECTONIC_REGION_TYPE
                 for key, gsim in available_gsims.items()}

    @classmethod
    def get_available_gsims_json(cls):
        return [(g_name, list(cls.gsims2imts.get(g_name, [])), cls.gsim2trts.get(g_name, ''))
                for g_name in cls.available_gsims_names]

    @classmethod
    def imtdefinedfor(cls, gsim_name, *imt_names):
        return all(imt_name in cls.gsims2imts.get(gsim_name, []) for imt_name in imt_names)

