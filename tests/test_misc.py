"""
Created on 16 Feb 2018

@author: riccardo
"""
from datetime import datetime, date

import pytest

from egsim.api.forms import relabel_sa
from egsim.api.forms.fields import NArrayField, vectorize
from smtk.residuals.gmpe_residuals import Residuals


def test_vectorize():
    """tests the vectorize function"""
    for arg in (None, '', 'abc', 1, 1.4005, True):
        expected = [arg]
        assert vectorize(arg) == expected
        assert vectorize(expected) is expected
    args = ([1, 2, 3], range(5), (1 for _ in [1, 2, 3]))
    for arg in args:
        assert vectorize(arg) is arg


def test_querystring(querystring):
    """tests the querystring fixture"""
    value = 'abc'
    with pytest.raises(AttributeError):  # @UndefinedVariable
        querystring(value)
    value = {'abc': {'a': 9}}
    with pytest.raises(ValueError):  # @UndefinedVariable
        querystring(value)
    ddd = datetime(2016, 1, 3, 4, 5, 6, 345)
    value = {'abc': ddd}
    patt = querystring(value)
    assert patt == "abc=2016-01-03T04%3A05%3A06.000345"
    for ddd in [date(2011, 4, 5), datetime(2011, 4, 5)]:
        assert querystring({'abc': ddd}) == "abc=2011-04-05"
    value = {'abc': [1, 'a', 1.1, '&invalid']}
    patt = querystring(value)
    assert patt == 'abc=1,a,1.1,%26invalid'


# @pytest.mark.django_db
def test_narrayfield_get_decimals():
    """tests ndarrayfield get_decimals"""
    d_0 = NArrayField.get_decimals('1.3e45')
    assert d_0 == 0
    d_0 = NArrayField.get_decimals('1.3e1')
    assert d_0 == 0
    d_0 = NArrayField.get_decimals('1.3e0')
    assert d_0 == 1
    d_1 = NArrayField.get_decimals('1e-45')
    assert d_1 == 45
    d_2 = NArrayField.get_decimals('-5.005601')
    assert d_2 == 6
    d_2 = NArrayField.get_decimals('-5.0')
    assert d_2 == 1
    d_3 = NArrayField.get_decimals('-6')
    assert d_3 == 0
    d_4 = NArrayField.get_decimals('1.3E-6')
    assert d_4 == 7
    d_5 = NArrayField.get_decimals('1.3e45', '1.3E-6', '-6', '-5.005601',
                                   '1e-45')
    assert d_5 == 45


def test_relabel_sa():
    '''tests _relabel_sa, which removes redundant trailing zeroes'''
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
