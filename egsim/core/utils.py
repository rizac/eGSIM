"""
Created on 29 Jan 2018

@author: riccardo
"""
import inspect
import sys
from os import listdir
from os.path import join, isfile, isdir, abspath, getmtime
from io import StringIO
from typing import Union, Iterable, TextIO, Dict, Tuple
from urllib.parse import quote
from datetime import date, datetime
from yaml import safe_load, YAMLError

from django.conf import settings

from smtk.database_visualiser import DISTANCE_LABEL as SMTK_DISTANCE_LABEL
from smtk.sm_utils import MECHANISM_TYPE


# Copy SMTK_DISTANCE_LABELS replacing the key 'r_x' with 'rx':
DISTANCE_LABEL = dict(
    **{k: v for k, v in SMTK_DISTANCE_LABEL.items() if k != 'r_x'},
    rx=SMTK_DISTANCE_LABEL['r_x']
)


class MOF:  # noqa
    # simple class emulating an Enum
    RES = 'res'
    LH = 'lh'
    LLH = "llh"
    MLLH = "mllh"
    EDR = "edr"


# Set the non-encoded characters. Sources:
# https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/encodeURIComponent#Description
# NOTE THAT THE LAST 5 CHARACTERS ARE NOT SAFE
# ACCORDING TO RFC 3986 EVEN THOUGH THESE CHARACTERS HAVE NOT FORMALIZED
# URI DELIMITING USE. WE MIGHT APPEND [:-5] to QUERY_PARAMS_SAFE_CHARS BUT
# WE SHOULD CHANGE THEN ALSO encodeURIComponent in the javascript files, to
# make it consistent
QUERY_PARAMS_SAFE_CHARS = "-_.~!*'()"


def querystring(query_args: dict, baseurl: str = None):
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
        if isinstance(obj, date) or (obj.microsecond == obj.hour ==
                                     obj.minute == obj.second == 0):
            return obj.strftime('%Y-%m-%d')
        if obj.microsecond == 0:
            return obj.strftime('%Y-%m-%dT%H:%M:%S')
        return obj.strftime('%Y-%m-%dT%H:%M:%S.%f')
    return str(obj)


def yaml_load(obj: Union[str, TextIO, dict]) -> dict:
    """Safely load the YAML-formatted object `obj` into a dict and returns
    that dict. Note that being YAML a superset of json, all properly
    json-formatted strings are also correctly loaded and the quote character
    ' is also allowed (in pure json, only " is allowed).

    :param obj: (dict, stream, string denoting an existing file path, or
        string denoting the file content in YAML syntax): If stream (i.e.,
        an object with the `read` attribute), uses it for reading and parsing
        its content into dict. If dict, this method is no-op and the dict is
        returned, if string denoting an existing file, a stream is opened
        from the file and processed as explained above (the stream will be
        closed in this case). If string, the string is treated as YAML
        content and parsed: in this case, the output must be a dict otherwise
        a YAMLError is thrown

    :raises: YAMLError
    """
    if isinstance(obj, dict):
        return obj

    close_stream = False
    if isinstance(obj, str):
        close_stream = True
        if isfile(obj):  # file input
            stream = open(obj, 'r')
        else:
            stream = StringIO(obj)  # YAML content input
    elif not hasattr(obj, 'read'):
        # raise a general message meaningful for a Rest framework:
        raise YAMLError('Invalid input, expected data as string in YAML or '
                        'JSON syntax, found %s' % str(obj.__class__.__name__))
    else:
        stream = obj

    try:
        ret = safe_load(stream)
        # for some weird reason, in case of a string ret is the string itself,
        # and no error is raised. Let's do it here:
        if not isinstance(ret, dict):
            if isinstance(obj, (str, bytes)):
                raise YAMLError('The given string input is neither a valid '
                                'YAML content nor the path of an existing '
                                'YAML file')
            raise YAMLError('Unable to load input (%s) as YAML'
                            % str(obj.__class__.__name__))
        return ret
    finally:
        if close_stream:
            stream.close()


def vectorize(value):
    """Return `value` if it is already an iterable, otherwise `[value]`.
    Note that :class:`str` and :class:`bytes` are considered scalars:
    ```
        vectorize(3) = vectorize([3]) = [3]
        vectorize('a') = vectorize(['a']) = ['a']
    ```
    """
    return [value] if isscalar(value) else value


def isscalar(value):
    """Return True if `value` is a scalar object, i.e. a :class:`str`, a
    :class:`bytes` or without the attribute '__iter__'. Example:
    ```
        isscalar(1) == isscalar('a') == True
        isscalar([1]) == isscalar(['a']) == False
    ```
    """
    return not hasattr(value, '__iter__') or isinstance(value, (str, bytes))

