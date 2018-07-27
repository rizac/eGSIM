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
from smtk.residuals.residual_plotter import ResidualPlot


GSIM = 'gsim'
IMT = 'imt'

def compute_residuals(params):
    gmdb = compute_selection(params)
    residuals = Residuals(params[GSIM], params[IMT])
    residuals.get_residuals(gmdb)
    statistics = residuals.get_residual_statistics()
    ret = defaultdict(lambda: defaultdict(lambda: {}))
    binwidth = 0.5
    # linestep = binwidth/10
    for gsim in residuals.residuals:
        for imt in residuals.residuals[gsim]:
            data = residuals.residuals[gsim][imt]
            for res_type in data.keys():
                vals, bins = get_histogram_data(data[res_type], bin_width=0.5)
                # step = binwidth/5
                # xdata = np.arange(bins[0], bins[-1] + linestep, linestep)
                mean = statistics[gsim][imt][res_type]["Mean"]
                stddev = statistics[gsim][imt][res_type]["Std Dev"]
                # norm_dist = norm.pdf(xdata, mean, stddev)
                # ref_dist = norm.pdf(xdata, 0.0, 1.0)
                ret[gsim][imt][res_type] = {'x': bins[:-1].tolist(), 'y': vals.tolist(),
                                            'mean': mean,
                                            'stddev': stddev}
    return ret

def get_histogram_data(data, bin_width=0.5):
    """
    Retreives the histogram of the residuals
    """
    bins = np.arange(np.floor(np.min(data)),
                     np.ceil(np.max(data)) + bin_width,
                     bin_width)
    vals = np.histogram(data, bins, density=True)[0]
    return vals.astype(float), bins
