"""flatfile root module"""
from __future__ import annotations
from io import IOBase
from os.path import join, dirname
from datetime import datetime
import re
from pandas.core.base import IndexOpsMixin
from pandas.errors import ParserError
from tables import HDF5ExtError
from typing import Union, Any, Optional
from collections.abc import Collection, Container
from enum import Enum

import numpy as np
import pandas as pd

from yaml import load as yaml_load
try:
    from yaml import CSafeLoader as SafeLoader  # faster, if available
except ImportError:
    from yaml import SafeLoader  # same as using yaml.safe_load

from .validators import sa_period

_csv_default_args = (
    ('na_values', ("", "null", "NULL", "None",
                   "nan", "-nan", "NaN", "-NaN",
                   "NA", "N/A", "n/a",  "<NA>", "#N/A", "#NA")),
    ('keep_default_na', False),
    ('comment', '#'),
    ('encoding', 'utf-8-sig')
)


def read_flatfile(
        filepath_or_buffer: Union[str, IOBase],
        rename: dict[str, str] = None,
        dtypes: dict[str, Union[str, list, ColumnDtype, pd.CategoricalDtype]] = None,
        defaults: dict[str, Any] = None,
        csv_sep: str = None,
        **kwargs) -> pd.DataFrame:
    """
    Read a flatfile from either a comma-separated values (CSV) or HDF file,
    returning the corresponding pandas DataFrame.

    :param filepath_or_buffer: str, path object or file-like object of the data.
        HDF files are the recommended formats but support only files on-disk as
        parameter. CSV files on the other hand can be supplied as in-memory stream, or
        compressed files that will be inferred from the extension (e.g. 'gzip', 'zip')
    :param rename: a dict mapping a file column to a new column name. Mostly useful
        for renaming columns to standard flatfile names, delegating all data types
        check to the function without (see also dtypes and defaults for info)
    :param dtypes: dict of file column names mapped to user-defined data types, to
        check and cast data after the data is read. Standard flatfile columns do not
        need to be present. If they are, the value here will overwrite the default dtype,
        if set. Columns in `dtype` not present in the file will be ignored.
        Dict values can be either 'int', 'bool', 'float', 'str', 'datetime', 'category'`,
        list, pandas `CategoricalDtype`: the last three denote data that can
        take only a limited amount of possible values and should be mostly used with
        string data as it might save a lot of memory (with "category", pandas will infer
        the possible values from the data. In this case, note that with CSV files each
        category will be of type `str`).
    :param defaults: dict of file column names mapped to user-defined default to
        replace missing values. Because 'int' and 'bool' columns do not support missing
        values, with CSV files a default should be provided (e.g. 0 or False) to avoid
        raising Exceptions.
        Standard flatfile columns do not need to be present. If they are, the value here
        will overwrite the default dtype, if set. Columns in `defaults` not present in
        the file will be ignored
    :param csv_sep: the separator (or delimiter), only used for CSV files.
        None means 'infer' (look in `kwargs` and if not found, infer from data header)

    :return: pandas DataFrame representing a Flat file
    """
    is_hdf = False
    cur_pos = None
    if isinstance(filepath_or_buffer, IOBase):
        cur_pos = filepath_or_buffer.tell()

    try:
        dfr = pd.read_hdf(filepath_or_buffer, **kwargs)
        is_hdf = True
    except (HDF5ExtError, NotImplementedError):
        # HdfError -> some error in the data
        # NotImplementedError -> generic buffer not implemented in HDF
        # try with CSV:
        if cur_pos is not None:
            filepath_or_buffer.seek(cur_pos)

        kwargs = dict(_csv_default_args) | kwargs
        if csv_sep is None:
            kwargs['sep'] =  _infer_csv_sep(filepath_or_buffer, **kwargs)
        else:
            kwargs['sep'] = csv_sep

        try:
            dfr = pd.read_csv(filepath_or_buffer, **kwargs)
        except ValueError as exc:
            # invalid_columns = _read_csv_inspect_failure(filepath_or_buffer, **kwargs)
            raise InvalidDataError(str(exc)) from None

    if rename:
        dfr.rename(columns=rename, inplace=True)
        # rename defaults and dtypes:
        for old, new in rename.items():
            if dtypes and old in dtypes:
                dtypes[new] = dtypes.pop(old)
            if defaults and old in defaults:
                defaults[new] = dtypes.pop(old)

    validate_flatfile_dataframe(dfr, dtypes, defaults, 'raise' if is_hdf else 'coerce')
    if not isinstance(dfr.index, pd.RangeIndex):
        dfr.reset_index(drop=True, inplace=True)
    return dfr


