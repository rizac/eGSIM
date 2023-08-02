"""flatfile pandas module"""

from datetime import datetime
from enum import Enum
from os.path import join, dirname
import re
from openquake.hazardlib import imt
from openquake.hazardlib.gsim.base import GMPE
from pandas.core.indexes.numeric import IntegerIndex
from scipy.interpolate import interp1d

from typing import Union, Callable, Any, Iterable

import yaml
import numpy as np
import pandas as pd
from openquake.hazardlib.scalerel import PeerMSR
from openquake.hazardlib.contexts import RuptureContext

from ..smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14


class ColumnType(Enum):
    """Flatfile column type / family (to know a type from a specific column, use
    `column_type[column]`, which returns an item of this enum)
    """
    rupture_parameter = 'r'
    site_parameter = 's'
    distance_measure = 'd'
    intensity_measure = 'i'
    unknown = 'u'


class ColumnDtype(Enum):
    """Flatfile column **data** type enum. Enum names are the string values to be used
    as descriptors (e.g., the supported values of a column `dtype` in the YAML file.
    Note that categorical dtypes have to be given as list), enum values are the relative
    Python/numpy classes (NOTE: Python native class must be the 1st ELEMENT)
    """
    # Note: to get if the dtype of flatfile column `c` (pandas Series) is supported:
    # isinstance(c.dtype, pd.CategoricalDtype) or \
    #     any(issubclass(c.dtype.type, e.value) for e in ColumnDtype)
    float = float, np.floating
    int = int, np.integer
    bool = bool, np.bool_
    datetime = datetime, np.datetime64
    str = str, np.str_, np.object_


def _check_column_metadata(column: dict[str, Any]) -> dict[str, Any]:
    """checks the Column metadata dict issued from the YAML flatfile"""
    # convert type to corresponding Enum:
    column.setdefault('type', ColumnType.unknown.value)
    try:
        column['type'] = ColumnType(column['type']).name
    except KeyError:
        raise ValueError(f"Invalid type: {column['type']}")

    if column['type'] == ColumnType.intensity_measure.name and 'alias' in column:
        raise ValueError(f"Intensity measure columns cannot have an alias")

    # perform some check on the data type consistencies:
    bounds_are_given = 'bounds' in column
    default_is_given = 'default' in column

    # check dtype null and return in case:
    if 'dtype' not in column:
        if bounds_are_given or default_is_given:
            raise ValueError(f"With `dtype` null or missing, metadata cannot have "
                             f"the keys `default` and `bounds`")
        return column

    dtype = column['dtype']

    # handle categorical data:
    if isinstance(dtype, (list, tuple)):  # categorical data type
        if not all(any(isinstance(_, d.value) for d in ColumnDtype) for _ in dtype):
            raise ValueError(f"Invalid data type(s) in provided categorical data")
        if len(set(type(_) for _ in dtype)) != 1:
            raise ValueError(f"Categorical values must all be of the same type, found: "
                             f"{set(type(_) for _ in dtype)}")
        if bounds_are_given:
            raise ValueError(f"bounds cannot be provided with "
                             f"categorical data type")
        if default_is_given and column['default'] not in dtype:
            raise ValueError(f"default is not in the list of possible values")
        column['dtype'] = pd.CategoricalDtype(dtype)
        return column

    # handle non-categorical data with a base dtype:
    try:
        py_dtype = ColumnDtype[dtype].value[0]
    except KeyError:
        raise ValueError(f"Invalid data type: {dtype}")

    # check bounds:
    if bounds_are_given:
        try:
            column['bounds'] = _parse_bounds_str(column['bounds'], py_dtype)
        except Exception as exc:
            raise ValueError(f"invalid bounds: {str(exc)}")


    # check default value:
    if default_is_given:
        default = column['default']
        # type promotion (int is a valid float):
        if py_dtype == float and isinstance(column['default'], int):
            column['default'] = float(default)
        elif not isinstance(default, py_dtype):
            raise ValueError(f"default must be of type {dtype}")

    return column


def _parse_bounds_str(bounds_string, py_dtype):
    bounds = []
    for chunk in bounds_string.split(','):
        chunk = chunk.strip()
        symbol = chunk[:2] if chunk[:2] in ('>=', '<=') else chunk[:1]
        assert symbol in ('>', '<', '>=', '<='), 'comparison operator should be ' \
                                                 '<, >, <= or >='
        try:
            value = yaml.safe_load(chunk[len(symbol):])
        except Exception:
            raise ValueError(f'Invalid bound: {chunk[len(symbol):]}')
        if py_dtype is float and isinstance(value, int):
            value = float(value)
        if not isinstance(value, py_dtype):
            raise ValueError(f'Invalid bound type (expected {str(py_dtype)}): '
                             f'{str(value)}')
        bounds.append([symbol, value])
    return bounds


_ff_metadata_path = join(dirname(__file__), 'flatfile-metadata.yaml')


