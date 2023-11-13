"""flatfile root module"""

from io import IOBase
from datetime import date, datetime
import re
from typing import Union, Any
from collections.abc import Callable

import pandas as pd

from .columns import (ColumnDtype, get_rupture_params,
                      get_dtypes_and_defaults, get_all_names_of,
                      get_intensity_measures, MissingColumn,
                      InvalidDataInColumn, InvalidColumnName, ConflictingColumns,
                      cast_dtype, cast_value)


def read_flatfile(filepath_or_buffer: str, sep: str = None) -> pd.DataFrame:
    """
    Read a flat file into pandas DataFrame from a given CSV file

    :param filepath_or_buffer: str, path object or file-like object of the CSV
        formatted data. If string, compressed files are also supported
        and inferred from the extension (e.g. 'gzip', 'zip')
    :param sep: the separator (or delimiter). None means 'infer' (it might
        take more time)
    """
    kwargs = dict(_flatfile_default_args)
    dtypes, defaults = get_dtypes_and_defaults()
    return read_csv(filepath_or_buffer, sep=sep, dtype=dtypes, defaults=defaults,
                     _check_dtypes_and_defaults=False, **kwargs)


def parse_flatfile(filepath_or_buffer: str, sep: str = None,
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
    :param rename: optional dict specifying as keys the CSV fieldnames that
        correspond to a standard flatfile column (dict values). Keys of this
        dict will have data type and default automatically set from the registered
        flatfile columns (see `columns.yaml` for details)
    :param extra_dtype: optional dict specifying the data type of CSV
        fieldnames that are not standard  flatfile columns and are not implemented
        in `rename`. Dict values can be: 'float', 'datetime', 'bool', 'int', 'str',
        'category', `ColumnDType`s, list/tuples or pandas CategoricalDtype
    :param extra_defaults: optional dict of with the defaults for missing values.
        Keys are extra CSV fieldnames that are not standard flatfile columns and
        are not implemented in `rename`
    :param usecols: pandas `read_csv` parameter (exposed explicitly here for clarity)
        the column names to load, as list. Can be also a callable
        accepting a column name and returning True/False (keep/discard)
    """
    # get registered dtypes and defaults:
    kwargs |= dict(_flatfile_default_args)
    extra_dtype = extra_dtype or {}
    extra_defaults = extra_defaults or {}
    dtype, defaults = get_dtypes_and_defaults()
    for csv_col, ff_col in (rename or {}).items():
        if ff_col in defaults:
            extra_defaults[csv_col] = defaults[ff_col]
        if ff_col in dtype:
            extra_dtype[csv_col] = dtype[ff_col]

    dfr = read_csv(filepath_or_buffer, sep=sep, dtype=extra_dtype,
                   defaults=extra_defaults, usecols=usecols,
                   _check_dtypes_and_defaults=True, **kwargs)
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


def read_csv(filepath_or_buffer: Union[str, IOBase],
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
    check_dtypes_and_defaults = kwargs.pop('_check_dtypes_and_defaults', True)

    kwargs =  _read_csv_prepare(filepath_or_buffer, sep=sep, dtype=dtype,
                                usecols=usecols, check_dtypes=check_dtypes_and_defaults,
                                **kwargs)
    try:
        dfr = pd.read_csv(filepath_or_buffer, **kwargs)
    except ValueError as exc:
        invalid_columns = _read_csv_inspect_failure(filepath_or_buffer, **kwargs)
        raise InvalidDataInColumn(*invalid_columns) from None

    # finalize and return
    _read_csv_finalize(dfr, dtype, defaults, check_dtypes_and_defaults)
    if not isinstance(dfr.index, pd.RangeIndex):
        dfr.reset_index(drop=True, inplace=True)
    return dfr


def _read_csv_prepare(filepath_or_buffer: IOBase, check_dtypes:bool, **kwargs) -> dict:
    """prepare the arguments for pandas read_csv: take tha passed **kwargs
    and return a modified version of it after checking some keys and values
    """
    dtype = kwargs.pop('dtype', {})  # removed and handled later

    if check_dtypes:
        for col, _dtype in dtype.items():
            dtype[col] = cast_dtype(_dtype)

    parse_dates = set(kwargs.pop('parse_dates', []))  # see above

    # infer `sep` and read the CSV header (dataframe columns), as some args of
    # `read_csv` (e.g. `parse_dates`) cannot contain columns not present in the flatfile
    header = []
    sep = kwargs.get('sep', None)
    nrows = kwargs.pop('nrows', None)
    if sep is None:
        kwargs.pop('sep')  # if it was None needs removal
        for _sep in [';', ',', r'\s+']:
            _header = _read_csv_get_header(filepath_or_buffer, sep=_sep,
                                           **kwargs)
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

    # Set the `dtype` and `parse_dates` arguments of read_csv. NOTE: dtypes that will
    # be changed here will be restored later (see `_read_csv_finalize`)
    if dtype:  # did we provide a dtype?
        kwargs['dtype'] = {}
        for col in csv_columns:
            col_dtype = dtype.get(col, None)
            if col_dtype is None:
                continue

            if isinstance(col_dtype, pd.CategoricalDtype):
                # if `col_dtype.categories=None` or `col_dtype='category'`, then
                # `read_csv` will infer the categories from the data. Otherwise,
                # it will silently convert values not found in categories to N/A,
                # making invalid and missing values indistinguishable. To do that, we
                # set now `col_dtype` as the dtype of the categories (which must be all
                # the same type) to get missing values, checking invalid values
                # after reading:
                if col_dtype.categories is not None:
                    col_dtype = ColumnDtype.of(*col_dtype.categories)

            if col_dtype == ColumnDtype.int:
                # let `read_csv` treat ints as floats, so that we can have NaN and
                # check later if we can replace them with the column default, if set
                kwargs['dtype'][col] = ColumnDtype.float
            elif col_dtype == ColumnDtype.bool:
                # let `read_csv` infer the data type of bools by not passing a dtype at
                # all. We will check later if we can cast the values to bool, not only
                # in terms of replacing N/A with the column default, if set, but also
                # string values (e.g. 'FALSE') to valid values
                continue
            elif col_dtype == ColumnDtype.datetime:
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
    kwargs['nrows'] = 0  # read just header
    ret = pd.read_csv(filepath_or_buffer, sep=sep, **kwargs).columns  # noqa
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
    # might raise are also bool and int, but we do not have those stypes here
    # (see `_read_csv_prepare` for details):
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
        expected_dtype = dtype.get(col, None)  # ColumnDtype or pd.CategoricalDtype
        if expected_dtype is None:
            continue
        # is expected dtype a pandas CategoricalDtype?
        expected_categories = None
        if isinstance(expected_dtype, pd.CategoricalDtype):
            if expected_dtype.categories is None:
                # categories inferred from data, no dtype to check
                continue
            expected_categories = expected_dtype
            # expected_dtype is the dtype of all categories
            expected_dtype = ColumnDtype.of(*expected_dtype.categories)
        # actual dtype. NOTE: cannot be categorical (see `_read_csv_prepare`)
        actual_dtype: ColumnDtype = ColumnDtype.of(dfr[col])
        # check matching dtypes:
        dtype_ok = actual_dtype == expected_dtype
        do_type_cast = False
        # handle mismatching dtypes (bool and int):
        if not dtype_ok:
            if expected_dtype == ColumnDtype.int:
                not_na = pd.notna(dfr[col])
                values = dfr[col][not_na]
                if (values == values.astype(int)).all():  # noqa
                    dtype_ok = True
                    do_type_cast = True
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