def _infer_csv_sep(filepath_or_buffer: IOBase, **kwargs) -> str:
    """Infer `sep` from kwargs, and or return it"""
    sep = kwargs.get('sep', None)
    if sep is not None:
        return sep
    nrows = kwargs.pop('nrows', None)
    header = []
    for _sep in [';', ',', r'\s+']:
        _header = _read_csv_get_header(filepath_or_buffer, sep=_sep, **kwargs)
        if len(_header) > len(header):
            sep = _sep
            header = _header
    if nrows is not None:
        kwargs['nrows'] = nrows
    return sep


def _read_csv_get_header(filepath_or_buffer: IOBase, sep=None, **kwargs) -> list[str]:
    _pos = None
    if isinstance(filepath_or_buffer, IOBase):
        _pos = filepath_or_buffer.tell()
    # use only args necessary to parse columns, we might raise unnecessary errors
    # otherwise (these errors might be fixed afterwards before reading the whole csv):
    args = ['header', 'names', 'skip_blank_lines', 'skipinitialspace', 'engine',
            'lineterminator', 'quotechar', 'quoting', 'doublequote', 'escapechar',
            'comment', 'dialect', 'delim_whitespace']
    _kwargs = {k: kwargs[k] for k in args if k in kwargs}
    _kwargs['nrows'] = 0  # read just header
    _kwargs['sep'] = sep
    ret = pd.read_csv(filepath_or_buffer, **_kwargs).columns  # noqa
    if _pos is not None:
        filepath_or_buffer.seek(_pos)
    return ret


def validate_flatfile_dataframe(
        dfr: pd.DataFrame,
        extra_dtypes: dict[str, Union[str, ColumnDtype, pd.CategoricalDtype, list]] = None,  # noqa
        extra_defaults: dict[str, Any] = None,
        mixed_dtype_categorical='raise'):
    """Validate the flatfile dataframe checking data types, conflicting column names,
    or missing mandatory columns (e.g. IMT related columns). This method raises
    or returns None on success
    """
    # post-process:
    invalid_columns = []
    if not extra_defaults:
        extra_defaults = {}
    if not extra_dtypes:
        extra_dtypes = {}
    # check dtypes correctness (actual vs expected) and try to fix mismatching ones:
    for col in dfr.columns:
        xp_categories = None
        if col in extra_dtypes:
            xp_dtype = extra_dtypes[col]
            if not isinstance(xp_dtype, ColumnDtype):
                try:
                    xp_dtype = ColumnDtype[extra_dtypes[col]]
                except KeyError:
                    try:
                        xp_categories, xp_dtype = _parse_categories(xp_dtype)
                    except ValueError:
                        invalid_columns.append(col)
                        continue
        else:
            xp_dtype = FlatfileMetadata.get_dtype(col)
            xp_categories = FlatfileMetadata.get_categories(col) or None

        if xp_dtype is None:
            continue

        if col in extra_dtypes:
            default = extra_defaults.get(col)
            if default is not None:
                default = cast_to_dtype(
                    default,
                    xp_dtype,
                    xp_categories,
                    mixed_dtype_categorical
                )
        else:
            default = FlatfileMetadata.get_default(col)
        if default is not None:
            is_na = pd.isna(dfr[col])
            dfr.loc[is_na, col] = default

        # handle mismatching dtypes (bool and int):
        actual_dtype = get_dtype_of(dfr[col])
        if actual_dtype != xp_dtype or actual_dtype is None:
            try:
                dfr[col] = cast_to_dtype(
                    dfr[col],
                    xp_dtype,
                    xp_categories,
                    mixed_dtype_categorical
                )
            except (ParserError, ValueError):
                invalid_columns.append(col)
                continue

    if invalid_columns:
        raise InvalidDataError(*invalid_columns)

    # check no dupes:
    ff_cols = set(dfr.columns)
    has_imt = False
    for c in dfr.columns:
        aliases = set(FlatfileMetadata.get_aliases(c))
        if len(aliases & ff_cols) > 1:
            raise ColumnConflictError(*list(aliases & ff_cols))
        if not has_imt and FlatfileMetadata.get_type(c) == ColumnType.intensity:
            has_imt = True

    if not has_imt:
        raise MissingColumnError('No IMT column found')

    return dfr


