"""Registry with helper functions to access OpenQuake entities and properties"""
from typing import Union, Iterable

import re
import warnings
from openquake.baselib.general import DeprecationWarning as OQDeprecationWarning
from openquake.hazardlib import imt as imt_module
from openquake.hazardlib.gsim.base import GMPE, registry, gsim_aliases
from openquake.hazardlib.gsim.gmpe_table import GMPETable
from openquake.hazardlib import valid


registered_gsim_names = frozenset(registry)
registered_imt_names:frozenset  # initialized below


# OpenQuake lacks a registry of IMTs, so we need to inspect the imt module:
def _registered_imt_names() -> Iterable[str]:
    """Return all IMT names registered in OpenQuake"""
    for name in dir(imt_module):
        if name[0].upper() != name[0]:  # only upper-case module elements
            continue
        func = getattr(imt_module, name)
        if not callable(func):  # only callable
            continue
        f_code = getattr(func, '__code__', None)
        if f_code is None:
            continue
        # call the function with the required arguments, assuming all floats
        try:
            imt_obj = func(*[1. for _ in range(f_code.co_argcount)])  # noqa
            if isinstance(imt_obj, imt_module.IMT):
                yield name
        except (ValueError, TypeError, AttributeError):
            pass


registered_imt_names = frozenset(_registered_imt_names())


# invert `gsim_aliases` (see `gsim_name` below)
_gsim_aliases = {v: k for k, v in gsim_aliases.items()}


def gsim_name(gsim: GMPE) -> str:
    """
    Returns the name of the GMPE given an instance of the class
    """
    name = str(gsim)
    # if name is "[" + gsim.__class__.__name__ + "]", return the class name:
    if name == f"[{gsim.__class__.__name__}]":
        return gsim.__class__.__name__
    # name is the TOML representation of gsim. Use _gsim_aliases to return the name:
    return _gsim_aliases[name]


def gsim(name: str, raise_deprecated=True) -> GMPE:
    """Return a Gsim instance (Python object of class `GMPE`) from the given name

    :param name: a gsim name, if GMPETable, it must be of the form
        "GMPETable(gmpe_table=filepath)"
    :param raise_deprecated: if True (the default) OpenQuake `DeprecationWarning`s
        (`egsim.smtk.OQDeprecationWarning`) will raise as normal exceptions
    :raise: a `GsimInitError`
    """
    if name.startswith('GMPETable'):
        is_table = True
        known_exceptions = (TypeError, ValueError, FileNotFoundError, OSError)
    else:
        is_table=False
        known_exceptions = (TypeError, IndexError, KeyError)
        if raise_deprecated:
            known_exceptions += (OQDeprecationWarning,)

    try:
        if is_table:  # GMPETable
            match = re.match(r'^GMPETable\(([^)]+?)\)$', name)
            if match:
                filepath = match.group(1).split("=")[1]  # get table filename
                return GMPETable(gmpe_table=filepath)
            raise ValueError("Invalid string, expected "
                             "'GMPETable(gmpe_table=file_path)'")
        elif not raise_deprecated:  # registered Gsims (relaxed: allow deprecated)
            return valid.gsim(name)
        else:  # "normal" case: registered Gsims but raise DeprecationWarning
            with warnings.catch_warnings():
                warnings.filterwarnings('error', category=OQDeprecationWarning)
                return valid.gsim(name)
    except known_exceptions as exc:
        raise GsimInitError(gsim, exc) from None


class GsimInitError(Exception):
    """Gsim initialization error. General exception class harmonizing all known
     exceptions (accessible via `self.base_exception`) occurring
     during initialization of a Ground motion model (`self.gsim_name`)
    """
    def __init__(self, name, exc):
        self.base_exception = exc
        self.gsim_name = name
        super().__init__(f'{gsim}: initialization error ({exc.__class__.__name__})')


def sa_limits(gsim: Union[str, GMPE, type[GMPE]]) -> Union[tuple[float, float], None]:
    """Return the SA period limits defined for the given gsim, or None"""
    if isinstance(gsim, str):
        gsim = registry[gsim]
    pers = None
    for c in dir(gsim):
        if 'COEFFS' in c:
            pers = [sa.period for sa in getattr(gsim, c).sa_coeffs]
            break
    return (min(pers), max(pers)) if pers is not None else None


def rupture_params_required_by(gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    """Return the rupture parameters required by the given model"""
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return gsim.REQUIRES_RUPTURE_PARAMETERS or frozenset()  # "cast" to set if '' or (,)


def site_params_required_by(gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    """Return the site parameters required by the given model"""
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return gsim.REQUIRES_SITES_PARAMETERS or frozenset()  # "cast" to set if '' or (,)


def distances_required_by(gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    """Return the distance measures required by the given model"""
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return gsim.REQUIRES_DISTANCES or frozenset()  # "cast" to set if '' or (,)


def imts_defined_for(gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    """Return the intensity measures defined for the given model"""
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return frozenset(_.__name__ for _ in gsim.DEFINED_FOR_INTENSITY_MEASURE_TYPES)