# global variables (initialized below from YAML file):
column_type: dict[str, str] = {} # flatfile column -> one of ColumnType names
# the above dict contains ALL defined flatfile columns as keys. All other globals
# below do not assure that (see code below)
column_dtype: dict[str, Union[str, pd.CategoricalDtype]] = {} # flatfile column -> data type name
column_default: dict[str, Any] = {} # flatfile column -> default value when missing
column_required: set[str] = set() # required flatfile column names
column_alias: dict[str, str] = {} # Gsim required attr. name -> flatfile column name
column_help: dict[str, str] = {}  # flatfile column -> Column type


# read YAML and setup custom attributes:
with open(_ff_metadata_path) as fpt:
    for name, props in yaml.safe_load(fpt).items():
        try:
            props = _check_column_metadata(props)
        except Exception as exc:
            raise ValueError(f'Error in metadata for column "{name}": {str(exc)}')
        if name in column_type:
            raise ValueError(f'Error in metadata for column "{name}": multiple '
                             f'instances of the column provided')
        column_type[name] = props['type']
        if props.get('help', ''):
            column_help[name] = props['help']
        if 'dtype' in props:
            column_dtype[name] = props['dtype']
        if 'default' in props:
            column_default[name] = props['default']
        if props.get('required', False):
            column_required.add(name)
        if 'alias' in props:
            if props['alias'] in column_type:
                raise ValueError(f'Error in metadata for column "{name}": alias '
                                 f"'{props['alias']}' already defined as column name")
            if props['alias'] in column_alias:
                raise ValueError(f'Error in metadata for column "{name}": alias '
                                 f"'{props['alias']}' already defined")
            column_alias[props['alias']] = name


# def is_imt(column_name: str, require_sa_with_periods=True):
#     if column_type[column_name] != ColumnType.intensity_measure.name:
#         if column_name.startswith('SA('):
#             try:
#                  imt.from_string(column_name)
#                  return True
#             except Exception:  # noqa
#                 pass
#         return False
#     return True if column_name != 'SA' or not require_sa_with_periods else False


############
# Flatfile #
############


def read_flatfile(filepath_or_buffer: str, sep: str = None) -> pd.DataFrame:
    """
    Read a flat file into pandas DataFrame from a given CSV file

    :param filepath_or_buffer: str, path object or file-like object of the CSV
        formatted data. If string, compressed files are also supported
        and inferred from the extension (e.g. 'gzip', 'zip')
    :param sep: the separator (or delimiter). None means 'infer' (it might
        take more time)
    """
    return read_csv(filepath_or_buffer, sep=sep, dtype=column_dtype,
                    defaults=column_default,
                    required=column_required)


missing_values = ("", "null", "NULL", "None",
                  "nan", "-nan", "NaN", "-NaN",
                  "NA", "N/A", "n/a",  "<NA>", "#N/A", "#NA")