def query(flatfile: pd.DataFrame, query_expression: str) -> pd.DataFrame:
    """Call `flatfile.query` with some utilities:
     - datetime can be input in the string, e.g. "datetime(2016, 12, 31)"
     - boolean can be also lower case ("true" or "false")
     - Some series methods with all args optional can also be given with no brackets
       (e.g. ".notna", ".median")
    """
    # Setup custom keyword arguments to dataframe query. See also
    # val2str for consistency (e.f. datetime, bools)
    __kwargs = {
        # add support for `datetime("<iso_string>")` inside expressions:
        'local_dict': {
            'datetime': lambda a: datetime.fromisoformat(a)
        },
        'global_dict': {},  # 'pd': pd, 'np': np }
        # add support for bools lower case (why doesn't work if set in local_dict?):
        'resolvers': [{'true': True, 'false': False}]
    }
    # methods which can be input without brackets (regex pattern group):
    __meths = '(mean|median|min|max|notna)'
    # flatfile columns (as regex pattern group):
    __ff_cols = f"({'|'.join(re.escape(_) for _ in flatfile.columns)})"
    # Append brackets to methods in query expression, if needed:
    query_expression = re.sub(f"\\b{__ff_cols}\\.{__meths}(?![\\w\\(])", r"\1.\2()",
                              query_expression)
    # evaluate expression:
    return flatfile.query(query_expression, **__kwargs)


# Flatfile columns utilities:

class ColumnType(Enum):
    """Flatfile column type"""
    rupture = 'rupture_parameter'
    site = 'site_parameter'
    distance = 'distance_measure'
    intensity = 'intensity_measure'


class ColumnDtype(Enum):
    """Enum where members are registered dtype names"""
    # for ref `numpy.sctypeDict.keys()` lists the possible numpy values
    float = "numeric float"
    int = "numeric integer"
    bool = "boolean"
    datetime = "date-time (ISO formatted)"
    str = "string of text"
    category = "categorical"


def get_dtype_of(obj: Union[IndexOpsMixin, np.ndarray, np.dtype, np.generic, Any]):
    """
    Get the dtype of the given pandas / numpy array, dtype or Python scalar. Examples:
    ```
    get_dtype_of(pd.Series(...))
    get_dtype_of(pd.CategoricalDtype().categories)
    get_dtype_of(dataframe.index)
    get_dtype_of(np.array(...))
    ```

    :param obj: any pandas numpy collection e.g. Series / Index, a
        numpy array or scalar, or a recognized Python object (flaot, int, bool,
        str)
    """
    # check bool / int / float in this order to avoid potential subclass issues:
    if pd.api.types.is_bool_dtype(obj) or isinstance(obj, bool):
        return ColumnDtype.bool
    if pd.api.types.is_integer_dtype(obj) or isinstance(obj, int):
        return ColumnDtype.int
    if pd.api.types.is_float_dtype(obj) or isinstance(obj, float):
        return ColumnDtype.float
    if pd.api.types.is_datetime64_any_dtype(obj) or isinstance(obj, datetime):
        return ColumnDtype.datetime
    if isinstance(obj, pd.CategoricalDtype):
        return ColumnDtype.category
    if pd.api.types.is_string_dtype(obj):
        # as mixed arrays are also considered strings (e.g. s=pd.Series([True, 2]),
        # is_string_dtype(s) = True) we need further checks.
        # 1. np.dtype, no check, return:
        if isinstance(obj, np.dtype):
            return ColumnDtype.str
        # python scalar (e.g., np.str_('a')) are also str, so return also:
        if isinstance(obj, str):
            return ColumnDtype.str
        # python arrays, check element-wise, very inefficient but unavoidable...
        if pd.api.types.is_list_like(obj):
            if all(isinstance(_, str) or pd.api.types.is_string_dtype(_) for _ in obj):
                return ColumnDtype.str
        # non-dimensional np.arrays (e.g. np.array('a')), check its `item()`:
        elif isinstance(obj, np.ndarray) and not obj.shape:
            if isinstance(obj.item(), str):
                return ColumnDtype.str
    return None


