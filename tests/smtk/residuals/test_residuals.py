"""
Core test suite for the database and residuals construction
"""
import os

import pandas as pd
from django.test import SimpleTestCase  # https://stackoverflow.com/a/59764739


import egsim.smtk.residuals.gmpe_residuals as res
from egsim.smtk.flatfile import ContextDB, read_flatfile
from egsim.smtk.residuals import convert_accel_units

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
        ifile = os.path.join(BASE_DATA_PATH, "residual_tests_esm_data.hdf.csv")
        cls.database = ContextDB(read_flatfile(ifile))
        # fix distances required for these tests (rjb and rrup are all NaNs):
        cls.database._data['rjb'] = cls.database._data['repi'].copy()
        cls.database._data['rrup'] = cls.database._data['rhypo'].copy()

        cls.num_events = len(pd.unique(cls.database._data['event_id']))
        cls.num_records = len(cls.database._data)

        cls.gsims = ["AkkarEtAlRjb2014",  "ChiouYoungs2014"]
        cls.imts = ["PGA", "SA(1.0)"]

    # def test_correct_build_load(self):
    #     """
    #     Verifies that the database has been built and loaded correctly
    #     """
    #     self.assertEqual(len(self.database), 41)
    #     self.assertListEqual([rec.id for rec in self.database],
    #                          EXPECTED_IDS)

    def _check_residual_dictionary_correctness(self, res_dict):
        """
        Basic check for correctness of the residual dictionary
        """
        for i, gsim in enumerate(res_dict):
            self.assertEqual(gsim, self.gsims[i])
            for j, imt in enumerate(res_dict[gsim]):
                self.assertEqual(imt, self.imts[j])
                if gsim == "AkkarEtAlRjb2014":
                    # For Akkar et al - inter-event residuals should have
                    # 4 elements and the intra-event residuals 41
                    self.assertEqual(
                        len(res_dict[gsim][imt]["Inter event"]), self.num_events)
                elif gsim == "ChiouYoungs2014":
                    # For Chiou & Youngs - inter-event residuals should have
                    # 41 elements and the intra-event residuals 41 too
                    self.assertEqual(
                        len(res_dict[gsim][imt]["Inter event"]), self.num_records)
                else:
                    pass
                self.assertEqual(
                        len(res_dict[gsim][imt]["Intra event"]), self.num_records)
                self.assertEqual(
                        len(res_dict[gsim][imt]["Total"]), self.num_records)

    def test_residuals_execution(self):
        """
        Tests basic execution of residuals - not correctness of values
        """
        residuals = res.Residuals(self.gsims, self.imts)
        residuals.get_residuals(self.database, component="Geometric")
        self._check_residual_dictionary_correctness(residuals.residuals)
        residuals.get_residual_statistics()

    def test_likelihood_execution(self):
        """
        Tests basic execution of residuals - not correctness of values
        """
        lkh = res.Residuals(self.gsims, self.imts)
        lkh.get_residuals(self.database, component="Geometric")
        self._check_residual_dictionary_correctness(lkh.residuals)
        lkh.get_likelihood_values()

    def test_llh_execution(self):
        """
        Tests execution of LLH - not correctness of values
        """
        llh = res.Residuals(self.gsims, self.imts)
        llh.get_residuals(self.database, component="Geometric")
        self._check_residual_dictionary_correctness(llh.residuals)
        llh.get_loglikelihood_values(self.imts)

    def test_multivariate_llh_execution(self):
        """
        Tests execution of multivariate llh - not correctness of values
        """
        multi_llh = res.Residuals(self.gsims, self.imts)
        multi_llh.get_residuals(self.database, component="Geometric")
        self._check_residual_dictionary_correctness(multi_llh.residuals)
        multi_llh.get_multivariate_loglikelihood_values()

    def test_edr_execution(self):
        """
        Tests execution of EDR - not correctness of values
        """
        edr = res.Residuals(self.gsims, self.imts)
        edr.get_residuals(self.database, component="Geometric")
        self._check_residual_dictionary_correctness(edr.residuals)
        edr.get_edr_values()

    def test_multiple_metrics(self):
        """
        Tests the execution running multiple metrics in one call
        """
        residuals = res.Residuals(self.gsims, self.imts)
        residuals.get_residuals(self.database, component="Geometric")
        config = {}
        for key in ["Residuals", "Likelihood", "LLH",
                    "MultivariateLLH", "EDR"]:
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
