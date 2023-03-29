"""flatfile pandas module"""

from datetime import datetime
from enum import Enum, IntEnum
from os.path import join, dirname
import re

from typing import Union, Callable, Any

# from enum import Enum
import yaml
import numpy as np
import pandas as pd
from pandas.errors import UndefinedVariableError
from scipy.interpolate import interp1d
from openquake.hazardlib import imt
from openquake.hazardlib.scalerel import PeerMSR
from openquake.hazardlib.contexts import DistancesContext, RuptureContext

from ..smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14


class ColumnType(IntEnum):
    """Flatfile column type / family"""
    rupture_parameter = 0
    site_parameter = 1
    distance_measure = 2
    imt = 3
    unknown = 4

class ColumnDtype(Enum):  # noqa
    """Column **data** type. Names of this enum must be valid strings to be passed as
    values of the `dtype` argument of `numpy` or `pandas.read_csv` (except for
    `datetime`), values are all Python classes that are compatible with the data type
    """
    float = float, np.floating
    int = int, np.integer
    bool = bool, np.bool_
    datetime = datetime, np.datetime64
    str = str, np.str_, np.object_
    category = pd.CategoricalDtype.type

    @classmethod
    def get(cls, obj) -> Union["ColumnDtype", None]:  # noqa
        """Return the Enum item of this class matching the given object type

        :param obj: any object suh as Python scalr, numpy array, pandas series
        (representing flatfile columns)
        """
        is_numpy = hasattr(obj, 'dtype') and hasattr(obj.dtype, 'type')
        for dtype in cls:
            if (is_numpy and issubclass(obj.dtype.type, dtype.value)) \
                    or isinstance(obj, dtype.value):
                return dtype
        return None


def read_registered_flatfile_columns_metadata() -> dict[str, dict[str, Any]]:
    """Returns the Flatfile column metadata registered in this package YAML file

    :return: a dict of column names mapped top their metadata. Each column metaedata
        is in turn a dict[str, dict] with keys 'dtype', 'type', 'help', 'bounds',
        'default', 'mandatory' (all optional)
    """
    ffcolumns = {}
    with open(join(dirname(__file__), 'flatfile-columns.yaml')) as fpt:
        ff_cols = yaml.safe_load(fpt)
        oq_params = ff_cols.pop('openquake_models_parameters')
        for param_category, params in oq_params.items():
            for param_name, ffcol_name in params.items():
                if ffcol_name:
                    ffcolumns[ffcol_name] = _check_column_metadata(
                        **ff_cols.pop(ffcol_name),
                        oq_name=param_name, ctype=ColumnType[param_category]
                    )

    for ffcol_name, ffcol_props in ff_cols.items():
        imt_ = get_imt(ffcol_name, ignore_case=False, accept_sa_without_period=True)
        typ = ColumnType.imt if imt_ else ColumnType.unknown
        ffcolumns[ffcol_name] = _check_column_metadata(**ffcol_props, ctype=typ)

    return ffcolumns