def cast_to_dtype(
        value: Any,
        dtype: ColumnDtype,
        categories: Optional[Union[Container, pd.CategoricalDtype]]=None,
        mixed_dtype_categorical='raise') -> Any:
    """Cast the given value to the given dtype, raise ValueError if unsuccessful

    :param value: pandas Series/Index, numpy array or scalar, Python scalar
    :param dtype: the base `ColumnDtype`
    :param categories: a list of pandas Categorical of possible choices. Must be
        all the same type of `dtype`
    :param mixed_dtype_categorical: what to if dtype is 'category' with no explicit
        categories given: None ignore, 'raise' raise ValueError, 'coerce' cast data
        to string
    """

    is_pd = isinstance(value, IndexOpsMixin)  # common interface for Series / Index
    is_np = not is_pd and isinstance(value, (np.ndarray, np.generic))
    if not is_pd and not is_np:
        values = pd.Series(value)
    else:
        values = value

    categorical_dtype = None
    if isinstance(categories, pd.CategoricalDtype):
        categorical_dtype = categories
    elif categories is not None:
        categorical_dtype = pd.CategoricalDtype(categories)

    if dtype == ColumnDtype.float:
        values = values.astype(float)
    elif dtype == ColumnDtype.int:
        values = values.astype(int)
    elif dtype == ColumnDtype.bool:
        # bool is too relaxed, e.g. [3, 'x'].astype(bool) works but it shouldn't
        if pd.api.types.is_list_like(values):
            # try to cast to int (only if array as pd.unique does not work otherwise):
            values = values.astype(int)
            if set(pd.unique(values)) - {0, 1}:
                raise ValueError('not a boolean')
        values = values.astype(bool)
    elif dtype == ColumnDtype.datetime:
        try:
            values = pd.to_datetime(values)
        except (ParserError, ValueError) as exc:
            raise ValueError(str(exc))  # dtype_ok = False, so go to end (see below)
    elif dtype  == ColumnDtype.str:
        values = values.astype(str)
    elif dtype == ColumnDtype.category:
        if categorical_dtype:
            values = values.astype(categorical_dtype)
            categorical_dtype = None  # do not fall back in the if below
        else:
            values_ = values.astype('category')
            mixed_dtype = get_dtype_of(values_.cat.categories) is None
            if mixed_dtype and mixed_dtype_categorical == 'raise':
                raise ValueError('mixed dtype in categories')
            elif mixed_dtype and mixed_dtype_categorical == 'coerce':
                values = values.astype(str).astype('category')
            else:
                values = values_

    if categorical_dtype:
        if is_pd:
            # check that we still have the same N/A. Pandas convert invalid values to NA
            # we want to raise:
            is_na = pd.isna(values)
            values = values.astype(categorical_dtype)
            is_na_after = pd.isna(values)
            ok = len(is_na) == len(is_na_after) and (is_na == is_na_after).all()
        elif dtype == ColumnDtype.datetime:
            # np.isin does not work for datetime / timestamps/. Verbose check:
            if pd.api.types.is_scalar(values) or (is_np and not values.shape):
                # scalar or no-size numpy array:
                ok = values in categorical_dtype.categories
            else:
                ok = all(v in categorical_dtype.categories for v in values)
        else:
            ok = np.isin(values, categorical_dtype.categories.tolist()).all()
        if not ok:
            raise ValueError('Value mismatch with provided categorical values')

    if is_pd or is_np:
        return values

    # we gave a Python object, return it from the Series:
    return values.tolist() if pd.api.types.is_list_like(value) else values.item()


def _parse_categories(values: Union[pd.CategoricalDtype, Collection]) \
        -> tuple[list, ColumnDtype]:
    if not isinstance(values, pd.CategoricalDtype):
        try:
            values = pd.CategoricalDtype(values)
        except (TypeError, ValueError):
            raise ValueError(f'Not categorical: {str(values)}')
    categories_dtype = get_dtype_of(values.categories)
    if categories_dtype is None:
        get_dtype_of(values.categories)
        raise ValueError(f'Invalid categorical data type, categories '
                         f'data types unrecognized or not homogeneous')
    return values.categories.tolist(), categories_dtype


# Exceptions:


class FlatfileError(Exception):
    """
    General flatfile column(s) error. See subclasses for details
    """
    def __str__(self):
        """Reformat ``str(self)``"""
        # Basically remove the brackets if `self.arg` is a tuple i.e. if  `__init__`
        # was called with multiple arguments:
        return ", ".join(str(arg) for arg in self.args)


class MissingColumnError(FlatfileError, AttributeError, KeyError):
    """MissingColumnError. It inherits also from AttributeError and
    KeyError to be compliant with pandas and OpenQuake"""
    pass


class ColumnConflictError(FlatfileError):
    pass


