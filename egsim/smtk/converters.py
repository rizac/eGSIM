"""Converter functions for the strong motion modeller toolkit (smtk) package of eGSIM"""

from collections.abc import Collection

from typing import Union
import pandas as pd
import numpy as np
from scipy.constants import g


def vs30_to_z1pt0_cy14(vs30: Union[float, np.ndarray], japan=False):
    """
    Return the estimate depth to the 1.0 km/s velocity layer based on Vs30
    from Chiou & Youngs (2014) California model

    :param vs30: Vs30 value(s) in m/s
    :param bool japan: if true returns the Japan model, otherwise the California model

    :return:Z1.0 in m
    """
    if japan:
        c1 = 412. ** 2.
        c2 = 1360.0 ** 2.
        return np.exp((-5.23 / 2.0) * np.log((np.power(vs30, 2.) + c1) / (
            c2 + c1)))
    else:
        c1 = 571 ** 4.
        c2 = 1360.0 ** 4.
        return np.exp((-7.15 / 4.0) * np.log((vs30 ** 4. + c1) / (c2 + c1)))


def vs30_to_z2pt5_cb14(vs30: Union[float, np.ndarray], japan=False):
    """
    Convert vs30 to depth to 2.5 km/s interface using model proposed by
    Campbell & Bozorgnia (2014)

    :param vs30: Vs30 value(s)
    :param bool japan: Use Japan formula (True) or California formula (False)

    :return: Z2.5 in km
    """
    if japan:
        return np.exp(5.359 - 1.102 * np.log(vs30))
    else:
        return np.exp(7.089 - 1.144 * np.log(vs30))


def convert_accel_units(
        acceleration: Union[Collection[float], float], from_: str, to_: str
) -> Union[Collection[float], float]:
    """
    Convert units of number or numeric array representing acceleration

    :param acceleration: the acceleration (numeric or numpy array)
    :param from_: unit of `acceleration`: string in "g", "m/s/s", "m/s**2",
        "m/s^2", "cm/s/s", "cm/s**2" or "cm/s^2"
    :param to_: new unit of `acceleration`: string in "g", "m/s/s", "m/s**2",
        "m/s^2", "cm/s/s", "cm/s**2" or "cm/s^2". When missing, it defaults
        to "cm/s/s"

    :return: acceleration converted to the given units (by default, 'cm/s/s')
    """
    m_sec_square = ("m/s/s", "m/s**2", "m/s^2")
    cm_sec_square = ("cm/s/s", "cm/s**2", "cm/s^2")
    acceleration = np.asarray(acceleration)
    if from_ == 'g':
        if to_ == 'g':
            return acceleration
        if to_ in m_sec_square:
            return acceleration * g
        if to_ in cm_sec_square:
            return acceleration * (100 * g)
    elif from_ in m_sec_square:
        if to_ == 'g':
            return acceleration / g
        if to_ in m_sec_square:
            return acceleration
        if to_ in cm_sec_square:
            return acceleration * 100
    elif from_ in cm_sec_square:
        if to_ == 'g':
            return acceleration / (100 * g)
        if to_ in m_sec_square:
            return acceleration / 100
        if to_ in cm_sec_square:
            return acceleration

    raise ValueError(
        "Unrecognised time history units. "
        "Should take either ''g'', ''m/s/s'' or ''cm/s/s''"
    )


