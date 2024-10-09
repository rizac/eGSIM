"""
"""
from io import StringIO

import pytest

import numpy as np
import pandas as pd

from egsim.smtk.converters import convert_accel_units, dataframe2dict, datetime2str, \
    datetime2float


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


def test_convert_datetimes():
    csv_str = "\n".join(['time', '', '2006', '2006-01-01', '2006-01-01T00:00:00',
                         '2006-01-01T00:00:00.0', '2006-01-01T00:00:00.001'])
    series = pd.read_csv(
        StringIO(csv_str),
        skip_blank_lines=False,
        parse_dates=['time'],
        date_format='ISO8601')['time']
    vals = datetime2str(series)
    # default format is seconds, micro/milliseconds are rounded/removed:
    assert all(_ == '2006-01-01T00:00:00' for _ in vals[1:])
    assert pd.isna(vals[0])
    # same test with numpy arrays:
    vals = datetime2str(series.values)
    assert all(_ == '2006-01-01T00:00:00' for _ in vals[1:])
    assert pd.isna(vals[0])

    # test a different format (default format is s):
    vals = datetime2str(series, '%Y-%m-%dT%H:%M:%S.%f')
    assert all(_ == '2006-01-01T00:00:00.000000' for _ in vals[1:-1])
    assert pd.isna(vals[0])
    # this time last value differs:
    assert vals[-1] == '2006-01-01T00:00:00.001000'

    vals = datetime2float(series)
    assert all(isinstance(_, float) for _ in vals[1:-1])
    assert pd.isna(vals[0])
    # check that the last values is 0.001 more than the next-to-last
    # (take into account rounding problems):
    assert np.isclose(vals[-1] - vals[-2], 0.001, rtol=1e-4, atol=0)
    # same test with numpy arrays:
    vals = datetime2float(series.values)
    assert pd.isna(vals[0])
    assert all(isinstance(_, float) for _ in vals[1:-1])
    # check that the last values is 0.001 more than the next-to-last
    # (take into account rounding problems):
    assert np.isclose(vals[-1] - vals[-2], 0.001, rtol=1e-4, atol=0)
