from collections import defaultdict
from typing import Union, Any, Callable

import pandas as pd

from egsim.core.modelparams import read_model_params, Prop, default_dtype
# from egsim.models import FlatfileField


def read_flatfile(filepath: str,
                  sep: str = None,
                  col_mapping: dict[str, str] = None,
                  usecols: Union[list[str], Callable[[str], bool]] = None,
                  dtype: dict[str, Union[str, list, tuple]] = None,
                  defaults: dict[str, Any] = None,
                  **kwargs):
    """
    Read a flat file into pandas DataFrame from a given CSV file

    :param filepath: the CSV file path. Compressed files are also supported
        and inferred from the extension (e.g. 'gzip', 'zip')
    :param sep: the separator (or delimiter). None means 'infer' (it might
        take more time)
    :param col_mapping: dict mapping CSV column names to Flat file column names.
        CSV column names not found in the dict keys are left unchanged.
        **CSV COLUMNS WILL BE RENAMED AS FIRST STEP**: when not otherwise
        indicated, all arguments below will work on flat file column names, i.e.
        the CSV columns renamed via this mapping
    :param dtype: dict of *flat file column names* mapped to the data type:
        either 'int', 'bool', 'float', 'str', 'datetime', 'category'` or list/tuple.
        'category', list or tuples are for data that can take only a limited amount
        of possible values and should be used mostly with string data as it might
        save a lot of memory. With "category", pandas will infer the number of
        categories from the data, whereas a list/tuple defines the possible
        categories, if known beforehand: in this case data values not found
        are converted to missing values (NA) and then replaced by a default, if
        set in `defaults` for the given column.
        Columns of type 'int' and 'bool' do not support NA data and must have a
        default in `defaults`, otherwise NA data will be replaced with 0 for int
        and False for bool.
        `dtype`=None (the default) means that pandas will try to infer the data
        type of each column (see `read_csv` documentation and `na_values` to see
        what it's considered NA).
    :param usecols: flat file column names to load, as list or callable accepting
        a flat file column name and returning True/False
    :param defaults: a dict of flat file column names mapped to the default
        value for missing/NA data. Defaults will be set AFTER the underlying
        `pandas.read_csv` is called, on the returned dataframe before returning
        it. None means: do not replace any NA data. Note however that if int and
        bool columns are specified in `dtype`, then a default is set for those
        columns anyway (0 for int, False for bool), because those data types do
        not support NA in numpy/pandas
    :param kwargs: additional keyword arguments not provided above that can be
        passed to `pandas.read_csv`. 'header', 'delim_whitespace' and 'names'
        should not be provided as they might be overwritten by this function

    :return: pandas DataFrame representing a Flat file
    """
    kwargs['sep'] = sep
    kwargs.setdefault('encoding', 'utf-8-sig')

    # CSV columns can be renamed via `read_csv(..., names=[...], header=0, ...)`
    # or simply by calling afterwards `dataframe.rename(columns={...})`. Both
    # approaches have drawbacks: in the first case we need to open the file
    # twice, in the latter we have to modify all arguments, such as `dtype`,
    # working on renamed columns.
    # We opt for the former for simplicity, as we need to open the file twice
    # also in case `sep` is not given (infer CSV separator). Note that we should
    # never need to open the file twice for user uploaded flat files: `col_mapping`
    # should not be given (it makes no sense) and we could simply recommend
    # passing explicitly `sep`

    if sep is None:
        kwargs |= _infer_csv_sep(filepath, col_mapping is not None)
    elif col_mapping:
        kwargs['names'] = _read_csv_header(filepath, sep)

    if col_mapping is not None:
        kwargs['header'] = 0
        # replace names with the new names of the mapping (if found) or leave
        # the name as it is if a mapping is not found:
        kwargs['names'] = [col_mapping.get(n, n) for n in kwargs['names']]

    # initialize the defaults dict if None and needs to be populated:
    if defaults is None:
        defaults = {}

    # Check which column is an int or bool, as those columns do not support NA
    # (e.g. a empty CSV cell for a boolean column raises)
    dtype_, dtype_ib, datetime_cols = {}, {}, kwargs.pop('parse_dates', [])
    for col, dtyp in dtype.items():
        if dtyp in ('bool', 'int'):
            # Move the dtype to dtype_ib:
            dtype_ib[col] = dtyp
            # Replace dtype with float in order to safely read NA:
            dtype_[col] = 'float'
            # Check that a default is set and is of type float, otherwise pandas
            # might perform useless data conversions to object. As such, when a
            # default is unset, provide 0, as eventually float(0) = float(False)
            defaults[col] = float(defaults.get(col, 0))
        elif dtyp == 'datetime':
            datetime_cols.append(col)
        elif isinstance(dtyp, (list, tuple)):
            dtype_[col] = pd.CategoricalDtype(categories)  # noqa
        else:
            dtype_[col] = dtyp

    dfr = pd.read_csv(filepath, dtype=dtype_, parse_dates=datetime_cols or None,
                      usecols=usecols, **kwargs)

    for col, def_val in defaults.items():
        if col not in dfr.columns:
            continue
        dfr.loc[dfr[col].isna(), col] = def_val
        if col in dtype_ib:
            dfr[col] = dfr[col].astype(dtype_ib[col])

    return dfr


