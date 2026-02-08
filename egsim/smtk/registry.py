"""Registry with helper functions to access OpenQuake entities and properties"""

from typing import Union, Iterable, Callable, Optional
import re
import numpy as np

from openquake.hazardlib import imt as imt_module
from openquake.hazardlib.imt import IMT, from_string as imt_from_string
from openquake.hazardlib.gsim.base import GMPE, registry, gsim_aliases
from openquake.hazardlib.gsim.gmpe_table import GMPETable
from openquake.hazardlib.valid import gsim as valid_gsim


def gsim(model: Union[str, GMPE], raise_deprecated=True) -> GMPE:
    """
    Return a Gsim instance (Python object of class `GMPE`) from the given input

    :param model: a gsim name or Gsim instance. If str, it can also denote a
        GMPETable in the form "GMPETable(gmpe_table=filepath)"
    :param raise_deprecated: if True (the default) deprecated models will raise
        an `SmtkError`, otherwise they will be returned as normal models

    :raise: a `SmtkError` if for some reason the input is invalid
    """
    # Note: we catch broad except because exceptions vary in different OQ releases
    if isinstance(model, str) and model.startswith('GMPETable'):
        try:
            matcher = re.match(r'^GMPETable\(([^)]+?)\)$', model)
            filepath = matcher.group(1).split("=")[1]
            assert len(filepath.strip())
        except (AttributeError, IndexError, AssertionError):
            # AttributeError: matcher is None, IndexError: matcher.group has no "="
            raise SmtkError(f'Invalid GMPETable "{model}"')
        try:
            model = GMPETable(gmpe_table=filepath)
        except Exception as e:
            raise SmtkError(str(e))
    elif not isinstance(model, GMPE):
        try:
            model = valid_gsim(model)
        except Exception as e:
            raise SmtkError(str(e))

    if raise_deprecated and model.superseded_by:
        raise SmtkError(f'Use {model.superseded_by} instead')
    return model


def gsim_names() -> Iterable[str]:
    """Return an iterable of all model names registered in OpenQuake"""
    return registry.keys()


def gsim_name(model: GMPE) -> str:
    """Return the name of the GMPE given an instance of the class"""

    name = str(model)
    # if name is the gsim class name within square brackets, return the class name:
    if name == f"[{model.__class__.__name__}]":
        return model.__class__.__name__
    global _toml2class
    if _toml2class is None:
        _toml2class = {v.strip(): k for k, v in gsim_aliases.items()}
    # name is the TOML representation of gsim. Use _toml2class to return the name:
    return _toml2class[name.strip()]


_toml2class: Optional[dict[str, str]] = None  #toml repr -> class name


def imt(arg: Union[float, str, IMT]) -> IMT:
    """
    Return an IMT object from the given argument

    :raise: TypeError, ValueError, KeyError
    """
    if isinstance(arg, IMT):
        return arg
    return imt_from_string(str(arg))


def imt_names() -> Iterable[str]:
    """Return all IMT names registered in OpenQuake"""
    for name in dir(imt_module):
        if not ('A' <= name[:1] <= 'Z'):  # only upper-case module elements
            continue
        func = getattr(imt_module, name)
        # only callable(s) and with documentation implemented:
        if not callable(func) or not hasattr(func, "__code__"):
            continue
        # Let's call func with defaults 1.0s and None's and see if returns IMT
        # (quite hacky, but it works for main IMTs such as SA):
        for args in [
            [1.] * func.__code__.co_argcount,
            [None] * func.__code__.co_argcount,
        ]:
            try:
                imt_obj = func(*args)
                if isinstance(imt_obj, IMT):
                    yield name
                    break
            except (ValueError, TypeError, AttributeError):
                pass


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


def sa_limits(model: GMPE) -> Union[tuple[float, float], None]:
    """Return the SA period limits defined for the given gsim, or None"""

    periods = None
    for c in dir(model):
        if 'COEFFS' in c:
            sa_coeffs = getattr(getattr(model, c), 'sa_coeffs', None)
            if sa_coeffs:
                periods = [sa.period for sa in sa_coeffs]
            if periods:  # might be an empty list, so break only if non-empty
                break
    return (min(periods), max(periods)) if periods is not None else None


def intensity_measures_defined_for(model: GMPE) -> frozenset[str]:
    """Return the intensity measures defined for the given model"""

    return frozenset(imt_name(_) for _ in model.DEFINED_FOR_INTENSITY_MEASURE_TYPES)


def ground_motion_properties_required_by(*models: GMPE) -> frozenset[str]:
    """
    Return the aggregated required ground motion properties (distance measures,
    rupture and site params all together) from all the passed models. Note: the
    returned names are those implemented in OpenQuake, use
    `smtk.flatfile.ColumnRegistry` to translate them into the registered flatfile
    column names
    """
    ret = []
    for model in models:
        ret.extend(model.REQUIRES_DISTANCES or [])
        ret.extend(model.REQUIRES_SITES_PARAMETERS or [])
        ret.extend(model.REQUIRES_RUPTURE_PARAMETERS or [])
    return frozenset(ret)


def gsim_info(model: GMPE) -> tuple[str, list, list, Union[list, None]]:
    """
    Return the model info as a tuple with elements:
     - the source code documentation (Python docstring) of the model
     - the list of the intensity measures defined for the model
     - the list of the ground motion properties required to compute the
        model predictions
     - the list of spectral acceleration period limits where the model
       is defined, or None if the model is not defined for SA
    """
    return (
        (model.__doc__ or ""),
        list(intensity_measures_defined_for(model) or []),
        list(ground_motion_properties_required_by(model) or []),
        sa_limits(model)
    )


class SmtkError(Exception):
    """
    Base exception for any input error (model, imt, flatfile).
    str(SmtkError(arg1, arg2, ...)) = str(arg1) + self.separator + str(arg2) + ...
    (self.separator = ', ' by default)
    """

    separator = ', '

    def __str__(self):
        """Reformat ``str(self)``"""

        return self.separator.join(sorted(str(a) for a in self.args))


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
