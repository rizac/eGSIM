'''
Created on 31 May 2018

@author: riccardo
'''
from collections import OrderedDict

import numpy as np

from smtk.trellis.trellis_plots import DistanceIMTTrellis as SmtkDistanceIMTTrellis, \
    DistanceSigmaIMTTrellis as SmtkDistanceSigmaIMTTrellis,\
    MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis, MagnitudeDistanceSpectraTrellis, \
    MagnitudeDistanceSpectraSigmaTrellis
from smtk.trellis.configure import GSIMRupture as SmtkGSIMRupture

from egsim.utils import vectorize
from egsim.core import validate
from egsim.forms import TrellisForm


class GSIMRupture(SmtkGSIMRupture):
    def _define_line_spacing(self, maximum_distance, spacing, as_log=False):
        return self._distances_


class BaseDistanceIMTTrellis(object):

    @staticmethod
    def from_rupture_model(cls, properties, mag, distances, gsim, imt):
        # GSIMRuptue(magnitude, dip, aspect,
        #            tectonic_region='Active Shallow Crust', rake=0., ztor=0.,
        #            strike=0., msr=WC1994(), initial_point=DEFAULT_POINT,
        #            hypocentre_location=None)
        rupture = GSIMRupture(magnitude=mag, dip=properties[DIP], aspect=properties[ASP],
                              tectonic_region=properties[TRT], rake=properties[RAKE],
                              ztor=properties[ZTOR], strike=properties[STRIKE], msr=properties[MSR],
                              initial_point=properties[INITPT],
                              hypocentre_location=properties[HYPLOC])
        rupture._distances_ = np.array(distances, dtype=float)
        # def get_target_sites_line(self, maximum_distance, spacing, vs30,
        #                           line_azimuth=90., origin_point=(0.5, 0.5), as_log=False,
        #                           vs30measured=True, z1pt0=None, z2pt5=None, backarc=False)
        rupture.get_target_sites_line(maximum_distance=distances[-1],
                                      spacing=distances[1]-distances[0], vs30=properties[VS30],
                                      line_azimuth=properties[LINEAZI],
                                      vs30measured=properties[VS30MEAS], z1pt0=properties[Z1PT0],
                                      z2pt5=properties[Z2PT5], backarc=properties[BAC])
        return SmtkDistanceIMTTrellis.from_rupture_model(rupture, gsim, imt, distance_type="rrup")


class DistanceIMTTrellis(object):
    @staticmethod
    def from_rupture_model(properties, mag, distances, gsim, imt):
        return BaseDistanceIMTTrellis.from_rupture_model(SmtkDistanceIMTTrellis,
                                                         properties, mag, distances, gsim, imt)


class DistanceSigmaIMTTrellis(SmtkDistanceSigmaIMTTrellis):
    @staticmethod
    def from_rupture_model(properties, mag, distances, gsim, imt):
        return BaseDistanceIMTTrellis.from_rupture_model(SmtkDistanceSigmaIMTTrellis,
                                                         properties, mag, distances, gsim, imt)


MAG = 'magnitude'
DIST = 'distance'
DIP = 'dip'
ASP = 'aspect'
TRT = 'tectonic_region'
RAKE = 'rake'
ZTOR = 'ztor'
STRIKE = 'strike'
MSR = 'msr'
INITPT = 'initial_point'
HYPLOC = 'hypocentre_location'
VS30 = 'vs30'
VS30MEAS = 'vs30_measured'
LINEAZI = 'line_azimuth'
Z1PT0 = 'z1pt0'
Z2PT5 = 'z2pt5'
BAC = 'backarc'
GSIM = 'gsim'
IMT = 'imt'

@validate(TrellisForm)
def compute(params):

    # dip, aspect will be used below, we oparse them here because they are mandatory (FIXME:
    # are they?)
    magnitude, distance, vs30, z1pt0, z2pt5, gsim, imt = \
        params.pop(MAG), params.pop(DIST), params.pop(VS30), \
        params.pop(Z1PT0), params.pop(Z2PT5), params.pop(GSIM), params.pop(IMT)
    magnitudes = vectorize(magnitude)
    distances = vectorize(distance)
    vs30s = vectorize(vs30)
    z1pt0s = vectorize(z1pt0)
    z2pt5s = vectorize(z2pt5)

    magiter = [None]
    distiter = [None]
    classes = params.pop('plot_type')
    if classes[0] == SmtkDistanceIMTTrellis:  # hack to convert to our classes
        # when A DistanceIMT trellis will implement the same from_rupture_model
        # signature as the Magnitude and MAgnitudeDistance Trellis, this "if" will be removed
        classes = (DistanceIMTTrellis, DistanceSigmaIMTTrellis)
        magiter = magnitudes
    elif classes[0] == MagnitudeIMTTrellis:
        distiter = distances

    ret = None
    fig_key, col_key, row_key = 'figures', 'column', 'row'
    for class_ in classes:
        for vs30, z1pt0, z2pt5 in zip(vs30s, z1pt0s, z2pt5s):
            params[VS30] = vs30
            params[Z1PT0] = z1pt0
            params[Z2PT5] = z2pt5
            for mag_ in magiter:
                for dist_ in distiter:
                    data = class_.from_rupture_model(params, magnitudes if mag_ is None else mag_,
                                                     distances if dist_ is None else dist_, gsim,
                                                     imt).to_dict()
                    if ret is None:
                        ret = {k: v for k, v in data.items() if k != fig_key}
                        ret[fig_key] = []
                    dst_figures = ret[fig_key]
                    src_figures = data[fig_key]
                    for fig in src_figures:
                        fig.pop(col_key, None)
                        fig.pop(row_key, None)
                        fig[DIST] = dist_
                        fig[VS30] = vs30
                        fig[MAG] = mag_
                        dst_figures.append(fig)
    return ret

