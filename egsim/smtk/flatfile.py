"""Flatfile root module"""

from __future__ import annotations

from io import IOBase, StringIO
from os.path import join, dirname
from datetime import datetime
import re
import tokenize

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

from egsim.smtk.registry import sa_period
from egsim.smtk.validation import InputError, ConflictError

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
    dtypes: dict[str, Union[str, list]] = None,
    defaults: dict[str, Any] = None,
    csv_sep: str = None,
    **kwargs
) -> pd.DataFrame:
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
        check and cast column data. Standard flatfile columns should not be present,
        otherwise the value provided in this dict will overwrite the registered dtype,
        if set. Columns in `dtypes` not present in the file will be ignored.
        Dict values can be 'int', 'bool', 'float', 'str', 'datetime', 'category'`,
        list: 'category' and lists denote data that can take only a limited amount of
        possible values and should be mostly used with string data for saving space
        (with "category", pandas will infer the possible values from the data. In this
        case, note that with CSV files each category will be of type `str`).
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

        # harmonize dtypes with only ColumnDtype enums or pd.,CategoricalDtype objects:
        # also put in kwargs['dtype'] the associated dtypes compatible with `read_csv`:
        kwargs['dtype'] = kwargs.get('dtype') or {}
        dtypes_raw = dtypes or {}
        dtypes = {}
        for c, v in dtypes_raw.items():
            if not isinstance(v, str):
                try:
                    v = pd.CategoricalDtype(v)
                    assert get_dtype_of(v.categories) is not None
                except (AssertionError, TypeError, ValueError):
                    raise ValueError(f'{c}: categories must be of the same type')
            else:
                try:
                    v = ColumnDtype[v]
                except KeyError:
                    raise ValueError(f'{c}: invalid dtype {v}')
            dtypes[c] = v
            # ignore bool int and date-times, we will parse them later
            if v in (ColumnDtype.bool, ColumnDtype.int, ColumnDtype.datetime):
                continue
            kwargs['dtype'][c] = v.name if isinstance(v, ColumnDtype) else v  # noqa

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
    args = [
        'header', 'names', 'skip_blank_lines', 'skipinitialspace', 'engine',
        'lineterminator', 'quotechar', 'quoting', 'doublequote', 'escapechar',
        'comment', 'dialect', 'delim_whitespace'
    ]
    _kwargs = {k: kwargs[k] for k in args if k in kwargs}
    _kwargs['nrows'] = 0  # read just header
    _kwargs['sep'] = sep
    ret = pd.read_csv(filepath_or_buffer, **_kwargs).columns  # noqa
    if _pos is not None:
        filepath_or_buffer.seek(_pos)
    return ret


def validate_flatfile_dataframe(
    dfr: pd.DataFrame,
    extra_dtypes: dict[str, Union[ColumnDtype, pd.CategoricalDtype]] = None,  # noqa
    extra_defaults: dict[str, Any] = None,
    mixed_dtype_categorical='raise'
):
    """
    Validate the flatfile dataframe checking data types, conflicting column names,
    or missing mandatory columns (e.g. IMT related columns). This method raises
    or returns None on success

    :param dfr: the flatfile, as pandas DataFrame
    :param extra_dtypes: dict of column names mapped to the desired data type.
        Standard flatfile columns should not to be present (unless for some reason
        their dtype must be overwritten). pd.CategoricalDtype categories must be
        all the same type (this is supposed to have been checked beforehand)
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
        else:
            xp_dtype = column_dtype(col)

        if xp_dtype is None:
            continue

        if col in extra_dtypes:
            default = extra_defaults.get(col)
            if default is not None:
                default = cast_to_dtype(default, xp_dtype, mixed_dtype_categorical)
        else:
            default = column_default(col)
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
        aliases = set(column_aliases(c))
        if len(aliases & ff_cols) > 1:
            raise IncompatibleColumnError(list(aliases & ff_cols))
        if not has_imt and column_type(c) == ColumnType.intensity:
            has_imt = True

    if not has_imt:
        raise MissingColumnError('No IMT column found')

    return dfr


def optimize_flatfile_dataframe(dfr: pd.DataFrame):
    """
    Optimize the given dataframe by replacing str column with
    categorical (if the conversion saves memory)
    """
    for c in dfr.columns:
        if get_dtype_of(dfr[c]) == ColumnDtype.str:
            cat_dtype = dfr[c].astype('category')
            if cat_dtype.memory_usage(deep=True) < dfr[c].memory_usage(deep=True):
                dfr[c] = cat_dtype


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
    # dtype of only-string Series, but for which `pd.api.types.is_string_dtype` is
    # False:
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
    """
    Cast the given value to the given dtype, raise ValueError if unsuccessful

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


def column_exists(column: str) -> bool:
    """
    Return whether the given argument is a registered flatfile column name
    (including aliases. 'SA(<period>)' is valid and will default to 'SA')
    """
    return column in ColumnPropertyRegistry.load_from_yaml()



def column_names(*, type: Union[str, ColumnType]='all') -> set[str]:  # noqa
    """
    Return a set of strings with all column names, filtered by the type parameter
    (default : "all", no filter). Spectral acceleration, if returned, will be
    given with no arguments, i.e. "SA", not "SA(...)".

    :param type: 'all' (all columns types), None (columns with no type defined) or
        any name or member of the ColumnDtype Enum (i.e. `ColumnType.rupture` or
        simply "rupture")
    """
    if isinstance(type, str) and type != 'all':
        type = ColumnType[type]  # noqa
    return {
        n for n, props in ColumnPropertyRegistry.load_from_yaml().items()
        if type == 'all' or props.get('type', None) == type
    }


def column_type(column: str) -> Union[ColumnType, None]:
    """
    Return the `ColumnType` enum item of the given column, or None.
    if `column` is 'SA(<period>)', it will default to 'SA'
    """
    return ColumnPropertyRegistry.get_properties(column).get('type', None)


def column_default(column: str) -> Union[None, Any]:
    """
    Return the default of the given column name (used to fill missing data), or
    None if no default is set. if `column` is 'SA(<period>)', it will default to 'SA'
    """
    return ColumnPropertyRegistry.get_properties(column).get('default', None)


def column_aliases(column: str) -> tuple[str]:
    """
    Return all possible names of the given column, as tuple set of strings
    where the first element is assured to be the flatfile default column name
    (primary name) and all remaining the secondary names. The tuple will be composed
    of `column` alone if `column` does not have registered aliases.
    if `column` is 'SA(<period>)', it will default to 'SA'
    """
    return ColumnPropertyRegistry.get_properties(column).get('alias', (column,))


def column_help(column: str) -> str:
    """
    Return the help (description) of the given column name, or ''.
    If `column` is 'SA(<period>)', it will default to 'SA'
    """
    return ColumnPropertyRegistry.get_properties(column).get('help', "")


def column_dtype(column: str) -> Union[ColumnDtype, pd.CategoricalDtype, None]:
    """
    Return the data type of the given column name, as None (no data type set),
    `ColumnDtype` Enum item, or pands `CategoricalDtype` object (in this case
    `column_dtype(...).categories` will list the possible values that the column can
    take). As such `ColumnDtype.category` is never returned.
    If `column` is 'SA(<period>)', it will default to 'SA'
    """
    return ColumnPropertyRegistry.get_properties(column).get('dtype', None)



class ColumnPropertyRegistry:
    """Column property registry (loaded from underlying YAML file)"""

    # cache storage of the data in the YAML:
    _flatfile_columns_props: dict = None  # noqa

    # YAML file path:
    _flatfile_columns_path = join(dirname(__file__), 'flatfile_columns.yaml')

    @classmethod
    def get_properties(cls, column:str) -> dict:
        props = cls.load_from_yaml()
        if column not in props:
            if sa_period(column) is not None:
                column = 'SA'
        return props.get(column, {})

    @classmethod
    def load_from_yaml(cls, cache=True) -> dict:
        """
        Load the flatfile metadata from the associated YAML file into a Python dict
        """
        if cache and cls._flatfile_columns_props is not None:
            return cls._flatfile_columns_props
        _cols = {}
        with open(cls._flatfile_columns_path) as fpt:
            for col_name, props in yaml_load(fpt, SafeLoader).items():
                # harmonize props:
                aliases = props.get('alias', [])
                if isinstance(aliases, str):
                    aliases = [aliases]
                props['alias'] = (col_name,) + tuple(aliases)
                if props.get('type') is not None:
                    props['type'] = ColumnType[props['type']]
                if isinstance(props.get('dtype'), str):
                    props['dtype'] = ColumnDtype[props['dtype']]
                elif props.get('dtype') is not None:
                    props['dtype'] = pd.CategoricalDtype(props['dtype'])
                if 'default' in props:
                    props['default'] = cast_to_dtype(props['default'], props['dtype'])
                # limits are not implemented. Uncomment in case:
                # for k in ("<", "<=", ">", ">="):
                #     if k in props:
                #         props[k] = cast_to_dtype(props[k], props['dtype'])

                # add all aliases mapped to the relative properties:
                for c_name in props['alias']:
                    _cols[c_name] = props
        if cache and cls._flatfile_columns_props is None:
            cls._flatfile_columns_props = _cols
        return _cols


# Exceptions:

class FlatfileError(InputError):
    """
    Subclass of :class:`smtk.validators.InputError` for describing flatfile
    errors (specifically, column errors). See subclasses for details. Remember
    that `str(FlatfileError(arg1, arg2, ...)) = str(arg1) + ", " + str(arg2) + ...
    """
    pass


class MissingColumnError(FlatfileError, AttributeError, KeyError):
    """
    MissingColumnError. It inherits also from AttributeError and
    KeyError to be compliant with pandas and OpenQuake"""
    pass


class IncompatibleColumnError(ConflictError, FlatfileError):
    pass


class ColumnDataError(FlatfileError, ValueError, TypeError):
    pass


class FlatfileQueryError(FlatfileError):
    """Error while filtering flatfile rows via query expressions"""

    pass


# flatfile query expression

def query(
    flatfile: pd.DataFrame, query_expression: str, raise_no_rows=True
) -> pd.DataFrame:
    """
    Call `flatfile.query` with some utilities:
     - ISO-861 strings (e.g. "2006-01-31") will be converted to datetime objects
     - booleans can be also lower case (true or false)
     - Some series methods can be called with the dot notation [col].[method]:
       notna(), median(), mean(), min(), max()
    """
    # Setup custom keyword arguments to dataframe query
    __kwargs = {
        'local_dict': {},
        'global_dict': {},  # 'pd': pd, 'np': np
        # add support for bools lower case (why doesn't work if set in local_dict?):
        'resolvers': [prepare_expr(query_expression, flatfile.columns)]
    }
    # evaluate expression:
    try:
        ret = flatfile.query(query_expression, **__kwargs)
    except Exception as exc:
        raise FlatfileQueryError(str(exc)) from None
    if raise_no_rows and ret.empty:
        raise FlatfileQueryError('no rows matching query')
    return ret


def prepare_expr(expr: str, columns: list[str]) -> dict:
    """
    Prepare the given selection expression to add a layer of protection
    to potentially dangerous untrusted input. Returns a dict to be used as
    `resolvers` argument in `pd.Dataframe.query`
    """
    # valid names:
    cols = set(columns)
    # backtick-quoted column names is pandas syntax. Check them now and replace them
    # with a valid name (replacement_col):
    replacement_col = '_'
    while replacement_col in columns:
        replacement_col += '_'
    new_expr = re.sub(f'`.*?`', replacement_col, expr)
    if new_expr != expr:
        # check that columns are correct
        cols.add(replacement_col)
        for match in re.finditer(f'`.*?`', expr):
            if match.group()[1:-1] not in columns:
                raise FlatfileQueryError(f'undefined column "{match.group()[1:-1]}"')

    meth_placeholder = replacement_col + '_'
    while meth_placeholder in cols:
        meth_placeholder += '_'
    new_expr = re.sub(
        r'\.\s*(notna|mean|std|median|min|max)\s*\(\s*\)',
        f' {meth_placeholder} ',
        new_expr
    )

    # analyze string and return the replacements to be done:
    replacements = {}
    toknums = []
    tokvals = []  # either str, or the int tokenize.NEWLINE
    # allowed sequences:
    allowed_names = cols | {'true', 'True', 'false', 'False'}
    token_generator = tokenize.generate_tokens(StringIO(new_expr).readline)
    for toknum, tokval, start, _, _ in token_generator:
        last_toknum = toknums[-1] if len(toknums) else None
        last_tokval = tokvals[-1] if len(tokvals) else None

        if toknum == tokenize.NAME:
            if tokval not in cols:
                if tokval == 'true':
                    replacements[tokval] = True
                elif tokval == 'false':
                    replacements[tokval] = False
        elif toknum == tokenize.STRING:
            try:
                dtime = datetime.fromisoformat(tokval[1:-1])
                replacements[tokval] = dtime
            except (TypeError, ValueError):
                pass

        skip_check_sequence = tokval == meth_placeholder and last_tokval in cols
        if not skip_check_sequence:
            if toknum == tokenize.NAME and tokval not in allowed_names:
                raise FlatfileQueryError(f'undefined column "{tokval}"')
            if not valid_expr_sequence(last_toknum, last_tokval, toknum, tokval):
                if last_toknum is None:
                    raise FlatfileQueryError(f'invalid first chunk {tokval}')
                elif last_toknum == tokenize.NEWLINE:
                    raise FlatfileQueryError(f'multi-line expression not allowed')
                elif toknum == tokenize.NEWLINE:
                    raise FlatfileQueryError(f'invalid last chunk "{last_tokval}"')
                else:
                    raise FlatfileQueryError(f'invalid sequence '
                                             f'"{last_tokval}" + "{tokval}"')

        tokvals.append(tokval)
        toknums.append(toknum)

    return replacements


def valid_expr_sequence(tok_num1: int, tok_val1: str, tok_num2: int, tok_val2: str):
    """Return true if the given sequence of two tokens is valid"""

    OP, STRING, NAME, NUMBER, NEWLINE, EOM = (
        tokenize.OP,
        tokenize.STRING,  # noqa
        tokenize.NAME,
        tokenize.NUMBER,
        tokenize.NEWLINE,
        tokenize.ENDMARKER
    )
    if tok_num1 is None:
        if tok_num2 == OP:
            return tok_val2 in '(~'
        return tok_num2 in {NAME, NUMBER, STRING}
    elif tok_num1 == NEWLINE:
        return tok_num2 == EOM
    elif tok_num2 == NEWLINE:
        return tok_num1 in {NUMBER, NAME, STRING} or tok_val1 == ')'
    elif (tok_num1, tok_num2) == (OP, OP):
        return (
            tok_val1 + tok_val2 in
            {'(~', '~(', '((', '~~', '))', '&(', '|(', ')|', ')&'}
        )
    elif (tok_num1, tok_num2) == (NAME, OP):
        return tok_val2 in {'==', '!=', '<', '<=', '>', '>=', ')', '+', '-', '*', '/'}
    elif (tok_num1, tok_num2) == (OP, NAME):
        return tok_val1 in {'==', '!=', '<', '<=', '>', '>=', '(', '+', '-', '*', '/'}
    elif (tok_num1, tok_num2) == (NUMBER, OP):
        return tok_val2 in {'==', '!=', '<', '<=', '>', '>=', ')', '+', '-', '*', '/'}
    elif (tok_num1, tok_num2) == (OP, NUMBER):
        return tok_val1 in {'==', '!=', '<', '<=', '>', '>=', '(', '+', '-', '*', '/'}
    elif (tok_num1, tok_num2) == (STRING, OP):
        return tok_val2 in {'==', '!=', '<', '<=', '>', '>=', ')'}
    elif (tok_num1, tok_num2) == (OP, STRING):
        return tok_val1 in {'==', '!=', '<', '<=', '>', '>=', '('}
    else:
        return False
