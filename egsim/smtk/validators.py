"""Validation functions for the strong motion modeller toolkit (smtk) package of eGSIM"""

from typing import Union
from collections.abc import Iterable
import numpy as np
from openquake.hazardlib.imt import IMT, from_string as imt_from_string
from openquake.hazardlib.gsim.base import GMPE

from .registry import (registered_gsim_names, gsim_name, imts_defined_for,
                       gsim, sa_limits)


def harmonize_and_validate_inputs(
        gsims: Union[Iterable[str, GMPE, type[GMPE]], dict[str, GMPE]],
        imts: Union[Iterable[str, IMT], dict[str, IMT]]) -> \
        tuple[dict[str, GMPE], dict[str, IMT]]:
    """Harmonize and validate the input ground motion models (`gsims`)
    and intensity measures types (`imts`) returning a tuple of two dicts
    `gsim, imts` with sorted ascending keys mapping each model / intensity
    measure name to the relative OpenQuake instance.

    The dicts will be returned after validating the inputs and assuring
    that the given models and imts can be used together, otherwise a
    ValueError is raised (the exception will have a special attribute
    `invalid` with all invalid model name mapped to thr incompatible imt names)

    :param gsims: an iterable of str (model name, see `get_registered_gsim_names`),
        Gsim classes or instances. It can also be a dict, in this case the argument
        is returned as-it-is, after checking that keys and values types are ok
    :param imts: an iterable of str (e.g. 'SA(0.1)' ,'PGV',  'PGA'),
        or IMT instances. It can also be a dict, in this case the argument is
        returned as-it-is, after checking that keys and values types are ok
    """
    if not isinstance(gsims, dict):
        gsims = harmonize_input_gsims(gsims)
    else:
        assert all(isinstance(k, str) and isinstance(v, GMPE)
                   for k, v in gsims.items()), "Input gsims must be a dict[str, GMPE]"
    if not isinstance(imts, dict):
        imts = harmonize_input_imts(imts)
    else:
        assert all(isinstance(k, str) and isinstance(v, IMT)
                   for k, v in imts.items()), "Input imts must be a dict[str, IMT]"

    periods = {}
    imtz = set()
    # get SA periods, and put in imtz just the imt names (e.g. 'SA' not 'SA(2.0)'):
    for imt_name, imtx in imts.items():
        period = sa_period(imtx)
        if period is not None:
            periods[period] = imt_name
            imt_name = imt_name[:imt_name.index('(')]
        imtz.add(imt_name)
    invalid = {}  # dict[str, set[str]] (model name -> incompatible imts)
    for gsim_name, gsim in gsims.items():
        invalid_imts = imtz - imts_defined_for(gsim)
        if periods and 'SA' not in invalid_imts:
            for p in invalid_sa_periods(gsim, periods):
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

    return gsims, imts


def harmonize_input_gsims(
        gsims: Iterable[Union[str, type[GMPE], GMPE]]) -> dict[str, GMPE]:
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
    output_gsims = {}
    for gs in gsims:
        if isinstance(gs, type) and issubclass(gs, GMPE):
            gs = gs()  # try to init with no args
        if isinstance(gs, GMPE):
            output_gsims[gsim_name(gs)] = gs  # get name of GMPE instance
            continue
        if isinstance(gs, str) and gs in registered_gsim_names():
            output_gsims[gs] = gsim(gs)  ## noqa
            continue
        raise ValueError(f'Invalid Gsim: {str(gs)}')

    return {k: output_gsims[k] for k in sorted(output_gsims)}


def harmonize_input_imts(imts: Iterable[Union[str, IMT]]) -> dict[str, IMT]:
    """harmonize IMTs given as names (str) or instances (IMT) returning a
    dict[str, IMT] where each name is mapped to the relative instance. Dict keys will
    be sorted ascending comparing SAs using their period. E.g.: 'PGA' 'SA(2)' 'SA(10)'
    """
    ret = []
    for imt_inst in imts:
        if not isinstance(imt_inst, IMT):
            imt_inst = imt_from_string(str(imt_inst))
            if not isinstance(imt_inst, IMT):
                raise ValueError(f'Invalid imt: {str(imt_inst)}')
        ret.append(imt_inst)

    return {repr(i): i for i in sorted(ret, key=_imtkey)}


def _imtkey(imt_inst) -> tuple[str, float]:
    period = sa_period(imt_inst)
    if period is not None:
        return 'SA', period
    else:
        return imt_inst.string, -np.inf


def sa_period(obj: Union[str, IMT]) -> Union[float, None]:
    """Return the period (float) from the given `obj` argument, or None if `obj`
    does not indicate a Spectral Acceleration object/string with a finite period
    (e.g. "SA(NaN)", "SA(inf)", "SA" return None).

    :arg: str or `IMT` instance, such as "SA(1.0)" or `imt.SA(1.0)`
    """
    if isinstance(obj, str):
        if not obj.startswith(f'SA('):  # fast check to return immediately in case
            return None
        try:
            obj = imt_from_string(obj)
        except ValueError:
            return None
    elif isinstance(obj, IMT):
        if not obj.string.startswith(f'SA('):
            return None
    else:
        return None

    period = obj.period
    # check also that the period is finite (SA('inf') and SA('nan') are possible:
    # this function is intended to return a "workable" period):
    return float(period) if np.isfinite(period) else None


def invalid_sa_periods(gsim: GMPE, periods: Iterable[float]) -> Iterable[float]:
    """Yield the SA periods in `periods` NOT supported by the model `gsim`"""
    limits = sa_limits(gsim)
    if limits is not None:
        for period in periods:
            if period < limits[0] or period > limits[1]:
                yield period
