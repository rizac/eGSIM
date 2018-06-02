'''
Created on 16 Feb 2018

@author: riccardo
'''
import numpy as np

from django.test import TestCase
from egsim.forms import NArrayField, validation
from django.core.exceptions import ValidationError
import unittest
from egsim.core.trellis import gets, vectorize, intersection


class Test(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testgets(self):
        assert gets({'a': 1}, 'a') == [1]
        assert gets({'a': 1}, 'a,alba') == [1]
        assert gets({'alba': 1}, 'a,alba') == [1]
        try:
            assert gets({'b': 1}, 'a,alba')
            raise ValueError('did not raise!')
        except KeyError as kerr:
            assert "missing parameter 'a/alba'" in str(kerr)

    def test_vectorize(self):
        for arg in (None, '', 'abc', 1, 1.4005, True):
            expected = [arg]
            assert vectorize(arg) == expected
            assert vectorize(expected) is expected
        args = ([1, 2, 3], range(5), (1 for _ in [1, 2, 3]))
        for arg in args:
            assert vectorize(arg) is arg

    def test_intersection(self):
        assert intersection({'a': 1}, 'a') == {'a': 1}
        assert intersection({'a': 1}, 'a,alba') == {'a': 1}
        assert intersection({'alba': 1}, 'a,alba') == {'alba': 1}
        assert intersection({'a': 1, 'b': 'c'}, 'a,alba') == {'a': 1}
        assert intersection({'a': 1, 'b': 'c'}, 'b,boca') == {}
        



if __name__ == "__main__":
    unittest.main()
