"""Validation functions for the strong motion modeller toolkit (smtk) package of eGSIM"""
from typing import Union, Any
from collections.abc import Iterable
import re
import warnings

import numpy as np
from openquake.hazardlib.imt import IMT, from_string as imt_from_string
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.valid import gsim as valid_gsim
from openquake.hazardlib.gsim.gmpe_table import GMPETable
from openquake.baselib.general import DeprecationWarning as OQDeprecationWarning

from .registry import gsim_name, imts_defined_for, sa_limits


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

    # create an IncompatibleGsmImt exception, adn populate it with errors if any:
    exc = IncompatibleGsimImt()
    for gsim_name, gsim in gsims.items():
        invalid_imts = imtz - imts_defined_for(gsim)
        if periods and 'SA' not in invalid_imts:
            for p in invalid_sa_periods(gsim, periods):
                invalid_imts.add(periods[p])
        if not invalid_imts:
            continue
        exc.add(gsim_name, invalid_imts)

    if not exc.empty:
        raise exc from None

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
        gsim_inst = gsim(gs)
        if not isinstance(gs, str):
            gs = gsim_name(gsim_inst)
        output_gsims[gs] = gsim_inst

    return {k: output_gsims[k] for k in sorted(output_gsims)}


def gsim(gmm: Union[str, type[GMPE], GMPE], raise_deprecated=True) -> GMPE:
    """Return a Gsim instance (Python object of class `GMPE`) from the given input

    :param gmm: a gsim name, class or instance (in this latter case, the instance is
        returned). If str, it can also denote a GMPETable in the form
        "GMPETable(gmpe_table=filepath)"
    :param raise_deprecated: if True (the default) OpenQuake `DeprecationWarning`s
        (`egsim.smtk.OQDeprecationWarning`) will raise as normal exceptions
    :raise: a `(TypeError, ValueError, FileNotFoundError, OSError) if name starts
        with "GMPETable", otherwise (TypeError, IndexError, KeyError) otherwise. If
        raise_deprecated is True (the default), it might also raise
        `openquake.baselib.general.DeprecationWarning`
    """
    if isinstance(gmm, type) and issubclass(gmm, GMPE):
        try:
            # try to init with no args:
            gmm = gmm()
        except Exception as exc:
            raise InvalidGsim(gmm, exc)
    if isinstance(gmm, GMPE):
        if raise_deprecated and gmm.superseded_by:
            raise InvalidGsim(gmm, OQDeprecationWarning())
        return gmm
    if isinstance(gmm, str):
        is_table = gmm.startswith('GMPETable')
        if is_table:  # GMPETable
            try:
                filepath = re.match(r'^GMPETable\(([^)]+?)\)$', gmm).\
                    group(1).split("=")[1]  # get table filename
                return GMPETable(gmpe_table=filepath)
            except (TypeError, ValueError, FileNotFoundError, OSError,
                    AttributeError) as exc:
                raise InvalidGsim(gmm, exc)
        elif not raise_deprecated:  # registered Gsims (relaxed: allow deprecated)
            try:
                return valid_gsim(gmm)
            except (TypeError, IndexError, KeyError) as exc:
                raise InvalidGsim(gmm, exc)
        else:  # "normal" case: registered Gsims but raise DeprecationWarning
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings('error', category=OQDeprecationWarning)
                    return valid_gsim(gmm)
            except (TypeError, IndexError, KeyError, OQDeprecationWarning) as exc:
                raise InvalidGsim(gmm, exc)
    raise TypeError(gmm)


def harmonize_input_imts(imts: Iterable[Union[str, float, IMT]]) -> dict[str, IMT]:
    """harmonize IMTs given as names (str) or instances (IMT) returning a
    dict[str, IMT] where each name is mapped to the relative instance. Dict keys will
    be sorted ascending comparing SAs using their period. E.g.: 'PGA' 'SA(2)' 'SA(10)'
    """
    ret = (imt(imtx) for imtx in imts)
    return {repr(i): i for i in sorted(ret, key=_imtkey)}


def imt(arg: Union[float, str, IMT]) -> IMT:
    """Return a IMT object from the given argument"""
    if isinstance(arg, IMT):
        return arg
    try:
        return imt_from_string(str(arg))
    except (TypeError, ValueError, KeyError) as exc:
        raise InvalidImt(arg, exc)


def _imtkey(imt_inst) -> tuple[str, float]:
    period = sa_period(imt_inst)
    if period is not None:
        return 'SA', period
    else:
        return imt_inst.string, -np.inf


def sa_period(obj: Union[float, str, IMT]) -> Union[float, None]:
    """Return the period (float) from the given `obj` argument, or None if `obj`
    does not indicate a Spectral Acceleration object/string with a finite period
    (e.g. "SA(NaN)", "SA(inf)", "SA" return None).

    :arg: str or `IMT` instance, such as "SA(1.0)" or `imt.SA(1.0)`
    """
    try:
        imt_inst = imt(obj)
        if not imt_inst.string.startswith('SA('):
            return None
    except InvalidImt:
        return None

    period = imt_inst.period
    # check also that the period is finite (SA('inf') and SA('nan') are possible:
    # this function is intended to return a "workable" period):
    return float(period) if np.isfinite(period) else None


def invalid_sa_periods(gsim: GMPE, periods: Iterable[float, str, IMT]) \
        -> Iterable[float]:
    """Yield the SA periods in `periods` NOT supported by the model `gsim`"""
    limits = sa_limits(gsim)
    if limits is not None:
        for p in periods:
            period = sa_period(p)
            if period is None:
                continue
            if period < limits[0] or period > limits[1]:
                yield period


# Custom Exceptions:


class InvalidInput(Exception):
    """Input initialization error. Abstract-like class, use subclasses instead"""

    def __init__(self, input:Any=None, error:Any=None):
        self._data = []
        super().__init__()
        if input is not None and error is not None:
            self.add(input, error)

    def add(self, input:Any, error:Any):
        """Add an invalid input and the corresponding error"""
        self._data.append((input, error))
        # customize the error message (stored in the `args` attribute)
        self.args = (self._build_msg(self._data),)

    def _build_msg(self, data:list[tuple[Any, Any]]) -> str:
        raise NotImplementedError()

    @property
    def empty(self):
        return not self._data

    @property
    def errors(self) -> tuple[Any, Any]:
        """Yield the tuple [input, error] for all inputs added to this object"""
        yield from self._data


class InvalidGsim(InvalidInput):

    def _build_msg(self, data: list[tuple[Any, Any]]) -> str:
        arg = f"Invalid model{'s' if len(self._data) != 1 else ''}"
        return f'{arg}: {", ".join(str(err[0]) for err in self.errors)}'


class InvalidImt(InvalidInput):

    def _build_msg(self, data: list[tuple[Any, Any]]) -> str:
        arg = f"Invalid imt{'s' if len(self._data) != 1 else ''}"
        return f'{arg}: {", ".join(str(err[0]) for err in self.errors)}'


class IncompatibleGsimImt(InvalidInput):

    def _build_msg(self, data: list[tuple[Any, Any]]) -> str:
        return f"{len(data)} model{'s are' if len(data) != 1 else ' is'} " \
              f"not defined for all input imts"