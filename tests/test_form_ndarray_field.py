'''
Created on 16 Feb 2018

@author: riccardo
'''
import pytest

import numpy as np

from django.core.exceptions import ValidationError
from egsim.forms import NArrayField


def test_str2nprange():
    '''tests the method str2nprange of the NAarrayfield Field object'''

    val = NArrayField.str2nprange('1:1:10')
    assert val == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    val = NArrayField.str2nprange('1: .1 : 1.7')
    assert val == [1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7]

    val = NArrayField.str2nprange('1: .1 : 1.799')
    assert val == [1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7]

    val = NArrayField.str2nprange('.11: .133 : 0.509')
    assert val == [0.11, 0.243, 0.376, 0.509]

    val = NArrayField.str2nprange('.11: .133 : 0.5099')
    assert val == [0.11, 0.243, 0.376, 0.509]

    val = NArrayField.str2nprange('.11: .133 : 0.508')
    assert val == [0.11, 0.243, 0.376]

    val = NArrayField.str2nprange('.11: .133 : 0.5089')
    assert val == [0.11, 0.243, 0.376]

    val = NArrayField.str2nprange('.11: .133 : 0.5089999')
    assert val == [0.11, 0.243, 0.376]

    val = NArrayField.str2nprange('.11: .133 : 5.09e-1')
    assert val == [0.11, 0.243, 0.376, 0.509]

    val = NArrayField.str2nprange('3.0: 4.0 : 5.0')
    assert val == [3.0]

    val = NArrayField.str2nprange('3.135e+2: 100 : 414')
    assert val == [313.5, 413.5]

    val = NArrayField.str2nprange('3.135e+2: 100 : 413.5')
    assert val == [313.5, 413.5]

    val = NArrayField.str2nprange('3.135e+2: 100 : 413.5000001')
    assert val == [313.5, 413.5]

    val = NArrayField.str2nprange('3.135e+2: 100 : 413.4999999')
    assert val == [313.5]


def test_narrayfield():
    '''tests the NAarrayfield Field object'''
    # test empty value with required:
    field = NArrayField()
    with pytest.raises(ValidationError):
        field.clean("")

    # test empty value with required:
    field = NArrayField(required=False)
    val = field.clean("")
    assert val == []

    # test mismatching brackets:
    field = NArrayField(required=False)
    with pytest.raises(ValidationError):
        field.clean("(2.2 1 3]")

    # test scalar and single value arrays, they should produce the same values
    for val in ("2.2", "2.2 ", " 2.2", " 2.2 ",
                "(2.2)", " (2.2)", " ( 2.2)", "(2.2) ", "(2.2 ) ", " ( 2.2 ) ",
                "[2.2]", " [2.2]", " [ 2.2]", "[2.2] ", "[2.2 ] ", " [ 2.2 ] ",):
        field = NArrayField(required=False)
        vector = '[' in val or '(' in val
        val = field.clean(val)
        if vector:
            assert val == [2.2]
        else:
            assert val == 2.2
    # test commas and spaces
    for val in ("2.2 , 1.003,4", " 2.2 , 1.003 4", "2.2 , 1.003, 4", " 2.2 , 1.003 ,4",
                "2.2  1.003 4", "2.2,1.003,4", " 2.2    1.003  ,    4",
                "[2.2  1.003 4]", "  [ 2.2,1.003,4]", "[2.2    1.003  ,    4  ]  ",
                "(2.2  1.003 4)", "  ( 2.2,1.003,4)", "[2.2    1.003  ,    4    ]    "):
        field = NArrayField(required=False)
        val = field.clean(val)
        assert val == [2.2, 1.003, 4]

    # test ranges:
    field = NArrayField(required=False)
    assert field.clean("0:1:10") == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert field.clean("0:1:10.001") == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert field.clean("0:1:9.999999999999999") == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert field.clean("0:1:9.99999999999999") == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert field.clean("[0.274:0.137:0.959]") == [0.274, .411, .548, .685, .822, .959]
    for val in ("[0.274:0.137:0.959 5 6.67]", "0.274:0.137:0.959 5  6.67",
                "0.274 : 0.137 : 0.959, 5 6.67", "0.274 : 0.137 : 0.959, 5,6.67"):
        field = NArrayField(required=False)
        val = field.clean(val)
        assert val == [0.274, .411, .548, .685, .822, .959, 5, 6.67]