def _infer_csv_sep(filepath: str, return_col_names=False) -> dict[str, Any]:
    """Prepares the CSV for reading by inspecting the header and inferring the
    separator `sep`, if the latter is None.

    :return: the arguments needed for pd.read_csv as dict (e.g. `{'sep': ','}`).
        if `return_colnames` is True, the dict also contains the key 'names'
        with the CSV column header names
    """
    params = {}
    # infer separator: pandas suggests to use the engine='python' argument,
    # but this takes approx 4.5 seconds with the ESM flatfile 2018
    # whereas the method below is around 1.5 (load headers and count).
    # So, try to read the headers only with comma and semicolon, and chose the
    # one producing more columns:
    comma_cols = _read_csv_header(filepath, sep=',')
    semicolon_cols = _read_csv_header(filepath, sep=';')
    if len(comma_cols) > 1 and len(comma_cols) >= len(semicolon_cols):
        params['sep'] = ','
        names = comma_cols.tolist()
    elif len(semicolon_cols) > 1:
        params['sep'] = ';'
        names = semicolon_cols.tolist()
    else:
        # try with spaces:
        space_cols = _read_csv_header(filepath, sep=r'\s+')
        if len(space_cols) > max(len(comma_cols), len(semicolon_cols)):
            params['sep'] = r'\s+'
            names = space_cols.tolist()
        else:
            raise ValueError('CSV separator could not be inferred by trying '
                             '",", ";" and "\\s+" (whitespaces)')

    if return_col_names:
        params['names'] = names

    return params


def _read_csv_header(filepath, sep: str) -> pd.Index:
    return pd.read_csv(filepath, nrows=0, sep=sep).columns


# def read_userdefined_flatfile(filepath):
#     dtype, parse_dates, col_mapping = _get_db_mappings()
#     return read_flatfile(filepath, dtype=dtype, parse_dates=parse_dates,
#                          col_mapping=col_mapping)
#     # FIXME: todo : check IDs!!!
#     if 'event_id' not in dfr:
#         if 'event_time' not in dfr:
#             raise ValueError('event_id')


# def test_esm_read():
#     dfr = read_esm('/Users/rizac/work/gfz/projects/sources/python/egsim/egsim/'
#                    'management/commands/data/raw_flatfiles/ESM_flatfile_2018_SA.csv.zip')
#     params = read_model_params('/Users/rizac/work/gfz/projects/sources/python'
#                               '/egsim/egsim/core/modelparams.yaml')
#
#     rename = {v['flatfile_name']: k for k, v in params.items() if v.get('flatfile_name', None)}
#     unknown_cols = set(rename) - set(dfr.columns)
#     # dfr2 = dfr.reanme(columns=rename)
#     extra_cols = set(dfr.columns) - set(rename)
#     asd = 9
#     dfr2 = dfr.copy()
#     catagorical_cols = []
#     for _ in dfr.columns:
#         if isinstance(dfr[_].dtype, pd.CategoricalDtype):
#             continue
#         ratio = 0.1
#         if dfr[_].dtype == 'object':
#             ratio = 0.5
#         if len(pd.unique(dfr[_])) < len(dfr) * ratio:
#             catagorical_cols.append(_)
#             dfr2[_] = dfr2[_].astype('category')
#     asd = 9


# def _get_yaml_dtype_defaults() -> tuple[dict[str, str], dict[str, str]]:
#     """
#     Return the tuple:
#     ```
#     dtype, parse_dates, col_mapping
#     ```
#     i.e. the arguments needed by
#     `read_flatfile`. The data is read from the eGSIM database
#     """
#     dtype, defaults = {}, {}
#     for (key, props) in read_model_params().items():
#         ffname = props.get(Prop.ffname, None)
#         if not ffname:
#             continue
#         dtype[ffname] = props.get(Prop.dtype, default_dtype)
#         if Prop.default in props:
#             defaults[ffname] = props[Prop.default]
#
#         # col_mappings[ffname] = key.split('.', 1)[1]
#
#     return dtype, defaults


def check_flatfile(filepath: str,
                   sep: str = None,
                   col_mapping: dict[str, str] = None,
                   usecols: Union[list[str], Callable[[str], bool]] = None,
                   dtype: dict[str, Union[str, list, tuple]] = None,
                   defaults: dict[str, Any] = None,
                   **kwargs):
    """
    """
    numeric_cols = {
        c: v
        for c, v in dtype.items() if v in ('datetime', 'float', 'int', 'bool')
    }
    dtyp_ = {c: dtype[c] for c in dtype if c not in numeric_cols}
    dfr = read_flatfile(filepath, sep, col_mapping, usecols, dtyp_, defaults)
    errors = defaultdict(list)  # dataframe index -> list of columns with errors

    for col, dtyp in numeric_cols.items():
        if col not in dfr.columns:
            continue
        na = dfr[col].isna()
        if dtyp == 'datetime':
            val = pd.to_datetime(dfr[col], errors='coerce')
        else:
            val = pd.to_numeric(dfr[col], errors='coerce')

        idxs = dfr.index[pd.isna(val) & (~na)]
        for idx in idxs:
            errors[idx].append(col)

    return errors
