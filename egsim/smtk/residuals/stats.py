"""
Residuals module
"""

from collections.abc import Iterable
from typing import Union
from math import ceil

import numpy as np
import pandas as pd

from scipy.stats import norm
from scipy.linalg import solve

from ..residuals import get_computed_columns, c_labels, column_label


def get_residuals_stats(gsim_names: Iterable[str], imt_names: Iterable[str],
                        flatfile: pd.DataFrame) -> \
        dict[str, dict[str, dict[str, float]]]:
    """
    Retrieve the mean and standard deviation values of the residuals

    :flatfile: the result of :ref:`get_residuals`
    """
    stats = {}
    for col, gsim, imtx, label in get_computed_columns(gsim_names, imt_names, flatfile):
        if label not in c_labels.residuals_columns:
            continue
        if gsim not in stats:
            stats[gsim] = {}
        if imtx not in stats[gsim]:
            stats[gsim][imtx] = {}
        stats[gsim][imtx][f"{label} Mean"] = flatfile[col].mean()
        stats[gsim][imtx][f"{label} Stddev"] = flatfile[col].std()
    return stats


def get_residuals_likelihood(gsims: Iterable[str], imts: Iterable[str],
                             flatfile: pd.DataFrame) -> \
        dict[str, dict[str, dict[str, float]]]:
    """
    Return the likelihood values for the residuals column found in `flatfile`
    (e.g. Total, inter- intra-event) according to Equation 9 of Scherbaum et al (2004)

    :param flatfile: a pandas DataFrame resulting from :ref:`get_residuals`.
        NOTE: the flatfile might be modified inplace (new likelihood columns added)
    """
    result = {}
    for col, gsim, imtx, label in get_computed_columns(gsims, imts, flatfile):
        if label not in c_labels.lh_columns:
            continue
        values = flatfile[col]
        if gsim not in result:
            result[gsim] = {}
        if imtx not in result[gsim]:
            result[gsim][imtx] = {}
        p25, p50, p75 = np.nanpercentile(values, [25, 50, 75])
        result[f"{label} Median"] = p50
        result[f"{label} IQR"] = p75 - p25
    return result


def get_residuals_loglikelihood(gsims: Iterable[str], imts: Iterable[str],
                                flatfile: pd.DataFrame) -> \
        dict[str, dict[str, float]]:
    """
    Return the loglikelihood fit for the "Total residuals" columns found in `flatfile`
    using the loglikehood (LLH) function described in Scherbaum et al. (2009)
    Scherbaum, F., Delavaud, E., Riggelsen, C. (2009) "Model Selection in
    Seismic Hazard Analysis: An Information-Theoretic Perspective",
    Bulletin of the Seismological Society of America, 99(6), 3234-3247

    :param flatfile: a pandas DataFrame resulting from :ref:`get_residuals`
    """
    result = {}
    log_residuals = {}
    for col, gsim, imtx, label in get_computed_columns(gsims, imts, flatfile):
        if label != c_labels.total_res:
            continue
        asll = np.log2(norm.pdf(flatfile[col], 0., 1.0))
        if gsim not in result:
            result[gsim] = {}
        result[imtx] = -(1.0 / len(asll)) * np.sum(asll)
        log_residuals[gsim] = np.hstack([log_residuals[gsim], asll])
    for gsim, asll in log_residuals.items():
        result[gsim]["All"] = -(1.0 / len(asll)) * np.sum(asll)
    return result


def get_residuals_edr_values(gsims: Iterable[str], imts: Iterable[str],
                             flatfile: pd.DataFrame, bandwidth=0.01,
                             multiplier=3.0) -> \
        dict[str, dict[str, float]]:
    """
    Calculates the EDR values for each Gsim found in `flatfile` with computed residuals
    according to the Euclidean Distance Ranking method of Kale & Akkar (2013)

    Kale, O., and Akkar, S. (2013) "A New Procedure for Selecting and
    Ranking Ground Motion Predicion Equations (GMPEs): The Euclidean
    Distance-Based Ranking Method", Bulletin of the Seismological Society
    of America, 103(2A), 1069 - 1084.

    :param flatfile: a pandas DataFrame resulting from :ref:`get_residuals`
    :param float bandwidth: Discretisation width
    :param float multiplier: "Multiplier of standard deviation (equation 8 of Kale
        and Akkar)
    """
    result = {}
    for gsim in gsims:
        obs, expected, stddev = _get_edr_gsim_information(gsim, imts, flatfile)
        results = get_edr(obs, expected, stddev, bandwidth, multiplier)
        if gsim not in result:
            result[gsim] = {}
        result[gsim]["MDE Norm"] = float(results[0])
        result[gsim]["sqrt Kappa"] = float(results[1])
        result[gsim]["EDR"] = float(results[2])
    return result


