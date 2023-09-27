"""Root module for the strong motion modeller toolkit (smtk) package of eGSIM"""

from typing import Union, Type
from collections.abc import Iterable, Collection
from math import inf
import re
import warnings
from scipy.constants import g
import numpy as np
from openquake.baselib.general import DeprecationWarning as OQDeprecationWarning
from openquake.hazardlib import imt
from openquake.hazardlib.gsim.gmpe_table import GMPETable
from openquake.hazardlib.gsim.base import GMPE, registry, gsim_aliases
from openquake.hazardlib import valid


# Regular expression to get a GMPETable from string:
_gmpetable_regex = re.compile(r'^GMPETable\(([^)]+?)\)$')


def get_gsim_names(sort=False) -> Iterable[str]:
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


def check_gsim_list(gsims) -> dict[str, GMPE]:
    """
    Check the GSIM models or strings in `gsims`, and return a dict of
    gsim names (str) mapped to their :class:`openquake.hazardlib.Gsim`.
    Raises error if any Gsim in the list is supported in OpenQuake.

    If a Gsim is passed as instance, its string representation is inferred
    from the class name and optional arguments. If a Gsim is passed as string,
    the associated class name is fetched from the OpenQuake available Gsims.

    :param gsims: list of GSIM names (str) or OpenQuake Gsim classes
    :return: a dict of GSIM names (str) mapped to the associated GSIM
    """
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

    return output_gsims


def get_gsim_name(gsim: GMPE) -> str:
    """
    Returns the name of the GMPE given an instance of the class
    """
    match = _gmpetable_regex.match(str(gsim))  # GMPETable ?
    if match:
        filepath = match.group(1).split("=")[1][1:-1]
        return 'GMPETable(gmpe_table=%s)' % filepath
    else:
        gsim_toml_repr = str(gsim)
        # gsim_toml_repr should be a TOML version of the gsim. We could return it,
        # but we want to return the name that allows us to make this function the
        # opposite of `get_gsim_instance`. So:
        # 1. `gsim_toml_repr` is actually "[<gsim_class_name>]": in this case
        # just return <class_name>:
        gsim_class_name = gsim.__class__.__name__
        if gsim_toml_repr == f'[{gsim_class_name}]':
            return gsim_class_name
        # 2. gsim is an aliased version of some model M. In this case, `
        # gsim_toml_repr` can be reduced to the simple class name of M:
        gsim_src = _get_src_name_from_aliased_version(gsim_toml_repr)  # might be None
        return gsim_src or gsim_toml_repr


_gsim_aliases: Union[dict[str, str], None] = None


def _get_src_name_from_aliased_version(gsim_toml_repr: str):
    global _gsim_aliases
    if _gsim_aliases is None:
        _gsim_aliases = {v: k for k, v in gsim_aliases.items()}
    return _gsim_aliases.get(gsim_toml_repr, None)


def get_rupture_params_required_by(gsim: Union[str, GMPE, Type[GMPE]]) -> frozenset[str]:
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return gsim.REQUIRES_RUPTURE_PARAMETERS or frozenset()  # "cast" to set if '' or (,)


def get_sites_params_required_by(gsim: Union[str, GMPE, Type[GMPE]]) -> frozenset[str]:
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return gsim.REQUIRES_SITES_PARAMETERS or frozenset()  # "cast" to set if '' or (,)


def get_distances_required_by(gsim: Union[str, GMPE, Type[GMPE]]) -> frozenset[str]:
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return gsim.REQUIRES_DISTANCES or frozenset()  # "cast" to set if '' or (,)


def get_imts_defined_for(gsim: Union[str, GMPE, Type[GMPE]]) -> frozenset[str]:
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return frozenset(_.__name__ for _ in gsim.DEFINED_FOR_INTENSITY_MEASURE_TYPES)


def n_jsonify(obj: Union[Collection, int, float, np.generic]) -> \
        Union[float, int, list, tuple, None]:
    """Attempt to convert the numeric input to a Python object that is JSON serializable,
    i.e. same as `obj.tolist()` but - in case `obj` is a list/tuple, with NoN or
    infinite values converted to None.

    :param obj: the numeric input to be converted. It can be a scalar or sequence as
        plain Python or numpy object. If this argument is non-numeric, this function is
        not guaranteed to return a JSON serializable object
    """
    # we could simply perform an iteration over `obj` but with numpy is faster. Convert
    # to numpy object if needed:
    np_obj = np.asarray(obj)

    if np_obj.shape:  # np_obj is array
        # `np_obj.dtype` is not float: try to cast it to float. This will be successful
        # if obj contains `None`s and numeric values only:
        if np.issubdtype(np_obj.dtype, np.object_):
            try:
                np_obj = np_obj.astype(float)
            except ValueError:
                # np_obj is a non-numeric array, leave it as it is
                pass
        # if obj is a numeric list tuples, convert non-finite (nan, inf) to None:
        if np.issubdtype(np_obj.dtype, np.floating):
            na = ~np.isfinite(np_obj)
            if na.any():  # has some non-finite numbers:
                np_obj = np_obj.astype(object)
                np_obj[na] = None
                return np_obj.tolist()  # noqa
        # there were only finite values:
        if isinstance(np_obj, (list, tuple)):  # we passed a list/tuple: return it
            return obj
        # we passed something else (e.g. a np array):
        return np_obj.tolist()  # noqa

    # np_obj is scalar:
    num = np_obj.tolist()
    # define infinity (note that inf == np.inf so the set below is verbose).
    # NaNs will be checked via `x != x` which works also when x is not numeric
    if num != num or num in {inf, -inf, np.inf, -np.inf}:
        return None
    return num  # noqa


def convert_accel_units(acceleration, from_, to_='cm/s/s'):  # noqa
    """
    Legacy function which can still be used to convert acceleration from/to
    different units

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
    # check also that the period is finite (SA('inf') and SA('nan') are possible,
    # and this function is intended to return a "workable" period):
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
