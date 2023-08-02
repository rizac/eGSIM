from typing import Union, Sequence, Type
from math import inf
import re
from scipy.constants import g
import numpy as np
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.gsim.gmpe_table import GMPETable
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib import valid


# Get a list of the available GSIMs (lazy loaded):
AVAILABLE_GSIMS: dict[str, Type[GMPE]] = get_available_gsims()


# Regular expression to get a GMPETable from string:
_gmpetable_regex = re.compile(r'^GMPETable\(([^)]+?)\)$')


def get_gsim_instance(gsim_name: str) -> GMPE:
    return valid.gsim(gsim_name)


def check_gsim_list(gsims) -> dict[str, GMPE]:
    """
    Check the GSIM models or strings in `gsims`, and return a dict of
    gsim names (str) mapped to their :class:`openquake.hazardlib.Gsim`.
    Raises error if any Gsim in the list is supported in OpenQuake.

    If a Gsim is passed as instance, its string representation is inferred
    from the class name and optional arguments. If a Gsim is passed as string,
    the associated class name is fetched from the OpenQuake available Gsims.

    :param gsims: list of GSIM names (str) or OpenQuake Gsim classes
    :return: a dict of GSIM names (str) mapped to the associated GSIM
    """
    output_gsims = {}
    for gs in gsims:
        if isinstance(gs, GMPE):
            output_gsims[get_gsim_name(gs)] = gs  # get name of GMPE instance
        elif gs in AVAILABLE_GSIMS:
            output_gsims[gs] = get_gsim_instance(gs)
        else:
            match = _gmpetable_regex.match(gs)  # GMPETable ?
            if match:
                filepath = match.group(1).split("=")[1]  # get table filename
                output_gsims[gs] = GMPETable(gmpe_table=filepath)
            else:
                raise ValueError('%s Not supported by OpenQuake' % gs)

    return output_gsims


def get_gsim_name(gsim: GMPE) -> str:  # FIXME
    """
    Returns the name of the GMPE given an instance of the class
    """
    match = _gmpetable_regex.match(str(gsim))  # GMPETable ?
    if match:
        filepath = match.group(1).split("=")[1][1:-1]
        return 'GMPETable(gmpe_table=%s)' % filepath
    else:
        gsim_name = gsim.__class__.__name__
        return gsim_name
        # parse GMPE argument disabled, as it has the side effect to return
        # not what users might have input as string FIXME handle with GW
        #
        # additional_args = []
        # # Build the GSIM string by showing name and arguments. Keep things
        # # simple (no replacements, no case changes) as we might want to be able
        # # to get back the GSIM from its string in the future.
        # for key in gsim.__dict__:
        #     if key.startswith("kwargs"):
        #         continue
        #     val = str(gsim.__dict__[key])  # quoting strings with json maybe?
        #     additional_args.append("{:s}={:s}".format(key, val))
        # if len(additional_args):
        #     gsim_name_str = "({:s})".format(", ".join(additional_args))
        #     return gsim_name + gsim_name_str
        # else:
        #     return gsim_name


def n_jsonify(obj: Union[Sequence, int, float, np.generic]) -> \
        Union[float, int, list, tuple, None]:
    """Attempt to convert the numeric input to a Python object that is JSON serializable,
    i.e. same as `obj.tolist()` but - in case `obj` is a list/tuple, with NoN or
    infinite values converted to None.

    :param obj: the numeric input to be converted. It can be a scalar or sequence as
        plain Python or numpy object. If this argument is non-numeric, this function is
        not guaranteed to return a JSON serializable object
    """
    # we could simply perform an iteration over `obj` but with numpy is faster. Convert
    # to numpy object if needed:
    np_obj = np.asarray(obj)

    if np_obj.shape:  # np_obj is array
        # `np_obj.dtype` is not float: try to cast it to float. This will be successful
        # if obj contains `None`s and numeric values only:
        if np.issubdtype(np_obj.dtype, np.object_):
            try:
                np_obj = np_obj.astype(float)
            except ValueError:
                # np_obj is a non-numeric array, leave it as it is
                pass
        # if obj is a numeric list tuples, convert non-finite (nan, inf) to None:
        if np.issubdtype(np_obj.dtype, np.floating):
            na = ~np.isfinite(np_obj)
            if na.any():  # has some non-finite numbers:
                np_obj = np_obj.astype(object)
                np_obj[na] = None
                return np_obj.tolist()  # noqa
        # there were only finite values:
        if isinstance(np_obj, (list, tuple)):  # we passed a list/tuple: return it
            return obj
        # we passed something else (e.g. a np array):
        return np_obj.tolist()  # noqa

    # np_obj is scalar:
    num = np_obj.tolist()
    # define infinity (note that inf == np.inf so the set below is verbose).
    # NaNs will be checked via `x != x` which works also when x is not numeric
    if num != num or num in {inf, -inf, np.inf, -np.inf}:
        return None
    return num  # noqa


def convert_accel_units(acceleration, from_, to_='cm/s/s'):  # noqa
    """
    Legacy function which can still be used to convert acceleration from/to
    different units

    :param acceleration: the acceleration (numeric or numpy array)
    :param from_: unit of `acceleration`: string in "g", "m/s/s", "m/s**2",
        "m/s^2", "cm/s/s", "cm/s**2" or "cm/s^2"
    :param to_: new unit of `acceleration`: string in "g", "m/s/s", "m/s**2",
        "m/s^2", "cm/s/s", "cm/s**2" or "cm/s^2". When missing, it defaults
        to "cm/s/s"

    :return: acceleration converted to the given units (by default, 'cm/s/s')
    """
    m_sec_square = ("m/s/s", "m/s**2", "m/s^2")
    cm_sec_square = ("cm/s/s", "cm/s**2", "cm/s^2")
    acceleration = np.asarray(acceleration)
    if from_ == 'g':
        if to_ == 'g':
            return acceleration
        if to_ in m_sec_square:
            return acceleration * g
        if to_ in cm_sec_square:
            return acceleration * (100 * g)
    elif from_ in m_sec_square:
        if to_ == 'g':
            return acceleration / g
        if to_ in m_sec_square:
            return acceleration
        if to_ in cm_sec_square:
            return acceleration * 100
    elif from_ in cm_sec_square:
        if to_ == 'g':
            return acceleration / (100 * g)
        if to_ in m_sec_square:
            return acceleration / 100
        if to_ in cm_sec_square:
            return acceleration

    raise ValueError("Unrecognised time history units. "
                     "Should take either ''g'', ''m/s/s'' or ''cm/s/s''")
