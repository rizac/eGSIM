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
from itertools import chain
from yaml import safe_load, YAMLError
import tables

from django.conf import settings
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import IMT
from openquake.hazardlib.const import TRT
from smtk.sm_table import get_dbnames, GMTableDescription, records_where
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


def get_gmdb_path():
    """Return the path to the directory housing all eGSIM Ground Motion
    Databases (HDF5 files)"""
    return join(settings.MEDIA_ROOT, 'gmdb')


def get_gmdb_names(fpath, sort_by_mtime=True):
    """Return a dict of Ground motion database names mapped to the relative
    HDF5 file path (absolute)

    :param sort_by_mtime: boolean (default True), self explanatory: each
        gmdb will be returned in the dict from oldest to newest
    """
    gmdbases = []  # first use a list of tuples (to easily sort them if needed)
    for fle in listdir(fpath) if isdir(fpath) else []:
        flepath = abspath(join(fpath, fle))
        try:
            # note that in egsim we will never write more than one gmdb per
            # HDF (but let's keep compatibility with smtk implementation):
            gmdbases.extend((k, flepath) for k in get_dbnames(flepath))
        except:  # @IgnorePep8 pylint: disable=bare-except
            pass
    if sort_by_mtime:
        gmdbases = sorted(gmdbases, key=lambda _: getmtime(_[1]))
    return dict(gmdbases)


def test_selexpr(selexpr: str):
    """tests the given selection expression on an in-memory hdf5 file that
    will be closed. Raises in case of failure"""
    # create an in-memory file with no save upon close:
    # https://www.pytables.org/cookbook/inmemory_hdf5_files.html#backing-store
    h5file = None
    try:
        h5file = tables.open_file("new_sample.h5", "w", driver="H5FD_CORE",
                                  driver_core_backing_store=0)
        # create a group:
        group = h5file.create_group("/", 'test_group')
        # create a new table
        # https://www.pytables.org/usersguide/tutorials.html#creating-a-new-table
        table = h5file.create_table(group, 'test_table',
                                    description=dict(GMTableDescription))
        # append a table row (made of nans):
        row = table.row
        row.append()  # pylint: disable=no-member
        table.flush()

        # execute sel expression. Remember to wrap into list otherwise it is
        # not run (a generator is returned). Use limit=1 to skip useless
        # iterations:
        list(records_where(table, selexpr, limit=1))
    finally:
        if h5file is not None:
            h5file.close()


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


class OQ:  # FIXME: get rid of this right? WE have the db for this
    """container class for OpenQuake entities"""

    SUPPORTED_IMT_NAMES = ('PGA', 'PGV', 'SA', 'PGD', 'IA', 'CAV')

    # Type hinting below are enclosed in quotes to still help the reader while
    # avoiding several imports (e.g. IMT, GMPE, typing.Dict. Note that at least
    # `dict[str, str]` should be valid without quotes from Python 3.9+)

    @classmethod
    def trts(cls) -> "dict[str, str]":
        """Returns a (new) dictionary of:
        att_name (string) mapped to its att_value (string)
        defining all Tectonic Region Types defined in OpenQuake
        """
        return {a: getattr(TRT, a) for a in dir(TRT)
                if a[:1] != '_' and isinstance(getattr(TRT, a), str)}

    @classmethod
    def imts(cls) -> "dict[str, IMT]":
        """Returns a (new) dictionary of:
        imt_name (string) mapped to its imt_class (class object)
        defining all Intensity Measure Types defined in OpenQuake
        """
        return {_: IMT(_) for _ in cls.SUPPORTED_IMT_NAMES}

    @classmethod
    def gsims(cls) -> "dict[str, GMPE]":
        """Returns a (new) dict of:
        gsim_name (string) mapped to its gsim_class (class object)
        defining all Ground Shaking Intensity Models defined in OpenQuake.
        The dict is sorted by gsim_name
        """
        return get_available_gsims()  # already returns a new dict

    @classmethod
    def required_attrs(cls, gsim) -> "Iterable[str]":
        """Returns an iterable yielding all the required attributes (strings)
        from the given Gsim (either string denoting the Gsim name, or class
        instance)"""
        gsim_class = cls.gsims()[gsim] if isinstance(gsim, str) else gsim
        return chain(*[getattr(gsim_class, _) for _ in dir(gsim_class)
                       if _.startswith('REQUIRES_')])


# dict mapping the REQUIRES_* attributes defined on each Gsim of `OpenQuake`
# to the columns of a GMTable (:class:`smtk.sm_table.GMTableDescription`).
# This mapping is used to enhance any selection expression by adding to the
# expression the column(s) that need to be available (see `egsim.core.smtk`).
# If OpenQuake will be upgraded, some Gsims might have one or more
# REQUIRES_* attribute not implemented here: the 'initdb' command takes care
# to issue a WARNING in case: if this happens, consult smtk maintainers and
# write the new attribute as string key mapped to the tuple:
# (column_name, missing value).
# Both tuple elements are strings. If the first element is empty, the attribute
# does not have a mapping with any GMTable column. If the second element
# is empty, there is no missing value available for the given column
GSIM_REQUIRED_ATTRS = {  # FIXME: get rid of this, we have a json file we load with the init command
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
    # ignore (it is handled within the smtk code):
    'width': ('rupture_width', '')
}


def get_classes(module_name: str,
                class_or_tuple: Union[type, Tuple[type]] = None,
                ignore_imported_classes: bool = True) -> Dict[str, type]:
    """Return all class(es) in a given module, matching the given criteria.
    The returned object is a `dict[str, class]`, where values are the given
    classes keyed by their name.

    :param module_name: (str) the module name, usually accessible through the
        variable `__name__`
    :param class_or_tuple: (type/class or tuple of types/classes) return only
        classes that are the same as, or a subclass of any of the given
        class(es). See builtin function `issubclass` for details.
        None (the default when missing) means: no filter (take all classes)
    :param ignore_imported_classes: bool (default True): return only those
        classes directly implemented in the module, and not imported from some
        other module
    """
    def _filter(obj):
        return _is_class(obj, module_name if ignore_imported_classes else None,
                         class_or_tuple)
    return {cls_name: cls for (cls_name, cls) in
            inspect.getmembers(sys.modules[module_name], _filter)}


def _is_class(obj, module_name: str = None,
              class_or_tuple: Union[type, Tuple[type]] = None):
    if inspect.isclass(obj):
        if module_name is None or obj.__module__ == module_name:
            if class_or_tuple is None or issubclass(obj, class_or_tuple):
                return True
    return False
