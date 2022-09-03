"""
Basic conftest.py defining fixtures to be accessed during tests

Created on 3 May 2018

@author: riccardo
"""

import os
import shutil
from os.path import isdir, abspath, dirname
import json

import pytest
import yaml
import numpy as np

from django.core.management import call_command
from django.test.client import Client

from datetime import date, datetime
from urllib.parse import quote
from typing import Union, Iterable
from egsim.api.views import QUERY_PARAMS_SAFE_CHARS
from egsim.api.forms.fields import isscalar


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


@pytest.fixture(scope='session')
def django_db_setup(django_db_blocker):
    with django_db_blocker.unblock():
        # delete flatfile subdirectory (no, we do not prompt the user too much
        # work and it's safe he/she deletes the dir in case)
        # from egsim.api.management.commands._egsim_flatfiles import Command as FlatfileCommand
        # ff_path = abspath(FlatfileCommand.dest_dir())
        # if isdir(ff_path) and ff_path.startswith(abspath(dirname(dirname(__file__)))):
        #     shutil.rmtree(ff_path)
        # run command:
        call_command('egsim_init', interactive=False)  # '--noinput')


@pytest.fixture(scope='session')
def querystring():
    """Returns a query string from a given dict and a base_url"""
    return get_querystring


# utility functions for `querystring`:


def get_querystring(query_args: dict, baseurl: str = None):
    """Convert `query_args` to a query string to be used in URLs. It escapes all
    unsafe characters (as defined in `QUERY_PARAMS_SAFE_CHARS`) from
    `query_args` keys (str) and values, which can be any "scalar" type: bool, str,
    date, datetime, numeric, and iterables of those elements (which will be
    converted to comma-separated encoded strings), with the exception of `dict`:
    values of type `dict` are not easily representable and will raise
    `ValueError` in case

    :param query_args: a dictionary of query arguments (strings) mapped to
        their values and to be encoded as "<key>=<value>" portions of the query
        string
    :param baseurl: if provided, it is the base url which will be prefixed in
        the returned url string. It does not matter if it ends or not with a
        '?' character
    """
    baseurl = baseurl or ''
    if baseurl and baseurl[-1:] != '?':
        baseurl += '?'

    return "%s%s" % (baseurl, "&".join("%s=%s" % (key, escape(val))
                                       for key, val in query_args.items()))


def escape(value: Union[bool, None, str, date, datetime, int, float, Iterable]) -> str:
    """Percent-escapes `value` with support for iterables and `None`s

    :param value: bool, str, date, datetime, numeric, `None`s
        (encoded as "null", with no quotes) and any iterables of those elements
        (which will be converted to comma-separated encoded strings), but not
        `dict` (raise ValueError in case)
    """
    if isinstance(value, dict):
        raise ValueError('Can not represent nested dictionaries '
                         'in a query string')
    return quote(tostr(value), safe=QUERY_PARAMS_SAFE_CHARS) \
        if isscalar(value) else \
        ','.join(quote(tostr(_), safe=QUERY_PARAMS_SAFE_CHARS)
                 for _ in value)


def tostr(obj: Union[bool, None, str, date, datetime, int, float], none='null') -> str:
    """Return a string representation of `obj` for injection into URL query
    strings. No character is escaped, use :func:`urllib.parse.quote` or
    :func:`querystring` for that.
    Return `str(obj)` with these exceptions:

    - `obj` is a `datetime.date` or `datetime.datetime`, return its ISO format
      representation, either '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S' or
      '%Y-%m-%dT%H:%M:%S.%f'
    - `obj` is boolean: return 'true' or 'false' (to lower case)
    - `obj` is None, return the `none` argument which defaults to "null"
      (with no leading and trailing quotation character)
    """
    if obj is None:
        return none
    if obj is True or obj is False:
        return str(obj).lower()
    if isinstance(obj, (date, datetime)):
        # note that datetimes are dates. Avoid isinstance, just simpler check:
        is_date = not hasattr(obj, 'hour')  # or seconds, so on
        if is_date or (obj.microsecond == obj.hour == obj.minute == obj.second == 0):
            return obj.strftime('%Y-%m-%d')
        if obj.microsecond == 0:
            return obj.strftime('%Y-%m-%dT%H:%M:%S')
        return obj.strftime('%Y-%m-%dT%H:%M:%S.%f')
    return str(obj)
