"""
test residuals computations (standard and likelihood)
"""
import json
from unittest.mock import patch

import numpy as np
import os
import pandas as pd
import pytest
from datetime import datetime

from egsim.smtk import residuals
from egsim.smtk.flatfile import read_flatfile, ColumnType
from scipy.constants import g
from egsim.smtk.registry import Clabel
from egsim.smtk.validators import ModelError

# load flatfile once:
BASE_DATA_PATH = os.path.join(os.path.dirname(__file__), "data")
ifile = os.path.join(BASE_DATA_PATH, "residual_tests_esm_data.csv" )
_flatfile = read_flatfile(ifile)


def get_gsims_imts_flatfile():
    """input data used in this module"""
    gsims = ["AkkarEtAlRjb2014", "ChiouYoungs2014"]
    imts = ["PGA", "SA(1.0)"]
    flatfile = _flatfile.copy()
    for i in imts:
        # convert cm/sec^2 to g:
        flatfile[i] = flatfile[i] / (100 * g)  # convert_accel_units(flatfile[i], 'cm/s/s', 'g')
    return gsims, imts, flatfile


label_mapping_res = {
    'Total': Clabel.total_res,
    'Inter-event': Clabel.inter_ev_res,
    'Intra-event': Clabel.intra_ev_res
}


def get_residuals(gsims, imts, flatfile, likelihood=False):
    """Run get_residuals with both multi- and single- header option, assuring that the
    two dataframes are equal. Return the multi-header dataframe because tests here
    rely on that
    """
    ff = flatfile.copy()
    df_single_header = residuals.get_residuals(gsims, imts, ff, likelihood)
    df_multi_header = residuals.get_residuals(gsims, imts, ff, likelihood,
                                              header_sep=None)
    df_multi_header2 = df_single_header.rename(
        columns={c: tuple(c.split(Clabel.sep)) for c in df_single_header.columns})
    df_multi_header2.columns = pd.MultiIndex.from_tuples(df_multi_header2.columns)
    pd.testing.assert_frame_equal(df_multi_header, df_multi_header2)
    return df_multi_header


def test_residuals_error():
    """GhofraniAtkinson2014CascadiaUpper requires a backarc attribute not present
    in a flatfile. Test that we correctly replace it with boolean false
    (this was not happening in previous eGSIM version due to DataFrame index != Series
    index. For details see https://stackoverflow.com/a/29706954)
    """
    flatfile = read_flatfile(os.path.join(BASE_DATA_PATH,
                             "test_flatfile_esm_2018_SA_mag_greater_than_7.hdf"))
    gsims = ['GhofraniAtkinson2014CascadiaUpper']
    imts = ['PGA']
    flatfile = flatfile[(flatfile.index >= 75) & (flatfile.index <= 77)]
    res_df = get_residuals(gsims, imts, flatfile)


def test_residuals_execution():
    """
    Tests basic execution of residuals - not correctness of values
    """
    # when comparing new and old data, try numpy `allclose` and if it fails, retry
    # with relaxed conditions:
    RTOL = 0.016  # relative tolerance defining "closeness": abs diff element-wise
    QTL = 0.95  # quantile defining how much data must be "close enough" (<RTOL)

    # compute data
    gsims, imts, flatfile = get_gsims_imts_flatfile()
    # legacy code
    res_df = get_residuals(gsims, imts, flatfile)

    # now test res_df (multi-level col header - legacy code) against old data to asure
    # consistency:
    file = "residual_tests_esm_data_old_smtk.json"
    with open(os.path.join(BASE_DATA_PATH, file)) as _:
        exp_dict = json.load(_)
    # check results:

    for lbl in exp_dict:
        # check values
        is_inter_ev = 'Inter-event' in lbl
        expected = np.array(exp_dict[lbl], dtype=float)
        # computed dataframes have different labelling:
        _model, _imt, _lbl = lbl.split(" ")
        lbl = (_imt, label_mapping_res[_lbl], _model)
        computed = res_df[lbl].values
        if is_inter_ev:
            # Are all inter events (per event) are close enough?
            # (otherwise its an Inter event residuals per-site e.g. Chiou
            # & Youngs (2008; 2014) case)
            _computed = []
            key = (Clabel.input, ColumnType.rupture.value, 'event_id')
            for ev_id, dfr in res_df.groupby([key], observed=False):
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
            # relax conditions and retry:
            rel_diff = (expected - computed) / computed
            max_diff = np.nanquantile(np.abs(rel_diff), QTL)
            vals_ok = max_diff < RTOL

        assert vals_ok