def read_csv(filepath_or_buffer: str,
             sep: str = None,
             dtype: dict[str, Union[str, pd.CategoricalDtype]]  = None,
             defaults: dict[str, Any] = None,
             required: set[str] = None,
             usecols: Union[list[str], Callable[[str], bool]] = None,
             **kwargs) -> pd.DataFrame:
    """
    Read a flat file into pandas DataFrame from a given CSV file

    :param filepath_or_buffer: str, path object or file-like object of the CSV
        formatted data. If string, compressed files are also supported
        and inferred from the extension (e.g. 'gzip', 'zip')
    :param sep: the separator (or delimiter). None means 'infer' (it might
        take more time)
    :param usecols: pandas `read_csv` parameter (exposed for clarity) column
        names to load, as list. Can be also a callable
        accepting a column name and returning True/False (keep/discard)
    :param dtype: dict of column names mapped to the data type:
        either 'int', 'bool', 'float', 'str', 'datetime', 'category'`, list, tuple or
        pandas `CategoricalDtype` (the last four data types are for data that can take
        only a limited amount of possible values and should be used mostly with string
        data as it might save a lot of memory. With "category", pandas will infer the
        number of categories from the data, with all other the categories are
        specified and the column will replace values nopt found in categories with
        missing values (NA) for categories not found in categories).
        Columns of type 'int' and 'bool' do not support NA data and must have a
        default in `defaults`, otherwise NA data will be replaced with 0 for int
        and False for bool.
    :param defaults: a dict of flat file column names mapped to the default
        value for missing/NA data. Defaults will be set AFTER the underlying
        `pandas.read_csv` is called. Note that if int and bool columns are specified in
        `dtype`, then a default is set for those columns anyway (0 for int, False for
        bool), because those data types do not support NA in numpy/pandas
    :param required: set of flat file column names that must be present
        in the flatfile. ValueError will be raised if this condition is not satisfied
    :param kwargs: additional keyword arguments not provided above that can be
        passed to `pandas.read_csv`. 'header', 'delim_whitespace' and 'names'
        should not be provided as they might be overwritten by this function

    :return: pandas DataFrame representing a Flat file
    """
    kwargs.setdefault('na_values', missing_values)
    kwargs.setdefault('keep_default_na', False)
    kwargs.setdefault('encoding', 'utf-8-sig')
    kwargs.setdefault('comment', '#')
    kwargs.setdefault('true_values', ['1'])
    kwargs.setdefault('false_values', ['0'])
    if sep is None:
        sep = _infer_csv_sep(filepath_or_buffer)
    kwargs['sep'] = sep
    datetime_columns = set(kwargs.pop('parse_dates', []))

    # initialize the defaults dict if None and needs to be populated:
    if defaults is None:
        defaults = {}
    if dtype is None:
        dtype = {}

    # `dtype` will be split into several `dict`s:

    # `dtype` entries that can not be passed to `pd.read_csv` (e.g. bool, int, float)
    # because they raise errors that we want to handle after reading the csv, will be
    # put here:
    post_dtype = {}
    # `dtype` entries that can be passed to `pd.read_csv` ('category', 'str', 'datetime')
    # will be put here (or in `datetime_columns`):
    pre_dtype = {}
    # Also, convert categorical dtypes into their categories dtype, and put categorical data
    # in a separate dict
    categorical_dtypes = {}
    for col, col_dtype in dtype.items():
        if isinstance(col_dtype, (list, tuple)):  # covert lists and tuples beforehand
            col_dtype = categorical_dtypes[col] = pd.CategoricalDtype(col_dtype)
        if isinstance(col_dtype, pd.CategoricalDtype):
            values_dtype = col_dtype.categories.dtype.type
            # get the column data type (string) from the categories data type,
            # (using ColumnDtype):
            col_dtype_name: str = ''
            for c_dtype in ColumnDtype:
                if issubclass(values_dtype, c_dtype.value):
                    col_dtype_name = c_dtype.name
                    break
            if not col_dtype_name:
                raise ValueError(f'Column "{col}": unsupported type {str(values_dtype)} '
                                 f'in categorical values')
            # categorical data with str values can be safely passed to read_csv:
            if col_dtype_name == ColumnDtype.str.name:
                pre_dtype[col] = col_dtype
                continue
            # categorical data with non-str values will be stored in categorical_dtypes:
            categorical_dtypes[col] = col_dtype
            # and their string repr (col_dtype_name) handled "normally" few lines below:
            col_dtype = col_dtype_name

        if col_dtype == 'category':
            categorical_dtypes[col] = dtype[col]
        elif col_dtype == ColumnDtype.str.name:
            pre_dtype[col] = dtype[col]
        elif col_dtype == ColumnDtype.datetime.name:
            datetime_columns.add(col)
        else:
            post_dtype[col] = col_dtype

    # Read flatfile:
    try:
        dfr = pd.read_csv(filepath_or_buffer, dtype=pre_dtype, usecols=usecols,
                          parse_dates=list(datetime_columns), **kwargs)
    except ValueError as exc:
        raise ValueError(f'Error reading the flatfile: {str(exc)}')

    dfr_columns = set(dfr.columns)
    # check required columns first:
    if required and required - dfr_columns:
        missing = sorted(required - dfr_columns)
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")

    # check dtypes correctness (in few cases try to cast, e.g. int bool), avoid
    # already processed dtypes (read_csv_dtypes)
    invalid_columns = []
    for col in set(post_dtype) & dfr_columns:
        # check all data type here because passing them to dtype above would raise
        # (except CategoricalDtype)
        expected_col_dtype_name:str = post_dtype[col]
        col_dtype = dfr[col].dtype.type
        if issubclass(col_dtype, ColumnDtype[expected_col_dtype_name].value):
            continue

        # convert int columns that should be float:
        if expected_col_dtype_name == ColumnDtype.float.name:  # "float"
            if issubclass(col_dtype, ColumnDtype.int.value):
                dfr[col] = dfr[col] .astype(float)
                continue
        # try to convert float columns that should be int:
        if expected_col_dtype_name == ColumnDtype.int.name:   # "int"
            if issubclass(col_dtype, ColumnDtype.float.value):
                series = dfr[col].copy()
                na_values = pd.isna(series)
                series.loc[na_values] = defaults.pop(col, 0)
                try:
                    series = series.astype(int)
                    if (dfr[col][~na_values] == series[~na_values]).all():  # noqa
                        dfr[col] = series
                        continue
                except Exception:  # noqa
                    pass
        # try to convert str/int/float columns that should be bool:
        if expected_col_dtype_name == ColumnDtype.bool.name:  # "bool"
            new_values = None
            if issubclass(col_dtype, ColumnDtype.int.value):
                new_values = dfr[col]
                if sorted(pd.unique(new_values)) != [0, 1]:
                    new_values = None
            elif issubclass(col_dtype, ColumnDtype.int.value):
                na_values = pd.isna(dfr[col])
                new_values = dfr[col]
                new_values.loc[na_values] = defaults.pop(col, False)
                if sorted(pd.unique(new_values)) != [0, 1]:
                    new_values = None
            elif issubclass(col_dtype, ColumnDtype.str.value):
                na_values = pd.isna(dfr[col])
                new_values = dfr[col].astype(str).str.lower()
                new_values.loc[na_values] = defaults.pop(col, False)
                true_values = ['true'] + list(kwargs.get('true_values', []))
                new_values.loc[new_values.isin(true_values)] = True
                false_values = ['false'] + list(kwargs.get('false_values', []))
                new_values.loc[new_values.isin(false_values)] = False
            if new_values is not None:
                try:
                    dfr[col] = new_values.astype(bool)
                    continue
                except Exception:  # noqa
                    pass
        invalid_columns.append(col)

    # set categorical columns:
    for col in set(categorical_dtypes) & dfr_columns:
        try:
            dfr[col] = dfr[col].astype(categorical_dtypes[col])
        except Exception:  # noqa
            invalid_columns.append(col)

    if invalid_columns:
        raise ValueError(f'Invalid values in column: {", ".join(invalid_columns)}')

    # set defaults:
    invalid_defaults = []
    for col in set(defaults) & set(dfr.columns):
        pre_dtype = dfr[col].dtype
        try:
            dfr.loc[dfr[col].isna(), col] = defaults[col]
            if dfr[col].dtype == pre_dtype:
                continue
        except Exception:  # noqa
            pass
        invalid_defaults.append(col)

    return dfr


