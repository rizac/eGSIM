"""
module containing all column metadata information stored in the associated
YAML file
"""
from datetime import datetime, date
from enum import Enum
from os.path import join, dirname

from typing import Union, Any

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


_ff_metadata_path = join(dirname(__file__), 'columns.yaml')


def read_column_metadata(*, names:set[str]=None,
                         rupture_params:set[str]=None,
                         sites_params: set[str] = None,
                         distances: set[str] = None,
                         imts: set[str] = None,
                         dtype:dict[str, Union[str, pd.CategoricalDtype]]=None,
                         alias:dict[str, set[str]]=None,
                         default:dict[str, Any]=None,
                         bounds:dict[str, dict[str, Any]]=None,
                         help:dict=None):
    """Put columns metadata stored in the YAML file into the passed function arguments.

    :param names: set or None. If set, it will be populated with the names of
        the flatfile columns registered in the YAML, aliases excluded
    :param rupture_params: set or None. If set, it will be populated with the flatfile
        columns that denote an OpenQuake rupture parameter
    :param sites_params: set or None. If set, it will be populated with the flatfile
        columns that denote an OpenQuake sites parameter
    :param distances: set or None. If set, it will be populated with the flatfile
        columns that denote an OpenQuake distance measure
    :param imts: set or None. If set, it will be populated with the flatfile
        columns that denote an OpenQuake intensity parameter
    :param dtype: dict or None. If dict, it will be populated with the flatfile columns
        and aliases mapped to their data type (a name of an item of
        the enum :ref:`ColumnDtype` - or pandas `CategoricalDtype`)
    :param alias: dict or None. If dict, it will be populated with the flatfile columns
        and aliases mapped to the set of their aliases. A dict value might be therefore
        keyed by more than one dict key, and contains at least its key
    :param default: dict or None. If dict, it will be populated with the
        flatfile columns and aliases mapped to their default, if defined
    :param bounds: dict or None, of dict, it will be populated with the flatfile
        columns and aliases mapped to a dict with keys "<=", "<" ">=", ">" mapped
        in turn to a value
    :param help: dict or None, if dict, it will be populated with all column names
        and aliases mapped to their description
    """

    def _upcast(val, dtype):
        """allow for some dtypes in certain cases"""
        if dtype == ColumnDtype.float.name and isinstance(val, int):
            return float(val)
        elif dtype == ColumnDtype.datetime.name and isinstance(val, date):
            return datetime(val.year, val.month, val.day)
        return val

    with open(_ff_metadata_path) as fpt:
        types = {
            'r': ColumnType.rupture_param,
            's': ColumnType.sites_param,
            'i': ColumnType.imt,
            'd': ColumnType.distance
        }
        for c_name, props in yaml_load(fpt, default_yaml_loader).items():
            if names is not None:
                names.add(c_name)
            aliases = props.get('alias', [])
            if isinstance(aliases, str):
                aliases = {aliases}
            else:
                aliases = set(aliases)
            aliases.add(c_name)
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
                    default[name] = _upcast(props['default'], props['dtype'])
                if bounds is not None:
                    _bounds = {k: _upcast(props[k], props['dtype'])
                               for k in ["<", "<=", ">", ">="]
                               if k in props}
                    if _bounds:
                        bounds[name] = _bounds
                if help is not None and props.get('help', ''):
                    help[name] = props['help']
