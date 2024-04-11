"""
"""
import pytest

import numpy as np
import pandas as pd

from egsim.smtk.converters import convert_accel_units, dataframe2dict


def test_dataframe2dict():
    """Test the flatfile metadata"""
    cols = [('mag', ''), ('PGA', 'CauzziEtAl')]
    data = [[np.nan, 1], [3, np.inf], [-np.inf, 5.37]]
    dfr = pd.DataFrame(columns=cols, data=data)
    _check_dataframe2dict(dfr)
    # the dataframe above does not actually have a
    # multi-index, so let's set one and check again
    # (the multiindex we are about to set does not change
    # the dataframe columns actually):
    dfr.columns = pd.MultiIndex.from_tuples(cols)
    assert isinstance(dfr.columns, pd.MultiIndex)
    _check_dataframe2dict(dfr)


def _check_dataframe2dict(dfr):
    """Test the flatfile metadata"""
    res = dataframe2dict(dfr, as_json=False, drop_empty_levels=False)
    expected = {
        ('mag', ''): [np.nan, 3, -np.inf],
        ('PGA', 'CauzziEtAl'): [1., np.inf, 5.37]
    }
    assert list(expected) == list(res)
    assert all(len(_1) == len(_2) for _1, _2, in zip(res.values(), expected.values()))
    assert all(_1==_2 or (np.isnan(_1) and np.isnan(_2))
               for k in res for _1, _2 in zip(expected[k], res[k]))

    res = dataframe2dict(dfr, as_json=False, drop_empty_levels=True)
    expected = {
        'mag': [np.nan, 3, -np.inf],
        ('PGA', 'CauzziEtAl'): [1., np.inf, 5.37]
    }
    assert list(expected) == list(res)
    assert all(len(_1) == len(_2) for _1, _2, in zip(res.values(), expected.values()))
    assert all(_1 == _2 or (np.isnan(_1) and np.isnan(_2))
               for k in res for _1, _2 in zip(expected[k], res[k]))

    res = dataframe2dict(dfr, as_json=True, drop_empty_levels=False)
    assert res == {'mag': {'': [None, 3.0, None]},
                   'PGA': {'CauzziEtAl': [1.0, None, 5.37]}}

    res = dataframe2dict(dfr, as_json=True, drop_empty_levels=True)
    assert res == {'mag': [None, 3.0, None], 'PGA': {'CauzziEtAl': [1.0, None, 5.37]}}


def test_convert_accel_units():
    """test convert accel units"""
    from scipy.constants import g
    for m_sec in ["m/s/s", "m/s**2", "m/s^2"]:
        for cm_sec in ["cm/s/s", "cm/s**2", "cm/s^2"]:
            assert convert_accel_units(1, m_sec, cm_sec) == 100
            assert convert_accel_units(1, cm_sec, m_sec) == .01
            assert convert_accel_units(g, m_sec, "g") == 1
            assert convert_accel_units(g, cm_sec, "g") == .01
            assert convert_accel_units(1, "g", m_sec) == g
            assert convert_accel_units(1, "g", cm_sec) == g*100
            assert convert_accel_units(1, cm_sec, cm_sec) == 1
            assert convert_accel_units(1, m_sec, m_sec) == 1

    assert convert_accel_units(1, "g", "g") == 1
    with pytest.raises(ValueError):
        assert convert_accel_units(1, "gf", "gf") == 1
