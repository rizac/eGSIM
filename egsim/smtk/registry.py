"""Registry with helper functions to access OpenQuake entities and properties"""
from typing import Union, Iterable, Callable
import re
import numpy as np

from openquake.hazardlib import imt as imt_module
from openquake.hazardlib.imt import IMT, from_string as imt_from_string
from openquake.hazardlib.gsim.base import GMPE, registry, gsim_aliases
from openquake.hazardlib.gsim.gmpe_table import GMPETable
from openquake.hazardlib.valid import gsim as valid_gsim


# added for compatibility with registered_imts (see below)  # FIXME NEEDED
registered_gsims:dict[str, type[GMPE]] = registry


def gsim(model: Union[str, GMPE], raise_deprecated=True) -> GMPE:
    """Return a Gsim instance (Python object of class `GMPE`) from the given input

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
        is_table = model.startswith('GMPETable')
        if is_table:
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


registered_imts: dict[str, Callable] = dict(_registered_imts())


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


def imt_name(imtx: Union[Callable, IMT]) -> str:
    if isinstance(imtx, IMT):
        return repr(imtx)
    # it's a callable (e.g. a function defined in the openquake `imt` module):
    return imtx.__name__


def get_sa_limits(
        model: Union[str, GMPE]
) -> Union[tuple[float, float], None]:
    """Return the SA period limits defined for the given gsim, or None"""
    if isinstance(model, str):
        model = gsim(model)
    pers = None
    for c in dir(model):
        if 'COEFFS' in c:
            pers = [sa.period for sa in getattr(model, c).sa_coeffs]
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


def ground_motion_properties_required_by(
        *models: Union[str, GMPE]) -> frozenset[str]:
    """Return the aggregated required ground motion properties (distance measures,
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


#  maybe not the best place but where otherwise?

def get_ground_motion_values(model: GMPE, imts: list[IMT], ctx: np.recarray):
    """
    Compute the ground motion values from the arguments returning 4 arrays each
    one of shape `( len(ctx), len(imts) )`. This is the main function to compute
    predictions to be used within the package.

    :param model: the ground motion model instance
    :param imts: a list of M Intensity Measure Types
    :param ctx: a numpy recarray of size N created from a given
        scenario (e.g. `RuptureContext`)

    :return: a tuple of 4-elements: (note: arrays below are simply the transposed
        matrices of OpenQuake computed values):
        - an array of shape (N, M) for the means (N=len(ctx), M=len(imts), see above)
        - an array of shape (N, M) for the TOTAL stddevs
        - an array of shape (N, M) for the INTER_EVENT stddevs
        - an array of shape (N, M) for the INTRA_EVENT stddevs
    """
    median = np.zeros([len(imts), len(ctx)])
    sigma = np.zeros_like(median)
    tau = np.zeros_like(median)
    phi = np.zeros_like(median)
    model.compute(ctx, imts, median, sigma, tau, phi)
    return median.T, sigma.T, tau.T, phi.T


class Clabel:
    """Custom column labels provided in the output Dataframes"""
    input_data = 'input_data'
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
