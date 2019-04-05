'''
Created on 16 Feb 2018

@author: riccardo
'''
from datetime import datetime, date

from egsim.core.utils import vectorize, querystring
from egsim.forms.fields import MultipleChoiceWildcardField
import pytest


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
    