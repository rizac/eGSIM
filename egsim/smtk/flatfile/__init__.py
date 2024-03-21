"""flatfile root module"""
from __future__ import annotations
from io import IOBase
from os.path import join, dirname
from datetime import datetime
import re
from pandas.core.base import IndexOpsMixin
from pandas.errors import ParserError
from typing import Union, Any, Optional
from collections.abc import Callable, Collection, Container
from enum import Enum

import numpy as np
import pandas as pd

from yaml import load as yaml_load
try:
    from yaml import CSafeLoader as SafeLoader  # faster, if available
except ImportError:
    from yaml import SafeLoader  # same as using yaml.safe_load


def parse_flatfile(
        filepath_or_buffer: str, sep: str = None,
        rename:dict[str,str]= None,
        extra_dtype: dict[
            str, Union[str, list, ColumnDtype, pd.CategoricalDtype]] = None,
        extra_defaults: dict[str, Any] = None,
        usecols: Union[list[str], Callable[[str], bool]] = None,
        **kwargs) -> pd.DataFrame:
    """
    Read a flatfile not in standard format

    :param filepath_or_buffer: str, path object or file-like object of the CSV
        formatted data. If string, compressed files are also supported
        and inferred from the extension (e.g. 'gzip', 'zip')
    :param sep: the separator (or delimiter). None means 'infer' (it might
        take more time)
    :param rename: optional dict mapping CSV fieldnames to a standard flatfile column.
        This dict keys will have data type and default automatically set from the
        registered flatfile columns (see `columns.yaml` for details)
    :param extra_dtype: optional dict mapping CSV fieldnames that are not standard
        flatfile columns and are not implemented in `rename`, to its data type.
        Dict values can be: 'float', 'datetime', 'bool', 'int', 'str',
        'category', `ColumnDType`s, list/tuples or pandas CategoricalDtype
    :param extra_defaults: optional mapping CSV fieldnames that are not standard
        flatfile columns and are not implemented in `rename`, to the default value
        that will be used to replace missing values
    :param usecols: pandas `read_csv` parameter (exposed explicitly here for clarity)
        the column names to load, as list. Can be also a callable
        accepting a column name and returning True/False (keep/discard)
    """
    # get registered dtypes and defaults:
    extra_dtype = extra_dtype or {}
    extra_defaults = extra_defaults or {}
    for csv_col, ff_col in (rename or {}).items():
        if ColumnsRegistry.get_default(ff_col) is not None:
            extra_defaults[csv_col] = ColumnsRegistry.get_default(ff_col)
        if ColumnsRegistry.get_dtype(ff_col) is not None:
            extra_dtype[csv_col] = ColumnsRegistry.get_dtype(ff_col).name

    dfr = read_flatfile(filepath_or_buffer, sep=sep, dtype=extra_dtype,
                        defaults=extra_defaults, usecols=usecols, **kwargs)
    if rename:
        dfr.rename(columns=rename, inplace=True)
    return dfr


_flatfile_default_args = (
    ('na_values', ("", "null", "NULL", "None",
                   "nan", "-nan", "NaN", "-NaN",
                   "NA", "N/A", "n/a",  "<NA>", "#N/A", "#NA")),
    ('keep_default_na', False),
    ('comment', '#'),
    ('encoding', 'utf-8-sig')
)


