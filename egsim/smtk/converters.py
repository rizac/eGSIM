"""Converter functions for the strong motion modeller toolkit (smtk) package of eGSIM"""
from collections.abc import Collection

from typing import Union
import pandas as pd
import numpy as np
from scipy.constants import g


def vs30_to_z1pt0_cy14(vs30: Union[float, np.ndarray], japan=False):
    """Return the estimate depth to the 1.0 km/s velocity layer based on Vs30
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
    """Convert vs30 to depth to 2.5 km/s interface using model proposed by
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
        acceleration: Union[Collection[float], float], from_, to_) \
        -> Union[Collection[float], float]:
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

    raise ValueError("Unrecognised time history units. "
                     "Should take either ''g'', ''m/s/s'' or ''cm/s/s''")


def dataframe2dict(dframe: pd.DataFrame, as_json=True,
                   drop_empty_levels=True) -> dict[Union[str, tuple], list]:
    """Convert the given dataframe into a Python dict, in the format:
    ```
    { column:Union[str, tuple]: values:list[Any], ... }
    ```
    :param dframe: the input dataframe
    :param as_json: if True (the default), the dict will be JSON serializable, i.e.
        with `str` keys (multi-level hierarchical columns will be
        converted from tuples into nested dicts) and `None`s in-place of NaN or +-inf
    :param drop_empty_levels: if True (the default) trailing empty strings / None in
        hierarchical columns will be dropped. E.g. the `dict` item
        ('A', '', '') -> values will be returned as {'A' -> values}
    """
    if not as_json and not drop_empty_levels:
        # use pandas default method:
        return dframe.to_dict(orient='list')
    # customized output:
    output = {}
    df_na = None
    if as_json:
        df_na = dframe.isna() | dframe.isin([-np.inf, np.inf])
    for col, vals in dframe.to_dict(orient='series').items():
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
            col_na = df_na[col]
            if col_na.any():
                vals = vals.astype(object)
                vals[col_na] = None
        dest_ret[key] = vals.tolist()
    return output