class InvalidDataError(FlatfileError, ValueError, TypeError):
    pass


# registered columns:

class FlatfileMetadata:
    """Container class to access registered flatfile columns properties defined
    in the associated YAML file
    """

    @staticmethod
    def get_rupture_params() -> set[str]:
        """Return a set of strings with all column names (including aliases)
        denoting a rupture parameter
        """
        return {c_name for c_name, c_props in _load_flatfile_metadata().items()
                if c_props.get('type', None) == ColumnType.rupture}

    @staticmethod
    def get_intensity_measures() -> set[str]:
        """Return a set of strings with all column names denoting an intensity
        measure name, with no arguments, e.g., "PGA", "SA" (not "SA(...)").
        """
        return {c_name for c_name, c_props in _load_flatfile_metadata().items()
                if c_props.get('type', None) == ColumnType.intensity}

    @staticmethod
    def get_type(column: str) -> Union[ColumnType, None]:
        """Return the ColumnType of the given column name, or None"""
        return FlatfileMetadata._props_of(column).get('type', None)

    @staticmethod
    def get_dtype(column: str) -> Union[ColumnDtype, None]:
        """Return the Column data type of the given column name, as ColumnDtype value
        (str), pandas CategoricalDtype, or None"""
        return FlatfileMetadata._props_of(column).get('dtype', None)

    @staticmethod
    def get_default(column: str) -> Union[None, Any]:
        """Return the Column data type of the given column name, or None"""
        return FlatfileMetadata._props_of(column).get('default', None)

    @staticmethod
    def get_aliases(column: str) -> tuple[str]:
        """Return all possible names of the given column, as tuple set of strings
        where the first element is assured to be the flatfile default column name
        (primary name) and all remaining the secondary names. The tuple will be composed
        of `column` alone if `column` does not have registered aliases
        """
        return FlatfileMetadata._props_of(column).get('alias', (column,))

    @staticmethod
    def get_help(column: str) -> str:
        """Return the help (description) ofthe given column name, or ''"""
        return FlatfileMetadata._props_of(column).get('help', "")

    @staticmethod
    def get_categories(column: str) -> list:
        return FlatfileMetadata._props_of(column).get('categories', [])

    @staticmethod
    def _props_of(column: str) -> dict:
        _meta = _load_flatfile_metadata()
        props = _meta.get(column, None)
        if props is None and sa_period(column) is not None:
            props = _meta.get('SA', None)
        return props or {}


# registered columns IO method:

# YAML file path:
_flatfile_metadata_path = join(dirname(__file__), 'flatfile_metadata.yaml')
# cache storage of the data in the YAML:
_flatfile_metadata: dict[str, dict[str, Any]] = None  # noqa


def _load_flatfile_metadata(cache=True) -> dict[str, dict[str, Any]]:
    """Loads the flatfile metadata from the associated YAML file into a Python dict

    :param cache: if True, a cache version will be returned (faster, but remember
        that any change to the cached version will persist permanently!). Otherwise,
        a new dict loaded from file (slower) will be returned
    """
    global _flatfile_metadata
    if cache and _flatfile_metadata:
        return _flatfile_metadata
    _cols = {}
    with open(_flatfile_metadata_path) as fpt:
        for col_name, props in yaml_load(fpt, SafeLoader).items():
            props = _harmonize_col_props(col_name, props)
            # add all aliases mapped to the relative properties:
            for c_name in props['alias']:
                _cols[c_name] = props
    if cache:
        _flatfile_metadata = _cols
    return _cols


def _harmonize_col_props(name:str, props:dict):
    """harmonize the values of a column property dict"""
    aliases = props.get('alias', [])
    if isinstance(aliases, str):
        aliases = [aliases]
    props['alias'] = (name,) + tuple(aliases)
    if 'type' in props:
        props['type'] = ColumnType[props['type']]
    if 'dtype' in props:
        if isinstance(props['dtype'], str):
            props['dtype'] = ColumnDtype[props['dtype']]
        else:
            categories, dtype = _parse_categories(props['dtype'])
            props['dtype'] = dtype
            props['categories'] = categories
    if 'default' in props:
        props['default'] = cast_to_dtype(
            props['default'],
            props['dtype'],
            props.get('categories', None))
    for k in ("<", "<=", ">", ">="):
        if k in props:
            props[k] = cast_to_dtype(
                props[k],
                props['dtype'],
                props.get('categories', None))
    return props
