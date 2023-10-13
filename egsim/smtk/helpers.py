"""Helper functions for the strong motion modeller toolkit (smtk) package of eGSIM"""

from typing import Union
from collections.abc import Iterable
import re
import warnings
import numpy as np
from openquake.baselib.general import DeprecationWarning as OQDeprecationWarning
from openquake.hazardlib import imt
from openquake.hazardlib.gsim.gmpe_table import GMPETable
from openquake.hazardlib.gsim.base import GMPE, registry, gsim_aliases
from openquake.hazardlib import valid


# Regular expression to get a GMPETable from string:
_gmpetable_regex = re.compile(r'^GMPETable\(([^)]+?)\)$')


def get_registered_gsim_names(sort=False) -> Iterable[str]:
    """Return all Gsim names registered in OpenQuake"""
    if not sort:
        yield from registry  # it's a dict, yield just the keys (names)
    else:
        yield from sorted(registry)


def get_gsim_instance(gsim_name: str, raise_deprecated=True) -> GMPE:
    """Return a Gsim from the given name

    :param raise_deprecated: if True (the default) OpenQuake `DeprecationWarning`s
        (`egsim.smtk.OQDeprecationWarning`) will raise as normal exceptions
    """
    if not raise_deprecated:
        return valid.gsim(gsim_name)
    with warnings.catch_warnings():
        warnings.filterwarnings('error', category=OQDeprecationWarning)
        return valid.gsim(gsim_name)


def harmonize_input_gsims(
        gsims: Iterable[Union[str, type[GMPE], GMPE]]) -> dict[str, GMPE]:
    """harmonize GSIMs given as names (str), OpenQuake Gsim classes or instances
    (:class:`GMPE`) into a dict[str, GMPE] where each name is mapped to
    the relative Gsim instance. Names will be sorted ascending.

    This method accounts for Gsim aliases stored in OpenQuake, and assures
    that each key, value of the returned dict:
    ```
        get_gsim_instance(key) == value
        get_gsim_name(value) == key
    ```

    :param gsims: iterable of GSIM names (str), OpenQuake Gsim classes or instances
    :return: a dict of GSIM names (str) mapped to the associated GSIM. Names (dict
        keys) are sorted ascending
    """
    if isinstance(gsims, dict):
        if all(isinstance(k, str) and isinstance(v, GMPE) for k, v in gsims.items()):
            return gsims
        raise ValueError('Invalid dict type, expected `dict[str, GMPE]`')
    
    output_gsims = {}
    for gs in gsims:
        if isinstance(gs, GMPE):
            output_gsims[get_gsim_name(gs)] = gs  # get name of GMPE instance
        elif gs in registry:
            output_gsims[gs] = get_gsim_instance(gs)
        else:
            match = _gmpetable_regex.match(gs)  # GMPETable ?
            if match:
                filepath = match.group(1).split("=")[1]  # get table filename
                output_gsims[gs] = GMPETable(gmpe_table=filepath)
            else:
                raise ValueError('%s not supported by OpenQuake' % str(gs))

    return {k: output_gsims[k] for k in sorted(output_gsims)}


def get_gsim_name(gsim: GMPE) -> str:
    """
    Returns the name of the GMPE given an instance of the class
    """
    match = _gmpetable_regex.match(str(gsim))  # GMPETable ?
    if match:
        filepath = match.group(1).split("=")[1][1:-1]
        return 'GMPETable(gmpe_table=%s)' % filepath
    else:
        gsim_toml_repr = str(gsim)  # TOML version of the gsim (see source code)
        # We want to return a string representation of gsim (called `s`) such as
        # `get_gsim_instance(s) = gsim`. `gsim_toml_repr` might not be such a string:
        # 1. `gsim_toml_repr` is actually "[<gsim_class_name>]": in this case
        # just return <class_name>:
        gsim_class_name = gsim.__class__.__name__
        if gsim_toml_repr == f'[{gsim_class_name}]':
            return gsim_class_name
        # 2. gsim is an aliased version of some other gsim. In this case, `
        # gsim_toml_repr` can be reduced to the simple class name of that gsim:
        gsim_src = _get_src_name_from_aliased_version(gsim_toml_repr)  # might be None
        return gsim_src or gsim_toml_repr


_gsim_aliases: Union[dict[str, str], None] = None


def _get_src_name_from_aliased_version(gsim_toml_repr: str):
    global _gsim_aliases
    if _gsim_aliases is None:
        _gsim_aliases = {v: k for k, v in gsim_aliases.items()}
    return _gsim_aliases.get(gsim_toml_repr, None)


def harmonize_input_imts(imts: Iterable[Union[str, imt.IMT]]) -> dict[str, imt.IMT]:
    """harmonize IMTs given as names (str) or instances (IMT) returning a
    dict[str, IMT] where each name is mapped to the relative instance. Dict keys will
    be sorted ascending comparing SAs using their period. E.g.: 'PGA' 'SA(2)' 'SA(10)'
    """
    ret = []
    for imt_item in imts:
        imt_inst = imt_item
        if not isinstance(imt_inst, imt.IMT):
            imt_inst = imt.from_string(str(imt_inst))
            if not isinstance(imt_inst, imt.IMT):
                raise ValueError(f'Invalid imt: {str(imt_inst)}')
        ret.append(imt_inst)

    return {repr(i): i for i in sorted(ret, key=_imtkey)}


def _imtkey(imt_inst) -> tuple[str, float]:
    period = get_SA_period(imt_inst)
    if period is not None:
        return 'SA', period
    else:
        return imt_inst.string, -np.inf


