"""
test rankings (measures of fit derived from residuals computations)
"""
import json
import numpy as np
import os

import pandas as pd

from egsim.smtk import residuals, get_measures_of_fit
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
        flatfile[i] = flatfile[i] / (100 * g)
    return gsims, imts, flatfile


label_mapping_res = {
    'Total': Clabel.total_res,
    'Inter-event': Clabel.inter_ev_res,
    'Intra-event': Clabel.intra_ev_res
}


def test_measures_of_fit_execution_no_lh():
    """
    Tests basic execution of measures of fit. No likelihood
    """
    # compute data
    gsims, imts, flatfile = get_gsims_imts_flatfile()
    res_df = residuals.get_residuals(gsims, imts, flatfile.copy())

    m_fit = get_measures_of_fit(gsims, imts, res_df)

    # check we have edr columns
    edr_columns = {'mde_norm', 'sqrt kappa', 'edr'}
    # assert  edr_columns & set(m_fit.columns) == edr_columns

    # check residuals columns (residuals stats):
    expected_res_cols_count = 3 * len(gsims) * 2  # 3 res. types and 2 measures of fit
    actual_res_cols_count = len([c for c in m_fit.columns
                                if c.endswith(' stddev') or c.endswith(' mean')])
    assert expected_res_cols_count == actual_res_cols_count

    # check loglikelihood columns:
    expected_llh_cols_count = 3
    actual_llh_cols_count = len([c for c in m_fit.columns
                                if c.endswith('loglikelihood')])
    assert expected_llh_cols_count == actual_llh_cols_count

    assert len(m_fit.columns) == (expected_res_cols_count + expected_llh_cols_count +
                                  len(edr_columns))
    # no NaN:
    # assert pd.notna(m_fit).all().all()


label_mapping_res_lh = {
    'Total': Clabel.total_lh,
    'Inter-event': Clabel.inter_ev_lh,
    'Intra-event': Clabel.intra_ev_lh
}


def tst_measures_of_fit_execution():
    """
    Tests basic execution of measures of fit (with likelihood)
    """
    # compute data
    gsims, imts, flatfile = get_gsims_imts_flatfile()
    res_df = residuals.get_residuals(gsims, imts, flatfile.copy(), likelihood=True)

    m_fit = get_measures_of_fit(gsims, imts, res_df)

    # check we have edr columns
    edr_columns = {'mde_norm', 'sqrt kappa', 'edr'}
    # assert  edr_columns & set(m_fit.columns) == edr_columns

    # check residuals columns (residuals stats):
    expected_res_cols_count = 3 * len(gsims) * 2  # 3 res. types and 2 measures of fit
    actual_res_cols_count = len([c for c in m_fit.columns
                                if c.endswith(' stddev') or c.endswith(' mean')])
    assert expected_res_cols_count == actual_res_cols_count

    # check loglikelihood columns:
    expected_llh_cols_count = 3
    actual_llh_cols_count = len([c for c in m_fit.columns
                                if c.endswith('loglikelihood')])
    assert expected_llh_cols_count == actual_llh_cols_count

    assert len(m_fit.columns) == (expected_res_cols_count + expected_llh_cols_count +
                                  len(edr_columns))
    # no NaN:
    # assert pd.notna(m_fit).all().all()