def _infer_csv_sep(filepath_or_buffer: str) -> str:
    """Prepares the CSV for reading by inspecting the header and inferring the
    separator `sep` returning it.

    :param filepath_or_buffer: str, path object or file-like object. If it has
        the attribute `seek` (e.g., file like object like `io.BytesIO`, then
        `filepath_or_buffer.seek(0)` is called before returning (reset the
        file-like object position at the start of the stream)
    """
    # infer separator: pandas suggests to use the engine='python' argument,
    # but this takes approx 4.5 seconds with the ESM flatfile 2018
    # whereas the method below is around 1.5 (load headers and count).
    # So, try to read the headers only with comma and semicolon, and chose the
    # one producing more columns:
    comma_cols = _read_csv_header(filepath_or_buffer, sep=',')
    semicolon_cols = _read_csv_header(filepath_or_buffer, sep=';')
    if len(comma_cols) > 1 and len(comma_cols) >= len(semicolon_cols):
        return ','
    if len(semicolon_cols) > 1:
        return ';'

    # try with spaces:
    space_cols = _read_csv_header(filepath_or_buffer, sep=r'\s+')
    if len(space_cols) > max(len(comma_cols), len(semicolon_cols)):
        return r'\s+'

    raise ValueError('CSV separator could not be inferred by trying '
                     '",", ";" and "\\s+" (whitespaces)')


def _read_csv_header(filepath_or_buffer, sep: str, reset_if_stream=True) -> pd.Index:
    """Reads the csv header and return a pandas Index (iterable) of column names

    :param filepath_or_buffer: str, path object or file-like object. If it has
        the attribute `seek` (e.g., file like object like `io.BytesIO`, then
        `filepath_or_buffer.seek(0)` is called before returning (reset the
        file-like object position at the start of the stream)
    """
    columns = pd.read_csv(filepath_or_buffer, nrows=0, sep=sep).columns
    if reset_if_stream and hasattr(filepath_or_buffer, 'seek'):
        filepath_or_buffer.seek(0)
    return columns


