"""
module containing all column metadata information stored in the associated
YAML file
"""
from datetime import datetime, date
from enum import Enum
from os.path import join, dirname

from typing import Union, Any, Iterable

# try to speed up yaml.safe_load (https://pyyaml.org/wiki/PyYAMLDocumentation):
from yaml import load as yaml_load

try:
    from yaml import CSafeLoader as default_yaml_loader  # faster, if available
except ImportError:
    from yaml import SafeLoader as default_yaml_loader  # same as using yaml.safe_load

import numpy as np
import pandas as pd


class ColumnType(Enum):
    """Flatfile column type"""
    rupture = 'Rupture parameter'
    sites = 'Sites parameter'
    distance = 'Distance measure'
    intensity = 'Intensity measure'


class ColumnDtype(Enum):
    """Flatfile column data type. Names are used as dtype values in
    the YAML file (note that categorical dtypes have to be given as list),
    enum values are the relative Python/numpy classes to be used in Python code.
    E.g., to get if the dtype of flatfile column `c` (pandas Series) is supported:
    ```
    isinstance(c.dtype, pd.CategoricalDtype) or \
         any(issubclass(c.dtype.type, e.value) for e in ColumnDtype)
    ```
    """
    # NOTE: the FIRST VALUE MUST BE THE PYTHON TYPE (e.g. int, not np.int64), AS
    # IT WILL BE USED TO CHECK THE CONSISTENCY OF DEFAULT / BOUNDS IN THE YAML
    float = float, np.floating
    int = int, np.integer
    bool = bool, np.bool_
    datetime = datetime, np.datetime64
    str = str, np.str_, np.object_


def get_rupture_param_columns() -> set[str]:
    """Return a set of strings with all column names (including aliases)
    denoting a rupture parameter
    """
    rup = set()
    _extract_from_columns(load_from_yaml(), rupture_params=rup)
    return rup


def get_intensity_measure_columns() -> set[str]:
    """Return a set of strings with all column names
    denoting an intensity measure. Sa, if given, is returned without period
    """
    imts = set()
    _extract_from_columns(load_from_yaml(), imts=imts)
    return imts


# Column name and aliases, mapped to all their aliases
# The dict values will always include at least the column name itself:
_alias: dict[str, set[str]] = None  # noqa


def get_column_names(column, sort=False) -> Union[set[str], list[str]]:
    """Return all possible names of the given column, as set of strings. If sort is
    True, a list is returned where the first element is the primary column name (one of
    the top-level keys defined in the YAML dict)
    """
    global _alias
    if _alias is None:
        _alias = {}
        _extract_from_columns(load_from_yaml(), alias=_alias)
    names = _alias.get(column, set())
    if not sort:
        return names
    else:
        return [n for n in names if n in _columns] + \
               [n for n in names if n in _columns]


def get_dtypes_and_defaults() -> \
        tuple[dict[str, Union[str, pd.CategoricalDtype]], dict[str, Any]]:
    """Return the column data types and defaults. Dict keys are all columns names
     (including aliases) mapped to their data type or default. Columns with no data
     type or default are not present.
    """
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
        _cols = yaml_load(fpt, default_yaml_loader)
    if cache:
        _columns = _cols
    return _cols


def _extract_from_columns(columns: dict[str, dict[str, Any]], *,
                          rupture_params:set[str]=None,
                          sites_params: set[str] = None,
                          distances: set[str] = None,
                          imts: set[str] = None,
                          dtype:dict[str, Union[str, pd.CategoricalDtype]]=None,
                          alias:dict[str, set[str]]=None,
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
        (aliases included) mapped to their aliases. E.g., a column that can take N
        additional names will have N+1 entries, all of them mapped to same the set of
        N+1 names. All columns will be present: if a column has no alias, it will be
        mapped to itself (1-element set).
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
                dtype[name] = props['dtype']
                if isinstance(dtype[name], (list, tuple)):
                    dtype[name] = pd.CategoricalDtype(dtype[name])
            if default is not None and 'default' in props:
                default[name] = _upcast(props['default'], props['dtype'])
            if bounds is not None:
                _bounds = {k: _upcast(props[k], props['dtype'])
                           for k in ["<", "<=", ">", ">="]
                           if k in props}
                if _bounds:
                    bounds[name] = _bounds
            if help is not None and props.get('help', ''):
                help[name] = props['help']


def _upcast(val, dtype):
    """allow for some dtypes in certain cases"""
    if dtype == ColumnDtype.float.name and isinstance(val, int):
        return float(val)
    elif dtype == ColumnDtype.datetime.name and isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    return val
