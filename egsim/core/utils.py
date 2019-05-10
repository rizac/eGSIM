'''
Created on 29 Jan 2018

@author: riccardo
'''
from os.path import join, isfile
from io import StringIO
from urllib.parse import quote
from datetime import date, datetime
from itertools import chain

from django.conf import settings
from yaml import safe_load, YAMLError
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import registry as hazardlib_imt_registry
from openquake.hazardlib.const import TRT
from smtk.sm_table import get_dbnames, GMTableDescription
from smtk.database_visualiser import DISTANCE_LABEL as SMTK_DISTANCE_LABEL
from smtk.sm_utils import MECHANISM_TYPE

DISTANCE_LABEL = dict(**{k: v for k, v in SMTK_DISTANCE_LABEL.items()
                         if k != 'r_x'},
                      rx=SMTK_DISTANCE_LABEL['r_x'])


class MOF:  # pylint: disable=missing-docstring, too-few-public-methods
    # simple class emulating an Enum
    RES = 'res'
    LH = 'lh'
    LLH = "llh"
    MLLH = "mllh"
    EDR = "edr"


def tostr(obj, none='null'):
    '''Returns str(obj) to be injected into YAML or JSON variables.

    Consequently, it returns `str(obj)` with these exceptions:
    - if obj is a date or datetime, returns its ISO format representation,
    either '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S' or '%Y-%m-%dT%H:%M:%S.%f'
    - if obj is boolean returns 'true' or 'false' (to lower case)
    - if obj is None, returns the `none` argument (defaults to 'null')
    '''
    if obj is None:
        return none
    if obj is True or obj is False:
        return str(obj).lower()
    if isinstance(obj, (date, datetime)):
        if not isinstance(obj, datetime) \
            or (obj.microsecond == obj.hour ==
                obj.minute == obj.second == 0):
            return obj.strftime('%Y-%m-%d')
        if obj.microsecond == 0:
            return obj.strftime('%Y-%m-%dT%H:%M:%S')
        return obj.strftime('%Y-%m-%dT%H:%M:%S.%f')
    return str(obj)


# Set the non-encoded characters. Sources:
# https://perishablepress.com/stop-using-unsafe-characters-in-urls/
# https://stackoverflow.com/a/2375597
# https://en.wikipedia.org/wiki/Query_string#URL_encoding (using the latter
# as ref here, although all links actually say something different).
# Letters (A–Z and a–z), numbers (0–9) and the characters "*-.?,:_" are left
# as they are (unencoded). Remember that eGSIM special characters might be
# '&|><=!' (for gmdb selection), '*?[~]' (for parameters accepting wildcards)
# and ':' (numeric range separator and time separator)
QUERY_PARAMS_SAFE_CHARS = "*-.?,:_"


def querystring(dic, baseurl=None):
    '''Converts dic to a query string to be used in URLs. It escapes all
    unsafe characters (as defined in `QUERY_PARAMS_SAFE_CHARS`) and converts
    lists to comma- separated encoded strings

    :param dic: a dictionary of values, as returned e.g., from JSON or YAML
        parsed content. The dictionary CAN NOT have nested dictionaries, as
        they can not be represented in a URL query string
    :param baseurl: if provided, it is the base url which will be prefixed in
        the returned url string. It does not matter if it ends or not with a
        '?' character
    '''

    def escape(value):
        '''escapes a scalar or array'''
        if isinstance(value, dict):
            raise ValueError('Can not represent nested dictionaries '
                             'in a query string')
        return quote(tostr(value), safe=QUERY_PARAMS_SAFE_CHARS) \
            if isscalar(value) else \
            ','.join(quote(tostr(_), safe=QUERY_PARAMS_SAFE_CHARS)
                     for _ in value)

    baseurl = baseurl or ''
    if baseurl and baseurl[-1:] != '?':
        baseurl += '?'

    return "%s%s" % (baseurl, "&".join("%s=%s" % (key, escape(val))
                                       for key, val in dic.items()))


def yaml_load(obj):
    '''Safely loads the YAML-formatted object `obj` into a dict. Note that
    being YAML a superset of json, all properly json-formatted strings are
    also correctly loaded and the quote character ' is also allowed (in pure
    json, only " is allowed).

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
    '''
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
            raise YAMLError('Output should be dict, got %s (input: %s)'
                            % (ret.__class__.__name__, obj.__class__.__name__))
        return ret
    except YAMLError as _:
        raise
    finally:
        if close_stream:
            stream.close()


def vectorize(value):
    '''Returns value if it is an iterable, otherwise [value]. Note that
    strings and bytes sequences (bytes) are considered scalars:
    ```
        vectorize([3]) = vectorize(3) = [3]
        vectorize('a') = vectorize(['a']) = ['a']
    ```
    '''
    return [value] if isscalar(value) else value


def isscalar(value):
    '''Returns True if value is a scalr object, i.e. not having the attribute
    '__iter__' Note that strings and bytes are the only exceptions as they
    are considered scalars: isscalar([1]) = isscalar('a') = True
    '''
    return not hasattr(value, '__iter__') or isinstance(value, (str, bytes))


def get_gmdb_path():
    '''Returns the path to the eGSIM Ground Motion Database'''
    return join(settings.BASE_DIR, 'gmdb.hf5')


