"""
Created on 16 Feb 2018

@author: riccardo
"""
from datetime import datetime, date

import pytest

from egsim.api.flatfile import read_flatfile
from egsim.api.forms import relabel_sa
from egsim.api.forms.fields import NArrayField, vectorize
from egsim.api.management.commands._egsim_oq import read_registered_flatfile_columns


def test_vectorize():
    """tests the vectorize function"""
    for arg in (None, '', 'abc', 1, 1.4005, True):
        expected = [arg]
        assert vectorize(arg) == expected
        assert vectorize(expected) is expected
    args = ([1, 2, 3], tuple(), range(5))
    for arg in args:
        assert list(vectorize(arg)) == list(arg)
        if hasattr(arg, '__len__'):
            assert vectorize(arg) is arg


# def test_querystring(querystring):
#     """tests the querystring fixture"""
#     value = 'abc'
#     with pytest.raises(AttributeError):  # @UndefinedVariable
#         querystring(value)
#     value = {'abc': {'a': 9}}
#     with pytest.raises(ValueError):  # @UndefinedVariable
#         querystring(value)
#     ddd = datetime(2016, 1, 3, 4, 5, 6, 345)
#     value = {'abc': ddd}
#     patt = querystring(value)
#     assert patt == "abc=2016-01-03T04%3A05%3A06.000345"
#     for ddd in [date(2011, 4, 5), datetime(2011, 4, 5)]:
#         assert querystring({'abc': ddd}) == "abc=2011-04-05"
#     value = {'abc': [1, 'a', 1.1, '&invalid']}
#     patt = querystring(value)
#     assert patt == 'abc=1,a,1.1,%26invalid'


def test_relabel_sa():
    """tests _relabel_sa, which removes redundant trailing zeroes"""
    inputs = ['SA(1)', 'SA(1.133)', 'SA(10000)',
              ' SA(1)', ' SA(1.133)', ' SA(10000)',
              'SA(1) ', 'SA(1.133) ', 'SA(10000) ',
              '-SA(.100)', 'aSA(.100)', 'SA(1.1030)r', 'SA(1.1030)-']
    for string in inputs:
        assert relabel_sa(string) == string

    assert relabel_sa('SA(.100)') == 'SA(.1)'
    assert relabel_sa('SA(.100) ') == 'SA(.1) '
    assert relabel_sa(' SA(.100)') == ' SA(.1)'
    assert relabel_sa('SA(1.1030)') == 'SA(1.103)'
    assert relabel_sa(' SA(1.1030)') == ' SA(1.103)'
    assert relabel_sa('SA(1.1030) ') == 'SA(1.103) '
    assert relabel_sa('SA(1.1030)') == 'SA(1.103)'
    assert relabel_sa(' SA(1.1030)') == ' SA(1.103)'
    assert relabel_sa('SA(1.1030) ') == 'SA(1.103) '
    assert relabel_sa('SA(1.000)') == 'SA(1.0)'
    assert relabel_sa(' SA(1.000)') == ' SA(1.0)'
    assert relabel_sa('SA(1.000) ') == 'SA(1.0) '
    assert relabel_sa('(SA(1.000))') == '(SA(1.0))'
    assert relabel_sa(' (SA(1.000))') == ' (SA(1.0))'
    assert relabel_sa('(SA(1.000)) ') == '(SA(1.0)) '
    # test some "real" case:
    assert relabel_sa('Median SA(0.200000) (g)') == \
        'Median SA(0.2) (g)'
    assert relabel_sa('Median SA(2.00000) (g)') == \
        'Median SA(2.0) (g)'
    assert relabel_sa('Z (SA(2.00000))') == \
        'Z (SA(2.0))'


def test_areequal(areequal):
    """tests our fixture areequal used extensively in tests"""
    obj1 = [{'a': 9, 'b': 120}, 'abc', [1.00000001, 2, 2.000000005]]
    obj2 = ['abc', [1, 2, 2], {'b': 120, 'a': 9}]
    assert areequal(obj1, obj2)
    # make a small perturbation in 'a':
    obj2 = ['abc', [1, 2, 2], {'b': 120, 'a': 9.00000001}]
    assert areequal(obj1, obj2)  # still equal
    assert not areequal([], {})
    assert not areequal({}, [])
    assert areequal([1.0000000000001], [1])
    assert areequal({'a': 1.0000000000001, 'b': [1, 2, 3], 'c': 'abc'},
                    {'c': 'abc', 'b': [1, 1.99999999998, 3], 'a': 1})
    # 'b' is now 1.9, retol says: not equal:
    assert not areequal({'a': 1.0000000000001, 'b': [1, 2, 3], 'c': 'abc'},
                        {'c': 'abc', 'b': [1, 1.9, 3], 'a': 1})
    assert areequal(1.0000000000001, 1)


def test_flatfile_turkey(testdata):
    fpath = testdata.path('Turkey_20230206_flatfile_geometric_mean.csv')
    dfr = read_flatfile(fpath)
    flatfile_cols = read_registered_flatfile_columns()
    asd = 9
    # in EGSIM flatfile definition and not in Turkey flatfile:
    # {'fpeak', 'azimuth', 'station_latitude', 'station_longitude'}
    # In Turkey flatfile and not in eGSIM flatfile definition (excluding PGA, PGV, and SA):
    # {'gc2t', 'gc2u', 'sta', 'depth_bottom_of_rupture', 'event_id', 'gmid', 'longest_period', 'event_time'}
