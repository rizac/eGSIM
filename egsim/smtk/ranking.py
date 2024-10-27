"""
Collection of function to extract fit measures from residuals for model ranking
"""

from collections.abc import Iterable
from typing import Union
from math import ceil

import numpy as np
import pandas as pd
from scipy.stats import norm

from .flatfile import ColumnType
from .registry import Clabel


def get_measures_of_fit(
        gsims: Iterable[str], imts: Iterable[str], residuals: pd.DataFrame,
        as_dataframe=True, edr_bandwidth=0.01, edr_multiplier=3.0
) -> Union[pd.DataFrame, dict]:
    """
    Retrieve several Measures of fit from the given residuals, models and imts

    :param gsims: the ground motion models (iterable of str)
    :param imts: the intensity measure types (iterable of str)
    :param residuals: the result of :ref:`get_residuals` where the residuals of the
        given model(s) and imt(s) are computed
    :param as_dataframe: whether to return Measures of fit as DataFrame (True,
        the default), or dict
    :param edr_bandwidth: bandwidth to use in EDR values computation (default 0.01)
    :param edr_multiplier: multiplier to use in EDR values computation (default 3.0)

    :return: a Pandas dataframe (columns: measures of fit, rows: model names) or
        dict[str, dict[str, float]] (measures of fit names mapped to a dict where model
        names are mapped to their measure of fit value
    """
    result = {}
    for res in [
        get_residuals_stats(gsims, imts, residuals),
        get_residuals_likelihood_stats(gsims, imts, residuals),
        get_residuals_loglikelihood(gsims, imts, residuals),
        get_residuals_edr_values(gsims, imts, residuals, edr_bandwidth, edr_multiplier),
    ]:
        for fit_measure, models in res.items():
            result[fit_measure] = {}
            for gsim in gsims:
                result[fit_measure][gsim] = models.get(gsim, None)

    if as_dataframe:
        return pd.DataFrame(result, dtype=float)
    return result


def get_residuals_stats(
        gsims: Iterable[str], imts: Iterable[str], residuals: pd.DataFrame) -> \
        dict[str, dict[str, float]]:
    """
    Retrieve the mean and standard deviation values of the residuals

    :param gsims: the ground motion models (iterable of str)
    :param imts: the intensity measure types (iterable of str)
    :param residuals: the result of :ref:`get_residuals` where the residuals of the
        given model(s) and imt(s) are computed
    """
    result = {}
    for gsim in gsims:
        for imt in imts:
            for res_type in (Clabel.total_res, Clabel.inter_ev_res, Clabel.intra_ev_res):
                col = (imt, res_type, gsim)
                if residuals.get(col) is None:
                    continue
                result.setdefault(f"{imt} {res_type} mean", {})[gsim] = \
                    residuals[col].mean()
                result.setdefault(f"{imt} {res_type} stddev", {})[gsim] = \
                    residuals[col].std(ddof=0)

    return result


def get_residuals_likelihood_stats(
        gsims: Iterable[str], imts: Iterable[str], residuals: pd.DataFrame) -> \
        dict[str, dict[str, float]]:
    """
    Return the likelihood values for the residuals column found in `flatfile`
    (e.g. Total, inter- intra-event) according to Equation 9 of Scherbaum et al. (2004)

    :param gsims: the ground motion models (iterable of str)
    :param imts: the intensity measure types (iterable of str)
    :param residuals: the result of :ref:`get_residuals` where the likelihood values
        of the given model(s) and imt(s) are computed
    """
    result = {}
    for gsim in gsims:
        for imt in imts:
            for lh_type in (Clabel.total_lh, Clabel.inter_ev_lh, Clabel.intra_ev_lh):
                col = (imt, lh_type, gsim)
                if residuals.get(col) is None:
                    continue
                p25, p50, p75 = np.nanpercentile(residuals[col], [25, 50, 75])
                result.setdefault(f"{imt} {lh_type} median", {})[gsim] = p50
                result.setdefault(f"{imt} {lh_type} iqr", {})[gsim] = p75 - p25

    return result


def get_residuals_loglikelihood(
        gsims: Iterable[str], imts: Iterable[str], residuals: pd.DataFrame) -> \
        dict[str, dict[str, float]]:
    """
    Return the loglikelihood fit for the "Total residuals"
    using the loglikehood (LLH) function described in Scherbaum et al. (2009)
    Scherbaum, F., Delavaud, E., Riggelsen, C. (2009) "Model Selection in
    Seismic Hazard Analysis: An Information-Theoretic Perspective",
    Bulletin of the Seismological Society of America, 99(6), 3234-3247

    :param gsims: the ground motion models (iterable of str)
    :param imts: the intensity measure types (iterable of str)
    :param residuals: the result of :ref:`get_residuals` where the residuals of the
        given model(s) and imt(s) are computed
    """
    result = {}
    imts = list(imts)
    for gsim in gsims:
        aslls = []
        for imt in imts:
            col = (imt, Clabel.total_res, gsim)
            values = residuals.get(col)
            if values is None:
                continue
            asll = np.log2(norm.pdf(values, 0., 1.0))
            result.setdefault(f'{imt} loglikelihood', {})[gsim] = \
                -(1.0 / len(asll)) * np.sum(asll)

            # concatenate all model assl(s) (see end of loop):
            aslls = np.hstack([aslls, asll])

        if len(imts) > 1:
            result.setdefault('All_IMT loglikelihood', {})[gsim] = \
                -(1.0 / len(aslls)) * np.sum(aslls)
        # result[gsim]["All"]['loglikelihood'] = -(1.0 / len(aslls)) * np.sum(aslls)

    return result


