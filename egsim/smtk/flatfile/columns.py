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
    site = 'Site parameter'
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
    return {c_name for c_name, c_props in load_from_yaml().items()
            if c_props.get('type', None) == ColumnType.rupture}


def get_intensity_measures() -> set[str]:
    """Return a set of strings with all column names denoting an intensity
    measure name, with no arguments, e.g., "PGA", "SA" (not "SA(...)").
    """
    return {c_name for c_name, c_props in load_from_yaml().items()
            if c_props.get('type', None) == ColumnType.intensity}


def get_type(column: str) -> Union[ColumnType, None]:
    """Return the ColumnType of the given column name, or None"""
    return load_from_yaml().get(column, {}).get('type', None)


def get_all_names_of(column: str) -> tuple[str]:
    """Return all possible names of the given column, as tuple set of strings
    where the first element is assured to be the flatfile default column name
    (primary name) and all remaining the secondary names. The tuple will be composed
    of `column` alone if `column` does not have registered aliases
    """
    # `aliases` should be populated with at least `col_name` (see _harmonize_props),
    # but for safety:
    return load_from_yaml().get(column, {}).get('aliases', (column,))


def get_dtypes_and_defaults() -> \
        tuple[dict[str, Union[ColumnDtype, pd.CategoricalDtype]], dict[str, Any]]:
    """Return the column data types and defaults. Dict keys are all columns names
     (including aliases) mapped to their data type or default. Columns with no data
     type or default are not present.
    """
    _dtype, _default = {}, {}
    for c_name, props in load_from_yaml().items():
        if 'dtype' in props:
            _dtype[c_name] = props['dtype']
        if 'default' in props:
            _default[c_name] = props['default']
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
    _cols = {}
    with open(_ff_metadata_path) as fpt:
        for col_name, props in yaml_load(fpt, SafeLoader).items():
            props = _harmonize_props(props)
            # makes aliases sorted with col_name the primary name:
            props['aliases'] = (col_name,) + props['aliases']
            # add all aliases mapped to the relative properties:
            for c_name in props['aliases']:
                _cols[c_name] = props
    if cache:
        _columns = _cols
    return _cols


def _harmonize_props(props:dict):
    """harmonize the values of a column property dict"""
    aliases = props.get('alias', [])
    if isinstance(aliases, str):
        aliases = [aliases]
    props['aliases'] = set(aliases)  # set -> remove duplicate aliases
    # props['help'] = props.get('help', '')
    props['type'] = ColumnType[props['type']] if 'type' in props else None
    props['dtype'] = cast_dtype(props['dtype']) if 'dtype' in props else None
    if 'default' in props:
        props['default'] = cast_value(props['default'], props['dtype'] )
    for k in ("<", "<=", ">", ">="):
        if k in props:
            props[k] = cast_value(props[k], props['dtype'] )
    return props


def cast_dtype(dtype: Union[Collection, str, pd.CategoricalDtype, ColumnDtype]) \
        -> Union[ColumnDtype, pd.CategoricalDtype]:
    """Return a value from the given argument that is suitable to be used as data type in
    pandas, i.e., either a `ColumnDtype` (str-like enum) or a pandas `CategoricalDtype`
    """
    try:
        if isinstance(dtype, ColumnDtype):
            return dtype
        if isinstance(dtype, str):
            if dtype == 'category':  # infer categories from data
                dtype = pd.CategoricalDtype() # see below
            else:
                try:
                    return ColumnDtype[dtype]  # try enum name (raise KeyError)
                except KeyError:
                    return ColumnDtype(dtype)  # try enum value (raises ValueError)
        if isinstance(dtype, (list, tuple)):
            dtype = pd.CategoricalDtype(dtype)
        if isinstance(dtype, pd.CategoricalDtype):
            # CategoricalDtype with no categories or categories=None (<=> infer
            # categories from data) needs no check. Otherwise, check that the categories
            # are *all* of the same supported dtype:
            if dtype.categories is None or \
                    ColumnDtype.of(*dtype.categories) is not None:
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
            sorted_names = get_all_names_of(name)
            suffix_str = repr(sorted_names[0])
            if len(sorted_names) > 1:
                suffix_str += f" (or {', '.join(repr(_) for _ in sorted_names[1:])})"
            _names.append(suffix_str)
        return _names


class ConflictingColumns(InvalidColumn):

    def __init__(self, name1, name2, *other_names):
        InvalidColumn.__init__(self, name1, name2, *other_names,
                               sep=" vs. ", plural_suffix='')


class InvalidDataInColumn(InvalidColumn, ValueError, TypeError):
    pass


class InvalidColumnName(InvalidColumn):
    pass
