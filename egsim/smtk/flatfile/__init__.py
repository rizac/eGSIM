"""flatfile root module"""
from __future__ import annotations
from io import IOBase
from os.path import join, dirname
from datetime import date, datetime
import re
from typing import Union, Any
from collections.abc import Callable, Collection
from enum import Enum

import numpy as np
import pandas as pd
from pandas.core.arrays import PandasArray
from pandas.core.dtypes.base import ExtensionDtype

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
            extra_dtype[csv_col] = ColumnsRegistry.get_dtype(ff_col)

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
        dtype: dict[str, Union[str, list, ColumnDtype, pd.CategoricalDtype]] = None,
        defaults: dict[str, Any] = None,
        usecols: Union[list[str], Callable[[str], bool]] = None,
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
    :param usecols: pandas `read_csv` parameter (exposed explicitly here for clarity)
        the column names to load, as list. Can be also a callable
        accepting a column name and returning True/False (keep/discard)
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
    dtype = dict(dtype or {})  # will be harmonized and modified inplace below:
    kwargs =  _read_csv_prepare(filepath_or_buffer, sep=sep, dtype=dtype,
                                usecols=usecols, **kwargs)
    try:
        dfr = pd.read_csv(filepath_or_buffer, **kwargs)
    except ValueError as exc:
        invalid_columns = _read_csv_inspect_failure(filepath_or_buffer, **kwargs)
        raise InvalidDataInColumn(*invalid_columns) from None

    # finalize and return
    defaults = defaults or {}
    _read_csv_finalize(dfr, dtype, defaults)
    if not isinstance(dfr.index, pd.RangeIndex):
        dfr.reset_index(drop=True, inplace=True)
    return dfr


def _read_csv_prepare(filepath_or_buffer: IOBase, **kwargs) -> dict:
    """prepare the arguments for pandas read_csv: take tha passed **kwargs
    and return a modified version of it after checking some keys and values
    """
    parse_dates = set(kwargs.pop('parse_dates', []))

    # infer `sep` and read the CSV header (dataframe columns), as some args of
    # `read_csv` (e.g. `parse_dates`) cannot contain columns not present in the flatfile
    header = []
    sep = kwargs.get('sep', None)
    nrows = kwargs.pop('nrows', None)
    if sep is None:
        kwargs.pop('sep')  # if it was None needs removal
        for _sep in [';', ',', r'\s+']:
            _header = _read_csv_get_header(filepath_or_buffer, sep=_sep, **kwargs)
            if len(_header) > len(header):
                sep = _sep
                header = _header
        kwargs['sep'] = sep
    else:
        header = _read_csv_get_header(filepath_or_buffer, **kwargs)
    if nrows is not None:
        kwargs['nrows'] = nrows

    # mix usecols with the flatfile columns just retrieved (it might speed up read):
    usecols = kwargs.pop('usecols', None)
    if callable(usecols):
        csv_columns = set(f for f in header if usecols(f))
        kwargs['usecols'] = csv_columns
    elif hasattr(usecols, "__iter__"):
        csv_columns = set(header) & set(usecols)
        kwargs['usecols'] = csv_columns
    else:
        csv_columns = set(header)

    # Set the `dtype` and `parse_dates` arguments of read_csv (see also
    # `_read_csv_finalize`)
    dtype = kwargs.pop('dtype', {})  # removed and handled later
    kwargs['dtype'] = {}
    for col in csv_columns:
        if col in dtype:
            col_dtype = _as_dtype_value(dtype[col]) # a ColumndDType value or pd.Categorical
        else:
            col_dtype = ColumnsRegistry.get_dtype(col)  # a ColumnDType value
            if col_dtype is None:
                continue
        # set the harmonized value into our dtype dict (see finalize_read_csv):
        dtype[col] = col_dtype

        if isinstance(col_dtype, pd.CategoricalDtype):
            # if `col_dtype.categories=None` or `col_dtype='category'`, then
            # `read_csv` will infer the categories from the data. Otherwise,
            # it will silently convert values not found in categories to N/A,
            # making invalid and missing values indistinguishable. To do that, we
            # set now `col_dtype` as the dtype of the categories (which must be all
            # the same type) to get missing values, checking invalid values
            # after reading:
            if col_dtype.categories is not None:
                col_dtype = get_dtype_of(*col_dtype.categories).value

        if col_dtype == ColumnDtype.int.value:
            # let `read_csv` treat ints as floats, so that we can have NaN and
            # check later if we can replace them with the column default, if set
            kwargs['dtype'][col] = ColumnDtype.float.value
        elif col_dtype == ColumnDtype.bool.value:
            # let `read_csv` infer the data type of bools by not passing a dtype at
            # all. We will check later if we can cast the values to bool, not only
            # in terms of replacing N/A with the column default, if set, but also
            # string values (e.g. 'FALSE') to valid values
            continue
        elif col_dtype == ColumnDtype.datetime.value:
            # date times in `read_csv` must be given in the `parse_dates` arg. Note
            # that, whereas missing values will still preserve the dtype and be set
            # as `NaT` (not a time), invalid datetime values will simply result in a
            # column with a more general dtype set (usually object): this will be
            # checked later
            parse_dates.add(col)
        else:
            kwargs['dtype'][col] = col_dtype

    if parse_dates:
        kwargs['parse_dates'] = list(parse_dates)

    return kwargs


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
            pd.read_csv(filepath_or_buffer , **kwargs)
        except ValueError:
            invalid_columns.append(c)
    # if no columns raised, just put everything in the message:
    return invalid_columns or cols2check


