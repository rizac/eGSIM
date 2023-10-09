"""
Tests for generation of data for trellis plots
"""
import os
import json
import numpy as np
import pandas as pd

from openquake.hazardlib.gsim.akkar_2014 import AkkarEtAlRjb2014
from openquake.hazardlib.gsim.bindi_2014 import BindiEtAl2014Rjb
from openquake.hazardlib.gsim.bindi_2017 import BindiEtAl2017Rjb


from egsim.smtk.trellis import get_trellis

BASE_DATA_PATH = os.path.join(os.path.dirname(__file__), "data")


imts = ["PGA", "SA(0.2)", "SA(2.0)", "SA(3.0)"]
periods = [0.05, 0.075, 0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16,
           0.17, 0.18, 0.19, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30,
           0.32, 0.34, 0.36, 0.38, 0.40, 0.42, 0.44, 0.46, 0.48,
           0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95,
           1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0,
           3.0, 4.001, 5.0, 7.5, 10.0]


# note below some GSIMS are passed as strings, some as instances (both
# types are valid, in the second case the str representation is
# inferred, see trellis_plot.py for details):
gsims = ["AkkarBommer2010", "CauzziFaccioli2008",
         "ChiouYoungs2008", "ZhaoEtAl2006Asc", AkkarEtAlRjb2014(),
         BindiEtAl2014Rjb(), "CauzziEtAl2014", "DerrasEtAl2014",
         "AbrahamsonEtAl2014", "BooreEtAl2014", "ChiouYoungs2014",
         "CampbellBozorgnia2014", "KothaEtAl2016Italy",
         "KothaEtAl2016Other", "KothaEtAl2016Turkey",
         "ZhaoEtAl2016Asc", BindiEtAl2017Rjb()]


def compare_jsons(self, old, new):
    """
    Compares the json data from file with the new data from trellis plot

    This version works with the magnitude IMT and distance IMT trellis
    plots. Magnitude-distance Spectra has a slightly different means of
    comparison, so this will be over-ridden in that test
    """
    # Check x-labels are the same
    self.assertEqual(old["xlabel"], new["xlabel"])
    # Check x-values are the same
    np.testing.assert_array_almost_equal(old["xvalues"], new["xvalues"], 7)
    for i in range(len(old["figures"])):
        self.assertEqual(old["figures"][i]["ylabel"],
                         new["figures"][i]["ylabel"])
        # self.assertEqual(old["figures"][i]["column"],
        #                  new["figures"][i]["column"])
        # self.assertEqual(old["figures"][i]["row"],
        #                  new["figures"][i]["row"])

        oldys = old["figures"][i]["yvalues"].values()
        newys = new["figures"][i]["yvalues"].values()
        for oldy, newy in zip(oldys, newys):
            np.testing.assert_array_almost_equal(oldy, newy, 7)


def test_distance_imt_trellis():
    """
    Tests the DistanceIMT trellis data generation
    """
    # Setup rupture
    properties = dict(dip=60.0, aspect=1.5, hypocentre_location=(0.5, 0.5),
                      vs30=800)
    distances = np.arange(0, 250.5, 1)
    magnitude = 6.5
    # Get trellis calculations
    dfr = get_trellis(
        gsims,
        imts,
        magnitude,
        distances,
        properties)
    # compare with old data:
    TEST_FILE = "trellis_vs_distance.hdf"
    ref = pd.read_hdf(os.path.join(BASE_DATA_PATH, TEST_FILE))
    ref = ref.iloc[1:]  # remove 1st line (was a bug in old code?)  noqa
    assert (dfr['mag'].values == ref['mag'].values).all()  # noqa
    assert (np.isna(dfr['period']) == np.isna(ref['period'])).all()
    asd = 9


def test_magnitude_imt_trellis():
    """
    Tests the MagnitudeIMT trellis data generation
    """
    magnitudes = np.arange(4., 8.1, 0.1)
    distance = 20.
    properties = {"dip": 60.0, "rake": -90.0, "aspect": 1.5, "ztor": 0.0,
                  "vs30": 800.0, "backarc": False, "z1pt0": 50.0,
                  "z2pt5": 1.0, "line_azimuth": 90.0}
    dfr = get_trellis(
        gsims,
        imts,
        magnitudes,
        distance,
        properties
    )
    # compare with old data:
    TEST_FILE = "test_magnitude_imt_trellis.json"
    with open(os.path.join(BASE_DATA_PATH, TEST_FILE), "r") as _:
        ref = json.load(_)
        compare_jsons(ref, dfr)


def test_magnitude_distance_spectra_trellis():
    """
    Tests the MagnitudeDistanceSpectra Trellis data generation
    """
    properties = {"dip": 60.0, "rake": -90.0, "aspect": 1.5, "ztor": 0.0,
                  "vs30": 800.0, "backarc": False, "z1pt0": 50.0,
                  "z2pt5": 1.0}
    magnitudes = [4.0, 5.0, 6.0, 7.0]
    distances = [5., 20., 50., 150.0]
    dfr = get_trellis(
        gsims,
        imts,
        magnitudes,
        distances,
        properties,
    )
    # compare with old data:
    TEST_FILE = "test_magnitude_distance_spectra_trellis.json"
    with open(os.path.join(BASE_DATA_PATH, TEST_FILE), "r") as _:
        ref = json.load(_)
        compare_jsons(ref, dfr)
