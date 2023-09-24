"""flatfile pandas module"""

from io import IOBase, TextIOBase, TextIOWrapper

from datetime import date, datetime
import re
from openquake.hazardlib.gsim.base import GMPE
from pandas.core.indexes.numeric import IntegerIndex
from scipy.interpolate import interp1d

from typing import Union, Callable, Any, Iterable, IO

import numpy as np
import pandas as pd
from openquake.hazardlib.scalerel import PeerMSR
from openquake.hazardlib.contexts import RuptureContext

from .columns import (ColumnDtype, get_rupture_params,
                      get_dtypes_and_defaults, get_all_names_of,
                      get_intensity_measures, MissingColumn,
                      InvalidDataInColumn, InvalidColumnName, ConflictingColumns,
                      cast_dtype, cast_value)
from .. import get_SA_period
from ...smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14


def read_flatfile(filepath_or_buffer: str, sep: str = None) -> pd.DataFrame:
    """
    Read a flat file into pandas DataFrame from a given CSV file

    :param filepath_or_buffer: str, path object or file-like object of the CSV
        formatted data. If string, compressed files are also supported
        and inferred from the extension (e.g. 'gzip', 'zip')
    :param sep: the separator (or delimiter). None means 'infer' (it might
        take more time)
    """
    dtypes, defaults = get_dtypes_and_defaults()
    return read_csv(filepath_or_buffer, sep=sep, dtype=dtypes, defaults=defaults,
                     _check_dtypes_and_defaults=False)


missing_values = ("", "null", "NULL", "None",
                  "nan", "-nan", "NaN", "-NaN",
                  "NA", "N/A", "n/a",  "<NA>", "#N/A", "#NA")