def _check_column_metadata(dtype: Union[str, list, tuple] = None,
                           default: Any = None,
                           bounds: tuple[Any, Any] = (None, None),
                           help: str = "",  # noqa
                           required: bool = False,
                           oq_name: str = None,
                           ctype: Union[str, ColumnType] = ColumnType.unknown) \
        -> dict[str, Any]:

    ret = {}
    # set help:
    if help:
        ret['help'] = help
    if oq_name:
        ret['oq_name'] = oq_name
    try:
        ret['type'] = ctype if isinstance(ctype, ColumnType) else ColumnType[ctype]
    except KeyError:
        raise ValueError(f'Invalid Column type: {ctype}')
    if required:
        ret['required'] = True

    # perform some check on the data type consistencies:
    bounds_are_given = bounds != (None, None) and bounds != [None, None] \
        and bounds is not None

    # check dtype null and return in case:
    if dtype is None:
        if bounds_are_given or default is not None:
            raise ValueError(f"With `dtype` null or missing, metadata cannot have "
                             f"the keys `default` and `bounds`")
        return ret

    ret['dtype'] = dtype

    # handle categorical data:
    if isinstance(dtype, (list, tuple)):  # categorical data type
        if any(ColumnDtype.get(_) is None for _ in dtype):
            raise ValueError(f"Invalid data type(s) in provided categorical data")
        if bounds_are_given:
            raise ValueError(f"bounds must be [null, null] or missing with "
                             f"categorical data type")
        if default is not None and default not in dtype:
            raise ValueError(f"default is not in the list of possible values")
        return ret

    # handle non categorical data with a base dtype:
    try:
        self_dtype = ColumnDtype[dtype]
    except KeyError:
        raise ValueError(f"Invalid data type: {dtype}")

    # check bounds:
    if bounds_are_given:
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise ValueError(f"bounds must be a 2-element list or tuple")
        bmin, bmax = bounds
        # type promotion (ints are valid floats):
        if self_dtype == ColumnDtype.float and ColumnDtype.get(bmin) == ColumnDtype.int:
            bmin = float(bmin)
        if self_dtype == ColumnDtype.float and ColumnDtype.get(bmax) == ColumnDtype.int:
            bmax = float(bmax)
        if bmin is not None and not isinstance(bmin, self_dtype.value):
            raise ValueError(f"bounds[0] must be of type {dtype}")
        if bmax is not None and not isinstance(bmax,  self_dtype.value):
            raise ValueError(f"bounds[0] must be of type {dtype}")
        if bmin is not None and bmax is not None and bmax <= bmin:
            raise ValueError(f"bounds[0] must be < bounds[1]")
        ret['bounds'] = (bmin, bmax)

    # check default value (defval, not required):
    if default is not None:
        # type promotion (int is a valid float):
        if self_dtype == ColumnDtype.float and \
                ColumnDtype.get(default) ==ColumnDtype.int:
            default = float(default)
        elif not isinstance(default, self_dtype.value):
            raise ValueError(f"default must be of type {dtype}")
        ret['default'] = default

    return ret

def get_imt(imt_name: str, ignore_case=False,
            accept_sa_without_period=False) -> Union[str, None]:
    """Return the OpenQuake formatted IMT CLASS name from string, or None if col does not
    denote a IMT name.
    Wit ignore_case=True:
    "sa(0.1)"  and "SA(0.1)" will be returned as "SA(0.1)"
    "pga"  and "pGa" will be returned as "PGA"
    With ignore_case=False, the comparison is strict:
    "sa(0.1)" -> None
    """
    if ignore_case:
        imt_name = imt_name.upper()
    if accept_sa_without_period and imt_name == 'SA':
        return 'SA'
    try:
        return imt.imt2tup(imt_name)[0]
    except Exception as _:  # noqa
        return None


############
# Flatfile #
############


