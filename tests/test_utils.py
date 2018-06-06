'''
Created on 16 Feb 2018

@author: riccardo
'''
import unittest

import numpy as np

from django.test import TestCase
from egsim.utils import vectorize


class Test(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_vectorize(self):
        '''tests the vectorize function'''
        for arg in (None, '', 'abc', 1, 1.4005, True):
            expected = [arg]
            assert vectorize(arg) == expected
            assert vectorize(expected) is expected
        args = ([1, 2, 3], range(5), (1 for _ in [1, 2, 3]))
        for arg in args:
            assert vectorize(arg) is arg


if __name__ == "__main__":
    unittest.main()
