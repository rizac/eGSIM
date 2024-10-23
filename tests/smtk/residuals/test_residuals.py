"""
test residuals computations (standard and likelihood)
"""
import json
import numpy as np
import os

from egsim.smtk import residuals
from egsim.smtk.flatfile import read_flatfile, ColumnType
from scipy.constants import g
from egsim.smtk.registry import Clabel


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
        flatfile[i] = flatfile[i] / (100 *g)  # convert_accel_units(flatfile[i], 'cm/s/s', 'g')
    return gsims, imts, flatfile


label_mapping_res = {
    'Total': Clabel.total_res,
    'Inter-event': Clabel.inter_ev_res,
    'Intra-event': Clabel.intra_ev_res
}


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
    res_df = residuals.get_residuals(gsims, imts, flatfile.copy())
    # old data:
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
            key = (Clabel.input_data, ColumnType.rupture.value, 'event_id')
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
    res_df = residuals.get_residuals(gsims, imts, flatfile, likelihood=True)
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
            key = (Clabel.input_data, ColumnType.rupture.value, 'event_id')
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
