"""Registry with helper functions to access OpenQuake entities and properties"""
from typing import Union, Iterable, Callable
import re
import numpy as np

from openquake.hazardlib import imt as imt_module
from openquake.hazardlib.imt import IMT, from_string as imt_from_string
from openquake.hazardlib.gsim.base import GMPE, registry, gsim_aliases
from openquake.hazardlib.gsim.gmpe_table import GMPETable
from openquake.hazardlib.valid import gsim as valid_gsim


# added for compatibility with registered_imts (see below)
registered_gsims: dict[str, type[GMPE]] = registry


def gsim(model: Union[str, GMPE], raise_deprecated=True) -> GMPE:
    """
    Return a Gsim instance (Python object of class `GMPE`) from the given input

    :param model: a gsim name or Gsim instance. If str, it can also denote a
        GMPETable in the form "GMPETable(gmpe_table=filepath)"
    :param raise_deprecated: if True (the default) OpenQuake `DeprecationWarning`s
        will raise (as normal Python  `DeprecationWarning`)
    :raise: a `(TypeError, ValueError, FileNotFoundError, OSError, AttributeError)`
        if name starts with "GMPETable", otherwise a
        `(TypeError, IndexError, KeyError, ValueError, DeprecationWarning)`
        (the last one only if `raise_deprecated` is True, the default)
    """
    if isinstance(model, str):
        if model.startswith('GMPETable'):
            # GMPETable. raises: TypeError, ValueError, FileNotFoundError, OSError,
            # AttributeError
            filepath = re.match(r'^GMPETable\(([^)]+?)\)$', model).\
                group(1).split("=")[1]  # get table filename
            return GMPETable(gmpe_table=filepath)
        else:
            # "normal" str case, calls valid_gsim which raises:
            # TypeError, IndexError, KeyError, ValueError
            model = valid_gsim(model)
    if isinstance(model, GMPE):
        if raise_deprecated and model.superseded_by:
            raise DeprecationWarning(f'Use {model.superseded_by} instead')
        return model
    raise TypeError(model)


def imt(arg: Union[float, str, IMT]) -> IMT:
    """
    Return an IMT object from the given argument

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


registered_imts: dict[str, Callable] = dict(_registered_imts())


# invert `gsim_aliases` (see `gsim_name` below)
_gsim_aliases = {v: k for k, v in gsim_aliases.items()}


def gsim_name(model: GMPE) -> str:
    """
    Returns the name of the GMPE given an instance of the class
    """
    name = str(model)
    # if name is the gsim class name within square brackets, return the class name:
    if name == f"[{model.__class__.__name__}]":
        return model.__class__.__name__
    # name is the TOML representation of gsim. Use _gsim_aliases to return the name:
    return _gsim_aliases[name]


def imt_name(imtx: Union[Callable, IMT]) -> str:
    if isinstance(imtx, IMT):
        return repr(imtx)
    # it's a callable (e.g. a function defined in the openquake `imt` module):
    return imtx.__name__


def sa_period(obj: Union[float, str, IMT]) -> Union[float, None]:
    """
    Return the period (float) from the given `obj` argument, or None if `obj`
    does not indicate a Spectral Acceleration object/string with a finite period
    (e.g. "SA(NaN)", "SA(inf)", "SA" return None).

    :arg: str or `IMT` instance, such as "SA(1.0)" or `imt.SA(1.0)`
    """
    try:
        imt_inst = imt(obj)
        if not imt_name(imt_inst).startswith('SA('):
            return None
    except (TypeError, KeyError, ValueError):
        return None

    period = imt_inst.period
    # check also that the period is finite (SA('inf') and SA('nan') are possible:
    # this function is intended to return a "workable" period):
    return float(period) if np.isfinite(period) else None


def get_sa_limits(
        model: Union[str, GMPE]
) -> Union[tuple[float, float], None]:
    """Return the SA period limits defined for the given gsim, or None"""
    if isinstance(model, str):
        model = gsim(model)
    pers = None
    for c in dir(model):
        if 'COEFFS' in c:
            pers = [sa.period for sa in getattr(model, c).sa_coeffs] or None
            if pers:  # might be an empty list, so break only if non-empty
                break
    return (min(pers), max(pers)) if pers is not None else None


def intensity_measures_defined_for(model: Union[str, GMPE]) -> frozenset[str]:
    """Return the intensity measures defined for the given model"""
    if isinstance(model, str):
        # try loading the class first from registry (faster), otherwise the instance
        # if the class does not hold the info we need:
        model = registry[model] if registry[model].DEFINED_FOR_INTENSITY_MEASURE_TYPES \
            else gsim(model)
    return frozenset(_.__name__ for _ in model.DEFINED_FOR_INTENSITY_MEASURE_TYPES)


def ground_motion_properties_required_by(*models: Union[str, GMPE]) -> frozenset[str]:
    """
    Return the aggregated required ground motion properties (distance measures,
    rupture and site params all together) from all the passed models. Note: the
    returned names are those implemented in OpenQuake, use
    `smtk.flatfile.ColumnRegistry` to translate them into the registered flatfile
    column names
    """
    ret = []
    for model in models:
        if isinstance(model, str):
            # try loading the class first from registry (faster), otherwise the instance
            # if the class does not hold the info we need:
            cls = registry[model]
            model = cls if any((cls.REQUIRES_DISTANCES,
                                cls.REQUIRES_SITES_PARAMETERS,
                                cls.REQUIRES_RUPTURE_PARAMETERS)) else gsim(model)
        ret.extend(model.REQUIRES_DISTANCES or [])
        ret.extend(model.REQUIRES_SITES_PARAMETERS or [])
        ret.extend(model.REQUIRES_RUPTURE_PARAMETERS or [])
    return frozenset(ret)


def gsim_info(model: Union[str, GMPE]) -> tuple[str, list, list, Union[list, None]]:
    """
    Return the model info as a tuple with elements:
     - the source code documentation (Python docstring) of the model
     - the list of the intensity measures defined for the model
     - the list of the ground motion properties required to compute the
        model predictions
     - the list of spectral acceleration period limits where the model
       is defined, or None if the model is not defined for SA
    """
    model = gsim(model)
    return (
        (model.__doc__ or ""),
        list(intensity_measures_defined_for(model) or []),
        list(ground_motion_properties_required_by(model) or []),
        get_sa_limits(model)
    )


class Clabel:
    """Custom column labels provided in the output Dataframes"""
    input = 'input'
    mean = "mean"
    median = "median"
    std = "stddev"
    total_std = f"total_{std}"
    inter_ev_std = f"inter_event_{std}"
    intra_ev_std = f"intra_event_{std}"
    total_res = "total_residual"
    inter_ev_res = "inter_event_residual"
    intra_ev_res = "intra_event_residual"
    total_lh = total_res.replace("_residual", "_likelihood")
    inter_ev_lh = inter_ev_res.replace("_residual", "_likelihood")
    intra_ev_lh = intra_ev_res.replace("_residual", "_likelihood")
    mag = "mag"
    rrup = 'rrup'
    uncategorized_input = 'uncategorized'
    sep = " "  # the default separator for single-row column header
