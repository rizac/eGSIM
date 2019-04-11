'''
Created on 29 Jan 2018

@author: riccardo
'''
from os import listdir
from os.path import join, dirname, isdir, isfile
from io import StringIO
from urllib.parse import quote
from datetime import date, datetime
from dateutil import parser as dateparser
from dateutil.tz import tzutc

from yaml import safe_load, YAMLError
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import registry as hazardlib_imt_registry
from openquake.hazardlib.const import TRT
from smtk import load_database


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
# https://en.wikipedia.org/wiki/Query_string#URL_encoding
# (using the latter as ref here, although all links actually say something different).
# Letters (A–Z and a–z), numbers (0–9) and the characters "*-.?,:_" are left as they are
# (unencoded)
# Remember that eGSIM special characters might be '&|><=!' (for gmdb selection),
# '*?[~]' (for parameters accepting wildcards) and ':' (numeric range separator
# and time separator)
QUERY_PARAMS_SAFE_CHARS = "*-.?,:_"


def querystring(dic, baseurl=None):
    '''Converts dic to a query string to be used in URLs. It escapes all unsafe
    characters (as defined in `QUERY_PARAMS_SAFE_CHARS`) and converts lists to comma-
    separated encoded strings

    :param dic: a dictionary of values, as returned e.g., from JSON or YAML
        parsed content. The dictionary CAN NOT have nested dictionaries, as they
        can not be represented in a URL query string
    :param baseurl: if provided, it is the base url which will be prefixed in the
        returned url string. It does not matter if it ends or not with a '?' character
    '''

    def escape(value):
        '''escapes a scalar or array'''
        if isinstance(value, dict):
            raise ValueError('Can not represent nested dicts in a query string')
        return quote(tostr(value), safe=QUERY_PARAMS_SAFE_CHARS) if isscalar(value) else \
            ','.join(quote(tostr(_), safe=QUERY_PARAMS_SAFE_CHARS) for _ in value)

    baseurl = baseurl or ''
    if baseurl and baseurl[-1:] != '?':
        baseurl += '?'

    return "%s%s" % (baseurl,
                     "&".join("%s=%s" % (key, escape(val)) for key, val in dic.items()))