def query(flatfile: pd.DataFrame, query_expression: str) -> pd.DataFrame:
    """Call `flatfile.query` with some utilities:
     - datetime can be input in the string, e.g. "datetime(2016, 12, 31)"
     - boolean can be also lower case ("true" or "false")
     - Some series methods with all args optional can also be given with no brackets
       (e.g. ".notna", ".median")
    """
    # Setup custom keyword arguments to dataframe query
    __kwargs = {
        # add support for `datetime(Y,M,...)` inside expressions:
        'local_dict': {
            'datetime': lambda *a, **k: datetime(*a, **k)
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


##################################
# Residuals calculation function #
##################################


def prepare_for_residuals(flatfile: pd.DataFrame,
                          gsims: Iterable[GMPE], imts: Iterable[str]):
    """Modify inplace the flatfile assuring that the attribute required by the given
    models and the SA periods passed in the given imts are present in the flatfile
    columns.
    Raise `MissingColumn` if the flatfile cannot be made compliant to the given arguments
    """
    required = set()
    # code copied from openquake,hazardlib.contexts.ContextMaker.__init__:
    for gsim in gsims:
        # NB: REQUIRES_DISTANCES is empty when gsims = [FromFile]
        required.update(gsim.REQUIRES_DISTANCES | {'rrup'})
        required.update(gsim.REQUIRES_RUPTURE_PARAMETERS or [])
        required.update(gsim.REQUIRES_SITES_PARAMETERS or [])
    for attr in required:
        _prepare_for_gsim_required_attribute(flatfile, attr)
    _prepare_for_sa(flatfile, [i for i in imts if i.startswith('SA(')])


def _prepare_for_sa(flatfile: pd.DataFrame, target_sa: Iterable[str]):
    """Modify inplace the flatfile assuring the SA columns identified by `target_sa`
    are present. The SA column present in the flatfile will be used to obtain
    the target SA via interpolation, and removed if not necessary
    """
    target_sa_columns = sorted(target_sa, key=lambda c: imt.from_string(c).period)
    if not target_sa_columns:
        return flatfile
    target_sa_periods = [imt.from_string(c).period for c in target_sa_columns]
    sa_columns = sorted((col for col in flatfile.columns if col.startswith("SA(")),
                        key=lambda c: imt.from_string(c).period)
    if len(sa_columns) < 2:
        raise MissingColumnError('Two or more SA columns required for interpolation, '
                                 f'found {len(sa_columns)}')
    sa_periods = [imt.from_string(c).period for c in sa_columns]


    spectrum = np.log10(flatfile[sa_columns])
    # we need to interpolate row wise
    # build the interpolation function:
    interp = interp1d(sa_periods, spectrum, axis=1)
    # and interpolate:
    values = 10 ** interp(target_sa_periods)
    # values is a matrix where each column represents the values of the target period.
    # First drop old SA:
    flatfile.drop(sa_columns, axis='columns', inplace=True)
    # add new Sa:
    flatfile[target_sa_columns] = values


DEFAULT_MSR = PeerMSR()


def _prepare_for_gsim_required_attribute(flatfile: pd.DataFrame, att_name: str):
    """Modify inplace the given flatfile to contain a column named
    `att_name` and be compliant with the specified Gsim required attribute.
    If the input `flatfile` does not have a column `att_name`, several rules -
    documented in the metadata YAML file - are applied to try to infer the column
    values (e.g., rename an existing column whose name is an `att_name` alias, fill
    missing values from functions or other columns).
    Eventually, if the column `att_name` cannot be set on `flatfile`, this function
    raises :ref:`MissingColumn` error.
    """
    column = column_alias.get(att_name, att_name)
    series = flatfile.get(column)  # -> None if column not found
    if column == 'depth_top_of_rupture':
        series = fill_na(flatfile.get('event_depth'), series)
    elif column == 'rupture_width':
        # Use the PeerMSR to define the area and assuming an aspect ratio
        # of 1 get the width
        mag = flatfile.get('magnitude')
        if mag is not None:
            if series is None:
                series = pd.Series(np.sqrt(DEFAULT_MSR.get_median_area(mag, 0)))
            else:
                na = pd.isna(series)
                if na.any():
                    series = series.copy()
                    series[na] = np.sqrt(DEFAULT_MSR.get_median_area(mag[na], 0))
    elif column in ['rjb', 'ry0']:
        series = fill_na(flatfile.get('repi'), series)
    elif column == 'rx':  # same as above, but -repi
        series = fill_na(flatfile.get('repi'), series)
        if series is not None:
            series = -series
    elif column == 'rrup':
        series = fill_na(flatfile.get('rhypo'), series)
    elif column == 'z1pt0':
        vs30 = flatfile.get('vs30')
        if vs30 is not None:
            if series is None:
                series = pd.Series(vs30_to_z1pt0_cy14(vs30))
            else:
                na = pd.isna(series)
                if na.any():
                    series = series.copy()
                    series[na] = vs30_to_z1pt0_cy14(vs30[na])
    elif column == 'z2pt5':
        vs30 = flatfile.get('vs30')
        if vs30 is not None:
            if series is None:
                series = pd.Series(vs30_to_z2pt5_cb14(vs30))
            else:
                na = pd.isna(series)
                if na.any():
                    series = series.copy()
                    series[na] = vs30_to_z2pt5_cb14(vs30[na])
    elif column == 'backarc' and series is None:
        series = pd.Series(np.full(len(flatfile), fill_value=False))
    elif column == 'rvolc' and series is None:
        series = pd.Series(np.full(len(flatfile), fill_value=0, dtype=int))
    if series is None:
        raise MissingColumnError(f'Missing flatfile column "{att_name}", '
                                 f'no inference possible')
    if column != att_name:
        flatfile.rename(columns={column: att_name}, inplace=True)
    if series is not flatfile.get(column):
        flatfile[column] = series
    return flatfile


class MissingColumnError(AttributeError):

    def __init__(self, arg: str):
        """
        Attribute error displaying missing flatfile column(s) massages

        :param arg: gsim required attribute (e.g. 'z1pt0'), flatfile column
            (e.g. 'event_time') or custom message (in this latter case, the argument
            will be displayed as it is)
        """
        # NOTE: this class MUST subclass AttributeError as it is required by OpenQuake
        # when retrieving Context attributes (see usage in :ref:`EventContext` below)
        column = None
        if arg in column_alias:
            # passed arg. is a gsim required param, convert to flatfile column
            column = column_alias[arg]
        elif arg in column_type:
            # passed arg. is a flatfile column
            column = arg
        if column:
            msg = f'Missing flatfile column "{column}"'
        else:
            msg = arg
        super().__init__(msg)


def fill_na(src: Union[None, np.ndarray, pd.Series],
            dest: Union[None, np.ndarray, pd.Series]) -> \
        Union[None, np.ndarray, pd.Series]:
    """Fill NAs (NaNs/Nulls) of `dest` with relative values from `src`.
    Return `dest` or a copy of it.
    """
    if src is not None and dest is not None:
        na = pd.isna(dest)
        if na.any():
            dest = dest.copy()
            dest[na] = src[na]
    return dest


class EventContext(RuptureContext):
    # Increase `column_type` including also aliases (gsim required attributes) as keys:
    col_type = {**column_type, **{a : column_type[c] for a, c in column_alias.items()}}

    def __init__(self, flatfile: pd.DataFrame):
        super().__init__()
        if not isinstance(flatfile.index, IntegerIndex):
            raise ValueError('flatfile index should be made of unique integers')
        self._flatfile = flatfile

    # def __len__(self):
    #     """Required by the model while computing residuals, returns the number of
    #     sites (records) of this context
    #     """
    #     return len(self.sids)

    def __eq__(self, other):
        assert isinstance(other, EventContext) and \
               self._flatfile is other._flatfile

    @property
    def sids(self) -> IntegerIndex:
        """Return the ids (iterable of integers) of the records (or sites) used to build
        this context. The returned pandas `IntegerIndex` must have unique values so that
        the records (flatfile rows) can always be retrieved from the source flatfile via
        `flatfile.loc[self.record_ids, :]`
        """
        # note that this attribute is used also when calculating `len(self)` so do not
        # delete or rename. See superclass for details
        return self._flatfile.index

    def __getattr__(self, item):
        """Return a non-found Context attribute by searching in the underlying
        flatfile column. Raises AttributeError (as usual) if `item` is not found
        """
        try:
            values = self._flatfile[item].values
        except KeyError:
            raise MissingColumnError(item)
        if self.col_type[item] == ColumnType.rupture_parameter.name:
            # rupture parameter, return a scalar (note: all values should be the same)
            values = values[0]
        return values


# FIXME REMOVE LEGACY STUFF CHECK WITH GW:

# FIXME: remove columns checks will be done when reading the flatfile and
# computing the residuals

# def _check_flatfile(flatfile: pd.DataFrame):
#     """Check the given flatfile: required column(s), upper-casing IMTs, and so on.
#     Modifications will be done inplace
#     """
#     ff_columns = set(flatfile.columns)
#
#     ev_col, ev_cols = _EVENT_COLUMNS[0], _EVENT_COLUMNS[1:]
#     if get_column(flatfile, ev_col) is None:
#         raise ValueError(f'Missing required column: {ev_col} or ' + ", ".join(ev_cols))
#
#     st_col, st_cols = _STATION_COLUMNS[0], _STATION_COLUMNS[1:]
#     if get_column(flatfile, st_col) is None:
#         # raise ValueError(f'Missing required column: {st_col} or ' + ", ".join(st_cols))
#         # do not check for station id (no operation requiring it implemented yet):
#         pass
#
#     # check IMTs (but allow mixed case, such as 'pga'). So first rename:
#     col2rename = {}
#     no_imt_col = True
#     imt_invalid_dtype = []
#     for col in ff_columns:
#         imtx = get_imt(col, ignore_case=True)
#         if imtx is None:
#             continue
#         no_imt_col = False
#         if not str(flatfile[col].dtype).lower().startswith('float'):
#             imt_invalid_dtype.append(col)
#         if imtx != col:
#             col2rename[col] = imtx
#             # do we actually have the imt provided? (conflict upper/lower case):
#             if imtx in ff_columns:
#                 raise ValueError(f'Column conflict, please rename: '
#                                  f'"{col}" vs. "{imtx}"')
#     # ok but regardless of all, do we have imt columns at all?
#     if no_imt_col:
#         raise ValueError(f"No IMT column found (e.g. 'PGA', 'PGV', 'SA(0.1)')")
#     if imt_invalid_dtype:
#         raise ValueError(f"Invalid data type ('float' required) in IMT column(s): "
#                          f"{', '.join(imt_invalid_dtype)}")
#     # rename imts:
#     if col2rename:
#         flatfile.rename(columns=col2rename, inplace=True)


# def get_imt(imt_name: str, ignore_case=False,   # FIXME is it USED?
#             accept_sa_without_period=False) -> Union[str, None]:
#     """Return the OpenQuake formatted IMT CLASS name from string, or None if col does not
#     denote a IMT name.
#     Wit ignore_case=True:
#     "sa(0.1)"  and "SA(0.1)" will be returned as "SA(0.1)"
#     "pga"  and "pGa" will be returned as "PGA"
#     With ignore_case=False, the comparison is strict:
#     "sa(0.1)" -> None
#     """
#     if ignore_case:
#         imt_name = imt_name.upper()
#     if accept_sa_without_period and imt_name == 'SA':
#         return 'SA'
#     try:
#         return imt.imt2tup(imt_name)[0]
#     except Exception as _:  # noqa
#         return None


# class ContextDB:
#     """This abstract-like class represents a Database (DB) of data capable of
#     yielding Contexts and Observations suitable for Residual analysis (see
#     argument `ctx_database` of :meth:`gmpe_residuals.Residuals.get_residuals`)
#
#     Concrete subclasses of `ContextDB` must implement three abstract methods
#     (e.g. :class:`smtk.sm_database.GroundMotionDatabase`):
#      - get_event_and_records(self)
#      - update_context(self, ctx, records, nodal_plane_index=1)
#      - get_observations(self, imtx, records, component="Geometric")
#        (which is called only if `imts` is given in :meth:`self.get_contexts`)
#
#     Please refer to the functions docstring for further details
#     """
#
#     def __init__(self, dataframe: pd.DataFrame):
#         """
#         Initializes a new EgsimContextDB.
#
#         :param dataframe: a dataframe representing a flatfile
#         """
#         self._data = dataframe
#         sa_columns_and_periods = ((col, imt.from_string(col.upper()).period)
#                                   for col in self._data.columns
#                                   if col.upper().startswith("SA("))
#         sa_columns_and_periods = sorted(sa_columns_and_periods, key=lambda _: _[1])
#         self.sa_columns = [_[0] for _ in sa_columns_and_periods]
#         self.sa_periods = [_[1] for _ in sa_columns_and_periods]
#
#     def get_contexts(self, nodal_plane_index=1,
#                      imts=None, component="Geometric"):
#         """Return an iterable of Contexts. Each Context is a `dict` with
#         earthquake, sites and distances information (`dict["Ctx"]`)
#         and optionally arrays of observed IMT values (`dict["Observations"]`).
#         See `create_context` for details.
#
#         This is the only method required by
#         :meth:`gmpe_residuals.Residuals.get_residuals`
#         and should not be overwritten only in very specific circumstances.
#         """
#         compute_observations = imts is not None and len(imts)
#         for evt_id, records in self.get_event_and_records():
#             dic = self.create_context(evt_id, records, imts)
#             # ctx = dic['Ctx']
#             # self.update_context(ctx, records, nodal_plane_index)
#             if compute_observations:
#                 observations = dic['Observations']
#                 for imtx, values in observations.items():
#                     values = self.get_observations(imtx, records, component)
#                     observations[imtx] = np.asarray(values, dtype=float)
#                 dic["Num. Sites"] = len(records)
#             # Legacy code??  FIXME: kind of redundant with "Num. Sites" above
#             # dic['Ctx'].sids = np.arange(len(records), dtype=np.uint32)
#             yield dic
#
#     def create_context(self, evt_id, records: pd.DataFrame, imts=None):
#         """Create a new Context `dict`. Objects of this type will be yielded
#         by `get_context`.
#
#         :param evt_id: the earthquake id (e.g. int, or str)
#         :param imts: a list of strings denoting the IMTs to be included in the
#             context. If missing or None, the returned dict **will NOT** have
#             the keys "Observations" and "Num. Sites"
#
#         :return: the dict with keys:
#             ```
#             {
#             'EventID': evt_id,
#             'Ctx: a new :class:`openquake.hazardlib.contexts.RuptureContext`
#             'Observations": dict[str, list] # (each imt in imts mapped to `[]`)
#             'Num. Sites': 0
#             }
#             ```
#             NOTE: Remember 'Observations' and 'Num. Sites' are missing if `imts`
#             is missing, None or an emtpy sequence.
#         """
#         dic = {
#             'EventID': evt_id,
#             'Ctx': EventContext(records)
#         }
#         if imts is not None and len(imts):
#             dic["Observations"] = {imt: [] for imt in imts}  # OrderedDict([(imt, []) for imt in imts])
#             dic["Num. Sites"] = 0
#         return dic
#
#     def get_event_and_records(self):
#         """Yield the tuple (event_id:Any, records:DataFrame)
#
#         where:
#          - `event_id` is a scalar denoting the unique earthquake id, and
#          - `records` are the database records related to the given event: it
#             must be a sequence with given length (i.e., `len(records)` must
#             work) and its elements can be any user-defined data type according
#             to the current user implementations. For instance, `records` can be
#             a pandas DataFrame, or a list of several data types such as `dict`s
#             `h5py` Datasets, `pytables` rows, `django` model instances.
#         """
#         ev_id_name = _EVENT_COLUMNS[0]
#         if ev_id_name not in self._data.columns:
#             self._data[ev_id_name] = get_column(self._data, ev_id_name)
#
#         for ev_id, dfr in  self._data.groupby(ev_id_name):
#             if not dfr.empty:
#                 # FIXME: pandas bug? flatfile bug? sometimes dfr is empty, skip
#                 yield ev_id, dfr
#
#     def get_observations(self, imtx, records, component="Geometric"):
#         """Return the observed values of the given IMT `imtx` from `records`,
#         as numpy array. This method is not called if `get_contexts`is called
#         with the `imts` argument missing or `None`.
#
#         *IMPORTANT*: IMTs in acceleration units (e.g. PGA, SA) are supposed to
#         return their values in cm/s/s (which should be by convention the unit
#         in which they are stored)
#
#         :param imtx: a string denoting a given Intensity measure type.
#         :param records: sequence (e.g., list, tuple, pandas DataFrame) of records
#             related to a given event (see :meth:`get_event_and_records`)
#
#         :return: a numpy array of observations, the same length of `records`
#         """
#
#         if imtx.lower().startswith("sa("):
#             sa_periods = self.sa_periods
#             target_period = imt.from_string(imtx).period
#             spectrum = np.log10(records[self.sa_columns])
#             # we need to interpolate row wise
#             # build the interpolation function
#             interp = interp1d(sa_periods, spectrum, axis=1)
#             # and interpolate
#             values = 10 ** interp(target_period)
#         else:
#             try:
#                 values = records[imtx].values
#             except KeyError:
#                 # imtx not found, try ignoring case: first `lower()`, more likely
#                 # (IMTs mainly upper case), then `upper()`, otherwise: raise
#                 for _ in (imtx.lower() if imtx.lower() != imtx else None,
#                           imtx.upper() if imtx.upper() != imtx else None):
#                     if _ is not None:
#                         try:
#                             values = records[_].values
#                             break
#                         except KeyError:
#                             pass
#                 else:
#                     raise ValueError("'%s' is not a recognized IMT" % imtx) from None
#         return values.copy()


    # def update_context(self, ctx, records, nodal_plane_index=1):
    #     """Update the attributes of the earthquake-based context `ctx` with
    #     the data in `records`.
    #     See `rupture_context_attrs`, `sites_context_attrs`,
    #     `distances_context_attrs`, for a list of possible attributes. Any
    #     attribute of `ctx` that is non-scalar should be given as numpy array.
    #
    #     :param ctx: a :class:`openquake.hazardlib.contexts.RuptureContext`
    #         created for a specific event. It is the key 'Ctx' of the Context dict
    #         returned by `self.create_context`
    #     :param records: sequence (e.g., list, tuple, pandas DataFrame) of records
    #         related to the given event (see :meth:`get_event_and_records`)
    #     """
    #     self._update_rupture_context(ctx, records, nodal_plane_index)
    #     self._update_distances_context(ctx, records)
    #     self._update_sites_context(ctx, records)
    #     # add remaining ctx attributes:  FIXME SHOULD WE?
    #     for ff_colname, ctx_attname in self.flatfile_columns.items():
    #         if hasattr(ctx, ctx_attname) or ff_colname not in records.columns:
    #             continue
    #         val = records[ff_colname].values
    #         val = val[0] if ff_colname in self._rup_columns else val.copy()
    #         setattr(ctx, ctx_attname, val)

    # def _update_rupture_context(self, ctx, records, nodal_plane_index=1):
    #     """see `self.update_context`"""
    #     record = records.iloc[0]  # pandas Series
    #     ctx.mag = record['magnitude']
    #     ctx.strike = record['strike']
    #     ctx.dip = record['dip']
    #     ctx.rake = record['rake']
    #     ctx.hypo_depth = record['event_depth']
    #
    #     ztor = record['depth_top_of_rupture']
    #     if pd.isna(ztor):
    #         ztor = ctx.hypo_depth
    #     ctx.ztor = ztor
    #
    #     rup_width = record['rupture_width']
    #     if pd.isna(rup_width):
    #         # Use the PeerMSR to define the area and assuming an aspect ratio
    #         # of 1 get the width
    #         rup_width = np.sqrt(DEFAULT_MSR.get_median_area(ctx.mag, 0))
    #     ctx.width = rup_width
    #
    #     ctx.hypo_lat = record['event_latitude']
    #     ctx.hypo_lon = record['event_longitude']
    #     ctx.hypo_loc = np.array([0.5, 0.5])  # <- this is compatible with older smtk. FIXME: it was like this: np.full((len(record), 2), 0.5)

    # def _update_distances_context(self, ctx, records):
    #     """see `self.update_context`"""
    #
    #     # TODO Setting Rjb == Repi and Rrup == Rhypo when missing value
    #     # is a hack! Need feedback on how to fix
    #     ctx.repi = records['repi'].values.copy()
    #     ctx.rhypo = records['rhypo'].values.copy()
    #
    #     ctx.rcdpp = np.full((len(records),), 0.0)
    #     ctx.rvolc = np.full((len(records),), 0.0)
    #     ctx.azimuth = records['azimuth'].values.copy()
    #
    #     dists = records['rjb'].values.copy()
    #     isna = pd.isna(dists)
    #     if isna.any():
    #         dists[isna] = records.loc[isna, 'repi']
    #     ctx.rjb = dists
    #
    #     dists = records['rrup'].values.copy()
    #     isna = pd.isna(dists)
    #     if isna.any():
    #         dists[isna] = records.loc[isna, 'rhypo']
    #     ctx.rrup = dists
    #
    #     dists = records['rx'].values.copy()
    #     isna = pd.isna(dists)
    #     if isna.any():
    #         dists[isna] = -records.loc[isna, 'repi']
    #     ctx.rx = dists
    #
    #     dists = records['ry0'].values.copy()
    #     isna = pd.isna(dists)
    #     if isna.any():
    #         dists[isna] = records.loc[isna, 'repi']
    #     ctx.ry0 = dists

    # def _update_sites_context(self, ctx, records):
    #     """see `self.update_context`"""
    #     # Legacy code not used please check in the future:
    #     # ------------------------------------------------
    #     # ctx.lons = records['station_longitude'].values.copy()
    #     # ctx.lats = records['station_latitude'].values.copy()
    #     ctx.depths = records['station_elevation'].values * -1.0E-3 if \
    #         'station_elevation' in records.columns else np.full((len(records),), 0.0)
    #     vs30 = records['vs30'].values.copy()
    #     ctx.vs30 = vs30
    #     ctx.vs30measured = records['vs30measured'].values.copy()
    #     ctx.z1pt0 = records['z1'].values.copy() if 'z1' in records.columns else \
    #         vs30_to_z1pt0_cy14(vs30)
    #     ctx.z2pt5 = records['z2pt5'].values.copy() if 'z2pt5' in records.columns else \
    #         vs30_to_z2pt5_cb14(vs30)
    #     if 'backarc' in records.columns:
    #         ctx.backarc = records['backarc'].values.copy()
    #     else:
    #         ctx.backarc = np.full(shape=ctx.vs30.shape, fill_value=False)
