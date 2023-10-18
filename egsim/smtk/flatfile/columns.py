"""
flatfile columns functions. see associated YAML file for info
"""
from __future__ import annotations

import re
from datetime import datetime, date
from enum import Enum, ReprEnum
from os.path import join, dirname
from typing import Union, Any
from collections.abc import Collection

import numpy as np
import pandas as pd
from pandas.core.arrays import PandasArray
from pandas.core.dtypes.base import ExtensionDtype
# try to speed up yaml.safe_load (https://pyyaml.org/wiki/PyYAMLDocumentation):
from yaml import load as yaml_load
try:
    from yaml import CSafeLoader as SafeLoader  # faster, if available
except ImportError:
    from yaml import SafeLoader  # same as using yaml.safe_load


class ColumnType(Enum):
    """Flatfile column type"""
    rupture = 'Rupture parameter'
    sites = 'Sites parameter'
    distance = 'Distance measure'
    intensity = 'Intensity measure'


class ColumnDtype(str, ReprEnum):
    """Enum where members are also strings representing supported data types for
    flatfile columns. E.g.: `pd_series.astype(ColumnDtype.datetime)`. Use the class
    method `ColumnDtype.of` to get the ColumnDType corresponding to any given Python
    / numpy/ pandas object or type
    """
    def __new__(cls, value, *py_types:type):
        """Constructs a new ColumnDtype member"""
        # subclassing StrEnum does not work, so we copy from StreEnum.__new__:
        member = str.__new__(cls, value)
        member._value_ = value
        member.py_types = tuple(py_types)
        return member

    # each member below must be mapped to the numpy name (see `numpy.sctypeDict.keys()`
    # for a list of supported names. Exception is 'string' that is pandas only) and
    # one or more Python classes that will be used
    # to get if an object (Python, numpy or pandas) is instance of a particular
    # `ColumnDtype` (see `ColumnDtype.of`)

    float = "float",  float, np.floating
    int = "int", int, np.integer
    bool = "bool", bool, np.bool_
    datetime = "datetime64", datetime, np.datetime64
    str = "string", str, np.str_  # , np.object_

    @classmethod
    def of(cls, *item: Union[int, float, datetime, bool, str,
                           np.array, pd.Series, PandasArray,
                           type[int, float, datetime, bool, str],
                           np.dtype, ExtensionDtype]) -> Union[ColumnDtype, None]:
        """Return the ColumnDtype of the given argument, or None if no associated
        dtype is found.
        If several arguments are passed, return None also if the arguments are
        not all the same dtype

        :param item: one or more Python objects, such as object instance (e.g. 4.5),
            object class (`float`), a numpy array, pandas Series / Array, a numpy dtype,
            pandas ExtensionDtype (e.g., as returned from a pandas dataframe
            `dataframe[column].dtype`).
        """
        ret_type = None
        for obj in item:
            if isinstance(obj, (pd.Series, np.ndarray, PandasArray)):
                obj = obj.dtype  # will fall back in the next "if"
            if isinstance(obj, (np.dtype, ExtensionDtype)):
                obj = obj.type  # will NOT fall back into the next "if"
            if not isinstance(obj, type):
                obj = type(obj)
            for c_dtype in cls:
                if issubclass(obj, c_dtype.py_types):  # noqa
                    # bool is a subclass of int in Python, so:
                    if c_dtype == ColumnDtype.int and \
                            issubclass(obj, ColumnDtype.bool.py_types):
                        c_dtype = ColumnDtype.bool
                    if ret_type is None:
                        ret_type = c_dtype
                    elif ret_type != c_dtype:
                        return None
                    break
            else:
                return None
        return ret_type


def get_rupture_params() -> set[str]:
    """Return a set of strings with all column names (including aliases)
    denoting a rupture parameter
    """
    rup = set()
    _extract_from_columns(load_from_yaml(), rupture_params=rup)
    return rup


def get_intensity_measures() -> set[str]:
    """Return a set of strings with all column names
    denoting an intensity measure. Sa, if given, is returned without period
    """
    imts = set()
    _extract_from_columns(load_from_yaml(), imts=imts)
    return imts


# Column name and aliases, mapped to all their aliases
# The dict values will always include at least the column name itself:
_alias: dict[str, frozenset[str]] = None  # noqa


def get_all_names_of(column, ordered=False) -> Union[frozenset[str], list[str]]:
    """Return all possible names of the given column, as set of strings (if ordered is
    False, the default). If ordered is True, a list is returned where the first element
    is assured to be the flatfile default column name (primary name) and all remaining
    the secondary names. The set/list will be empty if `column` does not denote a
    flatfile column
    """
    global _alias
    if _alias is None:
        _alias = {}
        _extract_from_columns(load_from_yaml(), alias=_alias)
    all_names = _alias.get(column, frozenset())
    if not ordered:
        return all_names
    # re-order putting the primary name in the 1st position:
    all_names = list(all_names)
    for i in range(len(all_names)):
        if all_names[i] in _columns:
            if i > 0:
                all_names.insert(0, all_names.pop(i))
            break
    return all_names


