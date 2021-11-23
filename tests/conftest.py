"""
Basic conftest.py defining fixtures to be accessed during tests

Created on 3 May 2018

@author: riccardo
"""

import os
import shutil
from io import StringIO, BytesIO
from os.path import isdir

import pytest
from pytest_django import fixtures as pytest_django_fixtures
import yaml
import numpy as np
from django.core.management import call_command
from django.test.client import Client

from egsim.core.utils import yaml_load, get_dbnames
from egsim.core.utils import querystring
import json
from egsim.forms.fields import GmdbField


# https://docs.pytest.org/en/3.0.0/parametrize.html#basic-pytest-generate-tests-example


# make all test functions having 'db' in their argument use the passed databases
def pytest_generate_tests(metafunc):
    '''This function is called before generating all tests and parametrizes
    all tests with the argument 'client' (which is a fixture defined below)'''
    # note August 2019: There is apparently no need to run the test twice
    # with two different USER AGENTs. We leave the code below and return:
    return
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
    """This fixture allows to *deeply* compare python numbers, lists, dicts,
    numpy arrays for equality. Numeric arrays can be compared, when found,
    using numpy's `allclose`. str and bytes are not considered equal
    (b"whatever" != "whatever")
    """
    class Comparator:

        def __call__(self, obj1, obj2, rtol=1e-05, atol=1e-08, equal_nan=True):
            if obj1 == obj2:
                return True

            # if any of the two is str, return False:
            s_b = (str, bytes)
            if isinstance(obj1, s_b) or isinstance(obj2, s_b):
                return False

            # from now on, if they are iterables they are lists, tuples etc
            # but not strings:
            both_iter = hasattr(obj1, '__iter__') + hasattr(obj2, '__iter__')

            # if both are not iterable, they might be numbers, try
            # with numpy:
            if both_iter == 0:
                try:
                    if np.allclose([obj1], [obj2], rtol=rtol, atol=atol,
                                   equal_nan=equal_nan):
                        return True
                except:  #noqa
                    pass

            # now, if not both are iterables, return False:
            if both_iter < 2:
                return False

            # both obj1 and obj2 are iterables and not strings
            isdic1, isdic2 = isinstance(obj1, dict), isinstance(obj2, dict)
            if isdic1 != isdic2:
                return False
            if isdic1:  # also obj2 is dict
                # convert dicts to a list of their values, sorted according
                skeys1, skeys2 = sorted(obj1.keys()), sorted(obj2.keys())
                if skeys1 != skeys2:
                    return False
                # convert to lists where each element having the same key
                # has the same position:
                obj1 = [obj1[k] for k in skeys1]
                obj2 = [obj2[k] for k in skeys2]
            else:  # obj1 and obj2 are iterables (not dict), convert to lists:
                obj1, obj2 = list(obj1), list(obj2)

            if len(obj1) != len(obj2):
                return False
            if obj1 != obj2:
                allclose = np.allclose  # @UndefinedVariable
                try:
                    if allclose(obj1, obj2, rtol=rtol, atol=atol,
                                equal_nan=equal_nan):
                        return True
                except (TypeError, ValueError):
                    pass
                    # TypeError means they are not numbers,
                    # so compare one by one below
                except:  # @IgnorePep8 pylint: disable=bare-except
                    return False
                    # any other exception raises False: objects are not equal

                # now try to comnpare equality of each element in obj1
                # with any element of obj2. The for loop takes into account
                # that their element do not need to be equal element-wise
                # (e.g. [1, 'a'] and ['a', 1] are equal)
                while obj1:
                    item1 = obj1.pop(0)
                    for i, item2 in enumerate(obj2):
                        if self.__call__(item1, item2, rtol=rtol, atol=atol,
                                         equal_nan=equal_nan):
                            obj2.pop(i)
                            break
                    else:  # no "break" hit above (i.e. no element found equal)
                        return False

            return True

    return Comparator()


@pytest.fixture(scope="session")
def testdata(request):  # pylint: disable=unused-argument
    """Fixture handling all data to be used for testing. It points to the
    testing 'data' directory allowing to just get files / read file contents
    by file name.
    Pass it as argument to a test function
    ```
        def test_bla(..., data,...)
    ```
    and just use its methods inside the code, e.g,:
    ```
        testdata.path('myfilename')
        testdata.read('myfilename')
    ```
    """
    class Data():
        """class handling common read operations on files in the 'data' folder"""

        def __init__(self, root=None):
            thisdir = os.path.dirname(os.path.abspath(__file__))
            self.root = root or os.path.join(thisdir, 'data')

        def path(self, filename):
            """returns the full path (string) of the given data file name
            :param filename: a string denoting the file name inside the test
                data directory"""
            filepath = os.path.join(self.root, filename)
            # assert os.path.isfile(filepath)
            return filepath

        def read(self, filename, decode=None):
            """reads the data (byte mode, with encoding) and returns it
            :param filename: a string denoting the file name inside the test
                data directory
            """
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
        # delete flatfile subdirectory (no, we do not prompt the user too much
        # work and it's safe he/she deletes the dir in case)
        from egsim.management.commands._egsim_flatfiles import Command as FlatfileCommand
        ff_path = FlatfileCommand.dest_dir()
        if isdir(ff_path):
            shutil.rmtree(ff_path)
        # run command:
        call_command('egsim_init', interactive=False)  # '--noinput')


@pytest.fixture(scope="session")
def mocked_gmdbfield(request, testdata):  # pylint: disable=unused-argument
    """Fixture returning a mock class for the GmdbField.
    """
    def func(tetdata_filename):
        gmdbpath = testdata.path(tetdata_filename)

        class MockedGmdbField(GmdbField):
            '''Mocks GmdbField'''
            _base_choices = {k: gmdbpath for k in get_dbnames(gmdbpath)}

#             def __init__(self, *a, **v):
#                 v['choices'] = [(_, _) for _ in get_dbnames(gmdbpath)]
#                 super(MockedGmdbField, self).__init__(*a, **v)

#             def clean(self, value):
#                 '''Converts the given value (string) into the tuple
#                 hf5 path, database name (both strings)'''
#                 (_, value) = super(MockedGmdbField, self).clean(value)
#                 return (gmdbpath, value)

        return MockedGmdbField()

    return func