def get_gmdb_names(fpath):
    '''Returns the path to each table in the eGSIM Ground Motion Database'''
    if not isfile(fpath):
        return []
    return get_dbnames(fpath)


def get_gmdb_column_desc(as_html=True):
    keys = sorted(GMTableDescription)
    ret = {}
    for key in keys:
        col = GMTableDescription[key]
        classname = col.__class__.__name__
        missingval = ''
        if key == 'event_time':
            type2str = ('date-time (ISO formatted) string: e.g.\n'
                        'event_time <= "2006-08-31"\n'
                        '(date format YYYY-MM-dd), or\n'
                        'event_time <= "2006-08-31T12:50:45"\n'
                        '(date-time format YYYY-MM-ddTHH:MM:SS)')
            missingval = '""'
        elif key == 'style_of_faulting':
            type2str = 'string. Possible values are:\n%s' % \
                '\n'.join('"%s" (%s)' % (str(k), str(v))
                          for k, v in MECHANISM_TYPE.items())
            missingval = '""'
        elif classname.lower().startswith('int'):
            type2str = 'numeric (integer)'
        elif classname.lower().startswith('float'):
            type2str = 'numeric (float)'
            missingval = 'nan'
        elif classname.lower().startswith('bool'):
            type2str = 'bool: true or false'
        elif classname.lower().startswith('str'):
            type2str = 'string'
            missingval = '""'
        else:
            type2str = '? (unkwnown type)'

        if as_html:
            type2str = "<span style='white-space: nowrap'>%s</span>" % \
                type2str.replace('\n', '<br>')
        ret[key] = (type2str, missingval)
    return ret
        

class OQ:
    '''container class for OpenQuake entities'''

    @classmethod
    def trts(cls):
        '''Returns a (new) dictionary of:
            att_name (string) mapped to its att_value (string)
            defining all Tectonic Region Types defined in OpenQuake
        '''
        return {a: getattr(TRT, a) for a in dir(TRT)
                if a[:1] != '_' and isinstance(getattr(TRT, a), str)}

    @classmethod
    def imts(cls):
        '''Returns a (new) dictionary of:
            imt_name (string) mapped to its imt_class (class object)
            defining all Intensity Measure Types defined in OpenQuake
        '''
        return dict(hazardlib_imt_registry)

    @classmethod
    def gsims(cls):
        '''Returns a (new) dict of:
            gsim_name (string) mapped to its gsim_class (class object)
            defining all Ground Shaking Intensity Models defined in OpenQuake.
        '''
        return dict(get_available_gsims())

    @classmethod
    def required_attrs(cls, gsim):
        '''Returns an iterator yielding all the required attributes (strings)
        from the given Gsim (either string denoting the Gsim name, or class
        instance)'''
        gsim_class = cls.gsims()[gsim] if isinstance(gsim, str) else gsim
        return chain(*[getattr(gsim_class, _) for _ in dir(gsim_class)
                     if _.startswith('REQUIRES_')])


# dict mapping the OpenQuake's REQUIRES_* attributes defined on each Gsim,
# and the columns of an smtk GMTable (keys of the :class:`GMTableDescription`
# dict). All attributes available for all Gsims used in eGSIM are here.
# If OpenQuake will be upgraded, the
# 'initdb' command takes care to issue a WARNING for any attribute not
# implemented here. In case, consult smtk maintainers and write the new
# attribute as string key mapped to the tuple: (column_name, missing value).
# Both tuple elements are strings. If the first element is empty, the attribute
# does not have a mapping with any GMTable column. If the second element
# is empty, there is no missing value available for the given column.
# For an example of the application of this dict, see egsim.core.smtk.
GSIM_REQUIRED_ATTRS = {
    # attrs with a mapping to itself:
    'rjb': ('rjb', 'nan'),
    'rhypo': ('rhypo', 'nan'),
    'azimuth': ('azimuth', 'nan'),
    'rrup': ('rrup', 'nan'),
    'ry0': ('ry0', 'nan'),
    'backarc': ('backarc', ''),  # empty => no missing value
    'z2pt5': ('z2pt5', 'nan'),
    'vs30': ('vs30', 'nan'),
    'rx': ('rx', 'nan'),
    'repi': ('repi', 'nan'),
    # attrs with a 1-1 mapping to another name:
    'z1pt0': ('z1', 'nan'),
    'mag': ('magnitude', 'nan'),
    'lat': ('event_latitude', 'nan'),
    'lon': ('event_longitude', 'nan'),
    'vs30measured': ('vs30_measured', ''),  # empty => no missing value
    'hypo_depth': ('hypocenter_depth', 'nan'),
    'ztor': ('depth_top_of_rupture', 'nan'),
    # attrs that we decided to skip from check for various reasons
    # simply put their mapping name to empty. Some of them will be handled
    # the other will use the empty missing val to be skipped
    'rake': ('', 'nan'),
    'dip': ('', 'nan'),
    'strike': ('', 'nan'),
    # ignored (not used in smtk):
    'rvolc': ('', ''),
    'rcdpp': ('', ''),
    'siteclass': ('', ''),
    # it is handled within the smtk code:
    'width': ('rupture_width', '')
}