# @validate(TrellisForm)
# def distance_imt(params):  # FIXME: distances hardcoded WHERE?
#     # vectorizable on: sigma/median, magnitudes
#     
#     # magnitude, dip, aspect, 
# #     tectonic_region='Active Shallow Crust', rake=0., ztor=0., 
# #     strike=0., msr=WC1994(), initial_point=DEFAULT_POINT, 
# #     hypocentre_location=None)
#     mag, dip, aspect, gsim, imt = params[MAG], params[DIP], params[ASP], params[GSIM], params[IMT]
# 
#     # parse other parameters:
#     optparams = {k: params[k]
#                  for k in [TRT, RAKE, ZTOR, STRIKE, MSR, INITPT, HYPLOC] if k in params}
#     vs30s = vectorize(params[VS30])
# 
#     ret = None
#     for class_ in [DistanceIMTTrellis, DistanceSigmaIMTTrellis]:
#         for vs30 in vs30s:
#             for mag in vectorize(mag):
#                 # FIXME: HERE ITERATE THROUGH vs30 AND use get_target_sites_line to config the rupture
#                 rupture = GSIMRupture(mag, dip, aspect, **optparams)
#                 rupture.get_target_sites_line(250.0, 1.0, 800.0)
#                 data = class_.from_rupture_model(rupture, gsim, imt, distance_type="rrup").to_dict()
#                 if ret is None:
#                     ret = {k: v for k, v in data.items() if k != 'figures'}
#                     ret['figures'] = []
#                 dst_figures = ret['figures']
#                 src_figures = data['figures']
#                 for fig in src_figures:
#                     fig.pop('column', None)
#                     fig.pop('row', None)
#                     fig['distance'] = None
#                     fig['vs30'] = vs30
#                     fig['magnitude'] = mag
#                     dst_figures.append(fig)
#     return ret
# 
# 
# @validate(TrellisForm)
# def magnitude_imt(params):  # FIXME: magnitudes hardcoded HERE?
#     # vectorizable on: sigma/median, magnitudes
#     
#     # magnitude, dip, aspect, 
# #     tectonic_region='Active Shallow Crust', rake=0., ztor=0., 
# #     strike=0., msr=WC1994(), initial_point=DEFAULT_POINT, 
# #     hypocentre_location=None)
# 
#     # dip, aspect will be used below, we oparse them here because they are mandatory (FIXME:
#     # are they?)
#     magnitude, distance, dip, aspect, gsim, imt = \
#         params[MAG], params[DIST], params[DIP], params[ASP], params[GSIM], params[IMT]
#     magnitudes = vectorize(magnitude)
#     distances = vectorize(distance)
# 
#     # parse other parameters:
# #     {"dip": 60.0, "rake": -90.0, "aspect": 1.5, "ztor": 0.0,
# #               "vs30": 800.0, "backarc": False, "z1pt0": 50.0, "z2pt5": 1.0,
# #               "line_azimuth": 90.0}
#     properties = {k: params[k]
#                   for k in (DIP, ASP, RAKE, ASP, ZTOR, VS30, BAC, Z1PT0, Z2PT5, LINEAZI)
#                   if k in params}
#     vs30s = vectorize(params[VS30])
# 
#     ret = None
#     for class_ in [MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis]:
#         for vs30 in vs30s:
#             properties[VS30] = vs30
#             for dist in distances:
#                 data = class_.from_rupture_model(properties, magnitudes, dist, gsim, imt).to_dict()
#                 if ret is None:
#                     ret = {k: v for k, v in data.items() if k != 'figures'}
#                     ret['figures'] = []
#                 dst_figures = ret['figures']
#                 src_figures = data['figures']
#                 for fig in src_figures:
#                     fig.pop('column', None)
#                     fig.pop('row', None)
#                     fig['distance'] = dist
#                     fig['vs30'] = vs30
#                     fig['magnitude'] = None
#                     dst_figures.append(fig)
#     return ret
# 
# 
# @validate(TrellisForm)
# def magnitudedistance_imt(params):
# 
#     # dip, aspect will be used below, we oparse them here because they are mandatory (FIXME:
#     # are they?)
#     magnitude, distance, dip, aspect, gsim, imt = \
#         params[MAG], params[DIST], params[DIP], params[ASP], params[GSIM], params[IMT]
#     magnitudes = vectorize(magnitude)
#     distances = vectorize(distance)
# 
# #     properties = {"dip": 60.0, "rake": -90.0, "aspect": 1.5, "ztor": 0.0,
# #                   "vs30": 800.0, "backarc": False, "z1pt0": 50.0, "z2pt5": 1.0}
#     properties = {k: params[k] for k in (DIP, RAKE, ASP, VS30, BAC, Z1PT0, Z2PT5) if k in params}
#     vs30s = vectorize(params[VS30])
# 
#     ret = None
#     for class_ in [MagnitudeDistanceSpectraTrellis, MagnitudeDistanceSpectraSigmaTrellis]:
#         for vs30 in vs30s:
#             properties[VS30] = vs30
#             data = class_.from_rupture_model(properties, magnitudes, distances, gsim,
#                                              imt).to_dict()
#             if ret is None:
#                 ret = {k: v for k, v in data.items() if k != 'figures'}
#                 ret['figures'] = []
#             dst_figures = ret['figures']
#             src_figures = data['figures']
#             for fig in src_figures:
#                 fig.pop('column', None)
#                 fig.pop('row', None)
#                 # fig['distance'] = dist
#                 fig['vs30'] = vs30
#                 # fig['magnitude'] = None
#                 dst_figures.append(fig)
#     return ret
