'''
Created on 29 Jan 2018

@author: riccardo
'''
from os import listdir
from os.path import join, dirname, isdir, splitext, isfile
import warnings
import json
from io import StringIO
from urllib.parse import quote
from collections import OrderedDict
from datetime import datetime
from dateutil import parser as dateparser
from dateutil.tz import tzutc

from yaml import safe_load, YAMLError
import numpy as np
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import registry as hazardlib_imt_registry
from openquake.hazardlib.const import TRT
from openquake.hazardlib import imt

from smtk import load_database
import csv
from contextlib import contextmanager


def tostr(object, none='null'):
    '''Returns str(object) with these exceptions:
    - if object is a datetime, returns its ISO format representation, either
    '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S' or '%Y-%m-%dT%H:%M:%S.%f'
    - if object is boolean returns 'true' or 'false' (to lower case)
    - if object is None, returns the `none` argument (defaults to 'null')
    '''
    if object is None:
        return none
    elif object is True or object is False:
        return str(object).lower()
    elif isinstance(object, datetime):
        if object.microsecond == 0:
            if object.hour == object.minute == object.second == 0:
                return object.strftime('%Y-%m-%d')
            return object.strftime('%Y-%m-%dT%H:%M:%S')
        return object.strftime('%Y-%m-%dT%H:%M:%S.%f')
    else:
        return str(object)


# From https://en.wikipedia.org/wiki/Query_string#URL_encoding:
# Letters (A–Z and a–z), numbers (0–9) and the characters '*','-','.' and '_' are left as-is
# Moreover, for query parameter other set of characters are permitted
# (see https://stackoverflow.com/a/2375597). Among those, '*' and '?' (which EGSIM might
# interpret as wildcards), ',' (interpreted as array separator) and ':' (numeric range separator
# and time separator). If other characters have to be added in the future, first check
# the latter link (and in case the RFC 3896 spec). For the moment, the safe characters for a
# query string in eGSIM are:
QUERY_PARAMS_SAFE_CHARS = "*-.?,:_"


def querystring(dic, baseurl=None):
    '''Converts dic to a query string to be used in URLs'''

    def escape(value):
        '''escapes a scalar or array'''
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


class Egsim:
    '''simple container object for a gsim: attributes are the gsim name (string),
    its intensity measure types (frozenset) and the tectonic region type (string)
    '''
    def __init__(self, name, imts, trt):
        '''Initializes a new Egsim
        :param name: string, name of the gsim
        :param imts: iterable of strings denoting the gsim intensoty measure types
        :pram trt: string, tectonic region type defined for the gsim
        '''
        self.name = name
        self.imts = frozenset(imts)
        self.trt = trt

    def __str__(self):
        return self.name

    def asjson(self):
        '''Converts this object as a json-serializable tuple of strings:
        (gsim, imts, tectonic_region_type) where the first and last arguments
        are strings, and the second is a list of strings'''
        return self.name, list(self.imts), self.trt

    # the two methods below are not used but make this class behave the same as the gsim name
    # (string) in sets and dicts. Note that we have to implement both __hash__ (used first) and
    # __eq__ (used as check in case hashes are the same). this way, called e=Egsim('bla',...),
    # both the statements are True: `'bla' in set([e])` and `e in {'bla': None}`
    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name.__eq__(other)


