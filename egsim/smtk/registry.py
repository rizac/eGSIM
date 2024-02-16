"""Registry with helper functions to access OpenQuake entities and properties"""
from typing import Union, Iterable, Callable
import re

from openquake.hazardlib import imt as imt_module
from openquake.hazardlib.imt import IMT, from_string as imt_from_string
from openquake.hazardlib.gsim.base import GMPE, registry, gsim_aliases
from openquake.hazardlib.gsim.gmpe_table import GMPETable
from openquake.hazardlib.valid import gsim as valid_gsim

from .flatfile import ColumnsRegistry


registered_gsims:dict[str, type[GMPE]] = registry.copy()


def gsim(gmm: Union[str, type[GMPE], GMPE], raise_deprecated=True) -> GMPE:
    """Return a Gsim instance (Python object of class `GMPE`) from the given input

    :param gmm: a gsim name, class or instance (in this latter case, the instance is
        returned). If str, it can also denote a GMPETable in the form
        "GMPETable(gmpe_table=filepath)"
    :param raise_deprecated: if True (the default) OpenQuake `DeprecationWarning`s
        will raise (as normal Python  `DeprecationWarning`)
    :raise: a `(TypeError, ValueError, FileNotFoundError, OSError, AttributeError)`
        if name starts with "GMPETable", otherwise a
        `(TypeError, IndexError, KeyError, ValueError, DeprecationWarning)`
        (the last one only if `raise_deprecated` is True, the default)
    """
    if isinstance(gmm, type) and issubclass(gmm, GMPE):
        gmm = gsim(gmm.__name__)
    if isinstance(gmm, str):
        is_table = gmm.startswith('GMPETable')
        if is_table:
            # GMPETable. raises: TypeError, ValueError, FileNotFoundError, OSError,
            # AttributeError
            filepath = re.match(r'^GMPETable\(([^)]+?)\)$', gmm).\
                group(1).split("=")[1]  # get table filename
            return GMPETable(gmpe_table=filepath)
        else:
            # "normal" str case, calls valid_gsim which raises:
            # TypeError, IndexError, KeyError, ValueError
            gmm = valid_gsim(gmm)
    if isinstance(gmm, GMPE):
        if raise_deprecated and gmm.superseded_by:
            raise DeprecationWarning(f'Use {gmm.superseded_by} instead')
        return gmm
    raise TypeError(gmm)


def imt(arg: Union[float, str, IMT]) -> IMT:
    """Return a IMT object from the given argument

    :raise: TypeError, ValueError, KeyError
    """
    if isinstance(arg, IMT):
        return arg
    return imt_from_string(str(arg))


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

# FIXME: REMOVE:
# def rupture_params_required_by(*gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
#     """Return the rupture parameters required by the given model(s)"""
#     ret = []
#     for model in gsim:
#         if isinstance(model, str):
#             model = registry[model]
#         ret.extend(model.REQUIRES_RUPTURE_PARAMETERS or [])
#     return frozenset(ret)
#
#
# def site_params_required_by(*gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
#     """Return the site parameters required by the given model(s)"""
#     ret = []
#     for model in gsim:
#         if isinstance(model, str):
#             model = registry[model]
#         ret.extend(model.REQUIRES_SITES_PARAMETERS or [])
#     return frozenset(ret)
#
#
# def distances_required_by(*gsim: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
#     """Return the distance measures required by the given model(s)"""
#     ret = []
#     for model in gsim:
#         if isinstance(model, str):
#             model = registry[model]
#         ret.extend(model.REQUIRES_DISTANCES or [])
#     return frozenset(ret)


def intensity_measures_defined_for(model: Union[str, GMPE, type[GMPE]]) -> frozenset[str]:
    """Return the intensity measures defined for the given model"""
    if not isinstance(model, GMPE):
        # creating a new GMPE via `gsim`is not super efficient wrt getting the class
        # name via `registry`, but the latter has sometimes the attributes below
        # empty (something to do with GMPE aliases I guess)
        model = gsim(model)
    return frozenset(_.__name__ for _ in model.DEFINED_FOR_INTENSITY_MEASURE_TYPES)


def ground_motion_properties_required_by(
        *models: Union[str, GMPE, type[GMPE]],
        as_ff_column=False) -> frozenset[str]:
    """Return the required ground motion properties (distance measures,
       rupture and site params all together)

    :param as_ff_column: False (the default) will return the ground motion property
        names as implemented in OpenQuake. True will check any property
        and return the relative flatfile column registered in this package
    """
    ret = []
    for model in models:
        if not isinstance(model, GMPE):
            # creating a new GMPE via `gsim`is not super efficient wrt getting the class
            # name via `registry`, but the latter has sometimes the attributes below
            # empty (something to do with GMPE aliases I guess)
            model = gsim(model)
        ret.extend(model.REQUIRES_DISTANCES or [])
        ret.extend(model.REQUIRES_SITES_PARAMETERS or [])
        ret.extend(model.REQUIRES_RUPTURE_PARAMETERS or [])
    if as_ff_column:
        return frozenset(ColumnsRegistry.get_aliases(c)[0] for c in ret)
    return frozenset(ret)
