"""Registry with helper functions to access OpenQuake entities and properties"""
from typing import Union, Iterable, Callable

from openquake.hazardlib import imt as imt_module
from openquake.hazardlib.imt import IMT
from openquake.hazardlib.gsim.base import GMPE, registry, gsim_aliases

from .flatfile import ColumnsRegistry


registered_gsims:dict[str, type[GMPE]] = registry.copy()


# OpenQuake lacks a registry of IMTs, so we need to inspect the imt module:
def _registered_imts() -> Iterable[tuple[str, Callable]]:
    """Return all IMT names registered in OpenQuake"""
    for name in dir(imt_module):
        if not ('A' <= name[:1] <= 'Z'):  # only upper-case module elements
            continue
        func = getattr(imt_module, name)
        if not callable(func):  # only callable
            continue
        # call the function with the required arguments, assuming all floats
        try:
            imt_obj = func(*[1. for _ in range(func.__code__.co_argcount)])  # noqa
            if isinstance(imt_obj, IMT):
                yield name, func
        except (ValueError, TypeError, AttributeError):
            pass


registered_imts:dict[str, Callable] = dict(_registered_imts())


# invert `gsim_aliases` (see `gsim_name` below)
_gsim_aliases = {v: k for k, v in gsim_aliases.items()}


def gsim_name(gsim: Union[type[GMPE], GMPE]) -> str:
    """
    Returns the name of the GMPE given an instance of the class
    """
    if isinstance(gsim, type) and issubclass(gsim, GMPE):  # is a class
        return gsim.__name__
    name = str(gsim)
    # if name is "[" + gsim.__class__.__name__ + "]", return the class name:
    if name == f"[{gsim.__class__.__name__}]":
        return gsim.__class__.__name__
    # name is the TOML representation of gsim. Use _gsim_aliases to return the name:
    return _gsim_aliases[name]


def imt_name(imtx: Union[Callable, IMT]) -> str:
    if isinstance(imtx, IMT):
        return repr(imtx)
    # it's a callable (e.g. a function defined in the openquake `imt` module):
    return imtx.__name__


def gsim_sa_limits(gsim: Union[str, GMPE, type[GMPE]]) -> Union[tuple[float, float], None]:
    """Return the SA period limits defined for the given gsim, or None"""
    if isinstance(gsim, str):
        gsim = registry[gsim]
    pers = None
    for c in dir(gsim):
        if 'COEFFS' in c:
            pers = [sa.period for sa in getattr(gsim, c).sa_coeffs]
            break
    return (min(pers), max(pers)) if pers is not None else None


def rupture_params_required_by(*gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    """Return the rupture parameters required by the given model(s)"""
    ret = []
    for model in gsim:
        if isinstance(model, str):
            model = registry[model]
        ret.extend(model.REQUIRES_RUPTURE_PARAMETERS or [])
    return frozenset(ret)


def site_params_required_by(*gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    """Return the site parameters required by the given model(s)"""
    ret = []
    for model in gsim:
        if isinstance(model, str):
            model = registry[model]
        ret.extend(model.REQUIRES_SITES_PARAMETERS or [])
    return frozenset(ret)


def distances_required_by(*gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    """Return the distance measures required by the given model(s)"""
    ret = []
    for model in gsim:
        if isinstance(model, str):
            model = registry[model]
        ret.extend(model.REQUIRES_DISTANCES or [])
    return frozenset(ret)


def intensity_measures_defined_for(gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    """Return the intensity measures defined for the given model"""
    if isinstance(gsim, str):
        gsim = registry[gsim]
    return frozenset(_.__name__ for _ in gsim.DEFINED_FOR_INTENSITY_MEASURE_TYPES)


def ground_motion_properties_required_by(
        *gsim: Union[str, GMPE, type[GMPE]],
        as_ff_column=False) -> frozenset[str]:
    """Return the required ground motion properties (distance measures,
       rupture and site params all together)

    :param as_ff_column: False (the default) will return the ground motion property
        names as implemented in OpenQuake. True will check any property
        and return the relative flatfile column registered in this package
    """
    ret = []
    for model in gsim:
        if isinstance(model, str):
            model = registry[model]
        ret.extend(model.REQUIRES_DISTANCES or [])
        ret.extend(model.REQUIRES_SITES_PARAMETERS or [])
        ret.extend(model.REQUIRES_RUPTURE_PARAMETERS or [])
    if as_ff_column:
        return frozenset(ColumnsRegistry.get_aliases(c)[0] for c in ret)
    return frozenset(ret)
