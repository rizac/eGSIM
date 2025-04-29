"""Validation functions for the strong motion modeller toolkit (smtk) package of eGSIM"""
from __future__ import annotations

from typing import Union, Optional
from collections.abc import Iterable

import numpy as np
from openquake.hazardlib.contexts import ContextMaker
from openquake.hazardlib.imt import IMT
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.gsim.gmpe_table import GMPETable

from .registry import (gsim_name, intensity_measures_defined_for, gsim, imt,
                       get_sa_limits, imt_name, sa_period)


def harmonize_input_gsims(gsims: Iterable[Union[str, GMPE]]) -> dict[str, GMPE]:
    """harmonize GSIMs given as names (str), OpenQuake Gsim classes or instances
    (:class:`GMPE`) into a dict[str, GMPE] where each name is mapped to
    the relative Gsim instance. Names will be sorted ascending.

    This method accounts for Gsim aliases stored in OpenQuake, and assures
    that for each `(key, value)` of the returned dict items:
    ```
        get_gsim_instance(key) == value
        get_gsim_name(value) == key
    ```

    :param gsims: iterable of GSIM names (str), OpenQuake Gsim classes or instances
    :return: a dict of GSIM names (str) mapped to the associated GSIM. Names (dict
        keys) are sorted ascending
    """
    errors = []
    output_gsims = {}
    for gs in gsims:
        try:
            gsim_inst = gsim(gs)
            if not isinstance(gs, str):
                gs = gsim_name(gsim_inst)
            output_gsims[gs] = gsim_inst
        except (TypeError, ValueError, IndexError, KeyError, FileNotFoundError,
                OSError, AttributeError, DeprecationWarning) as _:
            errors.append(gs if isinstance(gs, str) else gsim_name(gs))
    if errors:
        raise ModelError(*errors)

    return {k: output_gsims[k] for k in sorted(output_gsims)}


def harmonize_input_imts(imts: Iterable[Union[str, float, IMT]]) -> dict[str, IMT]:
    """harmonize IMTs given as names (str) or instances (IMT) returning a
    dict[str, IMT] where each name is mapped to the relative instance. Dict keys will
    be sorted ascending comparing SAs using their period. E.g.: 'PGA' 'SA(2)' 'SA(10)'
    """
    errors = []
    imt_set = set()
    for imtx in imts:
        try:
            imt_set.add(imt(imtx))
        except (TypeError, ValueError, KeyError) as _:
            errors.append(imtx if isinstance(imtx, str) else imt_name(imtx))
    if errors:
        raise ImtError(*errors)
    return {imt_name(i): i for i in sorted(imt_set, key=_imtkey)}


def _imtkey(imt_inst) -> tuple[str, float]:
    period = sa_period(imt_inst)
    if period is not None:
        return 'SA', period
    else:
        return imt_name(imt_inst), -np.inf


def validate_inputs(gsims: dict[str, GMPE], imts: dict[str, IMT]):
    """Validate the input ground motion models (`gsims`)
    and intensity measures types (`imts`), raising `IncompatibleInput` in case
    of failure, and simply returning (None) otherwise

    :param gsims: an iterable of str (model name, see `get_registered_gsim_names`),
        mapped to the GMPE instance, as output from `harmonize_input_gsims`
    :param imts: an iterable of str (e.g. 'SA(0.1)', 'PGA') mapped to the IMT
        instance, as output from `harmonize_input_imts`
    """
    imt_names = {n if sa_period(i) is None else n[:2] for n, i in imts.items()}
    errors = []
    for gm_name, gsim_inst in gsims.items():
        invalid_imts = imt_names - intensity_measures_defined_for(gsim_inst)
        if not invalid_imts:
            continue
        errors.extend([gm_name, i] for i in invalid_imts)

    if errors:
        raise IncompatibleModelImtError(*errors) from None

    return gsims, imts


def validate_imt_sa_limits(model: GMPE, imts: dict[str, IMT]) -> dict[str, IMT]:
    """Return a dict of IMT names mapped to the IMT instances that are either not SA,
    or have a period within the model SA period limits

    :param model: a Ground motion model instance
    :param imts: an iterable of str (e.g. 'SA(0.1)', 'PGA') mapped to IMT the
        instance, as output from `harmonize_input_imts`

    :return: a subset of the passed `imts` dict or `imts` unchanged if all its IMT
        are valid for the given model
    """
    model_sa_p_lim = get_sa_limits(model)
    return {
        i: v for i, v in imts.items()
        if model_sa_p_lim is None
        or sa_period(v) is None
        or model_sa_p_lim[0] <= sa_period(v) <= model_sa_p_lim[1]
    }


def init_context_maker(gsims: dict[str, GMPE],
                       imts: Iterable[Union[str, IMT]],
                       magnitudes: Iterable[float],
                       tectonic_region='') -> ContextMaker:
    """Initialize a ContextMaker. Raise `InvalidModel`"""
    param = {
        "imtls": {i if isinstance(i, str) else imt_name(i): [] for i in imts},
        "mags":  [f"{mag:.2f}" for mag in magnitudes]
    }
    oq_exceptions = (ValueError, KeyError)
    try:
        return ContextMaker(tectonic_region, gsims.values(), oq=param)
    except oq_exceptions as err:
        # any error should be returned associated to a model M, when possible.
        # Infer M (slightly inefficient if len(gsims)==1, but more readable):
        for g_name, g in gsims.items():
            try:
                return ContextMaker(tectonic_region, [g], oq=param)
            except err.__class__ as m_err:  # same error as `err`
                raise _format_model_error(g_name, m_err)
        raise err