def yaml_load(obj):
    '''Safely loads the YAML-formatted object `obj` into a dict. Note that being YAML a superset
    of json, all properly json-formatted strings are also correctly loaded and the quote
    character ' is also allowed (in pure json, only " is allowed).

    :param obj: (dict, stream, string denoting an existing file path, or string denoting
        the file content in YAML syntax): If stream (i.e., an object with the `read` attribute),
        uses it for reading and parsing its content into dict. If dict, this method is no-op
        and the dict is returned, if string denoting an existing file, a stream is opened
        from the file and processed as explained above (the stream will be closed in this case).
        If string, the string is treated as YAML content and parsed: in this case, the output
        must be a dict otherwise a YAMLError is thrown

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
        # raise a general message meaningful for a Rest framework and a web app:
        raise YAMLError('Invalid input, expected data as string in YAML or JSON syntax, '
                        'found %s' % str(obj.__class__.__name__))
    else:
        stream = obj

    try:
        ret = safe_load(stream)
        # for some weird reason, in case of a string ret is the string itself, and no error
        # is raised. Let's do it here:
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
    '''Returns value if it is an iterable, otherwise [value]. This method is primarily called from
    request/responses parameters where strings are considered scalars, i.e. not iterables
    (although they are in Python). Thus `vectorize('abc') = ['abc']` '''
    return [value] if isscalar(value) else value


def isscalar(value):
    '''Returns True if value is a scalr object, i.e. not having the attribute '__iter__'
    Note that strings and bytes are the only exceptions as they are considered scalars
    '''
    return not hasattr(value, '__iter__') or isinstance(value, (str, bytes))


def apply_if_input_notnone(func):
    '''function acting as decorator returning None if the input is None, otherwise calling
    func(input). Example: _convert(float)('5.5')
    '''
    def wrapper(string):
        '''wrapping function'''
        if not string or string is None:
            return None
        return func(string)
    return wrapper


def strptime(obj):
    """
        Converts `obj` to a `datetime` object **in UTC without tzinfo**.
        If `obj` is string, creates a `datetime` object by parsing it. If `obj`
        is not a date-time object, raises TypeError. Otherwise, uses `obj` as `datetime` object.
        Then, if the datetime object has a tzinfo supplied, converts it to UTC and removes the
        tzinfo attribute. Finally, returns the datetime object
        Implementation details: `datetime.strptime`does not keep time zone information in the
        parsed date-time, nor it recognizes 'Z' as 'UTC' (raises instead). The library `dateutil`,
        on the other hand, is too permissive and has too many false "positives"
        (e.g. integers or strings such as  '5-7' are succesfully parsed into date-time).
        We choose `dateutil` as the code is shorter, cleaner, and a single hack is needed:
        we simply check, after a string `obj` is succesfully parsed into `dtime`, that `obj`
        contains at least the string `dtime.strftime(format='%Y-%m-%d')` (such as e,g,
        '2006-01-31')

        The opposite can be obtained with :function:`tostr`

        :param obj: `datetime` object or string in ISO format (see examples below)
        :return: a datetime object in UTC, with the tzinfo removed
        :raise: TypeError or ValueError
        :Example. These are all equivalent:
        ```
            strptime("2016-06-01T00:00:00.000000Z")
            strptime("2016-06-01T00.01.00CET")
            strptime("2016-06-01 00:00:00.000000Z")
            strptime("2016-06-01 00:00:00.000000")
            strptime("2016-06-01 00:00:00")
            strptime("2016-06-01 00:00:00Z")
            strptime("2016-06-01")
            This raises ValueError:
            strptime("2016-06-01Z")
            This raises TypeError:
            strptime(45.5)
        ```
    """
    dtime = obj
    if isinstance(obj, str):
        try:
            dtime = dateparser.parse(obj, fuzzy=False, fuzzy_with_tokens=False)
            # now, dateperser is quite hacky on purpose, guessing too much.
            # datetime.strptime, on the other hand, does not parse Z as UTC (raises in case)
            # and does not include the timezone in the parsed date. The best (hacky) solution
            # is to assert the bare minimum: that %Y-%m-%d is in dtime:
            assert obj.strip().startswith(dtime.strftime('%Y-%m-%d'))
        except Exception as exc:
            raise ValueError(str(exc))

    if not isinstance(dtime, datetime):
        raise TypeError('string or datetime required, found %s' % str(type(obj)))

    if dtime.tzinfo is not None:
        # if a time zone is specified, convert to utc and remove the timezone
        dtime = dtime.astimezone(tzutc()).replace(tzinfo=None)

    # the datetime has no timezone provided AND is in UTC:
    return dtime


class EGSIM:  # For metaclasses (not used anymore): https://stackoverflow.com/a/6798042
    '''Namespace container for Openquake related data used in this program'''
#     aval_gsims, aval_imts, aval_trts = _get_data()
#     _trmodels = None  # dict of names mapped to a geojson colleciton (will be lazily created)
    _gmdbs = {}  # ground motion databases: name (str) -> [file_path, ground motion db obj

    @classmethod
    def gmdb_names(cls):
        if not cls._gmdbs:
            # FIXME: hardcoded, change it!
            root = join(dirname(dirname(dirname(__file__))),
                        'tmp', 'data', 'flatfiles', 'output')
            cls._gmdbs = {f: [join(root, f), None] for f in listdir(root)
                          if isdir(join(root, f))}
        return list(cls._gmdbs.keys())

    @classmethod
    def gmdb(cls, name):
        '''Returns a GroundMotionDatabase from the given file name (not path, just the name)'''
        entry = cls._gmdbs[name]
        if entry[1] is None:
            entry[1] = load_database(entry[0])
        return entry[1]


class OQ:

    @classmethod
    def trts(cls):
        '''Returns a (new) dictionary of:
            att_name (string) mapped to its att_value (string)
            defining all Tectonic Region Types defined in OpenQuake
        '''
        return {a: getattr(TRT, a) for a in dir(TRT)
                if a[:1] != '_' and isinstance(getattr(TRT, a), str)}
#         for attname in dir(TRT):
#             if attname[:1] != '_' and isinstance(getattr(TRT, attname), str):
#                 yield attname, getattr(TRT, attname)

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
        return get_available_gsims().items()

# class TextResponseCreator:
# 
#     def __init__(self, data, horizontal=True, delimiter=';'):
#         self.data = data
#         self.horizontal = horizontal
#         self.delimiter = delimiter
# 
#     def to_string_matrix(self, data):
#         '''Abstract-like method to be implemented in subclasses
# 
#         :return: a list of sub-lists, where each sub-list is a list of
#         strings representing a row to be printed to the csv. The orientation
#         (horizontal vs vertical) will be handled in the __str__ method'''
#         raise NotImplementedError()
# 
#     @staticmethod
#     def scalar2str(value):
#         if value is None:
#             return ''
#         if isinstance(value, str):
#             return value
#         if isinstance(value, bytes):
#             return value.decode('utf8')
#         try:
#             if np.isnan(value):
#                 return ''
#         except TypeError:
#             pass
#         return str(value)
# 
#     def __str__(self):
#         fileobj = StringIO()
#         data2print = self.to_string_matrx(self.data)
#         if not self.horizontal:
#             data2print = zip(*data2print)
# 
#         csv_writer = csv.writer(fileobj, delimiter=self.delimiter,
#                                 quotechar='"',
#                                 quoting=csv.QUOTE_MINIMAL)
#         for row in data2print:
#             csv_writer.writerow([self.scalar2str(r) for r in row])
#         ret = fileobj.getvalue()
#         fileobj.close()
#         return ret
# 
# 
# class TrellisTextResponseCreator(TextResponseCreator):
# 
#     def to_string_matrx(self, data):
#         figures = data['figures']
#         gsims = None
# 
#         def_header_fields = ['gsim:', 'magnitude:', 'distance:', 'vs30:']
#         if len(figures) > 0:
#             yield def_header_fields +\
#                 [''] * (1 + len(data['xvalues']))
# 
#             yield [''] * len(def_header_fields) + [data['xlabel']] + data['xvalues']
# 
#             if gsims is None:
#                 gsims = sorted(figures[0]['yvalues'].keys())
# 
#             for gsim in gsims:
#                 for fig in figures:
#                     yvalues = fig['yvalues'].get(gsim, None)
#                     if yvalues is not None:
#                         mag, dist, vs30 = fig['magnitude'], fig['distance'], fig['vs30']
#                         yield [gsim, mag, dist, vs30, fig['ylabel']] + yvalues
