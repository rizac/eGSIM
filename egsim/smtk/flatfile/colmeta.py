"""module container of all column metadata information stored in the associated
YAML file"""
from datetime import datetime
from enum import Enum
from os.path import join, dirname

from typing import Union, Any

import yaml
import numpy as np
import pandas as pd


class ColumnType(Enum):
    """Flatfile column type"""
    rupture_param = 'Rupture parameter'
    sites_param = 'Sites parameter'
    distance = 'Distance measure'
    imt = 'Intensity measure'
    unknown = 'Unknown'


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


# global variables (populated at module first import - see code below):
# the set of column names (top level keys of the YAML file):
names: set[str] = set()
# Column names and alies denoting rupture params:
rupture_params: set[str] = set()
# Column names and aliases denoting sites params:
sites_params: set[str] = set()
# Column names and aliases denoting distances:
distances: set[str] = set()
# Column names denoting intensity measures:
imts: set[str] = set()
# Column names and aliases, mapped to their dtype:
dtype: dict[str, Union[str, pd.CategoricalDtype]] = {}
# Column names and aliases, mapped to their default:
default: dict[str, Any] = {}  # flatfile column -> default value when missing
# Column name and aliases, mapped to the set of all possible column aliases
# (the set will always include at least the column name itself):
alias: dict[str, set[str]] = {} # every column name -> its aliases
# Required column names (each item in the list is a set of all possible aliases for a
# column. The set will always include at least the column name itself):
required: list[set[str]] = []


_ff_metadata_path = join(dirname(__file__), 'colmeta.yaml')


def read_column_metadata(*, names:set[str],
                         rupture_params:set[str]=None,
                         sites_params: set[str] = None,
                         distances: set[str] = None,
                         imts: set[str] = None,
                         dtype:dict[str, Union[str, pd.CategoricalDtype]]=None,
                         alias:dict[str, set[str]]=None,
                         default:dict[str, Any]=None,
                         required:list[set[str]]=None,
                         bounds:dict[str, dict[str, Any]]=None,
                         help:dict=None):
    """Put columns metadata stored in the YAML file into the passed function arguments.

    :param names: set or None. If set, it will be populated with the names of
        the flatfile columns registered in the YAML, aliases excluded
    :param dtype: dict or None. If dict, it will be populated with the flatfile columns
        and aliases (keys) which have a defined data type ( a name of an item of
        the enum :ref:`ColumnDtype` - or pandas `CategoricalDtype`)
    :param alias: dict or None. If dict, it will be populated with the flatfile column
        and aliases (keys) mapped to the set of all aliases. The set contains at least
        the associated key
    :param default: dict or None. If dict, it will be populated with the
        flatfile columns and aliases (keys) mapped to their default, if defined
    :param required: list or None. If list, it will contain all required columns in
        form of sets, where each set contains a column names (name + aliases)
    """
    with open(_ff_metadata_path) as fpt:
        types = {
            'r': ColumnType.rupture_param,
            's': ColumnType.sites_param,
            'i': ColumnType.imt,
            'd': ColumnType.distance
        }
        for c_name, props in yaml.load(fpt, yaml.BaseLoader).items():
            if names is not None:
                names.add(c_name)
            aliases = props.get('alias', [])
            if isinstance(aliases, str):
                aliases = {aliases}
            else:
                aliases = set(aliases)
            aliases.add(c_name)
            if required is not None and props.get('required', False):
                required.append(aliases)
            for name in aliases:
                if 'type' in props:
                    ctype = types[props['type']]
                    if rupture_params is not None and \
                            ctype == ColumnType.rupture_param:
                        rupture_params.add(name)
                    if sites_params is not None and \
                            ctype == ColumnType.sites_param:
                        sites_params.add(name)
                    if distances is not None and \
                            ctype == ColumnType.distance:
                        distances.add(name)
                    if imts is not None and \
                            ctype == ColumnType.imt:
                        imts.add(name)
                if alias is not None:
                    alias[name] = aliases
                if dtype is not None and 'dtype' in props:
                    dtype[name] = props['dtype']
                    if isinstance(dtype[name], (list, tuple)):
                        dtype[name] = pd.CategoricalDtype(dtype[name])
                if default is not None and 'default' in props:
                    default[name] = props['default']
                if bounds is not None:
                    _bounds = {k: props[k] for k in ["<", "<=", ">", ">="]
                               if k in props}
                    if _bounds:
                        bounds[name] = _bounds
                if help is not None and props.get('help', ''):
                    help[name] = props['help']


# initialize the above class with data from the YAMl file:
read_column_metadata(names=names,
                     rupture_params=rupture_params,
                     sites_params=sites_params,
                     distances=distances,
                     imts=imts,
                     dtype=dtype,
                     alias=alias,
                     required=required,
                     default=default)