_dtype: dict[str, Union[ColumnDtype, pd.CategoricalDtype]] = None  # noqa
_default: dict[str, Any] = None  # noqa


def get_dtypes_and_defaults() -> \
        tuple[dict[str, Union[ColumnDtype, pd.CategoricalDtype]], dict[str, Any]]:
    """Return the column data types and defaults. Dict keys are all columns names
     (including aliases) mapped to their data type or default. Columns with no data
     type or default are not present.
    """
    global _dtype, _default
    if _dtype is None or _default is None:
        _dtype, _default = {}, {}
        _extract_from_columns(load_from_yaml(), dtype=_dtype, default=_default)
    return _dtype, _default



# YAML file path:
_ff_metadata_path = join(dirname(__file__), 'columns.yaml')
# cache storage of the data in the YAML:
_columns: dict[str, dict[str, Any]] = None  # noqa


def load_from_yaml(cache=True) -> dict[str, dict[str, Any]]:
    """Loads the content of the associated YAML file with all columns
    information and returns it as Python dict

    :param cache: if True, a cache version will be returned (faster, but remember
        that any change to the cached version will persist permanently!). Otherwise,
        a new dict loaded from file (slower) will be returned
    """
    global _columns
    if cache and _columns:
        return _columns
    with open(_ff_metadata_path) as fpt:
        _cols = yaml_load(fpt, SafeLoader)
    if cache:
        _columns = _cols
    return _cols


def _extract_from_columns(columns: dict[str, dict[str, Any]], *,
                          rupture_params:set[str]=None,
                          sites_params: set[str] = None,
                          distances: set[str] = None,
                          imts: set[str] = None,
                          dtype:dict[str, Union[str, pd.CategoricalDtype]]=None,
                          alias:dict[str, frozenset[str]]=None,
                          default:dict[str, Any]=None,
                          bounds:dict[str, dict[str, Any]]=None,
                          help:dict=None):
    """Extract data from `columns` (the metadata stored in the YAML file)
     and put it into the passed function arguments that are not missing / None.

    :param rupture_params: set or None. If set, it will be populated with all flatfile
        columns (aliases included) that denote an OpenQuake rupture parameter
    :param sites_params: set or None. If set, it will be populated with all flatfile
        columns (aliases included) that denote an OpenQuake sites parameter
    :param distances: set or None. If set, it will be populated with all flatfile
        columns (aliases included) that denote an OpenQuake distance measure
    :param imts: set or None. If set, it will be populated with all flatfile
        columns (aliases included) that denote an OpenQuake intensity parameter
    :param dtype: dict or None. If dict, it will be populated with all flatfile columns
         (aliases included) mapped to their data type (a name of an item of
        the enum :ref:`ColumnDtype` - or pandas `CategoricalDtype`). Columns with no
        data type will not be present
    :param alias: dict or None. If dict, it will be populated with all flatfile columns
        (aliases included) mapped to their aliases. A column with N aliases will be
        mapped to a set of N+1 names (if N=0, the column will be mapped to itself).
    :param default: dict or None. If dict, it will be populated with all flatfile
        columns (aliases included) mapped to their default, if defined. Columns with no
        default will not be present
    :param bounds: dict or None, of dict, it will be populated with all flatfile
        columns (aliases included) mapped to a dict with keys "<=", "<" ">=", ">" mapped
        in turn to a value consistent with the column dtype. Columns with no bounds
        will not be present
    :param help: dict or None, if dict, it will be populated with all flatfile columns
        (aliases included) mapped to their description. Columns with no help will not be
        present
    """
    check_type = rupture_params is not None or sites_params is not None \
                 or distances is not None or imts is not None
    for c_name, props in columns.items():
        aliases = props.get('alias', [])
        if isinstance(aliases, str):
            aliases = {aliases}
        else:
            aliases = set(aliases)
        aliases.add(c_name)
        aliases = frozenset(aliases)
        _dtype = None  # cache value, see below
        for name in aliases:
            if check_type and 'type' in props:
                ctype = ColumnType[props['type']]
                if rupture_params is not None and ctype == ColumnType.rupture:
                    rupture_params.add(name)
                if sites_params is not None and ctype == ColumnType.sites:
                    sites_params.add(name)
                if distances is not None and ctype == ColumnType.distance:
                    distances.add(name)
                if imts is not None and ctype == ColumnType.intensity:
                    imts.add(name)
            if alias is not None:
                alias[name] = aliases
            if dtype is not None and 'dtype' in props:
                dtype[name] = _dtype = cast_dtype(props['dtype'])
            if default is not None and 'default' in props:
                default[name] = props['default'] if dtype is None else \
                    cast_value(props['default'], _dtype)
            if bounds is not None:
                keys = [k for k in ["<", "<=", ">", ">="] if k in props]
                if keys:
                    bounds[name] = {}
                    for k in keys:
                        bounds[name][k] = props[k] if _dtype is None else \
                            cast_value(props[k], _dtype)
            if help is not None and props.get('help', ''):
                help[name] = props['help']


