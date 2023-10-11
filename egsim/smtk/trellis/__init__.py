"""trellis plots module"""
from itertools import product
from collections.abc import Collection, Iterable
from typing import Union

import numpy as np
import pandas as pd
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.imt import IMT
from openquake.hazardlib.contexts import ContextMaker
from openquake.hazardlib.scalerel.wc1994 import WC1994
from openquake.hazardlib.geo import Point

from .rupture import (get_target_sites, create_planar_surface,
                      get_hypocentre_on_planar_surface,
                      create_rupture)
from .. import harmonize_input_imts, harmonize_input_gsims, get_SA_period


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
    "initial_point": Point(45.18333, 9.15, 0.),  # random location on Earth
    "hypocenter_location": None
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

    is_spectra = trellis_type == "Magnitude-Distance-Spectra"
    if is_spectra:
        # sort keys according to SA period:
        imts = {i: imts[i] for i in sorted(imts, key=lambda i: get_SA_period(i))}

    # Get the context objects as a numpy recarray
    ctxts = build_contexts(
        gsims, magnitudes, distances, **rupture_properties, **site_properties)

    # prepare dataframe
    dist_label = site_properties['distance_type']

    trellis_df = prepare_dataframe(imts, gsims, magnitudes, distances,
                                   dist_label, is_spectra)

    # Get the ground motion values
    for gsim_label, medians, sigmas in get_ground_motion_values(gsims, imts, ctxts):
        # both medians and spectra are numpy matrices of
        # `len(imt)` rows X `len(ctxts) columns`. Convert them to
        # `len(ctxts) rows X len(imt)`columns` matrices
        medians = medians.T
        sigmas = sigmas.T
        if is_spectra:
            medians = medians.reshape(1, len(ctxts) * len(imts)).flatten()
            sigmas = sigmas.reshape(1, len(ctxts) * len(imts)).flatten()
            trellis_df.loc[:,  (labels.MEDIAN, 'SA', gsim_label)] = medians
            trellis_df.loc[:, (labels.SIGMA, 'SA', gsim_label)] = sigmas
        else:
            trellis_df.loc[:, (labels.MEDIAN, list(imts), gsim_label)] = medians
            trellis_df.loc[:, (labels.SIGMA, list(imts), gsim_label)] = sigmas
            # for i, mag in enumerate(magnitudes):
            #     row_filter = trellis_df['mag'] == mag
            #     start, end = i*len(distances), (i+1)*len(distances)
            #     trellis_df.loc[row_filter, medians_col] = medians[start:end, :]
            #     trellis_df.loc[row_filter, sigmas_col] = sigmas[start:end, :]

    return trellis_df
    # if trellis_type == "Magnitude-IMT":
    #     # make array [mag1, ..., mag1, mag2, ..., mag2, ..., magN, ..., magN]:
    #     trellis_data[('mag', '', '')] = np.hstack((np.full(step_len, m) for m in magnitudes))
    #
    #
    # elif trellis_type == "Distance-IMT":
    #     # make array [dist1, ..., distN, dist1, ..., distN, ..., dist1, ..., distN]:
    #     dist_label = site_properties['distance_type']
    #     trellis_data[(dist_label, '', '')] = pd.Series(np.tile(distances, step_len), name=dist_label)
    #
    # elif trellis_type == "Magnitude-Distance-Spectra":
    #     return self.magnitude_distance_spectra_trellis_output(medians, sigmas,
    #                                                           magnitudes,
    #                                                           distances, ctxts)
    # return trellis_data
    #
    # else:
    #     pass
    # return medians, sigmas


def build_contexts(gsims: dict[str, GMPE],
                   magnitudes: Collection[float],
                   distances: Collection[float],
                   *,
                   msr, rake, initial_point, strike, dip, aspect, tectonic_region,
                   hypocenter_location,
                   vs30, ztor, **site_properties) -> np.recarray:
    """Build the context objects from the set of magnitudes and distances and
    then returns them as a numpy recarray

    :param gsims: dict of GSIM names mapped to a GSIM instance (class `GMPE`)
    :param magnitudes: the magnitudes
    :param distances: the distances

    :return: Context objects in the form of a single numpy recarray of length:
        len(magnitudes) * len(distances)
    """
    cmaker = ContextMaker(tectonic_region, gsims.values(), oq={"imtls": {"PGA": []}})
    ctxts = []
    for i, magnitude in enumerate(magnitudes):
        area = msr.get_median_area(magnitude, rake)
        surface = create_planar_surface(initial_point, strike,
                                        dip, area, aspect, ztor)
        hypocenter = get_hypocentre_on_planar_surface(surface, hypocenter_location)
        # this is the old rupture.target.sites:
        target_sites = get_target_sites(hypocenter, surface,
                                        distances, vs30, **site_properties)

        rupture = create_rupture(i, magnitude, rake, tectonic_region,
                                 hypocenter, surface)
        ctx = cmaker.get_ctx(rupture, target_sites)
        ctxts.append(ctx)

    # Convert to recarray

    return cmaker.recarray(ctxts)


def prepare_dataframe(imts:dict, gsims:dict, magnitudes, distances, dist_label, is_spectra):

    # get columns:
    columns = [('mag', '', ''), (dist_label, '', ''), ('period', '', '')] + \
              list(product([labels.MEDIAN, labels.SIGMA], imts, gsims))
    columns = pd.MultiIndex.from_tuples(columns, names=["name", "imt", "model"])
    ret = pd.DataFrame(columns=columns)
    # get the values for magnitudes, distances and periods:
    if is_spectra:
        periods = np.tile([i.period for i in imts.values()],
                          len(magnitudes) * len(distances))
        dists = np.hstack((np.full(len(imts), m) for m in distances))
        mags = np.hstack((np.full(len(imts) * len(distances), m)
                          for m in magnitudes))
    else:
        periods = np.full(len(magnitudes) * len(distances), np.nan)
        dists = np.tile(distances, len(magnitudes))
        mags = np.hstack((np.full(len(distances), m) for m in magnitudes))
    # assign:
    ret['period'] = periods
    ret[dist_label] = dists
    ret['mag'] = mags
    return ret


def get_ground_motion_values(
        gsims: dict[str, GMPE],
        imts: dict[str, IMT],
        ctxts: np.recarray) -> Iterable[tuple[np.ndarray, np.ndarray]]:
    """Return the ground motion values for the expected scenarios

    :param gsims: dict of GSIM names mapped to a GSIM instance (class `GMPE`)
    :param imts: dict of IMT names mapped to an IMT instance (class `IMT`)
    :param ctxts: Scenarios as numpy recarray (output from context maker) as
        N (rows) x M (columns) matrix where N is the number of magnitudes
        and M the number of distances

    :return: Iterable of tuples:
        `gsim_label, medians, sigmas`
        where `medians` and `sigmas` are two matrices
        (`len(imt)` rows X `len(ctxts)` columns)
        denoting the medians and standard deviations of the motions, respectively
    """
    # Get the GMVs
    # imts_values = list(imts.values())
    # n_gmvs = len(ctxts)
    # n_imts = len(imts)
    for gsim_label, gsim in gsims.items():
        # Need to pre-allocate arrays for median, sigma, tau and phi
        median = np.zeros([len(imts), len(ctxts)])
        sigma = np.zeros_like(median)
        tau = np.zeros_like(median)
        phi = np.zeros_like(median)
        # Call OpenQuake GSIM
        gsim.compute(ctxts, imts.values(), median, sigma, tau, phi)
        median = np.exp(median)
        yield gsim_label, median, sigma



class labels:
    MEDIAN = "Median"
    SIGMA = "Stddev"
