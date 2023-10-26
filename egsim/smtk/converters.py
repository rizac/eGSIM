"""Converter functions for the strong motion modeller toolkit (smtk) package of eGSIM"""
from collections.abc import Collection

from typing import Union
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


# FIXME REMOVE UNUSED

# def n_jsonify(obj: Union[Collection, int, float, np.generic]) -> \
#         Union[float, int, list, tuple, None]:
#     """Attempt to convert the numeric input to a Python object that is JSON serializable,
#     i.e. same as `obj.tolist()` but - in case `obj` is a list/tuple, with NoN or
#     infinite values converted to None.
#
#     :param obj: the numeric input to be converted. It can be a scalar or sequence as
#         plain Python or numpy object. If this argument is non-numeric, this function is
#         not guaranteed to return a JSON serializable object
#     """
#     # we could simply perform an iteration over `obj` but with numpy is faster. Convert
#     # to numpy object if needed:
#     np_obj = np.asarray(obj)
#
#     if np_obj.shape:  # np_obj is array
#         # `np_obj.dtype` is not float: try to cast it to float. This will be successful
#         # if obj contains `None`s and numeric values only:
#         if np.issubdtype(np_obj.dtype, np.object_):
#             try:
#                 np_obj = np_obj.astype(float)
#             except ValueError:
#                 # np_obj is a non-numeric array, leave it as it is
#                 pass
#         # if obj is a numeric list tuples, convert non-finite (nan, inf) to None:
#         if np.issubdtype(np_obj.dtype, np.floating):
#             na = ~np.isfinite(np_obj)
#             if na.any():  # has some non-finite numbers:
#                 np_obj = np_obj.astype(object)
#                 np_obj[na] = None
#                 return np_obj.tolist()  # noqa
#         # there were only finite values:
#         if isinstance(np_obj, (list, tuple)):  # we passed a list/tuple: return it
#             return obj
#         # we passed something else (e.g. a np array):
#         return np_obj.tolist()  # noqa
#
#     # np_obj is scalar:
#     num = np_obj.tolist()
#     # define infinity (note that inf == np.inf so the set below is verbose).
#     # NaNs will be checked via `x != x` which works also when x is not numeric
#     if num != num or num in {inf, -inf, np.inf, -np.inf}:
#         return None
#     return num  # noqa
#
#