def get_ground_motion_values(model: GMPE, imts: list[IMT], ctx: np.recarray, *,
                             model_name: Optional[str] = None):
    """
    Compute the ground motion values from the arguments returning 4 arrays each
    one of shape `( len(ctx), len(imts) )`. This is the main function to compute
    predictions to be used within the package.

    :param model: the ground motion model instance
    :param imts: a list of M Intensity Measure Types
    :param ctx: a numpy recarray of size N created from a given
        scenario (e.g. `RuptureContext`)
    :param model_name: the model name, only used in case of exceptions, if any is
        raised from OpenQuake. If empty or not given, the name will be inferred
        from `model`

    :return: a tuple of 4-elements: (note: arrays below are simply the transposed
        matrices of OpenQuake computed values):
        - an array of shape (N, M) for the means (N=len(ctx), M=len(imts), see above)
        - an array of shape (N, M) for the TOTAL stddevs
        - an array of shape (N, M) for the INTER_EVENT stddevs
        - an array of shape (N, M) for the INTRA_EVENT stddevs
    """
    oq_exceptions = (ValueError, KeyError)
    median = np.zeros([len(imts), len(ctx)])
    sigma = np.zeros_like(median)
    tau = np.zeros_like(median)
    phi = np.zeros_like(median)
    if isinstance(model, GMPETable):
        # GMPETables need to compute their values magnitude-wise. Allocate a copy of
        # variables where we will temporarily buffer the computed values per-magnitude:
        m_buf = np.zeros_like(median)
        s_buf = np.zeros_like(median)
        t_buf = np.zeros_like(median)
        p_buf = np.zeros_like(median)
        start = 0
        for mag in np.unique(ctx.mag):
            idxs = np.where(ctx.mag == mag)[0]
            end = start + len(idxs)
            # Note: we use buffers to pass *contiguous* slices (`start:end`) and be sure
            # to update the original array (`idxs` might not be contiguous)
            try:
                model.compute(ctx[idxs], imts,
                              m_buf[:, start:end],
                              s_buf[:, start:end],
                              t_buf[:, start:end],
                              p_buf[:, start:end])
            except oq_exceptions as exc:
                raise _format_model_error(model_name or model, exc)
            # set computed values back to our variables:
            median[:, idxs] = m_buf[:, start:end]
            sigma[:, idxs] = s_buf[:, start:end]
            tau[:, idxs] = t_buf[:, start:end]
            phi[:, idxs] = p_buf[:, start:end]
            start = end  # move start forward
    else:
        try:
            model.compute(ctx, imts, median, sigma, tau, phi)
        except oq_exceptions as exc:
            raise _format_model_error(model_name or model, exc)
    return median.T, sigma.T, tau.T, phi.T


def _format_model_error(model: Union[GMPE, str], exception: Exception) -> ModelError:
    """Re-format the given exception into  a ModelError"""
    suffix = str(exception.__class__.__name__)
    import sys
    import traceback
    exc_type, exc_value, exc_tb = sys.exc_info()
    tb_list = traceback.extract_tb(exc_tb)
    if tb_list:
        fname = tb_list[-1].filename
        lineno = tb_list[-1].lineno
        if '/openquake/' in fname and fname.rfind('/') < len(fname) - 3:
            suffix = f"OpenQuake {suffix} @{fname[fname.rfind('/') + 1:]}:{lineno}"

    return ModelError(f'{model if isinstance(model, str) else gsim_name(model)}: '
                      f'{str(exception)} ({suffix})')


# Custom Exceptions ===========================================================


class InputError(ValueError):
    """Base **abstract** exception for any input error (model, imt, flatfile).
    Note that `str(InputError(arg1, arg2, ...)) = str(arg1) + ", " + str(arg2) + ...
    """

    def __str__(self):
        """Reformat ``str(self)``"""
        return ", ".join(sorted(str(a) for a in self.args))


class ModelError(InputError):
    """Error for invalid models (e.g., misspelled, unable to compute predictions)"""
    pass


class ImtError(InputError):
    """Error for invalid intensity measures (e.g., misspelled)"""
    pass


class ConflictError(ValueError):
    """Describes conflicts among entities (model and imt, flatfile column names).
    Each argument to this class is a conflict, represented by a sequence of the
    items E1, ... EN in conflict within each other. As such,
    `str(ConflictError([E1, E2, E3], ...)) =
    str(E1) + "+" + str(E2) + "+" + str(E3) + ", " + ...`
    """

    def __str__(self):
        """Custom error msg"""
        return ", ".join(sorted(f'+'.join(sorted(a)) for a in self.args))


class IncompatibleModelImtError(ConflictError):
    """Describes conflicts within model and imts"""
    pass