def get_residuals_edr_values(
        gsims: Iterable[str], imts: Iterable[str], residuals: pd.DataFrame,
        bandwidth=0.01, multiplier=3.0) -> \
        dict[str, dict[str, float]]:
    """
    Calculates the EDR values for each Gsim found in `flatfile` with computed residuals
    according to the Euclidean Distance Ranking method of Kale & Akkar (2013)

    Kale, O., and Akkar, S. (2013) "A New Procedure for Selecting and
    Ranking Ground Motion Prediction Equations (GMPEs): The Euclidean
    Distance-Based Ranking Method", Bulletin of the Seismological Society
    of America, 103(2A), 1069 - 1084.

    :param gsims: the ground motion models (iterable of str)
    :param imts: the intensity measure types (iterable of str)
    :param residuals: a pandas DataFrame resulting from :ref:`get_residuals`
    :param float bandwidth: Discretisation width
    :param float multiplier: "Multiplier of standard deviation (equation 8 of Kale
        and Akkar)
    """
    result = {}
    for gsim in gsims:
        obs, expected, stddev = _get_edr_gsim_information(gsim, imts, residuals)
        results = get_edr(obs, expected, stddev, bandwidth, multiplier)
        result.setdefault("mde norm", {})[gsim] = float(results[0])
        result.setdefault("sqrt kappa", {})[gsim] = float(results[1])
        result.setdefault("edr", {})[gsim] = float(results[2])
    return result


def _get_edr_gsim_information(
        gsim: str, imts: Iterable[str], residuals: pd.DataFrame) -> \
        tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extract the observed ground motions, expected and total standard
    deviation for the given model `gsim` (aggregating over all IMTs)
    """
    obs = np.array([], dtype=float)
    expected = np.array([], dtype=float)
    stddev = np.array([], dtype=float)

    for imt in imts:
        col = (imt, Clabel.total_res, gsim)
        _stddev = residuals.get(col)
        col = (Clabel.input_data, ColumnType.intensity.value, imt)
        _obs = np.log(residuals.get(col))
        col = (imt, Clabel.mean, gsim)
        _expected = residuals.get(col)
        if _stddev is None or _obs is None or _expected is None:
            continue
        obs = np.hstack([obs, _obs])
        expected = np.hstack([expected, _expected])
        stddev = np.hstack([stddev, _stddev])

    return obs, expected, stddev


def get_edr(obs: Union[np.ndarray, pd.Series],
            expected: Union[np.ndarray, pd.Series],
            stddev: Union[np.ndarray, pd.Series],
            bandwidth=0.01, multiplier=3.0) -> tuple[float, float, float]:
    """
    Calculated the Euclidean Distanced-Based Rank for a set of
    observed and expected values from a particular Gsim
    """
    finite = np.isfinite(obs) & np.isfinite(expected) & np.isfinite(stddev)
    if not finite.any():
        return np.nan, np.nan, np.nan
    elif not finite.all():
        obs, expected, stddev = obs[finite], expected[finite], stddev[finite]
    nvals = len(obs)
    min_d = bandwidth / 2.
    kappa = _get_edr_kappa(obs, expected)
    mu_d = obs - expected
    d1c = np.fabs(obs - (expected - (multiplier * stddev)))
    d2c = np.fabs(obs - (expected + (multiplier * stddev)))
    dc_max = ceil(np.max(np.array([np.max(d1c), np.max(d2c)])))
    num_d = len(np.arange(min_d, dc_max, bandwidth))
    mde = np.zeros(nvals)
    for iloc in range(0, num_d):
        d_val = (min_d + (float(iloc) * bandwidth)) * np.ones(nvals)
        d_1 = d_val - min_d
        d_2 = d_val + min_d
        p_1 = norm.cdf((d_1 - mu_d) / stddev) -\
            norm.cdf((-d_1 - mu_d) / stddev)
        p_2 = norm.cdf((d_2 - mu_d) / stddev) -\
            norm.cdf((-d_2 - mu_d) / stddev)
        mde += (p_2 - p_1) * d_val
    inv_n = 1.0 / float(nvals)
    mde_norm = np.sqrt(inv_n * np.sum(mde ** 2.))
    edr = np.sqrt(kappa * inv_n * np.sum(mde ** 2.))
    return float(mde_norm), float(np.sqrt(kappa)), float(edr)


def _get_edr_kappa(obs: Union[np.ndarray, pd.Series],
                   expected: Union[np.ndarray, pd.Series]) -> np.floating:
    """
    Return the correction factor kappa
    """
    mu_a = np.mean(obs)
    mu_y = np.mean(expected)
    b_1 = np.sum((obs - mu_a) * (expected - mu_y)) /\
        np.sum((obs - mu_a) ** 2.)
    b_0 = mu_y - b_1 * mu_a
    y_c = expected - ((b_0 + b_1 * obs) - obs)
    de_orig = np.sum((obs - expected) ** 2.)
    de_corr = np.sum((obs - y_c) ** 2.)
    return de_orig / de_corr
