'''
Created on 31 May 2018

@author: riccardo
'''
from collections import OrderedDict

import numpy as np

from smtk.trellis.trellis_plots import DistanceIMTTrellis, DistanceSigmaIMTTrellis,\
    MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis, MagnitudeDistanceSpectraTrellis, \
    MagnitudeDistanceSpectraSigmaTrellis
from smtk.trellis.configure import GSIMRupture

from egsim.utils import vectorize
from egsim.core import validate
from egsim.forms import TrellisForm


MAG = 'magnitude'
DIST = 'distance'
DIP = 'dip'
ASP = 'aspect'
TRT = 'tectonic_region'
RAKE = 'rake'
ZTOR = 'ztor'
STRIKE = 'strike'
MSR = 'msr'
INITPT = 'initial_point,initpt'
HYPLOC = 'hypocentre_location'
VS30 = 'vs30'
VS30MEAS = 'vs30_measured,vs30m'
LINEAZI = 'line_azimuth'
Z1PT0 = 'z1pt0'
Z2PT5 = 'z2pt5'
BAC = 'backarc'
GSIM = 'gsim'
IMT = 'imt'


@validate(TrellisForm)
def distance_imt(params):  # FIXME: distances hardcoded WHERE?
    # vectorizable on: sigma/median, magnitudes
    
    # magnitude, dip, aspect, 
#     tectonic_region='Active Shallow Crust', rake=0., ztor=0., 
#     strike=0., msr=WC1994(), initial_point=DEFAULT_POINT, 
#     hypocentre_location=None)
    mag, dip, aspect, gsim, imt = params[MAG], params[DIP], params[ASP], params[GSIM], params[IMT]

    # parse other parameters:
    optparams = {k: params[k]
                 for k in [TRT, RAKE, ZTOR, STRIKE, MSR, INITPT, HYPLOC] if k in params}

    ret = None
    for class_ in [DistanceIMTTrellis, DistanceSigmaIMTTrellis]:
        for mag in vectorize(mag):
            rupture = GSIMRupture(mag, dip, aspect, **optparams)
            data = class_.from_rupture_model(rupture, gsim, imt, distance_type="rrup").to_dict()
            if ret is None:
                ret = {k: v for k, v in data.items() if k != 'figures'}
                ret['figures'] = []
            dst_figures = ret['figures']
            src_figures = data['figures']
            for fig in src_figures:
                fig.pop('column', None)
                fig.pop('row', None)
                fig['distance'] = fig['vs30'] = None
                fig['magnitude'] = mag
                dst_figures.append(fig)
    return ret


@validate(TrellisForm)
def magnitude_imt(params):  # FIXME: magnitudes hardcoded HERE?
    # vectorizable on: sigma/median, magnitudes
    
    # magnitude, dip, aspect, 
#     tectonic_region='Active Shallow Crust', rake=0., ztor=0., 
#     strike=0., msr=WC1994(), initial_point=DEFAULT_POINT, 
#     hypocentre_location=None)

    # dip, aspect will be used below, we oparse them here because they are mandatory (FIXME:
    # are they?)
    magnitude, distance, dip, aspect, gsim, imt = \
        params[MAG], params[DIST], params[DIP], params[ASP], params[GSIM], params[IMT]
    magnitudes = vectorize(magnitude)
    distances = vectorize(distance)

    # parse other parameters:
#     {"dip": 60.0, "rake": -90.0, "aspect": 1.5, "ztor": 0.0,
#               "vs30": 800.0, "backarc": False, "z1pt0": 50.0, "z2pt5": 1.0,
#               "line_azimuth": 90.0}
    properties = {k: params[k]
                  for k in (DIP, ASP, RAKE, ASP, ZTOR, VS30, BAC, Z1PT0, Z2PT5, LINEAZI)
                  if k in params}
    vs30s = vectorize(params[VS30])

    ret = None
    for class_ in [MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis]:
        for vs30 in vs30s:
            properties[VS30] = vs30
            for dist in distances:
                data = class_.from_rupture_model(properties, magnitudes, dist, gsim, imt).to_dict()
                if ret is None:
                    ret = {k: v for k, v in data.items() if k != 'figures'}
                    ret['figures'] = []
                dst_figures = ret['figures']
                src_figures = data['figures']
                for fig in src_figures:
                    fig.pop('column', None)
                    fig.pop('row', None)
                    fig['distance'] = dist
                    fig['vs30'] = vs30
                    fig['magnitude'] = None
                    dst_figures.append(fig)
    return ret


@validate(TrellisForm)
def magnitudedistance_imt(params):

    # dip, aspect will be used below, we oparse them here because they are mandatory (FIXME:
    # are they?)
    magnitude, distance, dip, aspect, gsim, imt = \
        params[MAG], params[DIST], params[DIP], params[ASP], params[GSIM], params[IMT]
    magnitudes = vectorize(magnitude)
    distances = vectorize(distance)

#     properties = {"dip": 60.0, "rake": -90.0, "aspect": 1.5, "ztor": 0.0,
#                   "vs30": 800.0, "backarc": False, "z1pt0": 50.0, "z2pt5": 1.0}
    properties = {k: params[k] for k in (DIP, RAKE, ASP, VS30, BAC, Z1PT0, Z2PT5) if k in params}
    vs30s = vectorize(params[VS30])

    ret = None
    for class_ in [MagnitudeDistanceSpectraTrellis, MagnitudeDistanceSpectraSigmaTrellis]:
        for vs30 in vs30s:
            properties[VS30] = vs30
            data = class_.from_rupture_model(properties, magnitudes, distances, gsim,
                                             imt).to_dict()
            if ret is None:
                ret = {k: v for k, v in data.items() if k != 'figures'}
                ret['figures'] = []
            dst_figures = ret['figures']
            src_figures = data['figures']
            for fig in src_figures:
                fig.pop('column', None)
                fig.pop('row', None)
                # fig['distance'] = dist
                fig['vs30'] = vs30
                # fig['magnitude'] = None
                dst_figures.append(fig)
    return ret
