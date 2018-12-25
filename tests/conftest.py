'''
Basic conftest.py defining fixtures to be accessed during tests

Created on 3 May 2018

@author: riccardo
'''

import os
from io import StringIO, BytesIO

import pytest
import yaml

import numpy as np

from egsim.core.utils import yaml_load
from egsim.core.utils import querystring
from django.test.client import Client


# https://docs.pytest.org/en/3.0.0/parametrize.html#basic-pytest-generate-tests-example


# make all test functions having 'db' in their argument use the passed databases
def pytest_generate_tests(metafunc):
    '''This function is called before generating all tests and parametrizes all tests with the
    argument 'client' (which is a fixture defined below)'''
    if 'client' in metafunc.fixturenames:
        client_args = [{'HTTP_USER_AGENT': 'Mozilla/5.0'}, {}]
        dburls = [_ for _ in client_args if _]
        ids = ["Django Test Client(%s)" % str(_) for _ in client_args]
        # metafunc.parametrize("db", dburls)
        metafunc.parametrize('client', [Client(**_) for _ in client_args],
                             ids=ids,
                             indirect=True, scope='module')

@pytest.fixture(scope="function")
def comparator(request):
    class Comparator:

        def equal(self, obj1, obj2, rtol=1e-05, atol=1e-08, equal_nan=True):
            if obj1 == obj2:
                return True

            isiter1, isiter2 = hasattr(obj1, '__iter__'), hasattr(obj2, '__iter__')
            # if any of the two is not iterable,
            # or any of the two is string, return False: no other comparison possible
            if isiter1 is False or isiter2 is False or \
                    isinstance(isiter1, str) or isinstance(isiter2, str):
                return False

            # both obj1 and obj2 are iterables and not strings
            if isinstance(obj1, dict):
                if not isinstance(obj2, dict):
                    return False
                keys1, keys2 = sorted(obj1.keys()), sorted(obj2.keys())
                if keys1 != keys2:
                    return False
                obj1 = [obj1[k] for k in keys1]
                obj2 = [obj2[k] for k in keys2]
            else:
                obj1, obj2 = sorted(obj1), sorted(obj2)

            if obj1 != obj2:
                if len(obj1) != len(obj2):
                    return False
                try:
                    if np.allcose(obj1, obj2, rtol=rtol, atol=atol, equal_nan=equal_nan):
                        return True
                except TypeError:
                    pass  # TypeError means they are not numbers, so compare one by one below
                except:  # @IgnorePep8
                    return False  # any other exception raises False: objects are not equal
                for val1, val2 in zip(obj1, obj2):
                    if not self.equal(val1, val2, rtol=rtol, atol=atol, equal_nan=equal_nan):
                        return False
            return True

    return Comparator()


@pytest.fixture(scope="module")
def requesthandler(request):  # pylint: disable=unused-argument
    '''Fixture handling a request.
    It takes the calling modules and rad the 'request.yaml' file into a dict.
    From there, it can return the dict or perform some automated Django utilities
    '''
    class Data:
        '''class handling common read operations on files in the 'data' folder'''

        def __init__(self):
            self.yamlfile = os.path.join(os.path.dirname(request.fspath), 'request.yaml')
            self._dict = yaml_load(self.yamlfile)

        def dict(self, **overrides):
            return dict(self._dict, **overrides)

        def querystr(self, baseurl=None, **overrides):
            return querystring(self.dict(**overrides), baseurl=baseurl)

    return Data()
