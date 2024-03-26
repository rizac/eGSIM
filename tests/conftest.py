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

# FIXME check which fixtures are still needed. Provide a path?

@pytest.fixture(scope="session", autouse=True)
def auto_create_media_root():
    if not os.path.isdir(settings.MEDIA_ROOT):
        os.makedirs(settings.MEDIA_ROOT)

@pytest.fixture()
def client() -> Client:
    """A Django test client instance. Overwrite default pytest-django fixture with
    the same name to provide a client with enforce_csrf_checks=True.
    This allows to spot when a request would need a csfr token, and fix it by
    adding the CSFR Token it or making the request @csrf_exempt
    For info see:
    https://docs.djangoproject.com/en/stable/ref/csrf/#module-django.views.decorators.csrf
    """
    # skip_if_no_django()

    from django.test.client import Client
    return Client(enforce_csrf_checks=True)


@pytest.fixture(scope="session")
def datadir(request):  # noqa
    thisdir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(thisdir, 'data')


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