def _read_csv_finalize(
        dfr: pd.DataFrame,
        dtype: dict[str, Union[ColumnDtype, pd.CategoricalDtype]],
        defaults: dict[str, Any]):
    """Finalize `read_csv` by adjusting the values and dtypes of the given dataframe
    `dfr`, and return it

    :return: a pandas DataFrame (the same `dfr` passed as argument, with some
        modifications if needed)
    """
    # post-process:
    invalid_columns = []
    if defaults is None:
        defaults = {}
    # check dtypes correctness (actual vs expected) and try to fix mismatching ones:
    for col in dfr.columns:
        expected_dtype = dtype.get(col, None)  # ColumnDtype value or pd.CategoricalDtype
        if expected_dtype is None:
            continue
        if expected_dtype == ColumnDtype.category.value and \
                isinstance(dfr[col].dtype, pd.CategoricalDtype):
            continue
        # is expected dtype a pandas CategoricalDtype?
        expected_categories = None
        if isinstance(expected_dtype, pd.CategoricalDtype):
            if expected_dtype.categories is None:
                # categories inferred from data, no dtype to check
                continue
            expected_categories = expected_dtype
            # expected_dtype is the dtype of all categories
            expected_dtype = get_dtype_of(*expected_dtype.categories).value
        # actual dtype. NOTE: cannot be categorical (see `_read_csv_prepare`)
        actual_dtype = get_dtype_of(dfr[col])
        # check matching dtypes:
        dtype_ok = actual_dtype is not None and actual_dtype.value == expected_dtype
        do_type_cast = False
        # handle mismatching dtypes (bool and int):
        if not dtype_ok:
            if expected_dtype == ColumnDtype.int.value:
                not_na = pd.notna(dfr[col])
                values = dfr[col][not_na]
                if (values == values.astype(int)).all():  # noqa
                    dtype_ok = True
                    do_type_cast = True
            elif expected_dtype == ColumnDtype.bool.value:
                not_na = pd.notna(dfr[col])
                unique_vals = pd.unique(dfr[col][not_na])
                mapping = {}
                for val in unique_vals:
                    if isinstance(val, str):
                        if val.lower() in {'0', 'false'}:
                            mapping[val] = False
                        elif val.lower() in {'1', 'true'}:
                            mapping[val] = True
                if mapping:
                    dfr[col].replace(mapping, inplace=True)
                    unique_vals = pd.unique(dfr[col][not_na])
                if set(unique_vals).issubset({0, 1}):
                    dtype_ok = True
                    do_type_cast = True
        # if expected and actual dtypes match, set defaults (if any) and cast (if needed)
        if dtype_ok:
            #set default
            if col in defaults:
                has_default = True
                default = _cast_value(defaults[col],
                                      expected_categories or expected_dtype)
            else:
                default = ColumnsRegistry.get_default(col)
                has_default = default is not None
            if has_default:
                is_na = pd.isna(dfr[col])
                dfr.loc[is_na, col] = default
            # if we expected categories, set the categories, nut be sure that we do not
            # have invalid values (pandas automatically set them to N/A):
            if expected_categories is not None:
                is_na = pd.isna(dfr[col])
                dfr[col] = dfr[col].astype(expected_categories)
                # check that we still have the same N/A (=> all values in dfr[col] are
                # valid categories):
                is_na_after = pd.isna(dfr[col])
                if len(is_na) != len(is_na_after) or (is_na != is_na_after).any():
                    dtype_ok = False
            elif do_type_cast:  # type-cast bool and int columns, if needed:
                try:
                    dfr[col] = dfr[col].astype(expected_dtype)
                except (ValueError, TypeError):
                    dtype_ok = False

        if not dtype_ok:
            invalid_columns.append(col)

    if invalid_columns:
        raise InvalidDataInColumn(*invalid_columns)

    return dfr


