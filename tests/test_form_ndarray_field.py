'''
Tests array fields functionalities
(array fields are django textfields which
accept scalar and vectors as string inputs)

Created on 16 Feb 2018

@author: riccardo
'''
import pytest

from django.core.exceptions import ValidationError
from egsim.forms.fields import NArrayField
from egsim.core.utils import isscalar


@pytest.mark.parametrize("input,expected", [
    ('1:1:10', [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
    ('1: .1 : 1.7', ValidationError),
    ('1:.1:1.7',  [1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7]),
    ('1:.1:1.7',  [1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7]),
    ('1:.1:1.799', [1, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7]),
    ('.11:.133:0.509', [0.11, 0.243, 0.376, 0.509]),
    ('.11:.133:0.5099', [0.11, 0.243, 0.376, 0.509]),
    ('.11:.133:0.508', [0.11, 0.243, 0.376]),
    ('.11:.133:0.5089', [0.11, 0.243, 0.376]),
    ('.11:.133:0.5089999', [0.11, 0.243, 0.376]),
    ('.11:.133:5.09e-1', [0.11, 0.243, 0.376, 0.509]),
    ('3.0:4.0:5.0', [3.0]),
    ('3.135e+2:100:414', [313.5, 413.5]),
    ('3.135e+2:100:413.5', [313.5, 413.5]),
    ('3.135e+2:100:413.5000001', [313.5, 413.5]),
    ('3.135e+2:100:413.4999999', [313.5]),
    ("[123.56]", [123.56]),  # check that we return an array (brackets given)
    ("123.56", 123.56),  # check we return a scalar (no brackets)
    ("1  , 55, 67.5", [1, 55, 67.5]),  # check no need for brackets in json
    ("[1  , 55, 67.5]", [1, 55, 67.5]),  # check this is the same as above
    ("1 55   67.5", [1, 55, 67.5]),  # check shlex
    ("[1 55   67.5]", [1, 55, 67.5]),  # check this is the same as above
    ("[  1 55   67.5   ]", [1, 55, 67.5]),  # (spaces after brackets ignored)
    ("1 55 ,  67.5", ValidationError),
    # check various floating point potential errors:
    ("0:1:10.001", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]),
    ("0:1:9.999999999999999", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
    ("0:1:9.99999999999999", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),
    ("[0.274:0.137:0.959]", [0.274, .411, .548, .685, .822, .959]),
    # mixed notations, check all these are the same:
    ("[0.274:0.137:0.959 5 6.67]",
     [0.274, .411, .548, .685, .822, .959, 5, 6.67]),
    ("0.274:0.137:0.959 5  6.67",
     [0.274, .411, .548, .685, .822, .959, 5, 6.67]),
    ("0.274:0.137:0.959,  5,  6.67", ValidationError),  # json invalid with ":"
    # this should work (quote):
    ('"0.274:0.137:0.959", 5 ,  6.67',
     [0.274, .411, .548, .685, .822, .959, 5, 6.67]),
    ("0.274:0.137:0.959, 5 6.67", ValidationError),
    ("", []),
    ("[]", []),
    ("[", ValidationError),
    ("]", ValidationError),
])
def test_to_python(input, expected):
    '''tests the method to_python of the NAarrayfield Field object'''
    
    n = NArrayField()
    
    if expected == ValidationError:
        with pytest.raises(ValidationError):  # @UndefinedVariable
            val = n.to_python(input)
    else:
        val = n.to_python(input)
        assert val == expected
        assert n.to_python(expected) == expected
        # test failing cases by providing boundary conditions:
        len_ = 1 if isscalar(val) else len(val)
        if len_ > 0:
            min_ = val if isscalar(val) else min(val)
            max_ = val if isscalar(val) else max(val)
            with pytest.raises(ValidationError):  # @UndefinedVariable
                NArrayField(min_value=min_+1).to_python(val)
            with pytest.raises(ValidationError):  # @UndefinedVariable
                NArrayField(max_value=max_-1).to_python(val)
            with pytest.raises(ValidationError):  # @UndefinedVariable
                NArrayField(min_count=len_+1).to_python(val)
            with pytest.raises(ValidationError):  # @UndefinedVariable
                NArrayField(max_count=len_-1).to_python(val)
            # test ok case by providing boundary conditions:
            val2 = \
                NArrayField(max_count=len_+1, min_count=len_-1,
                            min_value=min_-1, max_value=max_+1).to_python(val)
            # test ok case by providing boundary conditions as arrays (val):
            val2 = NArrayField(max_count=len_+1, min_count=len_-1,
                               min_value=val, max_value=val).to_python(val)
            assert val2 == expected
