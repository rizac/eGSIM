'''
Basic conftest.py defining fixtures to be accessed during tests

Created on 3 May 2018

@author: riccardo
'''

import os
from io import StringIO, BytesIO

import pytest
from pytest_django import fixtures as pytest_django_fixtures
import yaml
import numpy as np
from django.core.management import call_command
from django.test.client import Client

from egsim.core.utils import yaml_load
from egsim.core.utils import querystring
import json
from egsim.models import Trt


# https://docs.pytest.org/en/3.0.0/parametrize.html#basic-pytest-generate-tests-example


# make all test functions having 'db' in their argument use the passed databases
def pytest_generate_tests(metafunc):
    '''This function is called before generating all tests and parametrizes all tests with the
    argument 'client' (which is a fixture defined below)'''
    if 'client' in metafunc.fixturenames:
        client_args = [{'HTTP_USER_AGENT': 'Mozilla/5.0'}, {}]
        # dburls = [_ for _ in client_args if _]
        ids = ["Django Test Client(%s)" % str(_) for _ in client_args]
        # metafunc.parametrize("db", dburls)
        metafunc.parametrize('client', [Client(**_) for _ in client_args],
                             ids=ids,
                             indirect=True, scope='module')


@pytest.fixture(scope="function")
def areequal(request):
    '''This fixture allows to deeply compare two objects for equality, allowing
    numeric arrays (including nested ones) to be compared as for numpy's
    `allclose`'''
    class Comparator:

        def __call__(self, obj1, obj2, rtol=1e-05, atol=1e-08, equal_nan=True):
            if obj1 == obj2:
                return True

            isiter1, isiter2 = \
                hasattr(obj1, '__iter__'), hasattr(obj2, '__iter__')
            # if any of the two is not iterable, or any of the two is string,
            # return False: no other comparison possible
            if any(_ is False for _ in [isiter1, isiter2]) \
                    or any(isinstance(_, (str, bytes)) for _ in [obj1, obj2]):
                return False

            # both obj1 and obj2 are iterables and not strings
            if isinstance(obj1, dict):
                # convert dicts to a list of their values, sorted according
                # to their keys (which must be equal)
                if not isinstance(obj2, dict):
                    return False
                keys1, keys2 = sorted(obj1.keys()), sorted(obj2.keys())
                if keys1 != keys2:
                    return False
                obj1 = [obj1[k] for k in keys1]
                obj2 = [obj2[k] for k in keys2]
            else:
                # FIXME: what if obj1 and obj2 are lists of (unsortable) dicts?
                obj1, obj2 = sorted(obj1), sorted(obj2)

            if obj1 != obj2:
                if len(obj1) != len(obj2):
                    return False
                allclose = np.allclose  # @UndefinedVariable
                try:
                    if allclose(obj1, obj2, rtol=rtol, atol=atol,
                                equal_nan=equal_nan):
                        return True
                except TypeError:
                    pass
                    # TypeError means they are not numbers,
                    # so compare one by one below
                except:  # @IgnorePep8 pylint: disable=bare-except
                    return False
                    # any other exception raises False: objects are not equal
                for val1, val2 in zip(obj1, obj2):
                    if not self.__call__(val1, val2, rtol=rtol, atol=atol,
                                         equal_nan=equal_nan):
                        return False
            return True

    return Comparator()


@pytest.fixture(scope="session")
def testdata(request):  # pylint: disable=unused-argument
    '''Fixture handling all data to be used for testing. It points to the testing 'data' folder
    allowing to just get files / read file contents by file name.
    Pass it as argument to a test function
    ```
        def test_bla(..., data,...)
    ```
    and just use its methods inside the code, e.g,:
    ```
        testdata.path('myfilename')
        testdata.read('myfilename')
    ```
    '''
    class Data():
        '''class handling common read operations on files in the 'data' folder'''

        def __init__(self, root=None):
            self.root = root or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

        def path(self, filename):
            '''returns the full path (string) of the given data file name
            :param filename: a string denoting the file name inside the test data directory'''
            filepath = os.path.join(self.root, filename)
            # assert os.path.isfile(filepath)
            return filepath

        def read(self, filename, decode=None):
            '''reads the data (byte mode, with encoding) and returns it
            :param filename: a string denoting the file name inside the test data directory
            '''
            with open(self.path(filename), 'rb') as opn:
                return opn.read().decode(decode) if decode else opn.read()

        def readjson(self, filename):
            with open(self.path(filename), 'r') as opn:
                return json.load(opn)
        
        def readyaml(self, filename):
            return yaml_load(self.path(filename))

    return Data()


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command('initdb')
