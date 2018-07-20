'''
Created on 16 Feb 2018

@author: riccardo
'''
from io import StringIO

import pytest

from egsim.core import yaml_load

@pytest.mark.parametrize('input', ["{'a':9}", '{"a":9}', {'a': 9}, "{a: 9}", "a: 9", "'a': 9",
                                   '"a": 9'])
def test_yaml_load(input):
    '''tests the yaml_load function. Note that json formatted string are also recognized,
    and the quote character can be ' (in json, only " is allowed)'''
    expected = {'a': 9}
    assert yaml_load(input) == expected
    if isinstance(input, str):
        assert yaml_load(StringIO(input)) == expected