def _get_data():
    '''Returns a tuple of three elements:
    1) all openquake-available gsim data in an Ordered dict keyed with the gsim
        names mapped to a Egsim object
    2) all openquake available imts used by the gsims, with no repetitions (list of strings)
    3) all openquake available tectonic region types used by the gsims,
        with no repetitions (dictionary of the openquake class attributes, lower case, mapped
        to their string value. Basically, each key is the same as each value but lowercase and
        with spaces replaced by the underscore)
    '''

    _aval_imts = OrderedDict()  # this should be a set of strings, but we want it ordered ...

    def sanitycheck(imt_objs):
        '''filters out the elements of `imt_obj` which require additional
           argument (except SA, which is fine) because we do not know how to deal with them,
           and populates the keys of _aval_imts representing all imts passed here, with no
           repetitions'''
        for imt_obj in imt_objs:
            imt_s = imt_obj.__name__
            if imt_s not in _aval_imts:
                imt_v = hazardlib_imt_registry.get(imt_s, None)
                if imt_v is None:
                    continue
                if imt_v != imt.SA:  # test we di not need arguments if imt is not SA
                    try:
                        # this creates an instance of the class. If the instance needs argument,
                        # it fails (except below)
                        imt.from_string(imt_s)
                    except:  # @IgnorePep8 pylint: disable=bare-except
                        continue
                _aval_imts[imt_s] = None  # whatever value is fine, None is just the one chosen ...
            yield imt_s

    # get all TRTs: use the TRT class of openquake and get all attributes without a leading
    # underscore and mapped to a string:
    _aval_trts = {getattr(TRT, a).replace(' ', '_').lower(): getattr(TRT, a)
                  for a in dir(TRT) if a[:1] != '_' and isinstance(getattr(TRT, a), str)}

    # inverse the _aval_trts above, and set for each Egsim the TRT stripped with spaces
    # and lower case:
    _trt_i = {v: k for k, v in _aval_trts.items()}

    # get all gsims:
    _aval_gsims = OrderedDict()
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        for key, gsim in get_available_gsims().items():
            try:
                gsim_inst = gsim()
            except (TypeError, OSError, NotImplementedError) as exc:
                gsim_inst = gsim
            try:
                gsim_imts = gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES
            except AttributeError:
                continue
            if gsim_imts and hasattr(gsim_imts, '__iter__'):
                trt = _trt_i.get(gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE, '')
                _aval_gsims[key] = Egsim(key, (_ for _ in sanitycheck(gsim_imts)), trt)

    return _aval_gsims, tuple(_aval_imts.keys()), _aval_trts


def _convert(func):
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
    aval_gsims, aval_imts, aval_trts = _get_data()
    _trmodels = None  # dict of names mapped to a geojson colleciton (will be lazily created)
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

    @classmethod
    def trmodels(cls):
        '''Returns a list of all available tectonic region model names (string)'''

        def loadjson(filepath):
            '''loads json from file'''
            with open(filepath) as fpt:  # https://stackoverflow.com/a/14870531
                return json.load(fpt)

        if not cls._trmodels:
            # FIXME: hardcoded, change it!
            root = join(dirname(dirname(__file__)), 'data')
            cls._trmodels = {splitext(f)[0]: loadjson(join(root, f)) for f in listdir(root)
                             if splitext(f)[1].lower() == '.json'}
        return cls._trmodels


class TextResponseCreator:

    def __init__(self, data, horizontal=True, delimiter=';'):
        self.data = data
        self.horizontal = horizontal
        self.delimiter = delimiter

    def to_string_matrix(self, data):
        '''Abstract-like method to be implemented in subclasses

        :return: a list of sub-lists, where each sub-list is a list of
        strings representing a row to be printed to the csv. The orientation
        (horizontal vs vertical) will be handled in the __str__ method'''
        raise NotImplementedError()

    @staticmethod
    def scalar2str(value):
        if value is None:
            return ''
        if isinstance(value, str):
            return value
        if isinstance(value, bytes):
            return value.decode('utf8')
        try:
            if np.isnan(value):
                return ''
        except TypeError:
            pass
        return str(value)

    def __str__(self):
        fileobj = StringIO()
        data2print = self.to_string_matrx(self.data)
        if not self.horizontal:
            data2print = zip(*data2print)

        csv_writer = csv.writer(fileobj, delimiter=self.delimiter,
                                quotechar='"',
                                quoting=csv.QUOTE_MINIMAL)
        for row in data2print:
            csv_writer.writerow([self.scalar2str(r) for r in row])
        ret = fileobj.getvalue()
        fileobj.close()
        return ret


class TrellisTextResponseCreator(TextResponseCreator):

    def to_string_matrx(self, data):
        figures = data['figures']
        gsims = None

        def_header_fields = ['gsim:', 'magnitude:', 'distance:', 'vs30:']
        if len(figures) > 0:
            yield def_header_fields +\
                [''] * (1 + len(data['xvalues']))

            yield [''] * len(def_header_fields) + [data['xlabel']] + data['xvalues']

            if gsims is None:
                gsims = sorted(figures[0]['yvalues'].keys())

            for gsim in gsims:
                for fig in figures:
                    yvalues = fig['yvalues'].get(gsim, None)
                    if yvalues is not None:
                        mag, dist, vs30 = fig['magnitude'], fig['distance'], fig['vs30']
                        yield [gsim, mag, dist, vs30, fig['ylabel']] + yvalues