def check_compatibility(gsims: dict[str, GMPE], imts: dict[str, imt.IMT]):
    periods = {}
    imtz = set()
    # get SA periods, and put in imtz just the imt names (e.g. 'SA' not 'SA(2.0)'):
    for imt_name, imtx in imts.items():
        period = get_SA_period(imtx)
        if period is not None:
            periods[period] = imt_name
            imt_name = imt_name[:imt_name.index('(')]
        imtz.add(imt_name)
    invalid = {}  # dict[str, set[str]] (model name -> incompatible imts)
    for gsim_name, gsim in gsims.items():
        invalid_imts = imtz - get_imts_defined_for(gsim)
        if 'SA' not in invalid_imts and periods:
            for p in get_invalid_sa_periods(gsim, periods):
                invalid_imts.add(periods[p])
        if not invalid_imts:
            continue
        invalid[gsim_name] = invalid_imts

    if invalid:
        unique_imts = len(set(i for imts in invalid.values() for i in imts))
        err = ValueError(f'{len(invalid)} '
                         f'model{"s are" if len(invalid) !=1 else " is"} '
                         f'not compatible with all IMTs (vice versa, {unique_imts} '
                         f'IMT{"s" if unique_imts != 1 else ""} '
                         f'are not compatible with all models)')
        err.invalid = invalid
        raise err from None


def get_invalid_sa_periods(
        gsim: GMPE, sa_periods: Iterable[float]) -> Iterable[float]:
    """Return the SA periods in `sa_periods` that are NOT supported by the
    model `gsim`
    """
    if 'SA' not in get_imts_defined_for(gsim):
        yield from sa_periods
    else:
        limits = get_sa_limits(gsim)
        if limits is not None:
            for period in sa_periods:
                if period < limits[0] or period > limits[1]:
                    yield period


def get_sa_limits(gsim: GMPE) -> Union[tuple[float, float], None]:
    """Return the SA period limits defined for the given gsim, or None"""
    pers = None
    for c in dir(gsim):
        if 'COEFFS' in c:
            pers = [sa.period for sa in getattr(gsim, c).sa_coeffs]
            break
    return (min(pers), max(pers)) if pers is not None else None


def get_rupture_params_required_by(gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return gsim.REQUIRES_RUPTURE_PARAMETERS or frozenset()  # "cast" to set if '' or (,)


def get_sites_params_required_by(gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return gsim.REQUIRES_SITES_PARAMETERS or frozenset()  # "cast" to set if '' or (,)


def get_distances_required_by(gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return gsim.REQUIRES_DISTANCES or frozenset()  # "cast" to set if '' or (,)


def get_imts_defined_for(gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return frozenset(_.__name__ for _ in gsim.DEFINED_FOR_INTENSITY_MEASURE_TYPES)


def get_SA_period(obj: Union[str, imt.IMT]) -> Union[float, None]:
    """Return the period (float) from the given `obj` argument, or None if `obj`
    does not indicate a Spectral Acceleration object/string with a finite period
    (e.g. "SA(NaN)", "SA(inf)", "SA" return None).

    :arg: str or `imt.IMT` instance, such as "SA(1.0)" or `imt.SA(1.0)`
    """
    if isinstance(obj, str):
        if not obj.startswith('SA('):  # fast check to return immediately in case
            return None
        try:
            obj = imt.from_string(obj)
        except ValueError:
            return None
    elif isinstance(obj, imt.IMT):
        if not obj.string.startswith('SA('):
            return None
    else:
        return None

    period = obj.period
    # check also that the period is finite (SA('inf') and SA('nan') are possible:
    # this function is intended to return a "workable" period):
    return float(period) if np.isfinite(period) else None


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
# def convert_accel_units(acceleration, from_, to_='cm/s/s'):  # noqa
#     """
#     Legacy function which can still be used to convert acceleration from/to
#     different units
#
#     :param acceleration: the acceleration (numeric or numpy array)
#     :param from_: unit of `acceleration`: string in "g", "m/s/s", "m/s**2",
#         "m/s^2", "cm/s/s", "cm/s**2" or "cm/s^2"
#     :param to_: new unit of `acceleration`: string in "g", "m/s/s", "m/s**2",
#         "m/s^2", "cm/s/s", "cm/s**2" or "cm/s^2". When missing, it defaults
#         to "cm/s/s"
#
#     :return: acceleration converted to the given units (by default, 'cm/s/s')
#     """
#     m_sec_square = ("m/s/s", "m/s**2", "m/s^2")
#     cm_sec_square = ("cm/s/s", "cm/s**2", "cm/s^2")
#     acceleration = np.asarray(acceleration)
#     if from_ == 'g':
#         if to_ == 'g':
#             return acceleration
#         if to_ in m_sec_square:
#             return acceleration * g
#         if to_ in cm_sec_square:
#             return acceleration * (100 * g)
#     elif from_ in m_sec_square:
#         if to_ == 'g':
#             return acceleration / g
#         if to_ in m_sec_square:
#             return acceleration
#         if to_ in cm_sec_square:
#             return acceleration * 100
#     elif from_ in cm_sec_square:
#         if to_ == 'g':
#             return acceleration / (100 * g)
#         if to_ in m_sec_square:
#             return acceleration / 100
#         if to_ in cm_sec_square:
#             return acceleration
#
#     raise ValueError("Unrecognised time history units. "
#                      "Should take either ''g'', ''m/s/s'' or ''cm/s/s''")

