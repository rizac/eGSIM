'''
Created on 16 Feb 2018

@author: riccardo
'''
import numpy as np

from django.test import TestCase
from egsim.forms import NArrayField, validation
from django.core.exceptions import ValidationError
import unittest



class Test(TestCase):


    def setUp(self):
        
        pass


    def tearDown(self):
        pass


    def testNArrayField(self):
        # test empty value with required:
        field = NArrayField()
        with self.assertRaises(ValidationError):
            val = field.clean("")
        
        # test empty value with required:
        field = NArrayField(required=False)
        val = field.clean("")
        assert val == []    
        
        # test mismatching brackets:
        field = NArrayField(required=False)
        with self.assertRaises(ValidationError):
            val = field.clean("(2.2 1 3]")
        
        
        # test scalar and single value arrays, they should produce the same values
        for val in ("2.2", "2.2 ", " 2.2", " 2.2 ",
                    "(2.2)", " (2.2)", " ( 2.2)", "(2.2) ", "(2.2 ) ", " ( 2.2 ) ",
                    "[2.2]", " [2.2]", " [ 2.2]", "[2.2] ", "[2.2 ] ", " [ 2.2 ] ",):
            field = NArrayField(required=False)
            val = field.clean(val)
            assert val == [2.2] 
        
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
        assert field.clean("0:1:10") == [0,1,2,3,4,5,6,7,8,9,10]
        assert field.clean("0:1:10.001") == [0,1,2,3,4,5,6,7,8,9,10]
        assert field.clean("0:1:9.999999999999999") == [0,1,2,3,4,5,6,7,8,9,10]
        # now test with last val not sufficienlty close:
        assert field.clean("0:1:9.99999999999999") == [0,1,2,3,4,5,6,7,8,9]
        # another test with more digits:
        try:
            assert field.clean("[0.274:0.137:0.959]") == [0.274, .411, .548, .685, .822, .959]
        except AssertionError:
            # what?!! oh yes, rounding errors, so:
            assert np.allclose(field.clean("[0.274:0.137:0.959]"),
                               [0.274, .411, .548, .685, .822, .959], rtol=validation.RTOL,
                               atol=validation.ATOL)
            
            
        # test colons, commas and spaces
        assert field.clean("0:1:9.999999999999999") == [0,1,2,3,4,5,6,7,8,9,10]
        for val in ("[0.274:0.137:0.959 5 6.67]", "0.274:0.137:0.959 5  6.67",
                    "0.274 : 0.137 : 0.959, 5 6.67", "0.274 : 0.137 : 0.959, 5,6.67"):
            field = NArrayField(required=False)
            val = field.clean(val)
            np.allclose(val, [0.274, .411, .548, .685, .822, .959, 5, 6.67], rtol=validation.RTOL,
                               atol=validation.ATOL) 
        
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()