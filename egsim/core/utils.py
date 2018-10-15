'''
Created on 29 Jan 2018

@author: riccardo
'''
from os import listdir
from os.path import join, dirname, isdir, splitext
import warnings
import json

from collections import OrderedDict
from datetime import datetime
from dateutil import parser as dateparser
from dateutil.tz import tzutc

from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import registry as hazardlib_imt_registry
from openquake.hazardlib.const import TRT
from openquake.hazardlib import imt

from smtk import load_database


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
    _aval_trts = {a.lower(): getattr(TRT, a) for a in dir(TRT) if a[:1] != '_'
                  and isinstance(getattr(TRT, a), str)}

    # get all gsims:
    _aval_gsims = OrderedDict()
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore')
        for key, gsim in get_available_gsims().items():
            try:
                gsim_inst = gsim()
            except (TypeError, OSError, NotImplementedError) as exc:
                gsim_inst = gsim
            gsim_imts = gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES
            if gsim_imts and hasattr(gsim_imts, '__iter__'):
                _aval_gsims[key] = Egsim(key, (_ for _ in sanitycheck(gsim_imts)),
                                         gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE)

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
        contains at least the string `dtime.strftime(format='%Y-%m-%d')` (such as e,g, '2006-01-31')
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
                             if splitext(f)[1].lower() == '.geojson'}
        return cls._trmodels
