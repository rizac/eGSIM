'''
Created on 27 Jul 2018

@author: riccardo
'''

from collections import defaultdict

import numpy as np
from scipy.stats import norm, linregress

# Tools to run the analysis
from smtk.residuals.gmpe_residuals import (Residuals, Likelihood,
                                           LLH, MultivariateLLH, EDR,
                                           SingleStationAnalysis)
# Tools to produce plots
# import smtk.residuals.residual_plotter as rspl

from egsim.core.gmdbselection import compute_selection
from smtk.residuals.residual_plots import residuals_density_distribution,\
    residuals_with_depth, residuals_with_distance, residuals_with_magnitude,\
    residuals_with_vs30, likelihood


GSIM = 'gsim'
IMT = 'imt'
DTYPE = 'distance_type'
MAG = 'magnitude'
DIST = 'distance'
VS30 = 'vs30'
PLOTTYPE = 'plot_type'


def compute_residuals(params):
    gmdb = compute_selection(params)
    func = params[PLOTTYPE]
    if func == likelihood:
        residuals = Likelihood(params[GSIM], params[IMT])
    else:
        residuals = Residuals(params[GSIM], params[IMT])

    # Compute residuals.
    residuals.get_residuals(gmdb)  # FIXME: add 'component' argument?
    # statistics = residuals.get_residual_statistics()
    ret = defaultdict(lambda: defaultdict(lambda: {}))
    distance_type = params[DTYPE]

    kwargs = dict(residuals=residuals, as_json=True)
    # linestep = binwidth/10
    for gsim in residuals.residuals:
        for imt in residuals.residuals[gsim]:
            kwargs['gmpe'] = gsim
            kwargs['imt'] = imt
            if func == residuals_with_distance:
                kwargs['distance_type'] = distance_type
            ret[gsim][imt] = func(**kwargs)
#             data = residuals.residuals[gsim][imt]
#             for res_type in data.keys():
#                 if plot_type == MAG:
#                     res_obj = ResMag(residuals, gsim, imt, distance_type=dtype)
#                     magnitudes = res_obj._get_magnitudes(gsim, imt, res_type)
#                     slope, intercept, _, pval, _ = linregress(magnitudes, data[res_type])
#                     jsondata = {'x': magnitudes.tolist(), 'y': data[res_type].tolist(),
#                                 'slope': slope, 'intercept': intercept, 'pvalue': pval,
#                                 'xlabel': "Magnitude", 'ylabel': "Z (%s)" % imt}
#                 elif plot_type == DIST:
#                     res_obj = ResDist(residuals, gsim, imt, distance_type=dtype)
#                     distances = res_obj._get_distances(gsim, imt, res_type)
#                     slope, intercept, _, pval, _ = linregress(distances, data[res_type])
#                     jsondata = {'x': distances.tolist(), 'y': data[res_type].tolist(),
#                                 'slope': slope, 'intercept': intercept, 'pvalue': pval,
#                                 'xlabel': "%s Distance (km)" % res_obj.distance_type,
#                                 'ylabel': "Z (%s)" % imt}
#                 elif plot_type == VS30:
#                     res_obj = ResVs30(residuals, gsim, imt, distance_type=dtype)
#                     vs30 = res_obj._get_vs30(gsim, imt, res_type)
#                     slope, intercept, _, pval, _ = linregress(vs30, data[res_type])
#                     jsondata = {'x': vs30.tolist(), 'y': data[res_type].tolist(),
#                                 'slope': slope, 'intercept': intercept, 'pvalue': pval,
#                                 'xlabel': "Vs30 (m/s)", 'ylabel': "Z (%s)" % imt}
#                 else:
#                     binwidth = 0.5
#                     res_obj = ResPlot(residuals, gsim, imt, distance_type=dtype)
#                     vals, bins = res_obj.get_histogram_data(data[res_type], bin_width=binwidth)
#                     # step = binwidth/5
#                     # xdata = np.arange(bins[0], bins[-1] + linestep, linestep)
#                     mean = statistics[gsim][imt][res_type]["Mean"]
#                     stddev = statistics[gsim][imt][res_type]["Std Dev"]
#                     # norm_dist = norm.pdf(xdata, mean, stddev)
#                     # ref_dist = norm.pdf(xdata, 0.0, 1.0)
#                     jsondata = {'x': bins[:-1].tolist(), 'y': vals.tolist(),
#                                 'mean': mean, 'stddev': stddev, 'xlabel': "Z (%s)" % imt,
#                                 'ylabel': "Frequency"}
#                 ret[gsim][imt][res_type] = jsondata
    return ret

# these classes prevent plotting. HACK: will be fixed in near future by providing dedicated
# function or classes
# class ResPlot(ResidualPlot):
# 
#     def create_plot(self, *args, **kwargs):
#         pass
# 
# 
# class ResMag(ResidualWithMagnitude):
# 
#     def create_plot(self, *args, **kwargs):
#         pass
# 
# 
# class ResDist(ResidualWithDistance):
# 
#     def create_plot(self, *args, **kwargs):
#         pass
# 
# 
# class ResVs30(ResidualWithVs30):
# 
#     def create_plot(self, *args, **kwargs):
#         pass

