'''
Created on 31 May 2018

@author: riccardo
'''
from collections import OrderedDict

import numpy as np

from smtk.trellis.trellis_plots import DistanceIMTTrellis, MagnitudeIMTTrellis

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
    if classes[0] == DistanceIMTTrellis:
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
                    func = class_.from_rupture_properties
                    data = func(params, magnitudes if mag_ is None else mag_,
                                distances if dist_ is None else dist_, gsim, imt).to_dict()
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
