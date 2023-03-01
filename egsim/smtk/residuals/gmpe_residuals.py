# Copyright (C) 2014-2017 GEM Foundation and G. Weatherill
"""
Module to get GMPE residuals - total, inter and intra
{'GMPE': {'IMT1': {'Total': [], 'Inter event': [], 'Intra event': []},
          'IMT2': { ... }}}
"""
from math import sqrt, ceil

import numpy as np
from scipy.special import erf
from scipy.stats import norm
from scipy.linalg import solve
from openquake.hazardlib import imt

from .. import check_gsim_list, AVAILABLE_GSIMS
from . import convert_accel_units

GSIM_LIST = AVAILABLE_GSIMS
GSIM_KEYS = set(GSIM_LIST)

# SCALAR_IMTS = ["PGA", "PGV", "PGD", "CAV", "Ia"]
SCALAR_IMTS = ["PGA", "PGV"]
STDDEV_KEYS = ["Mean", "Total", "Inter event", "Intra event"]


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


def get_multivariate_ll(contexts, gmpe, imt):
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


class Residuals(object):
    """
    Class to derive sets of residuals for a list of ground motion residuals
    according to the GMPEs
    """
    def __init__(self, gmpe_list, imts):
        """
        :param list gmpe_list:
            List of GMPE names (using the standard openquake strings)
        :param list imts:
            List of Intensity Measures
        """
        self.gmpe_list = check_gsim_list(gmpe_list)
        self.number_gmpes = len(self.gmpe_list)
        self.types = {gmpe: {} for gmpe in self.gmpe_list}
        self.residuals = []
        self.modelled = []
        self.imts = imts
        self.unique_indices = {}
        self.gmpe_sa_limits = {}
        self.gmpe_scalars = {}
        for gmpe in self.gmpe_list:
            gmpe_dict_1 = {}
            gmpe_dict_2 = {}
            self.unique_indices[gmpe] = {}
            # Get the period range and the coefficient types
            # gmpe_i = GSIM_LIST[gmpe]()
            gmpe_i = self.gmpe_list[gmpe]
            for c in dir(gmpe_i):
                if 'COEFFS' in c:
                    pers = [sa.period for sa in getattr(gmpe_i, c).sa_coeffs]
            min_per, max_per = (min(pers), max(pers))
            self.gmpe_sa_limits[gmpe] = (min_per, max_per)
            for c in dir(gmpe_i):
                if 'COEFFS' in c:
                    self.gmpe_scalars[gmpe] = list(
                        getattr(gmpe_i, c).non_sa_coeffs.keys())
            for imtx in self.imts:
                if "SA(" in imtx:
                    period = imt.from_string(imtx).period
                    if period < min_per or period > max_per:
                        print("IMT %s outside period range for GMPE %s"
                              % (imtx, gmpe))
                        gmpe_dict_1[imtx] = None
                        gmpe_dict_2[imtx] = None
                        continue
                gmpe_dict_1[imtx] = {}
                gmpe_dict_2[imtx] = {}
                self.unique_indices[gmpe][imtx] = []
                self.types[gmpe][imtx] = []
                for res_type in \
                    self.gmpe_list[gmpe].DEFINED_FOR_STANDARD_DEVIATION_TYPES:
                    gmpe_dict_1[imtx][res_type] = []
                    gmpe_dict_2[imtx][res_type] = []
                    self.types[gmpe][imtx].append(res_type)
                gmpe_dict_2[imtx]["Mean"] = []
            self.residuals.append([gmpe, gmpe_dict_1])
            self.modelled.append([gmpe, gmpe_dict_2])
        self.residuals = dict(self.residuals)
        self.modelled = dict(self.modelled)
        self.number_records = None
        self.contexts = None

    def get_residuals(self, ctx_database, nodal_plane_index=1,
                      component="Geometric", normalise=True):
        """
        Calculate the residuals for a set of ground motion records

        :param ctx_database: a :class:`context_db.ContextDB`, i.e. a database of
            records capable of returning dicts of earthquake-based Contexts and
            observed IMTs.
            See e.g., :class:`smtk.sm_database.GroundMotionDatabase` for an
            example
        """

        contexts = ctx_database.get_contexts(nodal_plane_index, self.imts,
                                             component)

        # Fetch now outside the loop for efficiency the IMTs which need
        # acceleration units conversion from cm/s/s to g. Conversion will be
        # done inside the loop:
        accel_imts = tuple([imtx for imtx in self.imts if
                            (imtx == "PGA" or "SA(" in imtx)])

        # Contexts is in either case a list of dictionaries
        self.contexts = []
        for context in contexts:

            # convert all IMTS with acceleration units, which are supposed to
            # be in cm/s/s, to g:
            for a_imt in accel_imts:
                context['Observations'][a_imt] = \
                    convert_accel_units(context['Observations'][a_imt],
                                        'cm/s/s', 'g')

            # Get the expected ground motions
            context = self.get_expected_motions(context)
            context = self.calculate_residuals(context, normalise)
            for gmpe in self.residuals.keys():
                for imtx in self.residuals[gmpe].keys():
                    if not context["Residual"][gmpe][imtx]:
                        continue
                    for res_type in self.residuals[gmpe][imtx].keys():
                        if res_type == "Inter event":
                            inter_ev = \
                                context["Residual"][gmpe][imtx][res_type]
                            if np.all(
                                    np.fabs(inter_ev - inter_ev[0]) < 1.0E-12):
                                # Single inter-event residual
                                self.residuals[gmpe][imtx][res_type].append(
                                    inter_ev[0])
                                # Append indices
                                self.unique_indices[gmpe][imtx].append(
                                    np.array([0]))
                            else:
                                # Inter event residuals per-site e.g. Chiou
                                # & Youngs (2008; 2014) case
                                self.residuals[gmpe][imtx][res_type].extend(
                                    inter_ev)
                                self.unique_indices[gmpe][imtx].append(
                                    np.arange(len(inter_ev)))
                        else:
                            self.residuals[gmpe][imtx][res_type].extend(
                                context["Residual"][gmpe][imtx][res_type])
                        self.modelled[gmpe][imtx][res_type].extend(
                            context["Expected"][gmpe][imtx][res_type])

                    self.modelled[gmpe][imtx]["Mean"].extend(
                        context["Expected"][gmpe][imtx]["Mean"])

            self.contexts.append(context)

        for gmpe in self.residuals.keys():
            for imtx in self.residuals[gmpe].keys():
                if not self.residuals[gmpe][imtx]:
                    continue
                for res_type in self.residuals[gmpe][imtx].keys():
                    self.residuals[gmpe][imtx][res_type] = np.array(
                        self.residuals[gmpe][imtx][res_type])
                    self.modelled[gmpe][imtx][res_type] = np.array(
                        self.modelled[gmpe][imtx][res_type])
                self.modelled[gmpe][imtx]["Mean"] = np.array(
                    self.modelled[gmpe][imtx]["Mean"])

    def get_expected_motions(self, context):
        """
        Calculate the expected ground motions from the context
        """
        # TODO Rake hack will be removed!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        if not context["Ctx"].rake:
            context["Ctx"].rake = 0.0
        expected = {gmpe: {} for gmpe in self.gmpe_list}
        # Period range for GSIM
        for gmpe in self.gmpe_list:
            expected[gmpe] = {imtx: {} for imtx in self.imts}
            for imtx in self.imts:
                gsim = self.gmpe_list[gmpe]
                if "SA(" in imtx:
                    period = imt.from_string(imtx).period
                    if period < self.gmpe_sa_limits[gmpe][0] or\
                            period > self.gmpe_sa_limits[gmpe][1]:
                        expected[gmpe][imtx] = None
                        continue
                mean, stddev = gsim.get_mean_and_stddevs(
                    context["Ctx"],
                    context["Ctx"],
                    context["Ctx"],
                    imt.from_string(imtx),
                    self.types[gmpe][imtx])
                expected[gmpe][imtx]["Mean"] = mean
                for i, res_type in enumerate(self.types[gmpe][imtx]):
                    expected[gmpe][imtx][res_type] = stddev[i]

        context["Expected"] = expected
        return context

    def calculate_residuals(self, context, normalise=True):
        """
        Calculate the residual terms
        """
        # Calculate residual
        residual = {}
        for gmpe in self.gmpe_list:
            residual[gmpe] = {}
            for imtx in self.imts:
                residual[gmpe][imtx] = {}
                obs = np.log(context["Observations"][imtx])
                if not context["Expected"][gmpe][imtx]:
                    residual[gmpe][imtx] = None
                    continue
                mean = context["Expected"][gmpe][imtx]["Mean"]
                total_stddev = context["Expected"][gmpe][imtx]["Total"]
                residual[gmpe][imtx]["Total"] = (obs - mean) / total_stddev
                if "Inter event" in self.residuals[gmpe][imtx].keys():
                    inter, intra = self._get_random_effects_residuals(
                        obs,
                        mean,
                        context["Expected"][gmpe][imtx]["Inter event"],
                        context["Expected"][gmpe][imtx]["Intra event"],
                        normalise)
                    residual[gmpe][imtx]["Inter event"] = inter
                    residual[gmpe][imtx]["Intra event"] = intra
        context["Residual"] = residual
        return context

    def _get_random_effects_residuals(self, obs, mean, inter, intra,
                                      normalise=True):
        """
        Calculates the random effects residuals using the inter-event
        residual formula described in Abrahamson & Youngs (1992) Eq. 10
        """
        nvals = float(len(mean))
        inter_res = ((inter ** 2.) * sum(obs - mean)) /\
            (nvals * (inter ** 2.) + (intra ** 2.))
        intra_res = obs - (mean + inter_res)
        if normalise:
            return inter_res / inter, intra_res / intra
        return inter_res, intra_res

    def get_residual_statistics(self):
        """
        Retreives the mean and standard deviation values of the residuals
        """
        statistics = {gmpe: {} for gmpe in self.gmpe_list}
        for gmpe in self.gmpe_list:
            for imtx in self.imts:
                if not self.residuals[gmpe][imtx]:
                    continue
                statistics[gmpe][imtx] = \
                    self.get_residual_statistics_for(gmpe, imtx)
        return statistics

    def get_residual_statistics_for(self, gmpe, imtx):
        """
        Retreives the mean and standard deviation values of the residuals for
        a given gmpe and imtx

        :param gmpe: (string) the gmpe. It must be in the list of this
            object's gmpes
        :param imtx: (string) the imt. It must be in the imts defined for
            the given `gmpe`
        """
        residuals = self.residuals[gmpe][imtx]
        return {res_type: {"Mean": np.nanmean(residuals[res_type]),
                           "Std Dev": np.nanstd(residuals[res_type])}
                for res_type in self.types[gmpe][imtx]}

    def get_likelihood_values(self):
        """
        Returns the likelihood values for Total, plus inter- and intra-event
        residuals according to Equation 9 of Scherbaum et al (2004)
        """
        statistics = self.get_residual_statistics()
        lh_values = {gmpe: {} for gmpe in self.gmpe_list}
        for gmpe in self.gmpe_list:
            for imtx in self.imts:
                if not self.residuals[gmpe][imtx]:
                    print("IMT %s not found in Residuals for %s"
                          % (imtx, gmpe))
                    continue
                lh_values[gmpe][imtx] = {}
                values = self._get_likelihood_values_for(gmpe, imtx)
                for res_type, data in values.items():
                    l_h, median_lh = data
                    lh_values[gmpe][imtx][res_type] = l_h
                    statistics[gmpe][imtx][res_type]["Median LH"] =\
                        median_lh
        return lh_values, statistics

    def _get_likelihood_values_for(self, gmpe, imt):
        """
        Returns the likelihood values for Total, plus inter- and intra-event
        residuals according to Equation 9 of Scherbaum et al (2004) for the
        given gmpe and the given intensity measure type.
        `gmpe` must be in this object gmpe(s) list and imt must be defined
        for the given gmpe: this two conditions are not checked for here.

        :return: a dict mapping the residual type(s) (string) to the tuple
        lh, median_lh where the first is the array of likelihood values and
        the latter is the median of those values
        """

        ret = {}
        for res_type in self.types[gmpe][imt]:
            zvals = np.fabs(self.residuals[gmpe][imt][res_type])
            l_h = 1.0 - erf(zvals / sqrt(2.))
            median_lh = np.nanpercentile(l_h, 50.0)
            ret[res_type] = l_h, median_lh
        return ret

    def get_loglikelihood_values(self, imts):
        """
        Returns the loglikelihood fit of the GMPEs to data using the
        loglikehood (LLH) function described in Scherbaum et al. (2009)
        Scherbaum, F., Delavaud, E., Riggelsen, C. (2009) "Model Selection in
        Seismic Hazard Analysis: An Information-Theoretic Perspective",
        Bulletin of the Seismological Society of America, 99(6), 3234-3247

        :param imts:
            List of intensity measures for LLH calculation
        """
        log_residuals = {gmpe: np.array([]) for gmpe in self.gmpe_list}
        imt_list = [(imtx, None) for imtx in imts]
        imt_list.append(("All", None))
        llh = {gmpe: dict(imt_list) for gmpe in self.gmpe_list}
        for gmpe in self.gmpe_list:
            for imtx in imts:
                if not (imtx in self.imts) or not self.residuals[gmpe][imtx]:
                    print("IMT %s not found in Residuals for %s"
                          % (imtx, gmpe))
                    continue
                # Get log-likelihood distance for IMT
                asll = np.log2(norm.pdf(self.residuals[gmpe][imtx]["Total"],
                               0.,
                               1.0))
                log_residuals[gmpe] = np.hstack([
                    log_residuals[gmpe],
                    asll])
                llh[gmpe][imtx] = -(1.0 / float(len(asll))) * np.sum(asll)

            llh[gmpe]["All"] = -(1. / float(len(log_residuals[gmpe]))) *\
                np.sum(log_residuals[gmpe])
        # Get weights
        weights = np.array([2.0 ** -llh[gmpe]["All"]
                            for gmpe in self.gmpe_list])
        weights = weights / np.sum(weights)
        model_weights = {gmpe: weights[i] for i, gmpe in enumerate(self.gmpe_list)}
        return llh, model_weights

    # Mak et al multivariate LLH functions
    def get_multivariate_loglikelihood_values(self, sum_imts=False):
        """
        Calculates the multivariate LLH for a set of GMPEs and IMTS according
        to the approach described in Mak et al. (2017)

        Mak, S., Clements, R. A. and Schorlemmer, D. (2017) "Empirical
        Evaluation of Hierarchical Ground-Motion Models: Score Uncertainty
        and Model Weighting", Bulletin of the Seismological Society of America,
        107(2), 949-965

        :param sum_imts:
            If True then retuns a single multivariate LLH value summing the
            values from all imts, otherwise returns sepearate multivariate
            LLH for each imt.
        """
        multi_llh_values = {gmpe: {} for gmpe in self.gmpe_list}
        # Get number of events and records
        for gmpe in self.gmpe_list:
            print("GMPE = {:s}".format(gmpe))
            for j, imtx in enumerate(self.imts):
                if self.residuals[gmpe][imtx] is None:
                    # IMT missing for this GMPE
                    multi_llh_values[gmpe][imtx] = 0.0
                else:
                    multi_llh_values[gmpe][imtx] = get_multivariate_ll(
                        self.contexts, gmpe, imtx)
            if sum_imts:
                total_llh = 0.0
                for imtx in self.imts:
                    if np.isnan(multi_llh_values[gmpe][imtx]):
                        continue
                    total_llh += multi_llh_values[gmpe][imtx]
                multi_llh_values[gmpe] = total_llh
        return multi_llh_values

    def get_edr_values(self, bandwidth=0.01, multiplier=3.0):
        """
        Calculates the EDR values for each GMPE according to the Euclidean
        Distance Ranking method of Kale & Akkar (2013)

        Kale, O., and Akkar, S. (2013) "A New Procedure for Selecting and
        Ranking Ground Motion Predicion Equations (GMPEs): The Euclidean
        Distance-Based Ranking Method", Bulletin of the Seismological Society
        of America, 103(2A), 1069 - 1084.

        :param float bandwidth:
            Discretisation width

        :param float multiplier:
            "Multiplier of standard deviation (equation 8 of Kale and Akkar)
        """
        edr_values = {gmpe: {} for gmpe in self.gmpe_list}
        for gmpe in self.gmpe_list:
            obs, expected, stddev = self._get_edr_gmpe_information(gmpe)
            results = self._get_edr(obs,
                                    expected,
                                    stddev,
                                    bandwidth,
                                    multiplier)
            edr_values[gmpe]["MDE Norm"] = results[0]
            edr_values[gmpe]["sqrt Kappa"] = results[1]
            edr_values[gmpe]["EDR"] = results[2]
        return edr_values

    def _get_edr_gmpe_information(self, gmpe):
        """
        Extract the observed ground motions, expected and total standard
        deviation for the GMPE (aggregating over all IMS)
        """
        obs = np.array([], dtype=float)
        expected = np.array([], dtype=float)
        stddev = np.array([], dtype=float)
        for imtx in self.imts:
            for context in self.contexts:
                obs = np.hstack([obs, np.log(context["Observations"][imtx])])
                expected = np.hstack([expected,
                                      context["Expected"][gmpe][imtx]["Mean"]])
                stddev = np.hstack([stddev,
                                    context["Expected"][gmpe][imtx]["Total"]])
        return obs, expected, stddev

    def _get_edr(self, obs, expected, stddev, bandwidth=0.01, multiplier=3.0):
        """
        Calculated the Euclidean Distanced-Based Rank for a set of
        observed and expected values from a particular GMPE
        """
        finite = np.isfinite(obs) & np.isfinite(expected) & np.isfinite(stddev)
        if not finite.any():
            return np.nan, np.nan, np.nan
        elif not finite.all():
            obs, expected, stddev = obs[finite], expected[finite], stddev[finite]
        nvals = len(obs)
        min_d = bandwidth / 2.
        kappa = self._get_edr_kappa(obs, expected)
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
        return mde_norm, np.sqrt(kappa), edr

    def _get_edr_kappa(self, obs, expected):
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
