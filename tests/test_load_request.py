'''
Tests yaml load function (the core function to load any input from POST
requests)

Created on 16 Feb 2018

@author: riccardo
'''
from io import StringIO

import pytest

from egsim.core.utils import yaml_load


@pytest.mark.parametrize('input_', ["{'a':9}", '{"a":9}', {'a': 9},
                                    "{a: 9}", "a: 9", "'a': 9",
                                    '"a": 9'])
def test_yaml_load(input_):
    '''
    tests the yaml_load function. Note that json formatted string are also
    recognized, and the quote character can be ' (in json, only " is
    allowed)
    '''
    expected = {'a': 9}
    assert yaml_load(input_) == expected
    if isinstance(input_, str):
        assert yaml_load(StringIO(input_)) == expected
