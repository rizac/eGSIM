"""Validation functions for the strong motion modeller toolkit (smtk) package of eGSIM"""
from __future__ import annotations

from typing import Union
from collections.abc import Iterable

import numpy as np
from openquake.hazardlib.imt import IMT
from openquake.hazardlib.gsim.base import GMPE

from .registry import (gsim_name, intensity_measures_defined_for, gsim, imt,
                       get_sa_limits, imt_name)


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


def sa_period(obj: Union[float, str, IMT]) -> Union[float, None]:
    """Return the period (float) from the given `obj` argument, or None if `obj`
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


def validate_inputs(gsims: dict[str, GMPE], imts: dict[str, IMT]):
    """Validate the input ground motion models (`gsims`)
    and intensity measures types (`imts`), raising `IncompatibleInput` in case
    of failure, and simply returning (None) otherwise

    :param gsims: an iterable of str (model name, see `get_registered_gsim_names`),
        mapped to the GMPE instance, as output from `harmonize_input_gsims`
    :param imts: an iterable of str (e.g. 'SA(0.1)', 'PGA') mapped to IMT the
        instance, as output from `harmonize_input_imts`
    """
    imt_names = {n if sa_period(i) is None else n[:2] for n, i in imts.items()}
    errors = {}
    for gm_name, gsim_inst in gsims.items():
        invalid_imts = imt_names - intensity_measures_defined_for(gsim_inst)
        if not invalid_imts:
            continue
        errors[gm_name] = list(invalid_imts)

    if errors:
        raise IncompatibleModelImtError(errors) from None

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
    if model_sa_p_lim is None:
        return imts
    imt_periods = {i: sa_period(v) for i, v in imts.items()}
    if all(_ is None for _ in imt_periods.values()):
        return imts
    imt_new = {}
    for imt_n, sa_p in imt_periods.items():
        if sa_p is None or model_sa_p_lim[0] <= sa_p <= model_sa_p_lim[1]:
            imt_new[imt_n] = imts[imt_n]
    return imt_new


# Custom Exceptions:


class InputError(ValueError):
    """Base **abstract** exception for any input error (model, imt, flatfile)"""

    def __str__(self):
        """Reformat ``str(self)``"""
        return ", ".join(sorted(str(a) for a in self.args))


class ModelError(InputError):
    pass


class ImtError(InputError):
    pass


class IncompatibleModelImtError(InputError):
    """Given any process with input models and input imts, this class is initialized
    with a dict of input model names mapped to the input imts they do NOT define
    (as class names, i.e. SA, not SA(period))
    """

    def __str__(self):
        """Custom error msg"""
        arg = self.args[0]
        return (
            "incompatible model(s) and intensity measure(s) " +
            ", ".join(f'{m}+{i}' for m in sorted(arg.keys()) for i in sorted(arg[m]))
        )
