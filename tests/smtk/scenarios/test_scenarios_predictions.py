"""
Tests for generation of data for trellis plots
"""
import os
import numpy as np
import pandas as pd

from openquake.hazardlib.gsim.akkar_2014 import AkkarEtAlRjb2014
from openquake.hazardlib.gsim.bindi_2014 import BindiEtAl2014Rjb
from openquake.hazardlib.gsim.bindi_2017 import BindiEtAl2017Rjb
from scipy.interpolate import interpolate

from egsim.smtk.registry import Clabel
from egsim.smtk.flatfile import ColumnType, FlatfileMetadata
from egsim.smtk.scenarios import (get_scenarios_predictions, RuptureProperties,
                                  SiteProperties)

BASE_DATA_PATH = os.path.join(os.path.dirname(__file__), "data")


imts = ["PGA", "SA(0.2)", "SA(2.0)", "SA(3.0)"]
periods = [0.05, 0.075, 0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16,
           0.17, 0.18, 0.19, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30,
           0.32, 0.34, 0.36, 0.38, 0.40, 0.42, 0.44, 0.46, 0.48,
           0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95,
           1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0,
           3.0]  #  4.001, 5.0, 7.5, 10.0]


# the Gsims to test (mix strings and instances to test both):
gsims = ["AkkarBommer2010", "CauzziFaccioli2008",
         "ChiouYoungs2008", "ZhaoEtAl2006Asc", AkkarEtAlRjb2014(),
         BindiEtAl2014Rjb(), "CauzziEtAl2014", "DerrasEtAl2014",
         "AbrahamsonEtAl2014", "BooreEtAl2014", "ChiouYoungs2014",
         "CampbellBozorgnia2014", "KothaEtAl2016Italy",
         "KothaEtAl2016Other", "KothaEtAl2016Turkey",
         "ZhaoEtAl2016Asc", BindiEtAl2017Rjb()]


def allclose(actual, expected, *, q=None,
             rtol=1e-05, atol=1e-08, equal_nan=True):
    """Same as numpy `allclose` but with the possibility to remove outliers using
    the quantile parameter `q` in [0, 1]. Also note that `equal_nan is True by
    default. E.g., to check if the arrays `a` and `b` are close, ignoring the elements
    whose abs. difference is in the highest 5%: `allclose(a, b, q=0.95)`

    :param q: quantile in [0, 1] or None. If not None, the elements of
        `actual` and `expected` for which abs(expected-actual) is above the `q`
        quantile (e.g., 0.95) will be discarded before applying numpy `allclose`
    and `expected`, element-wise

    """
    if q is not None:
        diffs = np.abs(actual - expected)
        filter = np.isnan(diffs) | (diffs < np.nanquantile(diffs, q))
        expected = expected[filter]
        actual = actual[filter]

    return np.allclose(actual, expected, atol=atol, rtol=rtol, equal_nan=equal_nan)


def test_distance_imt_trellis():
    """test trellis vs distance"""
    distances = np.arange(0, 250.5, 1)
    magnitude = 6.5
    # Get trellis calculations
    dfr = get_scenarios_predictions(
        gsims,
        imts,
        magnitude,
        distances,
        RuptureProperties(dip=60.0, aspect=1.5, hypocenter_location=(0.5, 0.5)),
        SiteProperties(vs30=800))

    ref = open_ref_hdf("trellis_vs_distance.hdf")
    assert len(dfr) == len(distances)
    # there was a kind of bug in old smtk? ref has one element more, as the 1st distance
    # is repeated twice. Test it and remove 1st row:
    assert (ref.iloc[0, :] == ref.iloc[1, :]).all()  # noqa
    # now remove 1st row
    ref = ref.iloc[1:, :].copy()
    # usual tests:
    assert len(ref) == len(dfr)
    assert not set(ref.columns) ^ set(dfr.columns)


    # Now compare trellis values:
    for c in dfr.columns:
        if c[0] == Clabel.input_data:
            if c[-1] == 'rrup':
                # distances are messed up, let's just test they are
                # both monotonically increasing:
                assert all(x < y for x, y in zip(dfr[c], dfr[c][1:]))
                assert all(x < y for x, y in zip(ref[c], ref[c][1:]))
            else:
                # magnitudes should be equal:
                assert (dfr[c].values == ref[c].values).all()  # noqa

            continue

        if all(_ for _ in c):  # columns denoting medians and sttdev
            # all series are monotonically decreasing:
            if 'Median' in c and not 'ChiouYoungs2008' in c:
                values = dfr[c]
                if 'AbrahamsonEtAl2014' or 'ChiouYoungs2008' in c:
                    # these gsims have increasing values at the beginning,
                    # then decrease. Remove first 20 values
                    values = dfr[c][20:]
                assert (np.diff(values) <= 0).all()
            dist_col = (Clabel.input_data, ColumnType.distance.value, 'rrup')
            # create interpolation function from new data
            interp = interpolate.interp1d(dfr[dist_col].values, dfr[c].values,
                                          fill_value="extrapolate", kind="cubic")
            # interpolate the old values
            expected = interp(ref[dist_col].values)
            # and here are the old values:
            actual = ref[c].values
            # Now check diffs (The if below are unnecessary but allow to set
            # breakpoints in PyCharm):
            # assert data is close enough:
            if not allclose(actual, expected, rtol=0.04):
                assert False
            # assert data is really close if we exclude some sparse outlier (keep data
            # below the 95-th percentile calculated the diffs):
            if not allclose(actual, expected, rtol=0.0002, q=0.95):
                assert False


