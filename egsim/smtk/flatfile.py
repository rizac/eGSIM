"""flatfile root module"""
from __future__ import annotations
from io import IOBase
from os.path import join, dirname
from datetime import datetime
import re
from pandas.core.base import IndexOpsMixin
from pandas.errors import ParserError
from tables import HDF5ExtError
from typing import Union, Any
from enum import Enum

import numpy as np
import pandas as pd

from yaml import load as yaml_load
try:
    from yaml import CSafeLoader as SafeLoader  # faster, if available
except ImportError:
    from yaml import SafeLoader  # same as using yaml.safe_load

from .validators import sa_period, InputError

_csv_default_args = (
    ('na_values', ("", "null", "NULL", "None",
                   "nan", "-nan", "NaN", "-NaN",
                   "NA", "N/A", "n/a",  "<NA>", "#N/A", "#NA")),
    ('keep_default_na', False),
    ('comment', '#'),
    ('encoding', 'utf-8-sig')
)


EVENT_ID_COLUMN_NAME = 'evt_id'


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
        HDF files are the recommended formats **but support only files on-disk as
        parameter**. CSV files on the other hand can be supplied as in-memory stream, or
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
        import traceback
        # HdfError -> some error in the data
        # NotImplementedError -> generic buffer not implemented in HDF
        # try with CSV:
        if cur_pos is not None:
            filepath_or_buffer.seek(cur_pos)

        kwargs = dict(_csv_default_args) | kwargs
        if csv_sep is None:
            kwargs['sep'] = _infer_csv_sep(filepath_or_buffer, **kwargs)
        else:
            kwargs['sep'] = csv_sep

        try:
            dfr = pd.read_csv(filepath_or_buffer, **kwargs)
        except ValueError as exc:
            # invalid_columns = _read_csv_inspect_failure(filepath_or_buffer, **kwargs)
            raise ColumnDataError(str(exc)) from None

    if rename:
        dfr.rename(columns=rename, inplace=True)
        # rename defaults and dtypes:
        for old, new in rename.items():
            if dtypes and old in dtypes:
                dtypes[new] = dtypes.pop(old)
            if defaults and old in defaults:
                defaults[new] = dtypes.pop(old)

    validate_flatfile_dataframe(dfr, dtypes, defaults, 'raise' if is_hdf else 'coerce')
    optimize_flatfile_dataframe(dfr)
    if not isinstance(dfr.index, pd.RangeIndex):
        dfr.reset_index(drop=True, inplace=True)
    return dfr


