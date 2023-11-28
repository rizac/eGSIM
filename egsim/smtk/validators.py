"""Validation functions for the strong motion modeller toolkit (smtk) package of eGSIM"""
from __future__ import annotations

from typing import Union
from collections.abc import Iterable
import re

import numpy as np
from openquake.hazardlib.imt import IMT, from_string as imt_from_string
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.valid import gsim as valid_gsim
from openquake.hazardlib.gsim.gmpe_table import GMPETable

from .registry import (gsim_name, intensity_measures_defined_for,
                       gsim_sa_limits, imt_name)


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
    errors = []
    output_gsims = {}
    for gs in gsims:
        try:
            gsim_inst = gsim(gs)
            if not isinstance(gs, str):
                gs = gsim_name(gsim_inst)
            output_gsims[gs] = gsim_inst
        except (TypeError, ValueError, IndexError, KeyError, FileNotFoundError,
                OSError,AttributeError, DeprecationWarning) as _:
            errors.append(gs if isinstance(gs, str) else gsim_name(gs))
    if errors:
        raise InvalidInput(*errors)

    return {k: output_gsims[k] for k in sorted(output_gsims)}


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
        except (TypeError, ValueError, KeyError) as exc:
            errors.append(imtx if isinstance(imtx, str) else imt_name(imtx))
    if errors:
        raise InvalidInput(*errors)
    return {imt_name(i): i for i in sorted(imt_set, key=_imtkey)}


def imt(arg: Union[float, str, IMT]) -> IMT:
    """Return a IMT object from the given argument

    :raise: TypeError, ValueError, KeyError
    """
    if isinstance(arg, IMT):
        return arg
    return imt_from_string(str(arg))


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


def validate_inputs(gsims:dict[str, GMPE], imts: dict[str, IMT]) -> \
        tuple[dict[str, GMPE], dict[str, IMT]]:
    """Validate the input ground motion models (`gsims`)
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
    periods = {}
    imt_names = set()
    # get SA periods, and put in imtz just the imt names (e.g. 'SA' not 'SA(2.0)'):
    for imt_name, imtx in imts.items():
        period = sa_period(imtx)
        if period is not None:
            periods[period] = imt_name
        else:
            imt_names.add(imt_name)
    if periods:
        imt_names.add('SA')

    # create an IncompatibleGsmImt exception, adn populate it with errors if any:
    errors = []
    for gm_name, gsim_inst in gsims.items():
        invalid_imts = imt_names - intensity_measures_defined_for(gsim_inst)
        if periods:
            if 'SA' in invalid_imts:
                invalid_imts.remove('SA')
                invalid_imts.update(periods.values())
            else:
                # gsim invalid if ALL periods are outside the gsim limits:
                sa_lim = gsim_sa_limits(gsim_inst)
                if sa_lim is not None and not \
                        any(sa_lim[0] <= p <= sa_lim[1] for p in periods):
                    invalid_imts.update(periods.values())
        if not invalid_imts:
            continue
        errors.append([gm_name] + list(invalid_imts))

    if errors:
        raise IncompatibleInput(*errors) from None

    return gsims, imts

# Custom Exceptions:

class InvalidInput(ValueError):
    """Exception describing any invalid ground motion model or intensity measure
    that was given as input in a routine.
    `self.args: tuple[str]` will return the list of invalid input names
    """

    def __str__(self):
        # print each input separated by comma (superclass uses `repr(self.args)`):
        return ", ".join(self.args)


class IncompatibleInput(InvalidInput):
    """Exception describing any invalid ground motion model or intensity measure
    that was given as input in a routine.
    `self.args` will yield all incompatible inputs as `tuple[str, list[str]]`
    (the model name and the list of incompatible IMT names)
    """

    def __str__(self):
        # print each input separated by comma, where each input has the form:
        # "({model}, {imt1}, {imt2}, ...)"
        return ", ".join(f"({', '.join(a)})" for a in self.args)