def read_flatfile(filepath_or_buffer: str,
                  sep: str = None,
                  col_mapping: dict[str, str] = None,
                  usecols: Union[list[str], Callable[[str], bool]] = None,
                  dtype: dict[str, Union[str, list, tuple]] = None,
                  defaults: dict[str, Any] = None,
                  required: list[str] = None,
                  **kwargs) -> pd.DataFrame:
    """
    Read a flat file into pandas DataFrame from a given CSV file

    :param filepath_or_buffer: str, path object or file-like object of the CSV
        formatted data. If string, compressed files are also supported
        and inferred from the extension (e.g. 'gzip', 'zip')
    :param sep: the separator (or delimiter). None means 'infer' (it might
        take more time)
    :param col_mapping: a dict mapping CSV column names to Flat file column names.
        CSV column names not found in the dict keys are left unchanged.
        **CSV COLUMNS WILL BE RENAMED AS FIRST STEP**: when not otherwise
        indicated, all arguments of this function will work on flat file column names,
        i.e. the CSV columns renamed via this mapping
    :param usecols: flat file column names to load, as list. Can be also a callable
        accepting a flat file column name and returning True/False (accept/discard)
    :param dtype: dict of *flat file column names* mapped to the data type:
        either 'int', 'bool', 'float', 'str', 'datetime', 'category'`, list/tuple.
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
        If None, data types will be loaded from the column metadata stored
        in the YAML flatfile of this package
    :param defaults: a dict of flat file column names mapped to the default
        value for missing/NA data. Defaults will be set AFTER the underlying
        `pandas.read_csv` is called, on the returned dataframe before returning
        it. None means: do not replace any NA data. Note however that if int and
        bool columns are specified in `dtype`, then a default is set for those
        columns anyway (0 for int, False for bool), because those data types do
        not support NA in numpy/pandas. If None, defaults will be loaded from
        the column metadata stored in the YAML flatfile of this package
    :param required: list/tuple of flat file column names that must be present
        in the flatfile. ValueError will be raised if this condition is not satisfied.
        If None, required columns will be loaded from the column metadata stored
        in the YAML flatfile of this package
    :param kwargs: additional keyword arguments not provided above that can be
        passed to `pandas.read_csv`. 'header', 'delim_whitespace' and 'names'
        should not be provided as they might be overwritten by this function

    :return: pandas DataFrame representing a Flat file
    """
    kwargs['sep'] = sep
    kwargs.setdefault('encoding', 'utf-8-sig')
    kwargs.setdefault('comment', '#')

    if dtype is None or defaults is None or required is None:
        # assign defaults from our yaml file:
        cols = read_registered_flatfile_columns_metadata()
        if dtype is None:
            dtype = {c: cm['dtype'] for c, cm in cols.items() if 'dtype' in cm}
        if defaults is None:
            defaults = {c: cm['default'] for c, cm in cols.items() if 'default' in cm}
        if required is None:
            required = tuple(c for c, cm in cols.items() if cm.get('required', False))

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
        kwargs |= _infer_csv_sep(filepath_or_buffer, col_mapping is not None)
    elif col_mapping:
        kwargs['names'] = _read_csv_header(filepath_or_buffer, sep)

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
    for col, dtyp in (dtype or {}).items():
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
            dtype_[col] = pd.CategoricalDtype(dtyp)  # noqa
        else:
            dtype_[col] = dtyp

    try:
        dfr = pd.read_csv(filepath_or_buffer, dtype=dtype_,
                          parse_dates=datetime_cols or None,
                          usecols=usecols, **kwargs)
    except ValueError as exc:
        raise ValueError(f'Error reading the flatfile: {str(exc)}')

    if required and set(required) - set(dfr.columns):
        missing = sorted(set(required) - set(dfr.columns))
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")

    for col, def_val in defaults.items():
        if col not in dfr.columns:
            continue
        dfr.loc[dfr[col].isna(), col] = def_val
        if col in dtype_ib:
            dfr[col] = dfr[col].astype(dtype_ib[col])

    _check(dfr)  # rename imts lower / upper case, check mandatory columns ...
    return dfr