def read_csv(filepath_or_buffer: Union[str, IO],
             sep: str = None,
             dtype: dict[str, Union[str, list, ColumnDtype, pd.CategoricalDtype]]  = None,
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
    :param dtype: dict of column names mapped to the data type. Columns not present
        in the flatfile will be ignored. Dtypes can be either 'int', 'bool', 'float',
        'str', 'datetime', 'category'`, list, pandas `CategoricalDtype`:
        the last four data types are for data that can take only a limited amount of
        possible values and should be used mostly with string data as it might save
        a lot of memory. With "category", pandas will infer the categories from the
        data - note that each category will be of type `str` - with all others,
        the categories can be any type input by the user. Flatfile values not
        found in the categories will be replaced with missing values (NA in pandas,
        see e.g. `pandas.isna`).
        Columns of type 'int' and 'bool' do not support missing values: NA data will be
        replaced with the default set in `defaults` (see doc), or with 0 for int and
        False for bool if no default is set for the column.
    :param defaults: a dict of flat file column names mapped to the default
        value for missing/NA data.  Columns not present in the flatfile will be ignored.
        Note that if int and bool columns are specified in `dtype`, then a default is
        set for those columns anyway (0 for int, False for bool. See `dtype` doc)

    :return: pandas DataFrame representing a Flat file
    """
    # convert the file input to a stream (IOBase): if already a stream, do not close
    # it at the end but restore the position with `seek`:
    buf_pos = None
    buf_detach = False
    encoding = kwargs.pop('encoding', 'utf-8-sig')
    if isinstance(filepath_or_buffer, IOBase):
        if not isinstance(filepath_or_buffer, TextIOBase):
            filepath_or_buffer = TextIOWrapper(filepath_or_buffer, encoding=encoding)
            buf_detach = True
        buf_pos = filepath_or_buffer.tell()
    else:
        filepath_or_buffer = open(filepath_or_buffer, 'rt', encoding=encoding)

    check_dtypes_and_defaults = kwargs.pop('_check_dtypes_and_defaults', True)
    if check_dtypes_and_defaults:
        for col, _dtype in dtype.items():
            dtype[col] = cast_dtype(_dtype)

    kwargs = _read_csv_prepare(filepath_or_buffer, sep=sep, dtype=dtype,
                               usecols=usecols, **kwargs)
    try:
        dfr = pd.read_csv(filepath_or_buffer, **kwargs)
    except ValueError as exc:
        invalid_columns = _read_csv_inspect_failure(filepath_or_buffer, **kwargs)
        raise InvalidDataInColumn(*invalid_columns) from None
    finally:
        if buf_pos is not None:
            filepath_or_buffer.seek(buf_pos)
            if buf_detach:
                filepath_or_buffer.detach()
        else:
            filepath_or_buffer.close()

    # finalize and return
    _read_csv_finalize(dfr, dtype, defaults, check_dtypes_and_defaults)
    if not isinstance(dfr.index, pd.RangeIndex):
        dfr.reset_index(drop=True, inplace=True)
    return dfr


def _read_csv_prepare(filepath_or_buffer: IOBase, **kwargs) -> dict:
    """prepare the arguments for pandas read_csv: take tha passed **kwargs
    and return a modified version of it after checking some keys and values
    """
    buf_pos = filepath_or_buffer.tell()
    # remove args that might not be suitable yet to be passed to `read_csv`:
    dtype = kwargs.pop('dtype', {})
    parse_dates = set(kwargs.pop('parse_dates', []))
    kwargs.setdefault('na_values', missing_values)
    kwargs.setdefault('keep_default_na', False)
    kwargs.setdefault('comment', '#')

    # infer `sep` by reading the CSV header with several separator strings. If `serp`
    # is given, read the header anyway once: we might need to know the columns anyway
    # (`dtype` keys not columns are skipped, whereas `parse_dates` raises in case)
    _separators = kwargs.pop('sep', None) or [';', ',', r'\s+']
    sep, headers = '', []
    for _sep in _separators:
        _headers = pd.read_csv(filepath_or_buffer, nrows=0, sep=_sep).columns
        if buf_pos is not None:
            filepath_or_buffer.seek(buf_pos)
        if len(_headers) > len(headers):
            headers = _headers
            sep = _sep
    kwargs['sep'] = sep

    # mix usecols with the flatfile columns just retrieved (it might speed up read):
    usecols = kwargs.pop('usecols', None)
    if callable(usecols):
        csv_columns = set(f for f in headers if usecols(f))
        kwargs['usecols'] = csv_columns
    elif isinstance(usecols, Iterable):
        csv_columns = set(headers) & set(usecols)
        kwargs['usecols'] = csv_columns
    else:
        csv_columns = set(headers)

    # Now set the dtype and parse_dates arguments of read_csv from our `dtype`
    # argument:
    if dtype:
        kwargs['dtype'] = {}
        for col in csv_columns:
            col_dtype = dtype.get(col, None)
            if col_dtype is None:
                continue

            # categorical data cannot be passed as they are to kwargs['dtype'] because
            # they silently convert invalid categories to N/A, whereas N/A should
            # be set only for missing values (e.g. empty CSV cells). As such, let's pass
            # the dtype of the categories (which must be all the same type):
            if isinstance(col_dtype, pd.CategoricalDtype):
                col_dtype = ColumnDtype.of_all(col_dtype.categories)

            if col_dtype == ColumnDtype.int:
                # let pandas handle ints as floats, so that we can have NaN and check
                # later if we can replace them with the column default, if set
                kwargs['dtype'][col] = ColumnDtype.float
            elif col_dtype == ColumnDtype.bool:
                # let pandas handle bools automatically (no dtype), so that we can have
                # NaN and check later if we can replace them with the column default, if
                # set. We cannot set float here because we might have str (e.g. 'FALSE')
                continue
            elif col_dtype == ColumnDtype.datetime:
                # date times in pandas csv must be given in the `parse_dates` arg. Note
                # that invalid datetime values will not raise but the column will have
                # more general dtype (usually object), whereas missing values will still
                # preserve the dtype and be set as NaT
                parse_dates.add(col)
            else:
                kwargs['dtype'][col] = col_dtype

        if parse_dates:
            kwargs['parse_dates'] = list(parse_dates)

    return kwargs


def _read_csv_inspect_failure(filepath_or_buffer: IOBase, **kwargs) -> list[str]:
    """Check the flatifle after failure returning the list of invalid columns"""
    buf_pos = filepath_or_buffer.tell()
    # To narrow down the choice of suspects, dtypes that might raise are bool, int and
    # float, but bool dtypes are not explicitly passed and int dtypes are converted to
    # float (see `_read_csv_prepare`):
    cols2check = [c for c, v in kwargs['dtype'].items() if v == ColumnDtype.float]
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


def _read_csv_finalize(dfr: pd.DataFrame,
                       dtype: dict[str, Union[ColumnDtype, pd.CategoricalDtype]],
                       defaults: dict[str, Any],
                       check_defaults: bool):
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
        expected_dtype: ColumnDtype = dtype.get(col, None)
        if expected_dtype is None:
            continue
        # is expected dtype a pandas CategoricalDtype?
        expected_categories = None
        if isinstance(expected_dtype, pd.CategoricalDtype):
            expected_categories = expected_dtype
            # expected_dtype is the dtype of all categories
            expected_dtype = ColumnDtype.of_all(expected_dtype.categories)
        # actual dtype. NOTE: cannot be categorical (see `_read_csv_prepare`)
        actual_dtype: ColumnDtype = ColumnDtype.of(dfr[col])
        # check matching dtypes:
        dtype_ok = actual_dtype == expected_dtype
        do_type_cast = False
        # handle mismatching dtypes (bool and int):
        if not dtype_ok:
            if expected_dtype == ColumnDtype.int:
                try:
                    not_na = pd.notna(dfr[col])
                    values = dfr[col][not_na]
                    if (values == values.astype(int)).all():
                        dtype_ok = True
                        do_type_cast = True
                except Exception:  # noqa
                    pass
            elif expected_dtype == ColumnDtype.bool:
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
                default = defaults[col]
                if check_defaults:
                    default = cast_value(default,
                                         expected_categories or expected_dtype)
                is_na = pd.isna(dfr[col])
                dfr.loc[is_na, col] = default
            # if we expected categories, set the categories, nut be sure that we do not
            # have invalid values (pandas automatically set them to N/A):
            if expected_categories is not None:
                not_na = pd.notna(dfr[col])
                dfr[col] = dfr[col].astype(expected_categories)
                # check that we still have the same N/A (=> all values in dfr[col] are
                # valid categories):
                not_na_after = pd.notna(dfr[col])
                if len(not_na) != len(not_na_after) or (not_na!=not_na_after).any():
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


##################################
# Residuals calculation function #
##################################


def get_column_name(flatfile:pd.DataFrame, column:str) -> Union[str, None]:
    """Return the flatfile column matching `column`. This could be `column`
     itself, or any of its aliases (see `columns` module and YAML file)
     Returns None if no column is found, raise `ConflictingColumns` if more than
     a matching column is found"""
    ff_cols = set(flatfile.columns)
    cols = get_all_names_of(column) & ff_cols
    if len(cols) > 1:
        raise ConflictingColumns(*cols)
    elif len(cols) == 0:
        return None
    else:
        return next(iter(cols))


def get_event_id_column_names(flatfile: pd.DataFrame) -> list[str, ...]:
    default_col_name = 'event_id'
    col_name = get_column_name(flatfile, default_col_name)
    if col_name is not None:
        return [col_name]
    cols = ['event_latitude', 'event_longitude', 'event_depth', 'event_time']
    col_names = [get_column_name(flatfile, c) for c in cols]
    if any(c is None for c in col_names):
        raise MissingColumn(default_col_name)
    return col_names


def get_station_id_column_names(flatfile: pd.DataFrame) -> list[str, ...]:
    default_col_name = 'station_id'
    col_name = get_column_name(flatfile, default_col_name)
    if col_name is not None:
        return [col_name]
    cols = ['station_latitude', 'station_longitude']
    col_names = [get_column_name(flatfile, c) for c in cols]
    if any(c is None for c in col_names):
        raise MissingColumn(default_col_name)
    return col_names


def prepare_for_residuals(flatfile: pd.DataFrame,
                          gsims: Iterable[GMPE], imts: Iterable[str]) -> pd.DataFrame:
    """Return a new dataframe with all columns required to compute residuals
    from the given models (`gsim`) and intensity measures (`imts`) given with
    periods, when needed (e.g. "SA(0.2)")
    """
    # concat all new dataframes in this list, then return a ne one from it:
    new_dataframes = []
    # prepare the flatfile for the required ground motion properties:
    props_flatfile = pd.DataFrame(index=flatfile.index)
    for prop in get_required_ground_motion_properties(gsims):
        props_flatfile[prop] = \
            get_ground_motion_property_values(flatfile, prop)
    if not props_flatfile.empty:
        new_dataframes.append(props_flatfile)
    # validate imts:
    imts = set(imts)
    non_sa_imts = {_ for _ in imts if get_SA_period(_) is None}
    sa_imts = imts - non_sa_imts
    # check if all models are defined for the given imts"
    required_imt_names = non_sa_imts | {'SA'} if sa_imts else non_sa_imts
    invalid_models = [f'"{m.__class__.__name__}"' for m in gsims
                      if required_imt_names - get_imts_defined_for(m)]
    if invalid_models:
        raise ValueError('Model(s) not defined for all given imt(s): '
                         f'", '.join(invalid_models))
    # get supported imts but does not allow 'SA' alone to be valid:
    if non_sa_imts:
        # get the imts supported by this program, and raise if some unsupported IMT
        # was requested:
        supported_imts = get_intensity_measures() - {'SA'}
        if non_sa_imts - supported_imts:
            raise InvalidColumnName(*list(non_sa_imts - supported_imts))
        # from the requested imts, raise if some are not in the flatfile:
        if non_sa_imts - set(flatfile.columns):
            raise MissingColumn(*list(non_sa_imts - set(flatfile.columns)))
        # add non SA imts:
        new_dataframes.append(flatfile[sorted(non_sa_imts)])
    # prepare the flatfile for SA (create new columns by interpolation if necessary):
    if sa_imts:
        sa_dataframe = _prepare_for_sa(flatfile, sa_imts)
        if not sa_dataframe.empty:
            new_dataframes.append(sa_dataframe)
    # return the new dataframe or an empty one:
    if not new_dataframes:
        return pd.DataFrame(columns=flatfile.columns)  # empty dataframe
    return pd.concat(new_dataframes, axis=1)



def get_required_ground_motion_properties(gsims: Union[GMPE, Iterable[GMPE]]) \
        -> set[str]:
    """Return a Python set containing the required ground motion properties
    (rupture or sites parameter, distance measure, all as `str`) for the given
    ground motion models `gsims`

    :param gsims a ground motion model (OpenQuake `GMPE`) or iterable of models
        (e.g. list of `GMPE`s)
    """
    required = set()
    if isinstance(gsims, GMPE):
        gsims = [gsims]
    # code copied from openquake,hazardlib.contexts.ContextMaker.__init__:
    for gsim in gsims:
        # NB: REQUIRES_DISTANCES is empty when gsims = [FromFile]
        required.update(gsim.REQUIRES_DISTANCES | {'rrup'})
        required.update(gsim.REQUIRES_RUPTURE_PARAMETERS or [])
        required.update(gsim.REQUIRES_SITES_PARAMETERS or [])
    return required


def get_imts_defined_for(gsims: Union[GMPE, Iterable[GMPE]]) -> set[str]:
    """Return a Python set containing the imts names (e.g. 'SA', 'PGA')
     which are defined for *all* the supplied Ground motion models `gsims`

    :param gsims a ground motion model (OpenQuake `GMPE`) or iterable of models
        (e.g. list of `GMPE`s)
    """
    required = None
    if isinstance(gsims, GMPE):
        gsims = [gsims]
    # each intensity measure type is a function implemented in openquake,hazardlib.imt
    # we use the __name__ attribute which will return 'SA', 'PGA' and so on:
    for gsim in gsims:
        _imts = set(func.__name__ for func in gsim.DEFINED_FOR_INTENSITY_MEASURE_TYPES)
        if required is None:
            required = _imts
        else:
            required &= _imts
        if not required:  # no need to proceed further (if several Gsims are provided)
            break
    return required


DEFAULT_MSR = PeerMSR()


def get_ground_motion_property_values(flatfile: pd.DataFrame,
                                      param_or_dist: str) -> pd.Series:
    """Get the values (pandas Series) relative to the ground motion property
    (rupture or sites parameter, distance measure) extracted from the given
    flatfile.
    The returned value might be a column of the flatfile or a new pandas Series
    depending on missing-data replacement rules.
    If the column cannot be retrieved or created, this function
    raises :ref:`MissingColumn` error notifying the required missing column.
    """
    column_name = get_column_name(flatfile, param_or_dist)
    series = None if column_name is None else flatfile[column_name]
    if param_or_dist == 'ztor':
        series = fill_na(flatfile, 'hypo_depth', series)
    elif param_or_dist == 'width':  # rupture_width
        # Use the PeerMSR to define the area and assuming an aspect ratio
        # of 1 get the width
        mag = get_column_name(flatfile, 'mag')
        if mag is not None:
            mag = flatfile[mag]  # convert string to column (pd.Series)
            if series is None:
                series = pd.Series(np.sqrt(DEFAULT_MSR.get_median_area(mag, 0)))
            else:
                na = pd.isna(series)
                if na.any():
                    series = series.copy()
                    series[na] = np.sqrt(DEFAULT_MSR.get_median_area(mag[na], 0))
    elif param_or_dist in ['rjb', 'ry0']:
        series = fill_na(flatfile, 'repi', series)
    elif param_or_dist == 'rx':  # same as above, but -repi
        series = fill_na(flatfile, 'repi', series)
        if series is not None:
            series = -series
    elif param_or_dist == 'rrup':
        series = fill_na(flatfile, 'rhypo', series)
    elif param_or_dist == 'z1pt0':
        vs30 = get_column_name(flatfile, 'vs30')
        if vs30 is not None:
            vs30 = flatfile[vs30]  # convert string to column (pd.Series)
            if series is None:
                series = pd.Series(vs30_to_z1pt0_cy14(vs30))
            else:
                na = pd.isna(series)
                if na.any():
                    series = series.copy()
                    series[na] = vs30_to_z1pt0_cy14(vs30[na])
    elif param_or_dist == 'z2pt5':
        vs30 = get_column_name(flatfile, 'vs30')
        if vs30 is not None:
            vs30 = flatfile[vs30]  # convert string to column (pd.Series)
            if series is None:
                series = pd.Series(vs30_to_z2pt5_cb14(vs30))
            else:
                na = pd.isna(series)
                if na.any():
                    series = series.copy()
                    series[na] = vs30_to_z2pt5_cb14(vs30[na])
    elif param_or_dist == 'backarc' and series is None:
        series = pd.Series(np.full(len(flatfile), fill_value=False))
    elif param_or_dist == 'rvolc' and series is None:
        series = pd.Series(np.full(len(flatfile), fill_value=0, dtype=int))
    if series is None:
        raise MissingColumn(param_or_dist)
    return series


def fill_na(flatfile:pd.DataFrame,
            src_col: str,
            dest: Union[None, np.ndarray, pd.Series]) -> \
        Union[None, np.ndarray, pd.Series]:
    """Fill NAs (NaNs/Nulls) of `dest` with relative values from `src`.
    :return: a numpy array or pandas Series (the same type of `dest`, whenever
        possible) which might be a new object or `dest`, unchanged
    """
    col_name = get_column_name(flatfile, src_col)
    if col_name is None:
        return dest
    src = flatfile[col_name]
    if dest is None:
        return src.copy()
    na = pd.isna(dest)
    if na.any():
        dest = dest.copy()
        dest[na] = src[na]
    return dest


def _prepare_for_sa(flatfile: pd.DataFrame, sa_imts: Iterable[str]) -> pd.DataFrame:
    """Return a new Dataframe with the SA columns defined in `sa_imts`
    The returned DataFrame will have all strings supplied in `sa_imts` as columns,
    with relative values copied (or inferred via interpolation) from the given flatfile

    :param flatfile: the flatfile
    :param sa_imts: Iterable of strings denoting SA (e.g. "SA(0.2)")
    Return the newly created Sa columns, as tuple of strings
    """
    src_sa = []
    for c in flatfile.columns:
        p = get_SA_period(c)
        if p is not None:
            src_sa.append((p, c))
    # source_sa: period [float] -> mapped to the relative column:
    source_sa: dict[float, str] = {p: c for p, c in sorted(src_sa, key=lambda t: t[0])}

    tgt_sa = []
    invalid_sa = []
    for i in sa_imts:
        p = get_SA_period(i)
        if p is None:
            invalid_sa.append(i)
            continue
        if p not in source_sa:
            tgt_sa.append((p, i))
    if invalid_sa:
        raise InvalidDataInColumn(*invalid_sa)

    # source_sa: period [float] -> mapped to the relative column:
    target_sa: dict[float, str] = {p: c for p, c in sorted(tgt_sa, key=lambda t: t[0])}

    source_sa_flatfile = flatfile[list(source_sa.values())]

    if not target_sa:
        return source_sa_flatfile

    # Take the log10 of all SA:
    source_spectrum = np.log10(source_sa_flatfile)
    # we need to interpolate row wise
    # build the interpolation function:
    interp = interp1d(list(source_sa), source_spectrum, axis=1)
    # and interpolate:
    values = 10 ** interp(list(target_sa))
    # values is a matrix where each column represents the values of the target period.
    # Add it to the dataframe:
    new_flatfile = pd.DataFrame(index=flatfile.index)
    new_flatfile[list(target_sa.values())] = values

    return new_flatfile


class EventContext(RuptureContext):
    """A RuptureContext accepting a flatfile (pandas DataFrame) as input"""

    rupture_params:set[str] = None

    def __init__(self, flatfile: pd.DataFrame):
        super().__init__()
        if not isinstance(flatfile.index, IntegerIndex):
            raise ValueError('flatfile index should be made of unique integers')
        self._flatfile = flatfile
        if self.__class__.rupture_params is None:
            # get rupture params once for all instances the first time only:
            self.__class__.rupture_params = get_rupture_params()

    def __eq__(self, other):  # FIXME: legacy code, is it still used?
        assert isinstance(other, EventContext) and \
               self._flatfile is other._flatfile

    @property
    def sids(self) -> IntegerIndex:
        """Return the ids (iterable of integers) of the records (or sites) used to build
        this context. The returned pandas `IntegerIndex` must have unique values so that
        the records (flatfile rows) can always be retrieved from the source flatfile via
        `flatfile.loc[self.sids, :]`
        """
        # note that this attribute is used also when calculating `len(self)` so do not
        # delete or rename. See superclass for details
        return self._flatfile.index


    def __getattr__(self, column_name):
        """Return a non-found Context attribute by searching in the underlying
        flatfile column. Raises AttributeError (as usual) if `item` is not found
        """
        try:
            values = self._flatfile[column_name].values
        except KeyError:
            raise MissingColumn(column_name)
        if column_name in self.rupture_params:
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
