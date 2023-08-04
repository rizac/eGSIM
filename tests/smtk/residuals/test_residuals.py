"""
Core test suite for the database and residuals construction
"""
from unittest import skip
import json
import numpy as np
import os

import pandas as pd
from django.test import SimpleTestCase  # https://stackoverflow.com/a/59764739


# import egsim.smtk.residuals.gmpe_residuals as res
# from egsim.smtk.flatfile import ContextDB, read_flatfile
# from egsim.smtk.residuals import convert_accel_units
from egsim.smtk import residuals
from egsim.smtk.flatfile import read_flatfile
from egsim.smtk import convert_accel_units
from egsim.smtk.residuals import column_label, c_labels

BASE_DATA_PATH = os.path.join(os.path.dirname(__file__), "data")


EXPECTED_IDS = [
    "EMSC_20040918_0000026_RA_PYAS_0", "EMSC_20040918_0000026_RA_PYAT_0",
    "EMSC_20040918_0000026_RA_PYLI_0", "EMSC_20040918_0000026_RA_PYLL_0",
    "EMSC_20041205_0000033_CH_BNALP_0", "EMSC_20041205_0000033_CH_BOURR_0",
    "EMSC_20041205_0000033_CH_DIX_0", "EMSC_20041205_0000033_CH_EMV_0",
    "EMSC_20041205_0000033_CH_LIENZ_0", "EMSC_20041205_0000033_CH_LLS_0",
    "EMSC_20041205_0000033_CH_MMK_0", "EMSC_20041205_0000033_CH_SENIN_0",
    "EMSC_20041205_0000033_CH_SULZ_0", "EMSC_20041205_0000033_CH_VDL_0",
    "EMSC_20041205_0000033_CH_ZUR_0", "EMSC_20041205_0000033_RA_STBO_0",
    "EMSC_20130103_0000020_HL_SIVA_0", "EMSC_20130103_0000020_HL_ZKR_0",
    "EMSC_20130108_0000044_HL_ALNA_0", "EMSC_20130108_0000044_HL_AMGA_0",
    "EMSC_20130108_0000044_HL_DLFA_0", "EMSC_20130108_0000044_HL_EFSA_0",
    "EMSC_20130108_0000044_HL_KVLA_0", "EMSC_20130108_0000044_HL_LIA_0",
    "EMSC_20130108_0000044_HL_NOAC_0", "EMSC_20130108_0000044_HL_PLG_0",
    "EMSC_20130108_0000044_HL_PRK_0", "EMSC_20130108_0000044_HL_PSRA_0",
    "EMSC_20130108_0000044_HL_SMTH_0", "EMSC_20130108_0000044_HL_TNSA_0",
    "EMSC_20130108_0000044_HL_YDRA_0", "EMSC_20130108_0000044_KO_ENZZ_0",
    "EMSC_20130108_0000044_KO_FOCM_0", "EMSC_20130108_0000044_KO_GMLD_0",
    "EMSC_20130108_0000044_KO_GOKC_0", "EMSC_20130108_0000044_KO_GOMA_0",
    "EMSC_20130108_0000044_KO_GPNR_0", "EMSC_20130108_0000044_KO_KIYI_0",
    "EMSC_20130108_0000044_KO_KRBN_0", "EMSC_20130108_0000044_KO_ORLT_0",
    "EMSC_20130108_0000044_KO_SHAP_0"]


