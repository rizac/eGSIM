# eGSIM Library Functions Reference
> Note: `smtk` stands for Strong Motion Toolkit, 
> a legacy project now integrated as the core package of eGSIM. 



### get_ground_motion_from_scenarios
```python
from egsim.smtk import get_ground_motion_from_scenarios

# Signature and docstring:
def get_ground_motion_from_scenarios(
    gsims: Iterable[str | GMPE],
    imts: Iterable[str | IMT],
    magnitudes: float | Collection[float],
    distances: float | Collection[float],
    rupture_properties: RuptureProperties | None = None,
    site_properties: SiteProperties | None = None,
    header_sep: str | None = Clabel.sep
) -> pd.DataFrame:
    """
    Calculate the ground motion values from different configured scenarios

    :param gsims: Iterable of Ground shaking intensity models or their names (str)
    :param imts: Iterable of Intensity measure types or their names (str)
    :param magnitudes: list or numpy array of magnitudes. Each magnitude
        defines a configured Rupture
    :param distances: list or numpy array of distances. Each distance defines a
        configured Site
    :param rupture_properties: the optional Rupture properties (see
        class RuptureProperties) to be applied to each Rupture
    :param site_properties: the optional Site properties (see class
        SiteProperties) to be applied to each Site
    :param header_sep: str or None (default: " "): the separator used to concatenate
        each column header into one string (e.g. "PGA median BindiEtAl2014Rjb"). Set
        to "" or None to return a multi-level column header composed of the first 3
        dataframe rows (e.g. ("PGA", "median", "BindiEtAl2014Rjb"). See
        "MultiIndex / advanced indexing" in the pandas doc for details)

    :return: pandas DataFrame
    """
```



### RuptureProperties
```python
from egsim.smtk import RuptureProperties

# Signature and docstring:
@dataclass
class RuptureProperties:
    """Dataclass defining one or more Ruptures via a set of common properties"""

    dip: float = 90.
    aspect: float = 1.0
    tectonic_region: str = "Active Shallow Crust"
    rake: float = 0.
    ztor: float = 0.
    strike: float = 0.
    hypocenter_location: tuple[float, float] | None = None
    msr: BaseMSR = field(default_factory=WC1994)
    # initial_point default is a random location on Earth:
    initial_point: Point = field(default_factory=lambda: Point(45.18333, 9.15, 0.))
```



### SiteProperties
```python
from egsim.smtk import SiteProperties

# Signature and docstring:
@dataclass
class SiteProperties:
    """Dataclass defining one or more Sites via a set of common properties"""

    vs30: float = 760.0
    line_azimuth: float = 90.0
    distance_type: str = "rrup"
    origin_point: tuple[float, float] = (0.5, 0.0)
    vs30measured: bool = True
    z1pt0: float | None = None
    z2pt5: float | None = None
    backarc: bool = False
    xvf: float = 150.0
    region: int = 0
```



### read_flatfile
```python
from egsim.smtk import read_flatfile

# Signature and docstring:
def read_flatfile(
    filepath_or_buffer: str | IOBase,
    rename: dict[str, str] = None,
    dtypes: dict[str, str | list] = None,
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
```



### get_residuals
```python
from egsim.smtk import get_residuals

# Signature and docstring:
def get_residuals(
    gsims: Iterable[str | GMPE],
    imts: Iterable[str | imt.IMT],
    flatfile: pd.DataFrame,
    likelihood=False,
    normalise=True,
    mean=False,
    header_sep: str | None = Clabel.sep
) -> pd.DataFrame:
    """
    Calculate the residuals from a given flatfile gsim(s) and imt(s)

    :param gsims: iterable of strings or ``GMPE`` instances
        denoting Ground shaking intensity models
    :param imts: iterable of strings or ``imt.IMT`` instances
        denoting intensity measures (Sa must be given with period, e.g. "SA(0.2)")
    :param flatfile: pandas DataFrame with the values
        of the ground motion properties required by the given models (param.
        `gsims`) and the observed intensity measures arranged in columns
    :param likelihood: boolean telling if also the likelihood of the residuals
        (according to Equation 9 of Scherbaum et al. (2004)) should be computed
        and returned
    :param mean: boolean telling if also the models mean (used to compute residuals)
        should be returned
    :param normalise: boolean (default True) normalize the residuals by
        the model standard deviations
    :param header_sep: str or None (default: " "): the separator used to concatenate
        each column header into one string (e.g. "PGA median BindiEtAl2014Rjb"). Set
        to "" or None to return a multi-level column header composed of the first 3
        dataframe rows (e.g. ("PGA", "median", "BindiEtAl2014Rjb"). See
        "MultiIndex / advanced indexing" in the pandas doc for details)

    :return: pandas DataFrame
    """
```



