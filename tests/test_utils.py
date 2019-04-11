'''
Created on 16 Feb 2018

@author: riccardo
'''
from datetime import datetime, date

import pytest

from egsim.core.utils import vectorize, querystring
from egsim.forms.fields import NArrayField

def test_vectorize():
    '''tests the vectorize function'''
    for arg in (None, '', 'abc', 1, 1.4005, True):
        expected = [arg]
        assert vectorize(arg) == expected
        assert vectorize(expected) is expected
    args = ([1, 2, 3], range(5), (1 for _ in [1, 2, 3]))
    for arg in args:
        assert vectorize(arg) is arg


def test_querystring():
    value = 'abc'
    with pytest.raises(AttributeError):  # @UndefinedVariable
        querystring(value)
    value = {'abc': {'a': 9}}
    with pytest.raises(ValueError):  # @UndefinedVariable
        querystring(value)
    ddd = datetime(2016, 1, 3, 4, 5, 6, 345)
    value = {'abc': ddd}
    patt = querystring(value)
    assert patt == "abc=2016-01-03T04:05:06.000345"
    for ddd in [date(2011, 4, 5), datetime(2011, 4, 5)]:
        assert querystring({'abc': ddd}) == "abc=2011-04-05"
    value = {'abc': [1, 'a', 1.1, '&invalid']}
    patt = querystring(value)
    assert patt == 'abc=1,a,1.1,%26invalid'


@pytest.mark.django_db
def test_narrayfield_get_decimals():
    # this should be impoerted inside the test marked with django_db
    
    d0 = NArrayField.get_decimals('1.3e45')
    assert d0 == 0
    d0 = NArrayField.get_decimals('1.3e1')
    assert d0 == 0
    d0 = NArrayField.get_decimals('1.3e0')
    assert d0 == 1
    d1 = NArrayField.get_decimals('1e-45')
    assert d1 == 45
    d2 = NArrayField.get_decimals('-5.005601')
    assert d2 == 6
    d2 = NArrayField.get_decimals('-5.0')
    assert d2 == 1
    d3 = NArrayField.get_decimals('-6')
    assert d3 == 0
    d4 = NArrayField.get_decimals('1.3E-6')
    assert d4 == 7
    d5 = NArrayField.get_decimals('1.3e45', '1.3E-6', '-6', '-5.005601',
                                  '1e-45')
    assert d5 == 45