def dataframe2dict(
    dframe: pd.DataFrame, as_json=True,
    drop_empty_levels=True,
    orient: str = 'list',  # or 'dict'
) -> dict[Union[str, tuple], list]:
    """
    Convert the given dataframe into a Python dict, in the format:
    ```
    { column:Union[str, tuple]: values:list[Any], ... }
    ```
    :param dframe: the input dataframe
    :param as_json: if True (the default), the dict will be JSON serializable, i.e.
        with `str` keys (multi-level hierarchical columns will be
        converted from tuples into nested dicts) and `None`s in-place of NaN or +-inf
    :param drop_empty_levels: if True (the default) trailing empty strings / None in
        hierarchical columns will be dropped. E.g. the `dict` item
        ("A", "", "") -> values will be returned as {'A' -> values}
    :param orient: determines the type of values of the dictionary:
        ‘dict’ (default) : dict like: {column -> {index -> value}}. Each column is
        mapped to a dict where each index value is mapped to the column value.
        Useful when the DataFrame index is a str or something meaningful: e
        ‘list’ : list like {column -> [values]}. Each column is mapped to the
        relative values, converted as list. Useful when the DataFrame index is the
        default RangeIndex indicating only the row position
    """
    # RangeIndex (0, 1, ...) the default index when no explicit index is provided:
    assert orient in ('list', 'dict'), 'orient should be either "list" ot "dict"'
    if not as_json and not drop_empty_levels:
        # use pandas default method:
        return dframe.to_dict(orient=orient)  # noqa
    # customized output:
    output = {}
    df_na = None
    if as_json:
        df_na = na_values(dframe)
    for col, series in dframe.to_dict(orient='series').items():
        if drop_empty_levels and isinstance(col, tuple):
            # multi-index columns (hierarchical), remove trailing '' / None:
            keys = list(col)
            while len(keys) > 1 and not keys[-1]:
                keys.pop()
            key = tuple(keys) if len(keys) > 1 else keys[0]
        else:
            key = col
        dest_ret = output
        if as_json:
            if isinstance(key, tuple):  # multi-index columns (hierarchical)
                # str keys only => create nested dicts
                for kol in key[:-1]:
                    dest_ret = dest_ret.setdefault(str(kol), {})
                key = key[-1]
            key = str(key)
            # remove nan +-inf:
            vals = array2json(series, df_na[col])
        else:
            vals = series.tolist()
        if orient == 'list':
            dest_ret[key] = vals
        else:
            dest_ret[key] = dict(zip(series.index.astype(str), vals))
    return output


def na_values(
    values: Union[pd.Series, pd.DataFrame, np.ndarray]
) -> Union[pd.Series, pd.DataFrame, np.ndarray]:
    """Return a bool ndarray of values that are na (pandas "na" or +-inf)"""

    return pd.isna(values) | np.isin(values, [np.inf, -np.inf])


def array2json(
    values: Union[pd.Series, np.ndarray, pd.DataFrame],
    na_vals: Union[pd.Series, np.ndarray, pd.DataFrame, bool, None] = None
) -> list:
    """
    Convert `values` to a JSON serializable list, basically converting
    all NA (NaN, Null, +-Inf, NaT) into None (null in JSON)

    :param values: the values (pandas Series/ DataFrame or nd array)
    :param na_vals: True, False or boolean array (the same shape of `values`)
        indicating which element is NA or +-inf. if None/True (the default)
        the array will be inferred from `values`. If False, no check for NA or +-inf
        will be performed, meaning that `values` is known to have only finite values
    """
    values = np.asarray(values)  # in case of pd.Series S, returns S.values by ref.
    if na_vals is not False:
        if na_vals is None or na_vals is True:
            na_vals = na_values(values)
        if na_vals.any():
            values = values.astype(object)
            values[na_vals] = None
    return values.tolist()  # noqa


def datetime2str(
    values: Union[np.ndarray, pd.Series], dformat='%Y-%m-%dT%H:%M:%S'
) -> np.ndarray:
    """
    Convert `values` to a numpy array of date-time strings

    :param values: A sequence of date-time-like values (e.g. numpy array, pandas Series,
        list. See pandas `to_datetime` for details)
    :param dformat: the string format of the resulting strings, defaults to
        '%Y-%m-%dT%H:%M:%S' (for millisecond resolution, use  '%Y-%m-%dT%H:%M:%S.%f')
    """
    if isinstance(values, pd.Series):
        values = values.values
        # Note: pd.to_datetime(series) > series,
        # pd.to_datetime(ndarray or list) > DatetimeIndex.
        # In the latter case we can use `strftime`, which will also preserves
        # NAs (so `pd.isna` will work on it):
    return pd.to_datetime(values).strftime(dformat).values  # noqa


def datetime2float(values: Union[np.ndarray, pd.Series]) -> np.ndarray:
    """
    Convert `values` to a numpy array of date-time floats (unit: second)

    :param values: A sequence of date-time-like values (e.g. numpy array, pandas Series,
        list. See pandas `to_datetime` for details)
    """
    values = pd.to_datetime(values)
    ret = np.full_like(values, np.nan, dtype=float)
    flt = np.isfinite(values)
    ret[flt] = values[flt].astype(int) / 10 ** 9
    return ret