label_mapping_res_lh = {
    'Total': Clabel.total_lh,
    'Inter-event': Clabel.inter_ev_lh,
    'Intra-event': Clabel.intra_ev_lh
}


def test_residuals_execution_lh():
    """
    Tests basic execution of residuals - not correctness of values
    """
    # when comparing new and old data, try numpy `allclose` and if it fails, retry
    # with relaxed conditions:
    RTOL = 0.012  # relative tolerance defining "closeness": abs. diff element-wise
    QTL = 0.95  # quantile defining how much data must be "close enough" (<RTOL)

    # compute data
    gsims, imts, flatfile = get_gsims_imts_flatfile()
    res_df = get_residuals(gsims, imts, flatfile, likelihood=True)
    # load old data:
    file = "residual_tests_esm_data_old_smtk_lh.json"
    with open(os.path.join(BASE_DATA_PATH, file)) as _:
        exp_dict = json.load(_)
    # check results:
    # self.assertEqual(len(exp_dict), len(res_dict))
    for lbl in exp_dict:
        is_inter_ev = 'Inter-event' in lbl
        expected = np.array(exp_dict[lbl], dtype=float)
        # computed dataframes have different labelling:
        _model, _imt, _lbl = lbl.split(" ")
        lbl = (_imt, label_mapping_res_lh[_lbl], _model)
        computed = res_df[lbl].values
        if is_inter_ev:
            # Are all inter events (per event) are close enough?
            # (otherwise its an Inter event residuals per-site e.g. Chiou
            # & Youngs (2008; 2014) case)
            _computed = []
            key = (Clabel.input, ColumnType.rupture.value, 'event_id')
            for ev_id, dfr in res_df.groupby([key]):
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
            # relax the conditions and retry:
            rel_diff = (expected - computed) / computed
            max_diff = np.nanquantile(np.abs(rel_diff), QTL)
            vals_ok = max_diff < RTOL

        assert vals_ok


def test_assign_series():
    # in residuals.get_required_ground_motion_properties we assign a series values to
    # a dataframe. Check that this is not causing a dtype change
    for vals in [
        [1, 2],
        [1.1, np.nan],
        [True, False],
        [datetime.utcnow(), pd.NaT],
        ['a', None]
    ]:
        series = pd.Series(vals)
        series1 = pd.DataFrame({'series': series}).series
        series2 = pd.DataFrame({'series': series.values}).series
        pd.testing.assert_series_equal(series1, series2)
        assert series1.dtype == series2.dtype
        # this is the problem we want to avoid:
        # provide an index to the DataFrame, the dtype might be different
        series3 = pd.DataFrame({'series': series}, index=[11, 12]).series
        # for ints and bools is not ok
        # (as index differs -> data not found -> set NaN in dframe -> change dtype)
        if series1.dtype in (np.bool_, np.int64):
            assert series1.dtype != series3.dtype
        else:
            # for dtypes supporting NaNs, dtype is preserved BUT VALUES ARE NOT!
            # dtype1 in (np.float64, np.dtype('<M8[ns]'), np.dtype('O')):
            assert series1.dtype == series3.dtype
            try:
                pd.testing.assert_series_equal(series1, series3)
                raise AssertionError('series are identical, they should not be')
            except AssertionError:
                pass


@patch('egsim.smtk.residuals.get_ground_motion_values', side_effect=ValueError('a'))
def test_model_error(mock_get_gmv):
    with pytest.raises(ModelError) as err:
        gsims, imts, flatfile = get_gsims_imts_flatfile()
        res_df = get_residuals(gsims, imts, flatfile, likelihood=True)
    assert mock_get_gmv.called
    # the expected model is the first among the gsims (sorted), so:
    expected_model = sorted(gsims)[0]
    assert f'{expected_model}: (ValueError) a' in str(err.value)