def read_flatfile(
        filepath_or_buffer: Union[str, IOBase],
        sep: str = None,
        rename: dict[str, str] = None,
        dtypes: dict[str, Union[str, list, ColumnDtype, pd.CategoricalDtype]] = None,
        defaults: dict[str, Any] = None,
        **kwargs) -> pd.DataFrame:
    """
    Read a comma-separated values (csv) file into DataFrame, behaving as pandas
    `read_csv` with some additional features:

    - int and bool columns can support missing values, as long as a default
      is explicitly set
    - bool columns recognize 0, 1 and all case-insensitive forms of true and false
    - categorical columns are allowed as long as the categories are all the
      same type. Missing values are allowed, nvalid categories will raise

    :param filepath_or_buffer: str, path object or file-like object of the CSV
        formatted data. If string, compressed files are also supported
        and inferred from the extension (e.g. 'gzip', 'zip')
    :param sep: the separator (or delimiter). None means 'infer' (it might
        take more time)
    :param dtype: dict of flatfile column names mapped to user-defined data type.
        Standard flatfile columns do not need to be present, unless their data type
        needs to be overwritten. Columns in `dtype` not present in the CSV will be
        ignored.
        Dtypes can be either 'int', 'bool', 'float', 'str', 'datetime', 'category'`,
        list, pandas `CategoricalDtype`: the last four data types are for data that can
        take only a limited amount of possible values and should be used mostly with
        string data as it might save a lot of memory. With "category", pandas will infer
        the categories from the data - note that each category will be of type `str` -
        with all others, the categories can be any type input by the user. Flatfile
        values not found in the categories will be replaced with missing values (NA in
        pandas, see e.g. `pandas.isna`). Columns of type 'int' and 'bool' do not support
        missing values: NA data will be replaced with the default set in `defaults`
        (see doc), or with 0 for int and False for bool if no default is set for the
        column.
    :param defaults: dict of flatfile column names mapped to user-defined default to
        replace missing values. Standard flatfile columns do not need to be present,
        unless their data type needs to be overwritten. Columns in `default` not present
        in the CSV will be ignored.
        Note that if int and bool columns are specified in `dtype`, then a default is
        set for those columns anyway (0 for int, False for bool. See `dtype` doc)

    :return: pandas DataFrame representing a Flat file
    """
    kwargs = dict(_flatfile_default_args) | kwargs
    if sep is None:
        kwargs['sep'] =  _infer_csv_sep(filepath_or_buffer, **kwargs)
    else:
        kwargs['sep'] = sep

    try:
        dfr = pd.read_csv(filepath_or_buffer, **kwargs)
    except ValueError as exc:
        invalid_columns = _read_csv_inspect_failure(filepath_or_buffer, **kwargs)
        raise InvalidDataInColumn(*invalid_columns) from None

    if rename:
        dfr.rename(columns=rename, inplace=True)
        # rename defaults and dtypes:
        for old, new in rename.items():
            if dtypes and old in dtypes:
                dtypes[new] = dtypes.pop(old)
            if defaults and old in defaults:
                defaults[new] = dtypes.pop(old)

    validate_flatfile_dataframe(dfr, dtypes, defaults)
    if not isinstance(dfr.index, pd.RangeIndex):
        dfr.reset_index(drop=True, inplace=True)
    return dfr


def _infer_csv_sep(filepath_or_buffer: IOBase, **kwargs) -> str:
    """ infer `sep` and or return it

    :param kwargs: read_csv arguments, excluding 'sep'
    """
    nrows = kwargs.pop('nrows', None)
    header = []
    kwargs.pop('sep', None)  # if it was None needs removal
    sep = ','
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


def _read_csv_inspect_failure(filepath_or_buffer: IOBase, **kwargs) -> list[str]:
    """Called upon failure of `pandas_read_csv`, check and return the flatifle
    invalid flatfile columns
    """
    buf_pos = filepath_or_buffer.tell()
    # As `read_csv` exception messages do not convey any column information, let's call
    # `read_csv` for each singular column, and collect those which raise.
    # To narrow down the choice of suspects let's pass only float columns: dtypes that
    # might raise are also bool and int, but we do not have those dtypes here
    # (see `_read_csv_prepare` for details):
    cols2check = [c for c, v in kwargs['dtype'].items() if v == ColumnDtype.float.value]
    invalid_columns = []
    for c in cols2check:
        try:
            kwargs['usecols'] = [c]
            filepath_or_buffer.seek(buf_pos)
            pd.read_csv(filepath_or_buffer , **kwargs)  # noqa
        except ValueError:
            invalid_columns.append(c)
    # if no columns raised, just put everything in the message:
    return invalid_columns or cols2check