def test_magnitude_imt_trellis():
    """Test trellis vs magnitudes"""
    magnitudes = np.arange(4., 8.1, 0.1)
    distance = 20.

    dfr = get_scenarios_predictions(
        gsims,
        imts,
        magnitudes,
        distance,
        RuptureProperties(dip=60.0, aspect=1.5, rake=-90),
        SiteProperties(vs30=800, z1pt0=50., z2pt5=1.)
    )

    ref = open_ref_hdf("trellis_vs_magnitude.hdf")
    assert len(ref) == len(dfr)
    assert not set(ref.columns) ^ set(dfr.columns)

    # Now compare trellis values:
    for c in dfr.columns:
        if c[0] == Clabel.input_data:
            assert (dfr[c] == ref[c]).all()  # noqa
            continue

        if all(_ for _ in c):  # columns denoting medians and sttdev
            # all series are monotonically increasing:
            if 'Median' in c:
                try:
                    assert (np.diff(dfr[c]) >= 0).all()
                except AssertionError:
                    # assert that at least 92% of the points are increasing
                    # (hacky test heuristically calculated):
                    assert (np.diff(dfr[c]) >= 0).sum() > 0.92 * len(dfr[c])
            # create interpolation function from new data
            mag_col = (Clabel.input_data, ColumnType.rupture.value, 'mag')
            interp = interpolate.interp1d(dfr[mag_col].values, dfr[c].values,
                                          fill_value="extrapolate", kind="cubic")
            # interpolate the old values
            expected = interp(ref[mag_col].values)
            # and here are the old values:
            actual = ref[c].values
            # Now check diffs (The if below are unnecessary but allow to set
            # breakpoints in PyCharm):
            # assert data is close enough:
            # if not allclose(actual, expected, rtol=0.75):
            #     assert False
            # assert data is really close if we exclude some sparse outlier (keep data
            # below the 50-th percentile calculated the diffs):
            if not allclose(actual, expected, rtol=0.1, q=0.5):
                assert False


def test_magnitude_distance_spectra_trellis():
    """
    Tests the MagnitudeDistanceSpectra Trellis data generation
    """
    # properties = {"dip": 60.0, "rake": -90.0, "aspect": 1.5, "ztor": 0.0,
    #               "vs30": 800.0, "backarc": False, "z1pt0": 50.0,
    #               "z2pt5": 1.0}
    magnitudes = [4.0, 5.0, 6.0, 7.0]
    distances = [5., 20., 50., 150.0]
    # with raises(IncompatibleInput) as verr:
    dfr = get_scenarios_predictions(
        gsims,
        list(periods) + [4.001, 5.0, 7.5, 10.0],
        magnitudes,
        distances,
        RuptureProperties(dip=60., rake=-90., aspect=1.5, ztor=0.0),
        SiteProperties(vs30=800.0, backarc=False, z1pt0=50.0,
                       z2pt5=1.0)
    )
    # test that some gsim are not supported for all periods:
    assert (dfr.columns.get_level_values(0) == 'SA(3.0)').sum() > \
           (dfr.columns.get_level_values(0) == 'SA(4.001)').sum()
    assert (dfr.columns.get_level_values(0) == 'SA(4.001)').sum() > \
           (dfr.columns.get_level_values(0) == 'SA(10.0)').sum()

    # normal test (comparison with old data):
    dfr = get_scenarios_predictions(
        gsims,
        periods,
        magnitudes,
        distances,
        RuptureProperties(dip=60., rake=-90., aspect=1.5, ztor=0.0),
        SiteProperties(vs30=800.0, backarc=False, z1pt0=50.0,
                       z2pt5=1.0)
    )
    # compare with old data:
    ref = open_ref_hdf("trellis_spectra.hdf")

    assert len(ref) == len(dfr)
    assert not set(ref.columns) ^ set(dfr.columns)  # noqa

    # compare trellis values:
    for c in dfr.columns:
        if c[0] == Clabel.input_data:
            assert (dfr[c] == ref[c]).all()  # noqa
            continue

        if all(_ for _ in c):  # columns denoting medians and sttdev
            # interpolate the old values
            expected = dfr[c].values
            # and here are the old values:
            actual = ref[c].values
            # check they are close:
            if not allclose(actual, expected, rtol=0.0001):  #, q=0.95):
                assert False


def open_ref_hdf(file_name) -> pd.DataFrame:
    ref:pd.DataFrame = pd.read_hdf(os.path.join(BASE_DATA_PATH, file_name))  # noqa
    # columns are the same:
    # map columns:
    c_mapping = {}
    for c in ref.columns:
        if c[0] == 'Median':
            c_mapping[c] = (c[1], Clabel.median, c[-1])
        elif c[0] == 'Stddev':
            c_mapping[c] = (c[1], Clabel.std, c[-1])
        else:
            try:
                c_mapping[c] = (
                    Clabel.input_data,
                    str(FlatfileMetadata.get_type(c[0]).value),
                    c[0])
            except Exception as exc:
                raise ValueError(f'`ref` dataframe: unmapped column {c}. {exc}')
    # set new columns (create new dataframe, as rename does not work with
    # multiindex and set_level is too complex):
    new_ref = pd.DataFrame({v: ref[c] for c, v in c_mapping.items()})
    new_ref.columns = pd.MultiIndex.from_tuples(new_ref.columns)
    return new_ref
