'''
Created on 16 Feb 2018

@author: riccardo
'''
from egsim.core.utils import vectorize

def test_vectorize():
    '''tests the vectorize function'''
    for arg in (None, '', 'abc', 1, 1.4005, True):
        expected = [arg]
        assert vectorize(arg) == expected
        assert vectorize(expected) is expected
    args = ([1, 2, 3], range(5), (1 for _ in [1, 2, 3]))
    for arg in args:
        assert vectorize(arg) is arg