def validate_flatfile_dataframe(
        dfr: pd.DataFrame,
        extra_dtypes: dict[str, Union[str, ColumnDtype, pd.CategoricalDtype, list]] = None,
        extra_defaults: dict[str, Any] = None):
    """FIXME doc
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
            xp_dtype = ColumnsRegistry.get_dtype(col)
            xp_categories = ColumnsRegistry.get_categories(col)

        if xp_dtype is None:
            continue

        if col in extra_dtypes:
            default = extra_defaults.get(col)
            if default is not None:
                default = cast_to_dtype(default, xp_dtype, xp_categories)
        else:
            default = ColumnsRegistry.get_default(col)
        if default is not None:
            is_na = pd.isna(dfr[col])
            dfr.loc[is_na, col] = default

        # handle mismatching dtypes (bool and int):
        actual_dtype = get_dtype_of(dfr[col])
        if actual_dtype != xp_dtype or actual_dtype is None:
            try:
                dfr[col] = cast_to_dtype(dfr[col], xp_dtype, xp_categories)
            except (ParserError, ValueError):
                invalid_columns.append(col)
                continue

    if invalid_columns:
        raise InvalidDataInColumn(*invalid_columns)

    # # check no dupes:
    ff_cols = set(dfr.columns)
    has_imt = False
    for c in dfr.columns:
        aliases = set(ColumnsRegistry.get_aliases(c))
        if len(aliases & ff_cols) > 1:
            raise ConflictingColumns(*list(aliases & ff_cols))
        if not has_imt and ColumnsRegistry.get_type(c) == ColumnType.intensity:
            has_imt = True

    if not has_imt:
        raise MissingColumn('No IMT column found')

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


# Columns utilities:

class ColumnType(Enum):
    """Flatfile column type"""
    rupture = 'rupture_parameter'
    site = 'site_parameter'
    distance = 'distance_measure'
    intensity = 'intensity_measure'


class ColumnDtype(Enum):
    """Enum where members are registered dtype names (see ColumnRegistry)"""
    # for a list of possible values, see `numpy.sctypeDict.keys()` (but also
    # check that they behave as you wish in pandas)
    float = "numeric float"
    int = "numeric integer"
    bool = "boolean"
    datetime = "date-time (ISO formatted)"
    str = "string of text"
    category = "categorical (a value from a list of possible choices)"


def get_dtype_of(arr_or_dtype: Union[IndexOpsMixin, np.ndarray, np.dtype]):
    """
    Get the dtype of the given pandas object, numpy array or dtype. Examples:
    ```
    get_dtype_of(pd.Series(...))
    get_dtype_of(pd.CategoricalDtype().categories)
    get_dtype_of(dataframe.index)
    get_dtype_of(np.array(...))
    ```

    :param arr_or_dtype: any pandas numpy collection e.g. Series / Index or a dtype
    """
    if  pd.api.types.is_bool_dtype(arr_or_dtype):
        return ColumnDtype.bool
    if pd.api.types.is_float_dtype(arr_or_dtype):
        return ColumnDtype.float
    if pd.api.types.is_integer_dtype(arr_or_dtype):
        return ColumnDtype.int
    if pd.api.types.is_datetime64_any_dtype(arr_or_dtype):
        return ColumnDtype.datetime
    if  pd.api.types.is_categorical_dtype(arr_or_dtype):
        return ColumnDtype.category
    if pd.api.types.is_string_dtype(arr_or_dtype):
        # str in pandas is a generic type that is returned also for mixed types. We
        # could use pandas 'string' type but it is not serializable to hdf so let's
        # use str but check here we really deal with strings and not mixed types
        if isinstance(arr_or_dtype, np.dtype):
            return ColumnDtype.str
        if isinstance(arr_or_dtype, np.ndarray) and not arr_or_dtype.shape:
            # numpy single element, make it fall in the next if (pd.is_scalar):
            arr_or_dtype = arr_or_dtype.item()
        if pd.api.types.is_scalar(arr_or_dtype):
            if isinstance(arr_or_dtype, str):
                # values a scalar (not a dtype), check its class
                return ColumnDtype.str
        if pd.api.types.is_list_like(arr_or_dtype):
            if all(isinstance(_, str) for _ in arr_or_dtype):
                # values is list-like, check that all elements are str. Inefficient
                # but unavoidable (e.g. pd.Series([True, 2]) would return str otherwise):
                return ColumnDtype.str
    return None

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
            sorted_names = ColumnsRegistry.get_aliases(name)
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


# registered columns:

class ColumnsRegistry:
    """Container class to access registered flatfile columns properties defined
    in the associated YAML file
    """

    @staticmethod
    def get_rupture_params() -> set[str]:
        """Return a set of strings with all column names (including aliases)
        denoting a rupture parameter
        """
        return {c_name for c_name, c_props in _load_columns_registry().items()
                if c_props.get('type', None) == ColumnType.rupture}

    @staticmethod
    def get_intensity_measures() -> set[str]:
        """Return a set of strings with all column names denoting an intensity
        measure name, with no arguments, e.g., "PGA", "SA" (not "SA(...)").
        """
        return {c_name for c_name, c_props in _load_columns_registry().items()
                if c_props.get('type', None) == ColumnType.intensity}

    @staticmethod
    def get_type(column: str) -> Union[ColumnType, None]:
        """Return the ColumnType of the given column name, or None"""
        return _load_columns_registry().get(_replace(column), {}).get('type', None)

    @staticmethod
    def get_dtype(column: str) -> Union[ColumnDtype, None]:
        """Return the Column data type of the given column name, as ColumnDtype value
        (str), pandas CategoricalDtype, or None"""
        return _load_columns_registry().get(_replace(column), {}).get('dtype', None)

    @staticmethod
    def get_default(column: str) -> Union[None, Any]:
        """Return the Column data type of the given column name, or None"""
        return _load_columns_registry().get(_replace(column), {}).get('default', None)

    @staticmethod
    def get_aliases(column: str) -> tuple[str]:
        """Return all possible names of the given column, as tuple set of strings
        where the first element is assured to be the flatfile default column name
        (primary name) and all remaining the secondary names. The tuple will be composed
        of `column` alone if `column` does not have registered aliases
        """
        return _load_columns_registry().get(_replace(column), {}).get('alias', (column,))

    @staticmethod
    def get_help(column: str) -> str:
        """Return the help (description) ofthe given column name, or ''"""
        return _load_columns_registry().get(_replace(column), {}).get('help', "")

    @staticmethod
    def get_categories(column: str) -> list:
        return _load_columns_registry().get(_replace(column), {}).get('categories', [])


# registered columns IO method:

# YAML file path:
_columns_registry_path = join(dirname(__file__), 'columns_registry.yaml')
# cache storage of the data in the YAML:
_columns_registry: dict[str, dict[str, Any]] = None  # noqa


def _load_columns_registry(cache=True) -> dict[str, dict[str, Any]]:
    """Loads the content of the associated YAML file with all columns
    information and returns it as Python dict

    :param cache: if True, a cache version will be returned (faster, but remember
        that any change to the cached version will persist permanently!). Otherwise,
        a new dict loaded from file (slower) will be returned
    """
    global _columns_registry
    if cache and _columns_registry:
        return _columns_registry
    _cols = {}
    with open(_columns_registry_path) as fpt:
        for col_name, props in yaml_load(fpt, SafeLoader).items():
            props = _harmonize_col_props(col_name, props)
            # add all aliases mapped to the relative properties:
            for c_name in props['alias']:
                _cols[c_name] = props
    if cache:
        _columns_registry = _cols
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


def _replace(name: str):
    return name if not name.startswith('SA(') else 'SA'


def _parse_categories(values: Union[pd.CategoricalDtype, Collection]) \
        -> tuple[list, ColumnDtype]:
    if not isinstance(values, pd.CategoricalDtype):
        try:
            values = pd.CategoricalDtype(values)
        except (TypeError, ValueError):
            raise ValueError(f'Not categorical: {str(values)}')
    categories_dtype = get_dtype_of(values.categories)
    if categories_dtype is None:
        raise ValueError(f'Invalid categorical data type, categories '
                         f'data types unrecognized or not homogeneous')
    return values.categories.tolist(), categories_dtype


def cast_to_dtype(
        value: Any,
        dtype: ColumnDtype,
        categories: Optional[Union[Container, pd.CategoricalDtype]]=None) -> Any:
    """Cast the given value to the given dtype, raise ValueError if unsuccessful

    :param value: pandas Series/Index, numpy array or scalar, Python scalar
    :param dtype: the base `ColumnDtype`
    :param categories: a list of poandas Categorical of possible choices. Must be
        all the same type of `dtype`
    """

    is_pd = isinstance(value, IndexOpsMixin)  # common interface for Series / Index
    is_np = not is_pd and isinstance(value, (np.ndarray, np.generic))
    if not is_pd:
        values = pd.Series(value)
    else:
        values = value

    categorical_dtype = None
    if isinstance(categories, pd.CategoricalDtype):
        categorical_dtype = categories
    elif categories:
        categorical_dtype = pd.CategoricalDtype(categories)

    if dtype == ColumnDtype.float:
        values = values.astype(float)
    elif dtype == ColumnDtype.int:
        values = values.astype(int)
    elif dtype == ColumnDtype.bool:
        # bool is too relaxed, e.g. [3, 'x'].astype(bool) works (it shouldn't). So:
        try:
            values = values.astype(int)
        except ValueError:
            values = values.replace({
                '0': False,
                'false': False,
                'False': False,
                'FALSE': False,
                '1': True,
                'true': True,
                'True': True,
                'TRUE': True
            }).astype(int)
        if sorted(pd.unique(values)) not in ([0], [1], [0, 1]):  # FIXME better?
            raise ValueError()
    elif dtype == ColumnDtype.datetime:
        try:
            values = pd.to_datetime(values)
        except (ParserError, ValueError) as exc:
            raise ValueError(str(exc))  # dtype_ok = False, so jump at the end (see below)
    elif dtype  == ColumnDtype.str:
        values = values.astype(str)
    elif dtype == ColumnDtype.category:
        if categorical_dtype:
            values = values.astype(categorical_dtype)
            categorical_dtype = None  # do not fall back in the if below
        else:
            values = values.astype('category')

    if categorical_dtype:
        # check that we still have the same N/A. Pandas convert invalid values to NA
        # we want to raise:
        is_na = pd.isna(values)
        values = values.astype(categorical_dtype)
        is_na_after = pd.isna(values)
        if len(is_na) != len(is_na_after) or (is_na != is_na_after).any():
            raise ValueError('Not all values in defined categories')

    if is_pd:
        return values

    list_like = pd.api.types.is_list_like(value)

    if is_np:
        return values.values if list_like else values.values[0]

    # Python object
    return values.tolist() if list_like else values.item()