def _val2str(val):
    """Return the string representation of the given val.
    See also :ref:`query` for consistency (therein, we expose functions
    and variables for flatfile selection)"""
    if isinstance(val, (date, datetime)):
        return f'datetime("{val.isoformat()}")'
    elif val is True or val is False:
        return str(val).lower()
    elif isinstance(val, str):
        # do not import json, just delegate Python:
        return f"{val}" if '"' not in val else val.__repr__()
    else:
        return str(val)


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
    rupture = 'Rupture parameter'
    site = 'Site parameter'
    distance = 'Distance measure'
    intensity = 'Intensity measure'


class ColumnDtype(Enum):
    """Enum where members are registered dtype names (see ColumnRegistry) and
    values are the pandas counterpart
    """
    float = "float"
    int = "int"
    bool = "bool"
    datetime = "datetime64"  # NOTE: datetime64 is actually not used in pandas read_csv,
    # We set here a unique value identifying date time types, and use the numpy value
    # "datetime64" (see `numpy.sctypeDict.keys()` for a list of supported names)
    str = "string"  # https://pandas.pydata.org/docs/user_guide/text.html
    category = "category"


def get_dtype_of(*item: Union[int, float, datetime, bool, str,
                 np.array, pd.Series, PandasArray,
                 type[int, float, datetime, bool, str],
                 np.dtype, ExtensionDtype]) -> Union[ColumnDtype, None]:
    """Return the dtype of the given argument, as member of the ColumnDtype Enum,
    or None if no associated dtype is found.
    If several arguments are passed and the arguments are not all the same dtype,
    returns None
    To get the ColumnDtype Enum from the returned value, call `ColumnDType(value)`

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
            obj = obj.type
        # define a 'is_type' function:
        is_type = issubclass if isinstance(obj, type) else isinstance
        if is_type(obj, (bool, np.bool_)):
            # Note: bool is a subclass of int in Python: this 'if' before any int check
            c_dtype = ColumnDtype.bool
        elif is_type(obj, (int, np.integer)):
            c_dtype = ColumnDtype.int
        elif is_type(obj, (float, np.floating)):
            c_dtype = ColumnDtype.float
        elif is_type(obj, (datetime, np.datetime64)):
            c_dtype = ColumnDtype.datetime
        elif is_type(obj, (str, np.str_)):
            c_dtype = ColumnDtype.str
        elif is_type(obj, (pd.CategoricalDtype.type,  # noqa
                           pd.core.arrays.categorical.Categorical)):
            c_dtype = ColumnDtype.category
        else:
            return None
        if ret_type is None:
            ret_type = c_dtype
        elif ret_type != c_dtype:
            return None
    return ret_type


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
    def get_dtype(column: str) -> Union[None, str, pd.CategoricalDtype]:
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
        props['dtype'] = _as_dtype_value(props['dtype'])
    if 'default' in props:
        props['default'] = _cast_value(props['default'], props['dtype'] )
    for k in ("<", "<=", ">", ">="):
        if k in props:
            props[k] = _cast_value(props[k], props['dtype'] )
    return props


def _replace(name: str):
    return name if not name.startswith('SA(') else 'SA'


def _as_dtype_value(dtype: Union[str, pd.CategoricalDtype, Collection]) \
        -> Union[str, pd.CategoricalDtype]:
    """Return a dtype that is suitable to be used as data type in pandas read_csv,
    i.e., either a `ColumnDtype` value (str) or a pandas `CategoricalDtype` (with all
    categories of the same type)
    """
    try:
        return ColumnDtype[dtype].value
    except (TypeError, KeyError):
        if isinstance(dtype, pd.CategoricalDtype):
            cat = dtype
        else:
            try:
                cat = pd.CategoricalDtype(dtype)
            except (TypeError, ValueError):
                if not isinstance(dtype, pd.CategoricalDtype):
                    raise ValueError(f'Invalid data type: {str(dtype)}')
                cat = dtype
        if len(set(type(v) for v in cat.categories)) != 1:
            raise ValueError(f'Invalid categorical data type, categories '
                             f'must be all of the same type')
        return cat


def _cast_value(val: Any, dtype_value: Union[str, pd.CategoricalDtype]) -> Any:
    """Cast the given value to the given dtype, raise ValueError if unsuccessful

    :param val: any Python object
    :param dtype_value: either a `ColumnDtype` value (str)
        or pandas `CategoricalDtype` object.
    """
    if isinstance(dtype_value, pd.CategoricalDtype):
        if val in dtype_value.categories:
            return val
        raise ValueError(f'Not in supplied categories: {str(val)}')

    expected_dtype = ColumnDtype(dtype_value)
    if expected_dtype == ColumnDtype.datetime and isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    actual_dtype = get_dtype_of(val)
    if actual_dtype == expected_dtype:
        return val
    if expected_dtype == ColumnDtype.float and actual_dtype == ColumnDtype.int:
        return float(val)
    raise ValueError(f'Not a {dtype_value}: {str(val)}')