def _infer_csv_sep(filepath_or_buffer: IOBase, **kwargs) -> str:
    """Infer `sep` from kwargs, and or return it"""
    sep = kwargs.get('sep')
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
    # otherwise (these errors might be fixed afterward before reading the whole csv):
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

    :param dfr: the flatfile, as pandas DataFrame
    :param extra_dtypes: dict of column names mapped to the desired data type.
        Standard flatfile columns should not to be present (unless for some reason
        their dtype must be overwritten)
    :param extra_defaults: dict of column names mapped to the desired default value
        to replace missing data. Standard flatfile columns do not need to be present
        (unless for some reason their dtype must be overwritten)
    :param mixed_dtype_categorical: what to do when `dtype=ColumnDtype.category`, i.e.,
        with the categories to be inferred and not explicitly given, and `value`
        (if array-like) contains mixed dtypes (e.g. float and strings).
        Then pass None to ignore and return `value` as it is, 'raise'
        (the default) to raise ValueError, and 'coerce' to cast all items to string
    """
    # post-process:
    invalid_columns = []
    if not extra_defaults:
        extra_defaults = {}
    if not extra_dtypes:
        extra_dtypes = {}
    # check dtypes correctness (actual vs expected) and try to fix mismatching ones:
    for col in dfr.columns:
        if col in extra_dtypes:
            xp_dtype = extra_dtypes[col]
            if not isinstance(xp_dtype, ColumnDtype):
                try:
                    xp_dtype = ColumnDtype[extra_dtypes[col]]
                except KeyError:
                    try:
                        xp_dtype = pd.CategoricalDtype(xp_dtype)
                    except (TypeError, ValueError):
                        invalid_columns.append(col)
                        continue
        else:
            xp_dtype = FlatfileMetadata._get_dtype(col)  # noqa

        if xp_dtype is None:
            continue

        if col in extra_dtypes:
            default = extra_defaults.get(col)
            if default is not None:
                default = cast_to_dtype(default, xp_dtype, mixed_dtype_categorical)
        else:
            default = FlatfileMetadata.get_default(col)
        if default is not None:
            is_na = pd.isna(dfr[col])
            dfr.loc[is_na, col] = default

        # cast to expected dtype (no op if dtype is already ok):
        try:
            dfr[col] = cast_to_dtype(dfr[col], xp_dtype, mixed_dtype_categorical)
        except (ParserError, ValueError):
            invalid_columns.append(col)
            continue

    if invalid_columns:
        raise ColumnDataError(*invalid_columns)

    # check no dupes:
    ff_cols = set(dfr.columns)
    has_imt = False
    for c in dfr.columns:
        aliases = set(FlatfileMetadata.get_aliases(c))
        if len(aliases & ff_cols) > 1:
            raise IncompatibleColumnError(*list(aliases & ff_cols))
        if not has_imt and FlatfileMetadata.get_type(c) == ColumnType.intensity:
            has_imt = True

    if not has_imt:
        raise MissingColumnError('No IMT column found')

    return dfr


def optimize_flatfile_dataframe(dfr: pd.DataFrame):
    """Optimize the given dataframe by replacing str column with
    categorical (if the conversion saves memory)
    """
    for c in dfr.columns:
        if get_dtype_of(dfr[c]) == ColumnDtype.str:
            cat_dtype = dfr[c].astype('category')
            if cat_dtype.memory_usage(deep=True) < dfr[c].memory_usage(deep=True):
                dfr[c] = cat_dtype


def query(flatfile: pd.DataFrame, query_expression: str,
          raise_no_rows=True) -> pd.DataFrame:
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
        'global_dict': {},  # 'pd': pd, 'np': np
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
    ret = flatfile.query(query_expression, **__kwargs)
    if raise_no_rows and ret.empty:
        raise FlatfileError('no rows matching query')
    return ret


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
    datetime = "ISO formatted date-time"
    str = "string of text"
    category = "categorical"


def get_dtype_of(
        obj: Union[IndexOpsMixin, np.dtype, str, float, int, datetime, bool]
) -> Union[ColumnDtype, None]:
    """
    Get the dtype of the given pandas array, dtype or Python scalar. If
    `ColumnDtype.category` is returned, then `obj.dtype` is assured to be
    a pandas `CategoricalDtype` object with all categories the same dtype,
    which can be retrieved by calling again: `get_dtype_of(obj.dtype.categories)`

    Examples:
    ```
    get_dtype_of(pd.Series(...))
    get_dtype_of(pd.CategoricalDtype())
    get_dtype_of(pd.CategoricalDtype().categories)
    get_dtype_of(dataframe.index)
    get_dtype_of(datetime.utcnow())
    get_dtype_of(5.5)
    ```

    :param obj: any pandas numpy collection e.g. Series / Index, or a
        recognized Python scalar (float, int, bool, str)
    """
    # check bool / int / float in this order to avoid potential subclass issues:
    if pd.api.types.is_bool_dtype(obj) or isinstance(obj, bool):
        # pd.Series([True, False]).astype('category') ends being here, but
        # we should return categorical dtype (this happens only with booleans):
        if isinstance(getattr(obj, 'dtype', None), pd.CategoricalDtype):
            return ColumnDtype.category
        return ColumnDtype.bool
    if pd.api.types.is_integer_dtype(obj) or isinstance(obj, int):
        return ColumnDtype.int
    if pd.api.types.is_float_dtype(obj) or isinstance(obj, float):
        return ColumnDtype.float
    if pd.api.types.is_datetime64_any_dtype(obj) or isinstance(obj, datetime):
        return ColumnDtype.datetime
    if isinstance(obj, pd.CategoricalDtype):
        return ColumnDtype.category
    if isinstance(getattr(obj, 'dtype', None), pd.CategoricalDtype):
        if get_dtype_of(obj.dtype.categories) is None:  # noqa
            return None  # mixed categories , return no dtype
        return ColumnDtype.category
    if pd.api.types.is_string_dtype(obj) or isinstance(obj, str):
        return ColumnDtype.str

    # Final check for data with str and Nones, whose dtype (np.dtype('O')) equals the
    # dtype of only-string Series, but for which `pd.api.types.is_string_dtype` is False:
    obj_dtype = None
    if getattr(obj, 'dtype', None) == np.dtype('O') and pd.api.types.is_list_like(obj):
        # check element-wise (very inefficient but unavoidable). Return ColumnDtype.str
        # if at least 1 element is str and all others are None:
        for item in obj:
            if item is None:
                continue
            if not pd.api.types.is_string_dtype(item):
                return None
            obj_dtype = ColumnDtype.str

    return obj_dtype


def cast_to_dtype(
        value: Any,
        dtype: Union[ColumnDtype, pd.CategoricalDtype],
        mixed_dtype_categorical='raise'
) -> Any:
    """Cast the given value to the given dtype, raise ValueError if unsuccessful

    :param value: pandas Series/Index or Python scalar
    :param dtype: the base `ColumnDtype`, or a pandas CategoricalDtype. In the latter
        case, if categories are not of the same dtype, a `ValueError` is raised
    :param mixed_dtype_categorical: what to do when `dtype=ColumnDtype.category`, i.e.,
        with the categories to be inferred and not explicitly given, and `value`
        (if array-like) contains mixed dtypes (e.g. float and strings).
        Then pass None to ignore and return `value` as it is, 'raise'
        (the default) to raise ValueError, and 'coerce' to cast all items to string
    """
    categories: Union[pd.CategoricalDtype, None] = None
    if isinstance(dtype, pd.CategoricalDtype):
        categories = dtype
        dtype = get_dtype_of(dtype.categories.dtype)

    actual_base_dtype = get_dtype_of(value)
    actual_categories: Union[pd.CategoricalDtype, None] = None
    if isinstance(getattr(value, 'dtype', None), pd.CategoricalDtype):
        actual_categories = value.dtype
        actual_base_dtype = get_dtype_of(value.dtype.categories)

    if dtype is None:
        raise ValueError('cannot cast column to dtype None. If you passed '
                         'categorical dtype, check that all categories '
                         'dtypes are equal')

    if categories and actual_categories:
        if set(categories.categories) != set(actual_categories.categories):
            raise ValueError('Value mismatch with provided categorical values')

    is_pd = isinstance(value, IndexOpsMixin)  # common interface for Series / Index
    if not is_pd:
        values = pd.Series(value)
    else:
        values = value

    if dtype != actual_base_dtype:
        if dtype == ColumnDtype.float:
            values = values.astype(float)
        elif dtype == ColumnDtype.int:
            values = values.astype(int)
        elif dtype == ColumnDtype.bool:
            # bool is too relaxed, e.g. [3, 'x'].astype(bool) works but it shouldn't
            values = values.astype(int)
            if set(pd.unique(values)) - {0, 1}:
                raise ValueError('not a boolean')
            values = values.astype(bool)
        elif dtype == ColumnDtype.datetime:
            try:
                values = pd.to_datetime(values)
            except (ParserError, ValueError) as exc:
                raise ValueError(str(exc))
        elif dtype == ColumnDtype.str:
            values = values.astype(str)
        elif dtype == ColumnDtype.category:
            values_ = values.astype('category')
            mixed_dtype = get_dtype_of(values_.cat.categories) is None
            if mixed_dtype and mixed_dtype_categorical == 'raise':
                raise ValueError('mixed dtype in categories')
            elif mixed_dtype and mixed_dtype_categorical == 'coerce':
                values = values.astype(str).astype('category')
            else:
                values = values_

    if categories is not None:
        # pandas converts invalid values (not in categories) to NA, we want to raise:
        is_na = pd.isna(values)
        values = values.astype(categories)
        is_na_after = pd.isna(values)
        ok = len(is_na) == len(is_na_after) and (is_na == is_na_after).all()  # noqa
        if not ok:
            raise ValueError('Value mismatch with provided categorical values')

    if is_pd:
        return values
    if pd.api.types.is_list_like(value):
        # for ref, although passing numpy arrays is not explicitly supported, numpy
        # arrays with no shape (e.g.np.array(5)) are *not* falling in this if
        return values.to_list()
    return values.item()


# Exceptions:


class FlatfileError(InputError):
    """General flatfile column(s) error. Inherits from smtks.validators.InputError.
    Note that the str representation equals the init arguments comma-separated:
    FlatfileError(arg1, arg2, ...) -> f"{str(arg1)}, {str(arg2)}, ..."
    See subclasses for details
    """
    pass


class MissingColumnError(FlatfileError, AttributeError, KeyError):
    """MissingColumnError. It inherits also from AttributeError and
    KeyError to be compliant with pandas and OpenQuake"""

    msg_prefix = 'missing column(s)'


class IncompatibleColumnError(FlatfileError):

    msg_prefix = 'column names conflict'


class ColumnDataError(FlatfileError, ValueError, TypeError):

    msg_prefix = 'invalid data for'


# registered columns:

class FlatfileMetadata:
    """Container class to access flatfile metadata defined
    in the associated YAML file
    """

    @staticmethod
    def has(column: str) -> bool:
        """Return whether the given column name is a registered flatfile column
        (column aliases included)
        """
        return bool(FlatfileMetadata._props_of(column))

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
        """Return the `ColumnType` enum item of the given column, or None"""
        return FlatfileMetadata._props_of(column).get('type', None)

    @staticmethod
    def get_default(column: str) -> Union[None, Any]:
        """Return the default of the given column name (used to fill missing data),
        or None if no default is set
        """
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
        """Return the help (description) of the given column name, or ''"""
        return FlatfileMetadata._props_of(column).get('help', "")

    @staticmethod
    def get_dtype(column: str) -> Union[ColumnDtype, None]:
        """Return the data type of the given column name, as item of the
        `ColumnDtype` Enum item, or None (=no data type set for the column).
        If the column dtype is categorical, this method returns the (unique) dtype
        of all categories. This means that `ColumnDtype.category` is never returned,
        and to check that the column dtype is categorical, check that
        `get_categories(column)` returns a non-empty list
        """
        dtype = FlatfileMetadata._get_dtype(column)
        if isinstance(dtype, pd.CategoricalDtype):
            return get_dtype_of(dtype.categories)
        return dtype

    @staticmethod
    def get_categories(column: str) -> list:
        """Return the list of possible values that the column can have
        (aka categories, all the same dtype) or an empty list otherwise
        """
        dtype = FlatfileMetadata._get_dtype(column)
        if isinstance(dtype, pd.CategoricalDtype):
            return dtype.categories.tolist()
        return []

    @staticmethod
    def _get_dtype(column: str) -> Union[pd.CategoricalDtype, ColumnDtype, None]:
        return FlatfileMetadata._props_of(column).get('dtype', None)

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
    """Load the flatfile metadata from the associated YAML file into a Python dict

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


def _harmonize_col_props(name: str, props: dict):
    """Harmonize the values of a column property dict"""
    aliases = props.get('alias', [])
    if isinstance(aliases, str):
        aliases = [aliases]
    props['alias'] = (name,) + tuple(aliases)
    if 'type' in props:
        props['type'] = ColumnType[props['type']]
    dtype: Union[None, ColumnDtype, pd.CategoricalDtype] = None
    if 'dtype' in props:
        if isinstance(props['dtype'], str):
            props['dtype'] = dtype = ColumnDtype[props['dtype']]
        else:
            props['dtype'] = dtype = pd.CategoricalDtype(props['dtype'])
    if 'default' in props:
        props['default'] = cast_to_dtype(props['default'], dtype)
    for k in ("<", "<=", ">", ">="):
        if k in props:
            props[k] = cast_to_dtype(props[k], dtype)
    return props