def _get_edr_gsim_information(gsim: str, imts: Iterable[str], flatfile:pd.DataFrame) -> \
        tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Extract the observed ground motions, expected and total standard
    deviation for the GMPE (aggregating over all IMS)

    Note: `get_residuals` must have been called on `flatfile` before this function
    """
    obs = np.array([], dtype=float)
    expected = np.array([], dtype=float)
    stddev = np.array([], dtype=float)
    for col, gsim, imtx, label in get_computed_columns([gsim], imts, flatfile):
        if label != c_labels.total:
            continue
        _stddev = flatfile[column_label(gsim, imtx, c_labels.total)]
        _obs = flatfile.get(imtx)
        _expected = flatfile.get(column_label(gsim, imtx, c_labels.mean))
        if _expected is not None and _obs is not None:
            obs = np.hstack([obs, np.log(flatfile[imtx])])
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
    Returns the correction factor kappa
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


# FIXME REMOVE:
GSIM_MODEL_DATA_TESTS = {
    "Residuals": lambda residuals, config:
        residuals.get_residual_statistics(),
    "Likelihood": lambda residuals, config: residuals.get_likelihood_values(),
    "LLH": lambda residuals, config: residuals.get_loglikelihood_values(
        config.get("LLH IMTs", [imt for imt in residuals.imts])),
    "MultivariateLLH": lambda residuals, config:
        residuals.get_multivariate_loglikelihood_values(),
    "EDR": lambda residuals, config: residuals.get_edr_values(
        config.get("bandwidth", 0.01), config.get("multiplier", 3.0))
}


# FIXME: from here on multivariate_llh need to be fixed with GW


# Mak et al multivariate LLH functions
def get_residuals_multivariate_loglikelihood(gsim_names: list[str], imt_names: list[str],
                                          flatfile: pd.DataFrame, contexts=None):
    """
    Calculates the multivariate LLH for a set of GMPEs and IMTS according
    to the approach described in Mak et al. (2017)

    Mak, S., Clements, R. A. and Schorlemmer, D. (2017) "Empirical
    Evaluation of Hierarchical Ground-Motion Models: Score Uncertainty
    and Model Weighting", Bulletin of the Seismological Society of America,
    107(2), 949-965

    """
    raise NotImplementedError('this method is not supported and needs verification')
    result = pd.DataFrame(index=flatfile.index)
    for col, gsim, imt, label in residuals_columns(gsim_names, imt_names, flatfile):
        result[col + "-multivariate-loglikelihood"] = _get_multivariate_ll(
                    contexts, gsim, imt)
    return result


def _get_multivariate_ll(contexts, gmpe, imt):
    """
    Returns the multivariate loglikelihood, as described om equation 7 of
    Mak et al. (2017)
    """
    observations, v_mat, expected_mat, neqs, nrecs = _build_matrices(
        contexts, gmpe, imt)
    sign, logdetv = np.linalg.slogdet(v_mat)
    b_mat = observations - expected_mat
    # `solve` below needs only finite values (see doc), but unfortunately raises
    # in case. In order to silently skip non-finite values:
    # 1. Check v_mat (square matrix), by simply returning nan if any cell value
    # is nan (FIXME: handle better?):
    if not np.isfinite(v_mat).all():
        return np.nan
    # 2. Check b_mat (array) by removing finite values:
    b_finite = np.isfinite(b_mat)
    if not b_finite.all():
        if not b_finite.any():
            return np.nan
        b_mat = b_mat[b_finite]
        v_mat = v_mat[b_finite, :][:, b_finite]
    # call `solve(...check_finite=False)` because the check is already done.
    # The function shouldn't raise anymore:
    return (float(nrecs) * np.log(2.0 * np.pi) + logdetv +
            (b_mat.T.dot(solve(v_mat, b_mat, check_finite=False)))) / 2.


# The following methods are used for the MultivariateLLH function
def _build_matrices(contexts, gmpe, imtx):
    """
    Constructs the R and Z_G matrices (based on the implementation
    in the supplement to Mak et al (2017)
    """
    neqs = len(contexts)
    nrecs = sum(ctxt["Num. Sites"] for ctxt in contexts)

    r_mat = np.zeros(nrecs, dtype=float)
    z_g_mat = np.zeros([nrecs, neqs], dtype=float)
    expected_mat = np.zeros(nrecs, dtype=float)
    # Get observations
    observations = np.zeros(nrecs)
    i = 0
    # Determine the total number of records and pass the log of the
    # observations to the observations dictionary
    for ctxt in contexts:
        n_s = ctxt["Num. Sites"]
        observations[i:(i + n_s)] = np.log(ctxt["Observations"][imtx])
        i += n_s

    i = 0
    for j, ctxt in enumerate(contexts):
        if not("Intra event" in ctxt["Expected"][gmpe][imtx]) and\
                not("Inter event" in ctxt["Expected"][gmpe][imtx]):
            # Only the total sigma exists
            # Total sigma is used as intra-event sigma (from S. Mak)
            n_r = len(ctxt["Expected"][gmpe][imtx]["Total"])
            r_mat[i:(i + n_r)] = ctxt["Expected"][gmpe][imtx]["Total"]
            expected_mat[i:(i + n_r)] = ctxt["Expected"][gmpe][imtx]["Mean"]
            # Inter-event sigma is set to 0
            i += n_r
            continue
        n_r = len(ctxt["Expected"][gmpe][imtx]["Intra event"])
        r_mat[i:(i + n_r)] = ctxt["Expected"][gmpe][imtx]["Intra event"]
        # Get expected mean
        expected_mat[i:(i + n_r)] = ctxt["Expected"][gmpe][imtx]["Mean"]
        if len(ctxt["Expected"][gmpe][imtx]["Inter event"]) == 1:
            # Single inter event residual
            z_g_mat[i:(i + n_r), j] =\
                ctxt["Expected"][gmpe][imtx]["Inter event"][0]
        else:
            # inter-event residual given at a vector
            z_g_mat[i:(i + n_r), j] =\
                ctxt["Expected"][gmpe][imtx]["Inter event"]
        i += n_r

    v_mat = np.diag(r_mat ** 2.) + z_g_mat.dot(z_g_mat.T)
    return observations, v_mat, expected_mat, neqs, nrecs