class ResidualsTestCase(SimpleTestCase):
    """
    Core test case for the residuals objects
    """

    @classmethod
    def setUpClass(cls):
        """
        Setup constructs the database from the ESM test data
        """
        # ifile = os.path.join(BASE_DATA_PATH, "flatfile_esm_data.hdf.csv")
        # cls.database = ContextDB(read_flatfile(ifile))
        # # fix distances required for these tests (rjb and rrup are all NaNs):
        # cls.database._data['rjb'] = cls.database._data['repi'].copy()
        # cls.database._data['rrup'] = cls.database._data['rhypo'].copy()
        #
        # cls.num_events = len(pd.unique(cls.database._data['event_id']))
        # cls.num_records = len(cls.database._data)
        #
        # cls.gsims = ["AkkarEtAlRjb2014",  "ChiouYoungs2014"]
        # cls.imts = ["PGA", "SA(1.0)"]

        ifile = os.path.join(BASE_DATA_PATH, "residual_tests_esm_data.csv" )  # "flatfile_esm_data.hdf.csv")
        flatfile = read_flatfile(ifile)
        # fix distances required for these tests (rjb and rrup are all NaNs):
        # flatfile['rjb'] = flatfile['repi'].copy()
        # flatfile['rrup'] = flatfile['rhypo'].copy()

        cls.num_events = len(pd.unique(flatfile['event_id']))
        cls.num_records = len(flatfile)

        cls.database = flatfile
        cls.gsims = ["AkkarEtAlRjb2014", "ChiouYoungs2014"]
        imts = ["PGA", "SA(1.0)"]
        for i in imts:
            flatfile[i] = convert_accel_units(flatfile[i], 'cm/s/s', 'g')
        cls.imts = imts

    def test_residuals_execution(self):
        """
        Tests basic execution of residuals - not correctness of values
        """
        # residuals = res.Residuals(self.gsims, self.imts)
        # residuals.get_residuals(self.database, component="Geometric")
        res_dict = residuals.get_residuals(self.gsims, self.imts, self.database)
        file = "residual_tests_esm_data_old_smtk.json"
        with open(os.path.join(BASE_DATA_PATH, file)) as _:
            exp_dict = json.load(_)
        # check results:
        # self.assertEqual(len(exp_dict), len(res_dict))
        for lbl in exp_dict:
            # self.assertEqual(len(exp_dict[gsim]), len(res_dict[gsim]))
                # check values
            expected = np.array(exp_dict[lbl], dtype=float)
            # computed dataframes have different labelling:
            lbl += " residuals"
            computed = res_dict[lbl].values
            if 'Inter-event' in lbl:
                # Are all inter events (per event) are close enough?
                # (otherwise its an Inter event residuals per-site e.g. Chiou
                # & Youngs (2008; 2014) case)
                _computed = []
                for ev_id, dfr in res_dict.groupby('event_id'):
                    vals = dfr[lbl].values
                    if ((vals - vals[0]) < 1.0E-12).all():
                        _computed.append(vals[0])
                    else:
                        _computed = None
                        break
                if _computed is not None:
                    computed = np.array(_computed, dtype=float)

            vals_ok = np.allclose(expected, computed)
            if not vals_ok:
                # vals_ok = np.allclose(expected, computed, rtol=1e-01, atol=0)
                # check that at least 90% of the data is close enough (<1% relative
                # error)
                data_ratio = .9
                threshold = 0.01
                rel_diff = (expected - computed) / computed
                max_diff = np.nanquantile(np.abs(rel_diff), data_ratio)
                vals_ok = max_diff < threshold

            self.assertTrue(vals_ok)

    def test_likelihood_execution(self):
        """
        Tests basic execution of residuals - not correctness of values
        """
        lkh = res.Residuals(self.gsims, self.imts)
        lkh.get_residuals(self.database, component="Geometric")
        self._check_residual_dictionary_correctness(lkh.residuals)
        res_dict = lkh.get_likelihood_values()
        res_dict = res_dict[0]
        file = "residual_lh_tests_esm_data.json"
        with open(os.path.join(BASE_DATA_PATH, file)) as _:
            exp_dict = json.load(_)
        # check results:
        self.assertEqual(len(exp_dict), len(res_dict))
        for gsim in res_dict:
            self.assertEqual(len(exp_dict[gsim]), len(res_dict[gsim]))
            for imt in res_dict[gsim]:
                # check values
                values = res_dict[gsim][imt]["Total"]
                vals_ok = np.allclose(values, exp_dict[gsim][imt]["Total"])
                self.assertTrue(vals_ok)
                values = res_dict[gsim][imt]["Inter event"]
                # values = np.nanmin(values_), np.nanmedian(values_), np.nanmax(values_)
                vals_ok = np.allclose(values, exp_dict[gsim][imt]["Inter event"])
                self.assertTrue(vals_ok)
                values = res_dict[gsim][imt]["Intra event"]
                # values = np.nanmin(values_), np.nanmedian(values_), np.nanmax(values_)
                vals_ok = np.allclose(values, exp_dict[gsim][imt]["Intra event"])
                self.assertTrue(vals_ok)

    def test_llh_execution(self):
        """
        Tests execution of LLH - not correctness of values
        """
        llh = res.Residuals(self.gsims, self.imts)
        llh.get_residuals(self.database, component="Geometric")
        self._check_residual_dictionary_correctness(llh.residuals)
        res_dict = llh.get_loglikelihood_values(self.imts)
        res_dict = res_dict[0]
        file = "residual_llh_tests_esm_data.json"
        with open(os.path.join(BASE_DATA_PATH, file)) as _:
            exp_dict = json.load(_)
        self.assertEqual(len(exp_dict), len(res_dict))
        for gsim in res_dict:
            self.assertEqual(len(exp_dict[gsim]), len(res_dict[gsim]))
            for imt in res_dict[gsim]:
                # check values
                values = res_dict[gsim][imt]
                vals_ok = np.allclose(values, exp_dict[gsim][imt])
                self.assertTrue(vals_ok)

    @skip('Multivariate not implemented yet')
    def test_multivariate_llh_execution(self):
        """
        Tests execution of multivariate llh - not correctness of values
        """
        multi_llh = res.Residuals(self.gsims, self.imts)
        multi_llh.get_residuals(self.database, component="Geometric")
        self._check_residual_dictionary_correctness(multi_llh.residuals)
        res_dict = multi_llh.get_multivariate_loglikelihood_values()
        file = "residual_mllh_tests_esm_data.json"
        with open(os.path.join(BASE_DATA_PATH, file)) as _:
            exp_dict = json.load(_)
        for gsim in res_dict:
            self.assertEqual(len(exp_dict[gsim]), len(res_dict[gsim]))
            for imt in res_dict[gsim]:
                # check values
                values = res_dict[gsim][imt]
                vals_ok = np.allclose(values, exp_dict[gsim][imt])
                self.assertTrue(vals_ok)

    def test_edr_execution(self):
        """
        Tests execution of EDR - not correctness of values
        """
        edr = res.Residuals(self.gsims, self.imts)
        edr.get_residuals(self.database, component="Geometric")
        self._check_residual_dictionary_correctness(edr.residuals)
        res_dict = edr.get_edr_values()
        file = "residual_edr_tests_esm_data.json"
        with open(os.path.join(BASE_DATA_PATH, file)) as _:
            exp_dict = json.load(_)
        self.assertEqual(len(exp_dict), len(res_dict))
        for gsim in res_dict:
            self.assertEqual(len(exp_dict[gsim]), len(res_dict[gsim]))
            for imt in res_dict[gsim]:
                # check values
                values = res_dict[gsim][imt]
                vals_ok = np.allclose(values, exp_dict[gsim][imt])
                self.assertTrue(vals_ok)

    def test_multiple_metrics(self):
        """
        Tests the execution running multiple metrics in one call
        """
        residuals = res.Residuals(self.gsims, self.imts)
        residuals.get_residuals(self.database, component="Geometric")
        config = {}
        for key in ["Residuals", "Likelihood", "LLH", "EDR"]:
                    # "MultivariateLLH", "EDR"]:
            _ = res.GSIM_MODEL_DATA_TESTS[key](residuals, config)

    def test_convert_accel_units(self):
        """test convert accel units"""
        from scipy.constants import g
        for m_sec in ["m/s/s", "m/s**2", "m/s^2"]:
            for cm_sec in ["cm/s/s", "cm/s**2", "cm/s^2"]:
                self.assertEqual(convert_accel_units(1, m_sec, cm_sec), 100)
                self.assertEqual(convert_accel_units(1, cm_sec, m_sec), .01)
                self.assertEqual(convert_accel_units(g, m_sec, "g"), 1)
                self.assertEqual(convert_accel_units(g, cm_sec, "g"), .01)
                self.assertEqual(convert_accel_units(1, "g", m_sec), g)
                self.assertEqual(convert_accel_units(1, "g", cm_sec), g*100)
                self.assertEqual(convert_accel_units(1, cm_sec, cm_sec), 1)
                self.assertEqual(convert_accel_units(1, m_sec, m_sec),1)

        self.assertEqual(convert_accel_units(1, "g", "g"), 1)
        with self.assertRaises(ValueError):
            self.assertEqual(convert_accel_units(1, "gf", "gf"), 1)
