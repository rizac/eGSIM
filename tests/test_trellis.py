'''
Created on 2 Jun 2018

@author: riccardo
'''
import unittest

import django
from django.test import TestCase

from egsim.forms import BaseForm, TrellisForm
import os
from egsim.core.trellis import compute
from egsim.core import yaml_load
from yaml import YAMLError
import mock

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

class Test(TestCase):

    GSIM, IMT = 'gsim', 'imt'

    def setUp(self):
        django.setup()
        pass


    def tearDown(self):
        pass


    # @mock.patch('egsim.core import yaml_load', side_effect=yaml_load)
    def tst_compute_raises(self): # , mock_yaml_load):
        with self.assertRaises(YAMLError) as context:  # https://stackoverflow.com/a/3166985
            compute(os.path.join(DATA_DIR, 'trellis1'))
        with self.assertRaises(YAMLError) as context:
            data = compute(os.path.join(DATA_DIR, 'trellis_malformed.yaml'))
        with self.assertRaises(YAMLError) as context:
            data = compute(os.path.join(DATA_DIR, 'trellis_filenot_found.yaml'))


    def test_compute_validation_errors(self):
        data = compute(os.path.join(DATA_DIR, 'trellis_dist.yaml'))
        # FIXME: better implementation, the form returns:
        # "SA(0.2)" not defined for all supplied gsim(s)
        form = data[0]
        assert not form.errors and form.is_valid
        # check output:
        
    
#     def test_compute_validation_errors(self):
#         data = compute(os.path.join(DATA_DIR, 'trellis_dist.yaml'))
#         # FIXME: better implementation, the form returns:
#         # "SA(0.2)" not defined for all supplied gsim(s)
#         form = data[0]
#         assert form.errors and not form.is_valid
#         pass

if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()