### get_measures_of_fit
```python
from egsim.smtk import get_measures_of_fit

# Signature and docstring:
def get_measures_of_fit(
    gsims: Iterable[str],
    imts: Iterable[str],
    residuals: pd.DataFrame,
    as_dataframe=True,
    edr_bandwidth=0.01,
    edr_multiplier=3.0
) -> pd.DataFrame | dict:
    """
    Retrieve several Measures of fit from the given residuals, models and imts

    :param gsims: the ground motion models (iterable of str)
    :param imts: the intensity measure types (iterable of str)
    :param residuals: the result of :ref:`get_residuals` where the residuals of the
        given model(s) and imt(s) are computed
    :param as_dataframe: whether to return Measures of fit as DataFrame (True,
        the default), or dict
    :param edr_bandwidth: bandwidth to use in EDR values computation (default 0.01)
    :param edr_multiplier: multiplier to use in EDR values computation (default 3.0)

    :return: a Pandas dataframe (columns: measures of fit, rows: model names) or
        dict[str, dict[str, float]] (measures of fit names mapped to a dict where model
        names are mapped to their measure of fit value
    """
```



### gsim_names
```python
from egsim.smtk import gsim_names

# Signature and docstring:
def gsim_names() -> Iterable[str]:
    """Return all model names registered in OpenQuake, as iterable"""
```



### imt_names
```python
from egsim.smtk import imt_names

# Signature and docstring:
def imt_names() -> Iterable[str]:
    """Return all IMT names registered in OpenQuake, as iterable"""
```



### gsim
```python
from egsim.smtk import gsim

# Signature and docstring:
def gsim(model: str | GMPE, raise_deprecated=True) -> GMPE:
    """
    Return a Gsim instance (Python object of class `GMPE`) from the given input

    :param model: a gsim name or Gsim instance. If str, it can also denote a
        GMPETable in the form "GMPETable(gmpe_table=filepath)"
    :param raise_deprecated: if True (the default) deprecated models will raise
        an `SmtkError`, otherwise they will be returned as normal models

    :raise: a `SmtkError` if for some reason the input is invalid
    """
```



### imt
```python
from egsim.smtk import imt

# Signature and docstring:
def imt(arg: float | str | IMT) -> IMT:
    """
    Return an IMT object from the given argument

    :raise: `SmtkError` if argument cannot be converted to a valid IMT
    """
```



### gsim_info
```python
from egsim.smtk import gsim_info

# Signature and docstring:
def gsim_info(model: GMPE) -> tuple[str, list, list, list| None]:
    """
    Return the model info as a tuple with elements:
     - the source code documentation (Python docstring) of the model
     - the list of the intensity measures defined for the model
     - the list of the ground motion properties required to compute the
        model predictions
     - the list of spectral acceleration period limits where the model
       is defined, or None if the model is not defined for SA
    """
```



### SmtkError
```python
from egsim.smtk import SmtkError

# Signature and docstring:
class SmtkError(Exception):
    """
    Base exception for any egsim.smtk error (e.g. invalid model, imt, flatfile error).

    The string representation of these kind of errors is the concatenation
    of the arguments given as input, separated by `self.separator` (= ", " by default)
    """

    separator = ', '

```



### FlatfileError
```python
from egsim.smtk import FlatfileError

# Signature and docstring:
class FlatfileError(SmtkError):
    """
    Subclass of :class:`SmtkError` describing a flatfile error
    (e.g., missing column, mising data, incompatible data type)
    """

    pass
```

