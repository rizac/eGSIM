"""
Core test suite for the database and residuals construction
"""
from unittest import skip
import json
import numpy as np
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
        ifile = os.path.join(BASE_DATA_PATH, "flatfile_esm_data.hdf.csv")
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
        expected_total = {
            'AkkarEtAlRjb2014': {
                'PGA': [9.738919038697901, 9.653757143922775, 9.890355348233294,
                        9.668832804237766, 10.526286056764045, 9.286881911015712,
                        8.655970520344649, 9.586917647042315, 11.844272686999453,
                        10.02069556197066, 9.78426136219533, 9.213236258883127,
                        10.725471759534278, 9.38766188289006, 11.98379175158191,
                        10.77099694600399, 7.61837305602139, 6.024204947337238,
                        9.036749357043869, 5.947628398407928, 7.56098476003127,
                        10.162264973769263, 8.975877088476462, 8.598715365740652,
                        7.513808588339909, 10.806303859190434, 10.122785401606617,
                        9.635618612619805, 7.102329117706171, 8.430619417689897,
                        14.119616885948247, 11.326573786085783, 12.420718149299411,
                        12.97590353891818, 10.878151256584296, 12.0722476502338,
                        13.127941609747673, 11.819343425765402, 13.161347964916224,
                        11.495489430665735],
                'SA(1.0)': [9.754810727852604, 10.250759610935983, 10.574997984888395,
                            10.70514147793748, 9.98815592689245, 9.359080256073975,
                            8.680621148002484, 9.198862021207857, 10.231084467905427,
                            8.023166126437483, 9.345882789853265, 9.527708392496997,
                            10.580212775039165, 8.022735278618445, 9.928538572809396,
                            8.250156747043562, 7.805038157391803, 7.320464165457093,
                            8.78942743136433, 5.740207520779572, 8.184412527836042,
                            9.501361260788805, 7.86813822468351, 8.40457812498918,
                            6.9867832434416774, 9.51670628474105, 8.639745394326948,
                            9.487445342431458, 6.745364598656149, 9.209670070639735,
                            12.778447773743727, 10.014029064087433, 11.20958816259471,
                            12.498668263705065, 10.72587719004694, 10.968665654909232,
                            11.556961874681194, 10.98447961467168, 12.331867016153058,
                            10.864721078645442]
            },
            'ChiouYoungs2014': {
                'PGA' : [10.752090873118208, 10.012128579655672, 11.195952500086047,
                         11.92184412630349, 9.770934559139521, 8.296390979852337,
                         8.781141273229721, 9.761004320727743, 10.922325849421345,
                         9.348589384545942, 9.823369100655206, 8.892986833226328,
                         9.603316630990712, 9.2371420047023, 10.798601619108899,
                         9.581200323232203, 5.341576808025353, 4.177026637447336,
                         9.203806942880412, 7.222718227727113, 8.952532264148955,
                         10.382225498514043, 9.166987136896434, 9.462193886929908,
                         7.8571146176612015, 10.987980480413425, 10.284821770668847,
                         9.8396636039173, 7.739239966301016, 9.972815173318537,
                         14.564907644618499, 11.671568201943014, 13.319222543664283,
                         13.364620693631304, 11.764659377017393, 12.413878821389797,
                         14.901911661654507, 12.22391603288246,
                         14.803882019632923, 13.371224298983307],
            'SA(1.0)': [9.657244519018793, 10.324179985094323, 10.547825847168484,
                        10.835648439589539, 9.911560173819181, 9.17591129591883,
                        8.727734697824442, 9.253360482720533, 9.962420964601268,
                        7.836403216289581, 9.371844651875026, 9.307588177495234,
                        10.4366666085311, 7.910257728628481, 9.731183946407176,
                        8.122346403330152, 8.29195617421199, 7.859247598595202,
                        8.94597069822924, 6.229668398734768, 8.979385128318784,
                        9.676063502202371, 7.913457016281386, 8.823091888662331,
                        7.163869961974717, 9.709192817045048, 8.781058584523658,
                        9.83584459368478, 7.018359591711046, 9.941635696305491,
                        13.116311286766035, 10.253613958214032, 11.693589763823507,
                        12.867357067295046, 11.20068042710456, 11.238595098125845,
                        12.342730614050149, 11.292143772314516, 13.123940478154308,
                        11.718234899310362]
            },
        }
        expected_inter_event = {  # just min median max
            'AkkarEtAlRjb2014': {
                'PGA': (5.4016186025712685, 13.7327083785088, 18.391530778699206),
                'SA(1.0)': (6.067141907806279, 13.294714508875902, 16.986421792710466)
            },
            'ChiouYoungs2014': {
                'PGA': (3.879551663058323, 19.68567527323765, 19.88597885668337),
                'SA(1.0)': (6.840009809949991, 17.3680294947619, 17.432481258299045)
            },
        }
        expected_intra_event = {  # just min median max
            'AkkarEtAlRjb2014': {
                'PGA': (-3.553518727578542, 2.4458742214594116, 5.83096227163716),
                'SA(1.0)': (-3.2298772030017706, 2.331403518498448, 5.523118063264394)
            },
            'ChiouYoungs2014': {
                'PGA': (-2.8137639106525345, 2.288502596100712, 6.173513217969853),
                'SA(1.0)': (-3.1835687286292753, 1.9787917412703837, 5.411486334689559)
            },
        }
        for gsim in res_dict:
            for imt in res_dict[gsim]:
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
                # check values
                values = res_dict[gsim][imt]["Total"]
                vals_ok = np.allclose(values, expected_total[gsim][imt])
                self.assertTrue(vals_ok)
                values_ = res_dict[gsim][imt]["Inter event"]
                values = np.nanmin(values_), np.nanmedian(values_), np.nanmax(values_)
                vals_ok = np.allclose(values, expected_inter_event[gsim][imt])
                self.assertTrue(vals_ok)
                values_ = res_dict[gsim][imt]["Intra event"]
                values = np.nanmin(values_), np.nanmedian(values_), np.nanmax(values_)
                vals_ok = np.allclose(values, expected_intra_event[gsim][imt])
                self.assertTrue(vals_ok)

    def test_residuals_execution(self):
        """
        Tests basic execution of residuals - not correctness of values
        """
        residuals = res.Residuals(self.gsims, self.imts)
        residuals.get_residuals(self.database, component="Geometric")
        res_dict = residuals.residuals
        file = "residual_tests_esm_data.json"
        with open(os.path.join(BASE_DATA_PATH, file)) as _:
            exp_dict = json.load(_)
        # check results:
        self.assertEqual(len(exp_dict), len(res_dict))
        for gsim in res_dict:
            self.assertEqual(len(exp_dict[gsim]), len(res_dict[gsim]))
            for imt in res_dict[gsim]:
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
                # check values
                values = res_dict[gsim][imt]["Total"]
                vals_ok = np.allclose(values, exp_dict[gsim][imt]["Total"])
                self.assertTrue(vals_ok)
                values = res_dict[gsim][imt]["Inter event"]
                vals_ok = np.allclose(values, exp_dict[gsim][imt]["Inter event"])
                self.assertTrue(vals_ok)
                values = res_dict[gsim][imt]["Intra event"]
                vals_ok = np.allclose(values, exp_dict[gsim][imt]["Intra event"])
                self.assertTrue(vals_ok)

        # residuals.get_residual_statistics()

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
