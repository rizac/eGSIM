from typing import Union

import re
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.gsim.gmpe_table import GMPETable
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib import valid

import numpy as np

# Get a list of the available GSIMs (lazy loaded):
AVAILABLE_GSIMS = get_available_gsims()

# Regular expression to get a GMPETable from string:
_gmpetable_regex = re.compile(r'^GMPETable\(([^)]+?)\)$')


def get_gsim_instance(gsim_name: str) -> GMPE:
    return valid.gsim(gsim_name)

def check_gsim_list(gsim_list) -> dict:
    """
    Check the GSIM models or strings in `gsim_list`, and return a dict of
    gsim names (str) mapped to their :class:`openquake.hazardlib.Gsim`.
    Raises error if any Gsim in the list is supported in OpenQuake.

    If a Gsim is passed as instance, its string representation is inferred
    from the class name and optional arguments. If a Gsim is passed as string,
    the associated class name is fetched from the OpenQuake available Gsims.

    :param gsim_list: list of GSIM names (str) or OpenQuake Gsims
    :return: a dict of GSIM names (str) mapped to the associated GSIM
    """
    output_gsims = {}
    for gs in gsim_list:
        if isinstance(gs, GMPE):
            output_gsims[_get_gmpe_name(gs)] = gs  # get name of GMPE instance
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


def _get_gmpe_name(gsim: GMPE) -> str:
    """
    Returns the name of the GMPE given an instance of the class
    """
    match = _gmpetable_regex.match(str(gsim))  # GMPETable ?
    if match:
        filepath = match.group(1).split("=")[1][1:-1]
        return 'GMPETable(gmpe_table=%s)' % filepath
    else:
        gsim_name = gsim.__class__.__name__
        additional_args = []
        # Build the GSIM string by showing name and arguments. Keep things
        # simple (no replacements, no case changes) as we might want to be able
        # to get back the GSIM from its string in the future.
        for key in gsim.__dict__:
            if key.startswith("kwargs"):
                continue
            val = str(gsim.__dict__[key])  # quoting strings with json maybe?
            additional_args.append("{:s}={:s}".format(key, val))
        if len(additional_args):
            gsim_name_str = "({:s})".format(", ".join(additional_args))
            return gsim_name + gsim_name_str
        else:
            return gsim_name


def jsonify1darray(array: np.ndarray) -> list:
    """Return a JSON serializable array from array. Basically converts efficiently
    all NaN/+-Infitnity to None

    :param array: a 1-dimensional numpy array
    """
    idxs = np.argwhere(~np.isfinite(array)).flatten()
    py_array: list = array.tolist()  # noqa
    for idx in idxs:
        py_array[idx] = None
    return py_array