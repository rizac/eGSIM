'''
Created on 31 May 2018

@author: riccardo
'''
from collections import OrderedDict
from itertools import repeat

import numpy as np

from smtk.trellis.trellis_plots import DistanceIMTTrellis, MagnitudeIMTTrellis, \
    DistanceSigmaIMTTrellis, MagnitudeSigmaIMTTrellis

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
    magnitudes = np.asarray(vectorize(magnitude))  # smtk wants numpy arrays
    distances = np.asarray(vectorize(distance))  # smtk wants numpy arrays

    vs30s = vectorize(vs30)
    z1pt0s = vectorize(z1pt0)
    z2pt5s = vectorize(z2pt5)

    trellisclass = params.pop('plot_type')
    isdist = trellisclass in (DistanceIMTTrellis, DistanceSigmaIMTTrellis)
    ismag = trellisclass in (MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis)
    if not isdist and not ismag:  # magnitudedistancetrellis:
        # imt is actually a vector of periods for the SA. FIXME: PR to gmpe-smtk?
        imt = [0.05, 0.075, 0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18, 0.19,
               0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34, 0.36, 0.38,
               0.40, 0.42, 0.44, 0.46, 0.48,
               0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95,
               1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0]

    def jsonserialize(value):
        '''serializes a numpy scalr into python scalar, no-op if value is not a numpy number'''
        try:
            return value.item()
        except AttributeError:
            return value

    ret = None
    fig_key, col_key, row_key = 'figures', 'column', 'row'
    for vs30, z1pt0, z2pt5 in zip(vs30s, z1pt0s, z2pt5s):
        params[VS30] = vs30
        params[Z1PT0] = z1pt0
        params[Z2PT5] = z2pt5
        # Depending on `trellisclass` we might need to iterate over `magnitudes`, or use
        # `magnitudes` once (the same holds for `distances`). In order to make code cleaner
        # we define a magnitude iterator which yields a two element tuple (m1, m2) where m1
        # is the scalar value to be saved as json, and m2 is the value (scalar or array) to
        # be passed to the Trellis class:
        magiter = zip(magnitudes, magnitudes) if isdist else zip([None], [magnitudes])
        for mag, mags in magiter:
            # same as magnitudes (see above):
            distiter = zip(distances, distances) if ismag else zip([None], [distances])
            for dist, dists in distiter:
                func = trellisclass.from_rupture_properties
                data = func(params, mags, dists, gsim, imt).to_dict()
                if ret is None:
                    ret = {k: v for k, v in data.items() if k != fig_key}
                    ret[fig_key] = []
                dst_figures = ret[fig_key]
                src_figures = data[fig_key]
                for fig in src_figures:
                    fig.pop(col_key, None)
                    fig.pop(row_key, None)
                    fig[VS30] = jsonserialize(vs30)
                    fig[MAG] = jsonserialize(fig.get(MAG, mag))
                    fig[DIST] = jsonserialize(fig.get(DIST, dist))
                    dst_figures.append(fig)
    return ret
