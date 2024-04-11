"""
Basic conftest.py defining Django fixtures to be accessed during tests.

Created on 3 May 2018

@author: riccardo
"""
import shutil

import os

import pytest

from django.core.management import call_command
from django.test.client import Client


@pytest.fixture(scope="session", autouse=True)
def create_and_set_tmp_media_root():
    from django.conf import settings
    data_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    assert os.path.isdir(os.path.dirname(data_root))
    media_root = os.path.join(data_root, 'tmp')
    # Note: for safety, "tmp/" should be git-ignored (even though we remove it at
    # the end of the tests, see below)
    if not os.path.isdir(media_root):
        os.makedirs(media_root)
    settings.MEDIA_ROOT = media_root
    yield  # makes all test work with the created media folder
    shutil.rmtree(media_root)  # remove the folder at the end of all tests


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