def _infer_csv_sep(filepath_or_buffer: str, return_col_names=False) -> dict[str, Any]:
    """Prepares the CSV for reading by inspecting the header and inferring the
    separator `sep`, if the latter is None.

    :param filepath_or_buffer: str, path object or file-like object. If it has
        the attribute `seek` (e.g., file like object like `io.BytesIO`, then
        `filepath_or_buffer.seek(0)` is called before returning (reset the
        file-like object position at the start of the stream)
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
    comma_cols = _read_csv_header(filepath_or_buffer, sep=',')
    semicolon_cols = _read_csv_header(filepath_or_buffer, sep=';')
    if len(comma_cols) > 1 and len(comma_cols) >= len(semicolon_cols):
        params['sep'] = ','
        names = comma_cols.tolist()
    elif len(semicolon_cols) > 1:
        params['sep'] = ';'
        names = semicolon_cols.tolist()
    else:
        # try with spaces:
        space_cols = _read_csv_header(filepath_or_buffer, sep=r'\s+')
        if len(space_cols) > max(len(comma_cols), len(semicolon_cols)):
            params['sep'] = r'\s+'
            names = space_cols.tolist()
        else:
            raise ValueError('CSV separator could not be inferred by trying '
                             '",", ";" and "\\s+" (whitespaces)')

    if return_col_names:
        params['names'] = names

    return params


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


def _check(flatfile: pd.DataFrame):
    """Check the given flatfile: required column(s), upper-casing IMTs, and so on.
    Modifications will be done inplace
    """
    # check IMTs (but allow mixed case, such as 'pga'). So first rename:
    col2rename = {}
    no_imt_col = True
    imt_invalid_dtype = []
    for col in flatfile.columns:
        imtx = get_imt(col, ignore_case=True)
        if imtx is None:
            continue
        no_imt_col = False
        if not str(flatfile[col].dtype).lower().startswith('float'):
            imt_invalid_dtype.append(col)
        if imtx != col:
            col2rename[col] = imtx
            # do we actually have the imt provided? (conflict upper/lower case):
            if imtx in flatfile.columns:
                raise ValueError(f'Column conflict, please rename: '
                                 f'"{col}" vs. "{imtx}"')
    # ok but regardless of all, do we have imt columns at all?
    if no_imt_col:
        raise ValueError(f"No IMT column found (e.g. 'PGA', 'PGV', 'SA(0.1)')")
    if imt_invalid_dtype:
        raise ValueError(f"Invalid data type ('float' required) in IMT column(s): "
                         f"{', '.join(imt_invalid_dtype)}")
    # rename imts:
    if col2rename:
        flatfile.rename(columns=col2rename, inplace=True)


def query(flatfile: pd.DataFrame, query_expression) -> pd.DataFrame:
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


#######################################
# ContextDB for Residuals calculation #
#######################################

DEFAULT_MSR = PeerMSR()


class ContextDB:
    """This abstract-like class represents a Database (DB) of data capable of
    yielding Contexts and Observations suitable for Residual analysis (see
    argument `ctx_database` of :meth:`gmpe_residuals.Residuals.get_residuals`)

    Concrete subclasses of `ContextDB` must implement three abstract methods
    (e.g. :class:`smtk.sm_database.GroundMotionDatabase`):
     - get_event_and_records(self)
     - update_context(self, ctx, records, nodal_plane_index=1)
     - get_observations(self, imtx, records, component="Geometric")
       (which is called only if `imts` is given in :meth:`self.get_contexts`)

    Please refer to the functions docstring for further details
    """

    def __init__(self, dataframe: pd.DataFrame,
                 rupture_columns: dict[str, str] = None,
                 site_columns: dict[str, str] = None,
                 distance_columns: dict[str, str] = None):
        """
        Initializes a new EgsimContextDB.

        :param dataframe: a dataframe representing a flatfile
        :param rupture_columns: dataframe column names mapped to the relative
            Rupture parameter in the Context
        :param site_columns: dataframe column names mapped to the relative
            Site parameter in the Context
        :param distance_columns: dataframe column names mapped to the relative
            Distance measure in the Context
        """
        if not rupture_columns or not site_columns or not distance_columns:
            # read from yaml:
            r, s, d = {}, {}, {}
            for cname, cmetadata in read_registered_flatfile_columns_metadata().items():
                if cmetadata['type'] == ColumnType.site_parameter:
                    s[cname] = cname
                elif cmetadata['type'] == ColumnType.rupture_parameter:
                    r[cname] = cname
                elif cmetadata['type'] == ColumnType.distance_measure:
                    d[cname] = cname
            if not rupture_columns:
                rupture_columns = r
            if not site_columns:
                site_columns = s
            if not distance_columns:
                distance_columns = d

        self._data = dataframe
        self._rup_columns = rupture_columns
        self._site_columns = site_columns
        self._dist_columns = distance_columns
        self.flatfile_columns = rupture_columns | site_columns | distance_columns
        sa_columns_and_periods = ((col, imt.from_string(col.upper()).period)
                                  for col in self._data.columns
                                  if col.upper().startswith("SA("))
        sa_columns_and_periods = sorted(sa_columns_and_periods, key=lambda _: _[1])
        self.sa_columns = [_[0] for _ in sa_columns_and_periods]
        self.sa_periods = [_[1] for _ in sa_columns_and_periods]
        self.filter_expression = None

    rupture_context_attrs = tuple(RuptureContext._slots_)  # noqa
    distances_context_attrs = tuple(DistancesContext._slots_)  # noqa
    sites_context_attrs = ('vs30', 'lons', 'lats', 'depths',
                           'vs30measured', 'z1pt0', 'z2pt5', 'backarc')

    def get_contexts(self, nodal_plane_index=1,
                     imts=None, component="Geometric"):
        """Return an iterable of Contexts. Each Context is a `dict` with
        earthquake, sites and distances information (`dict["Ctx"]`)
        and optionally arrays of observed IMT values (`dict["Observations"]`).
        See `create_context` for details.

        This is the only method required by
        :meth:`gmpe_residuals.Residuals.get_residuals`
        and should not be overwritten only in very specific circumstances.
        """
        compute_observations = imts is not None and len(imts)
        for evt_id, records in self.get_event_and_records():
            dic = self.create_context(evt_id, imts)
            ctx = dic['Ctx']
            self.update_context(ctx, records, nodal_plane_index)
            if compute_observations:
                observations = dic['Observations']
                for imtx, values in observations.items():
                    values = self.get_observations(imtx, records, component)
                    observations[imtx] = np.asarray(values, dtype=float)
                dic["Num. Sites"] = len(records)
            # Legacy code??  FIXME: kind of redundant with "Num. Sites" above
            dic['Ctx'].sids = np.arange(len(records), dtype=np.uint32)
            yield dic

    def create_context(self, evt_id, imts=None):
        """Create a new Context `dict`. Objects of this type will be yielded
        by `get_context`.

        :param evt_id: the earthquake id (e.g. int, or str)
        :param imts: a list of strings denoting the IMTs to be included in the
            context. If missing or None, the returned dict **will NOT** have
            the keys "Observations" and "Num. Sites"

        :return: the dict with keys:
            ```
            {
            'EventID': evt_id,
            'Ctx: a new :class:`openquake.hazardlib.contexts.RuptureContext`
            'Observations": dict[str, list] # (each imt in imts mapped to `[]`)
            'Num. Sites': 0
            }
            ```
            NOTE: Remember 'Observations' and 'Num. Sites' are missing if `imts`
            is missing, None or an emtpy sequence.
        """
        dic = {
            'EventID': evt_id,
            'Ctx': RuptureContext()
        }
        if imts is not None and len(imts):
            dic["Observations"] = {imt: [] for imt in imts}  # OrderedDict([(imt, []) for imt in imts])
            dic["Num. Sites"] = 0
        return dic

    #########################################
    # IMPLEMENTS ContextDB ABSTRACT METHODS #
    #########################################

    EVENT_ID_COL = 'event_id'

    def get_event_and_records(self):
        """Yield the tuple (event_id:Any, records:Sequence)

        where:
         - `event_id` is a scalar denoting the unique earthquake id, and
         - `records` are the database records related to the given event: it
            must be a sequence with given length (i.e., `len(records)` must
            work) and its elements can be any user-defined data type according
            to the current user implementations. For instance, `records` can be
            a pandas DataFrame, or a list of several data types such as `dict`s
            `h5py` Datasets, `pytables` rows, `django` model instances.
        """
        # FIXME: pandas bug? flatfile bug?
        # `return self._data.groupby([EVENT_ID_COL])` should be sufficient, but
        # sometimes in the yielded `(ev_id, dfr)` tuple, `dfr` is empty and
        # `ev_id` is actually not in the dataframe (???). So:
        yield from (_ for _ in self._data.groupby(self.EVENT_ID_COL) if not _[1].empty)

    def get_observations(self, imtx, records, component="Geometric"):
        """Return the observed values of the given IMT `imtx` from `records`,
        as numpy array. This method is not called if `get_contexts`is called
        with the `imts` argument missing or `None`.

        *IMPORTANT*: IMTs in acceleration units (e.g. PGA, SA) are supposed to
        return their values in cm/s/s (which should be by convention the unit
        in which they are stored)

        :param imtx: a string denoting a given Intensity measure type.
        :param records: sequence (e.g., list, tuple, pandas DataFrame) of records
            related to a given event (see :meth:`get_event_and_records`)

        :return: a numpy array of observations, the same length of `records`
        """

        if imtx.lower().startswith("sa("):
            sa_periods = self.sa_periods
            target_period = imt.from_string(imtx).period
            spectrum = np.log10(records[self.sa_columns])
            # we need to interpolate row wise
            # build the interpolation function
            interp = interp1d(sa_periods, spectrum, axis=1)
            # and interpolate
            values = 10 ** interp(target_period)
        else:
            try:
                values = records[imtx].values
            except KeyError:
                # imtx not found, try ignoring case: first `lower()`, more likely
                # (IMTs mainly upper case), then `upper()`, otherwise: raise
                for _ in (imtx.lower() if imtx.lower() != imtx else None,
                          imtx.upper() if imtx.upper() != imtx else None):
                    if _ is not None:
                        try:
                            values = records[_].values
                            break
                        except KeyError:
                            pass
                else:
                    raise ValueError("'%s' is not a recognized IMT" % imtx) from None
        return values.copy()

    def update_context(self, ctx, records, nodal_plane_index=1):
        """Update the attributes of the earthquake-based context `ctx` with
        the data in `records`.
        See `rupture_context_attrs`, `sites_context_attrs`,
        `distances_context_attrs`, for a list of possible attributes. Any
        attribute of `ctx` that is non-scalar should be given as numpy array.

        :param ctx: a :class:`openquake.hazardlib.contexts.RuptureContext`
            created for a specific event. It is the key 'Ctx' of the Context dict
            returned by `self.create_context`
        :param records: sequence (e.g., list, tuple, pandas DataFrame) of records
            related to the given event (see :meth:`get_event_and_records`)
        """
        self._update_rupture_context(ctx, records, nodal_plane_index)
        self._update_distances_context(ctx, records)
        self._update_sites_context(ctx, records)
        # add remaining ctx attributes:  FIXME SHOULD WE?
        for ff_colname, ctx_attname in self.flatfile_columns.items():
            if hasattr(ctx, ctx_attname) or ff_colname not in records.columns:
                continue
            val = records[ff_colname].values
            val = val[0] if ff_colname in self._rup_columns else val.copy()
            setattr(ctx, ctx_attname, val)

    def _update_rupture_context(self, ctx, records, nodal_plane_index=1):
        """see `self.update_context`"""
        record = records.iloc[0]  # pandas Series
        ctx.mag = record['magnitude']
        ctx.strike = record['strike']
        ctx.dip = record['dip']
        ctx.rake = record['rake']
        ctx.hypo_depth = record['event_depth']

        ztor = record['depth_top_of_rupture']
        if pd.isna(ztor):
            ztor = ctx.hypo_depth
        ctx.ztor = ztor

        rup_width = record['rupture_width']
        if pd.isna(rup_width):
            # Use the PeerMSR to define the area and assuming an aspect ratio
            # of 1 get the width
            rup_width = np.sqrt(DEFAULT_MSR.get_median_area(ctx.mag, 0))
        ctx.width = rup_width

        ctx.hypo_lat = record['event_latitude']
        ctx.hypo_lon = record['event_longitude']
        ctx.hypo_loc = np.array([0.5, 0.5])  # <- this is compatible with older smtk. FIXME: it was like this: np.full((len(record), 2), 0.5)

    def _update_distances_context(self, ctx, records):
        """see `self.update_context`"""

        # TODO Setting Rjb == Repi and Rrup == Rhypo when missing value
        # is a hack! Need feedback on how to fix
        ctx.repi = records['repi'].values.copy()
        ctx.rhypo = records['rhypo'].values.copy()

        ctx.rcdpp = np.full((len(records),), 0.0)
        ctx.rvolc = np.full((len(records),), 0.0)
        ctx.azimuth = records['azimuth'].values.copy()

        dists = records['rjb'].values.copy()
        isna = pd.isna(dists)
        if isna.any():
            dists[isna] = records.loc[isna, 'repi']
        ctx.rjb = dists

        dists = records['rrup'].values.copy()
        isna = pd.isna(dists)
        if isna.any():
            dists[isna] = records.loc[isna, 'rhypo']
        ctx.rrup = dists

        dists = records['rx'].values.copy()
        isna = pd.isna(dists)
        if isna.any():
            dists[isna] = -records.loc[isna, 'repi']
        ctx.rx = dists

        dists = records['ry0'].values.copy()
        isna = pd.isna(dists)
        if isna.any():
            dists[isna] = records.loc[isna, 'repi']
        ctx.ry0 = dists

    def _update_sites_context(self, ctx, records):
        """see `self.update_context`"""
        # Legacy code not used please check in the future:
        # ------------------------------------------------
        # ctx.lons = records['station_longitude'].values.copy()
        # ctx.lats = records['station_latitude'].values.copy()
        ctx.depths = records['station_elevation'].values * -1.0E-3 if \
            'station_elevation' in records.columns else np.full((len(records),), 0.0)
        vs30 = records['vs30'].values.copy()
        ctx.vs30 = vs30
        ctx.vs30measured = records['vs30measured'].values.copy()
        ctx.z1pt0 = records['z1'].values.copy() if 'z1' in records.columns else \
            vs30_to_z1pt0_cy14(vs30)
        ctx.z2pt5 = records['z2pt5'].values.copy() if 'z2pt5' in records.columns else \
            vs30_to_z2pt5_cb14(vs30)
        if 'backarc' in records.columns:
            ctx.backarc = records['backarc'].values.copy()
        else:
            ctx.backarc = np.full(shape=ctx.vs30.shape, fill_value=False)