def cast_dtype(dtype: Union[Collection, str, pd.CategoricalDtype, ColumnDtype]) \
        -> Union[ColumnDtype, pd.CategoricalDtype]:
    """Return a value from the given argument that is suitable to be used as data type in
    pandas, i.e., either a `ColumnDtype` (str-like enum) or a pandas `CategoricalDtype`
    """
    try:
        if isinstance(dtype, ColumnDtype):
            return dtype
        if isinstance(dtype, str):
            try:
                return ColumnDtype[dtype]  # try enum name (raise KeyError)
            except KeyError:
                return ColumnDtype(dtype)  # try enum value (raises ValueError)
        if isinstance(dtype, (list, tuple)):
            dtype = pd.CategoricalDtype(dtype)
        if isinstance(dtype, pd.CategoricalDtype):
            # check that the categories are *all* of the same supported data type:
            if ColumnDtype.of(*dtype.categories) is not None:
                return dtype
    except (KeyError, ValueError, TypeError):
        pass
    raise ValueError(f'Invalid data type: {str(dtype)}')


def cast_value(val: Any, dtype: Union[ColumnDtype, pd.CategoricalDtype]) -> Any:
    """Cast the given value to the given dtype, raise ValueError if unsuccessful

    :param val: any Python object
    :param dtype: either a `ColumnDtype` or pandas `CategoricalDtype` object.
        See `cast_dtype` for details
    """
    if dtype is None:
        raise ValueError(f'Invalid dtype: {str(dtype)}')
    if isinstance(dtype, pd.CategoricalDtype):
        if val in dtype.categories:
            return val
        dtype_name = 'categorical'
    else:
        actual_dtype = ColumnDtype.of(val)
        if actual_dtype == dtype:
            return val
        if dtype == ColumnDtype.float and actual_dtype == ColumnDtype.int:
            return float(val)
        elif dtype == ColumnDtype.datetime and isinstance(val, date):
            return datetime(val.year, val.month, val.day)
        dtype_name = dtype.name
    raise ValueError(f'Invalid value for type {dtype_name}: {str(val)}')


# Exceptions:

class InvalidColumn(Exception):
    """
    General flatfile column(s) error. See subclasses for details
    """
    def __init__(self, *names, sep=', ', plural_suffix='s'):
        super().__init__(*names)
        self._sep = sep
        self._plural_suffix = plural_suffix

    @property
    def names(self):
        """return the names (usually column names) raising this Exception
        and passed in `__init__`"""
        return [repr(_) for _ in self.args]

    def __str__(self):
        """Make `str(self)` more clear"""
        # get prefix (e.g. 'Missing column(s)'):
        prefix = self.__class__.__name__
        # replace upper cases with space + lower case letter
        prefix = re.sub("([A-Z])", " \\1", prefix).strip().capitalize()
        names = self.names
        if len(names) != 1:
            prefix += self._plural_suffix
        # return full string:
        return f"{prefix} {self._sep.join(names)}"

    def __repr__(self):
        return self.__str__()


class MissingColumn(InvalidColumn, AttributeError, KeyError):
    """MissingColumnError. It inherits also from AttributeError and
    KeyError to be compliant with pandas and OpenQuake"""

    @property
    def names(self):
        """return the names with their alias(es), if any"""
        _names = []
        for name in self.args:
            sorted_names = self.get_all_names_of(name)
            suffix_str = repr(sorted_names[0])
            if len(sorted_names) > 1:
                suffix_str += f" (or {', '.join(repr(_) for _ in sorted_names[1:])})"
            _names.append(suffix_str)
        return _names

    @classmethod
    def get_all_names_of(cls, col_name) -> list[str]:
        """Return a list of all column names of the argument, with the first element
        being the flatfile primary name. Returns `[col_name]` if the argument does not
        denote any flatfile column"""
        names = get_all_names_of(col_name, True)
        if len(names) <= 1:
            return [col_name]
        return names


class ConflictingColumns(InvalidColumn):

    def __init__(self, name1, name2, *other_names):
        InvalidColumn.__init__(self, name1, name2, *other_names,
                               sep=" vs. ", plural_suffix='')


class InvalidDataInColumn(InvalidColumn, ValueError, TypeError):
    pass


class InvalidColumnName(InvalidColumn):
    pass
