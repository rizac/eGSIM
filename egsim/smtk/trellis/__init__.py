"""trellis plots module"""
from collections.abc import Collection, Iterable
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.imt import IMT
from typing import Union

import numpy as np
import pandas as pd
from openquake.hazardlib.contexts import ContextMaker

from .rupture import GSIMRupture, NULL_OQ_PARAM, DEFAULT_POINT, WC1994
from .. import harmonize_input_imts, harmonize_input_gsims


class REQUIRED:
    pass

RUPTURE_DEFAULTS = {
    "dip": REQUIRED,
    "aspect": REQUIRED,
    "tectonic_region": "Active Shallow Crust",
    "rake": 0.,
    "ztor": 0.,
    "strike":0.,
    "msr": WC1994(),
    "initial_point": DEFAULT_POINT,
    "hypocentre_location": None
}

SITE_DEFAULT = {
    "vs30": REQUIRED,
    "line_azimuth": 90.0,
    "distance_type": "rrup",
    "origin_point": (0.5, 0.0),
    "vs30measured": True,
    "z1pt0": None,
    "z2pt5": None,
    "backarc": False,
    "xvf":150.0,
    "region":0
}


# FIXME: pga_periods is unused, as well as TrellisManager.periods

TRELLIS_TYPES = ("Magnitude-IMT", "Distance-IMT", "Magnitude-Distance-Spectra",)


def get_trellis(
        gsims: Iterable[Union[str, GMPE, type[GMPE]]],
        imts: Iterable[Union[str, IMT]],
        magnitudes: Union[float, Collection[float]],
        distances: Union[float, Collection[float]],
        input_properties: dict):
    """Calculate trellis plots"""

    gsims = harmonize_input_gsims(gsims)
    imts = harmonize_input_imts(imts)
    rupture_properties = {
        key: input_properties.get(key, RUPTURE_DEFAULTS[key])
        for key in RUPTURE_DEFAULTS
    }
    site_properties = {
        key: input_properties.get(key, SITE_DEFAULT[key])
        for key in SITE_DEFAULT
    }
    invalid = {k for k, v in {**rupture_properties, **site_properties}.items()
               if v is REQUIRED}
    if invalid:
        raise ValueError('bla bla')  # FIXME provide an exception

    return calculate_trellis(
        gsims, imts, magnitudes, distances, rupture_properties, site_properties)


def calculate_trellis(
        gsims: dict[str, GMPE],
        imts: dict[str, IMT],
        magnitudes: Union[float, Collection[float]],  # np.ndarray is a Collection
        distances: Union[float, Collection[float]],
        rupture_properties:dict,
        site_properties:dict,
        trellis_type: str = None,
    ) -> pd.DataFrame:
    """
    Calculates the ground motion values for the trellis plots

    :param magnitudes: list or numpy array of magnitudes
    :param distances: list or numpy array of distances
    :param trellis_type: If specified then returns the trellis output as
        a dictionary with arguments formatted for export to JSON, otherwise
        returns the dictionaries of medians and total standard deviations.
        Supported values are "Magnitude-IMT", "Distance-IMT",
        "Magnitude-Distace-Spectra", or None

    :return: pandas DataFrame
    """
    magnitudes = np.asarray(magnitudes)
    if not magnitudes.shape:  # convert to a 1-length array if scalar:
        magnitudes = magnitudes.reshape(1,)
    distances = np.asarray(distances)
    if not distances.shape:   # convert to a 1-length array if scalar:
        distances = distances.reshape(1,)

    # Get the context objects as a numpy recarray
    ctxts = build_contexts(
        gsims, magnitudes, distances, rupture_properties, site_properties)

    # Get the ground motion values
    trellis_data = get_ground_motion_values(gsims, imts, ctxts)

    # columns = product(magnitudes, distances, imts, models)

    # Export to dictionary
    if trellis_type == "Magnitude-IMT":
        trellis_data['mag']  = np.tile(magnitudes, len(ctxts) / len(magnitudes))

    elif trellis_type == "Distance-IMT":
        dist_label = site_properties['distance_type']
        trellis_data[dist_label] = np.tile(distances, len(ctxts) / len(distances))

    elif trellis_type == "Magnitude-Distance-Spectra":
        return self.magnitude_distance_spectra_trellis_output(medians, sigmas,
                                                              magnitudes,
                                                              distances, ctxts)
    return trellis_data
    #
    # else:
    #     pass
    # return medians, sigmas


def build_contexts(gsims: dict[str, GMPE],
                   magnitudes: Collection[float],
                   distances: Collection[float],
                   rupture_properties:dict,
                   site_properties:dict) -> np.recarray:
    """Build the context objects from the set of magnitudes and distances and
    then returns them as a numpy recarray

    :param gsims: dict of GSIM names mapped to a GSIM instance (class `GMPE`)
    :param magnitudes: the magnitudes
    :param distances: the distances

    :return: Context objects in the form of a single numpy recarray
    """
    ctxts = []
    for i, mag in enumerate(magnitudes):
        # Construct the rupture
        rup = GSIMRupture(i, mag, **rupture_properties)
        # Set the target sites
        rup.set_target_sites(distances, **site_properties)
        ctx = rup.build_context(gsims.values())
        ctxts.append(ctx)
    # Convert to recarray
    cmaker = ContextMaker(rupture_properties["tectonic_region"], gsims.values(),
                          NULL_OQ_PARAM)
    return cmaker.recarray(ctxts)


def get_ground_motion_values(
        gsims: dict[str, GMPE],
        imts: dict[str, IMT],
        ctxts: np.recarray) -> pd.DataFrame:
    """Return the ground motion values for the expected scenarios

    :param gsims: dict of GSIM names mapped to a GSIM instance (class `GMPE`)
    :param imts: dict of IMT names mapped to a IMT instance (class `IMT`)
    :param ctxts: Scenarios as numpy recarray (output from context maker)

    :return: pandas DataFrame
    """
    # Get the GMVs
    # imts_values = list(imts.values())
    # n_gmvs = len(ctxts)
    # n_imts = len(imts)
    ret = pd.DataFrame()

    for gsim_label, gsim in gsims.items():
        # Need to pre-allocate arrays for median, sigma, tau and phi
        median = np.zeros([len(imts), len(ctxts)])
        sigma = np.zeros_like(median)
        tau = np.zeros_like(median)
        phi = np.zeros_like(median)
        # Call OpenQuake GSIM
        gsim.compute(ctxts, imts.values(), median, sigma, tau, phi)

        median = np.exp(median)
        ret[[f'{gsim_label} {i} {labels.MEDIAN}' for i in imts]] = median.T
        ret[[f'{gsim_label} {i} {labels.SIGMA}' for i in imts]] = sigma.T

    return ret


class labels:
    MEDIAN = "Median"
    SIGMA = "Stddev"
