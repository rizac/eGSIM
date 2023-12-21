"""
Basic conftest.py defining fixtures to be accessed during tests

Created on 3 May 2018

@author: riccardo
"""

import os
import json

import pytest
import yaml
import numpy as np

from django.core.management import call_command
from django.test.client import Client
from django.conf import settings


@pytest.fixture(scope="session", autouse=True)
def auto_create_media_root():
    if not os.path.isdir(settings.MEDIA_ROOT):
        os.makedirs(settings.MEDIA_ROOT)

@pytest.fixture()
def client() -> Client:
    """A Django test client instance. Overwrite default pytest-django foxture with
    the same name to provide a client with enforce_csrf_checks=True.
    This allows to spot when a request would need a csfr token, and fix it by
    adding the CSFR Token it or making the request @csrf_exempt
    For info see:
    https://docs.djangoproject.com/en/stable/ref/csrf/#module-django.views.decorators.csrf
    """
    # skip_if_no_django()

    from django.test.client import Client
    return Client(enforce_csrf_checks=True)


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

                # now try to compare equality of each element in obj1
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
def testdata(request):  # noqa
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

        def open(self, filename, mode='rb'):
            return open(self.path(filename), mode)

        def read(self, filename, mode='rb', *, decode=None):
            """reads the data (byte mode, with encoding) and returns it
            :param filename: a string denoting the file name inside the test
                data directory
            """
            with self.open(filename, mode) as opn:
                _ = opn.read()
                if not decode:
                    return _
                return _.decode(decode)  # noqa

        def readjson(self, filename):
            with open(self.path(filename), 'r') as opn:
                return json.load(opn)

        def readyaml(self, filename):
            with open(self.path(filename)) as _:
                return yaml.safe_load(_)

    return Data()


@pytest.mark.django_db
@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):  # noqa
    """Set up the database and populates it with eGSIM data. This fixture is
    called whenever we decorate a test function with `@pytest.mark.django_db`.
    For info see:

     - https://pytest-django.readthedocs.io/en/latest/database.html#populate-the-test-database-if-you-don-t-use-transactional-or-live-server
     - https://pytest-django.readthedocs.io/en/latest/helpers.html#pytest.mark.django_db

    @param django_db_setup: "parent" fixture that ensures that the test databases are 
        created and available (see `pytest_django.fixtures.django_db_setup` for details. 
        Being a pytest fixture, do not treat it as "unused argument" and remove it)
    @param django_db_blocker: fixture used in the code to write custom data on the db
    """ # noqa
    with django_db_blocker.unblock():
        call_command('egsim_init', interactive=False)

