"""trellis plots module"""
from itertools import product
from collections.abc import Collection, Iterable
from typing import Union, Optional
from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd
from openquake.hazardlib.scalerel import BaseMSR
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.imt import IMT
from openquake.hazardlib.contexts import ContextMaker
from openquake.hazardlib.scalerel.wc1994 import WC1994
from openquake.hazardlib.geo import Point

from .rupture import (get_target_sites, create_planar_surface,
                      get_hypocentre_on_planar_surface,
                      create_rupture)
from ..validators import harmonize_and_validate_inputs


@dataclass
class RuptureProperties:
    dip:float
    aspect:float
    tectonic_region:str = "Active Shallow Crust"
    rake:float = 0.
    ztor:float = 0.
    strike:float = 0.
    hypocenter_location:Optional[tuple[float, float]] = None
    msr:BaseMSR = field(default_factory=WC1994)
    # set initial_point as a random location on Earth
    initial_point:Point = field(default_factory=lambda: Point(45.18333, 9.15, 0.))


@dataclass
class SiteProperties:
    vs30:float
    line_azimuth:float = 90.0
    distance_type:str = "rrup"
    origin_point:tuple[float, float] = (0.5, 0.0)
    vs30measured:bool = True
    z1pt0:Optional[float] = None
    z2pt5:Optional[float] = None
    backarc:bool = False
    xvf:float = 150.0
    region:int = 0


def get_trellis(
        gsims: Iterable[Union[str, GMPE, type[GMPE]]],
        imts: Iterable[Union[str, IMT]],
        magnitudes: Union[float, Collection[float]],
        distances: Union[float, Collection[float]],
        rupture_properties: RuptureProperties,
        site_properties: SiteProperties) -> pd.DataFrame:
    """
    Calculates the ground motion values for the trellis plots

    :param magnitudes: list or numpy array of magnitudes
    :param distances: list or numpy array of distances

    :return: pandas DataFrame
    """
    gsims, imts = harmonize_and_validate_inputs(gsims, imts)

    magnitudes = np.asarray(magnitudes)
    if not magnitudes.shape:  # convert to a 1-length array if scalar:
        magnitudes = magnitudes.reshape(1,)
    distances = np.asarray(distances)
    if not distances.shape:   # convert to a 1-length array if scalar:
        distances = distances.reshape(1,)

    # Get the context objects as a numpy recarray
    ctxts = build_contexts(gsims, magnitudes, distances, rupture_properties,
                           site_properties)

    # prepare dataframe
    trellis_df = prepare_dataframe(imts, gsims, magnitudes, distances,
                                   site_properties.distance_type)

    # Get the ground motion values
    for gsim_label, medians, sigmas in get_ground_motion_values(gsims, imts, ctxts):
        # both medians and spectra are numpy matrices of
        # `len(imt)` rows X `len(ctxts) columns`. Convert them to
        # `len(ctxts) rows X len(imt)`columns` matrices
        medians = medians.T
        sigmas = sigmas.T
        trellis_df.loc[:, (labels.MEDIAN, list(imts), gsim_label)] = medians
        trellis_df.loc[:, (labels.SIGMA, list(imts), gsim_label)] = sigmas

    return trellis_df


def build_contexts(
        gsims: dict[str, GMPE],
        magnitudes: Collection[float],
        distances: Collection[float],
        r_props: RuptureProperties,
        s_props: SiteProperties) -> np.recarray:
    """Build the context objects from the set of magnitudes and distances and
    then returns them as a numpy recarray

    :param gsims: dict of GSIM names mapped to a GSIM instance (class `GMPE`)
    :param magnitudes: the magnitudes
    :param distances: the distances

    :return: Context objects in the form of a single numpy recarray of length:
        len(magnitudes) * len(distances)
    """
    cmaker = ContextMaker(r_props.tectonic_region, gsims.values(),
                          oq={"imtls": {"PGA": []}})
    ctxts = []
    for i, magnitude in enumerate(magnitudes):
        area = r_props.msr.get_median_area(magnitude, r_props.rake)
        surface = create_planar_surface(r_props.initial_point, r_props.strike,
                                        r_props.dip, area, r_props.aspect,
                                        r_props.ztor)
        hypocenter = get_hypocentre_on_planar_surface(surface,
                                                      r_props.hypocenter_location)
        # this is the old rupture.target.sites:
        target_sites = get_target_sites(hypocenter, surface, distances,
                                        **asdict(s_props))

        rupture = create_rupture(i, magnitude, r_props.rake,
                                 r_props.tectonic_region,
                                 hypocenter, surface)
        ctx = cmaker.get_ctx(rupture, target_sites)
        ctxts.append(ctx)

    # Convert to recarray:
    return cmaker.recarray(ctxts)


def prepare_dataframe(imts:dict, gsims:dict, magnitudes, distances, dist_label):
    """prepare an empty dataframe for holding trellis plot data"""
    # get columns:
    columns = [('mag', '', ''), (dist_label, '', '')] + \
              list(product([labels.MEDIAN, labels.SIGMA], imts, gsims))
    columns = pd.MultiIndex.from_tuples(columns, names=["name", "imt", "model"])
    ret = pd.DataFrame(columns=columns)
    # get the values for magnitudes, distances and periods:
    dists = np.tile(distances, len(magnitudes))
    mags = np.hstack((np.full(len(distances), m) for m in magnitudes))
    # assign:
    ret[dist_label] = dists
    ret['mag'] = mags
    return ret


def get_ground_motion_values(
        gsims: dict[str, GMPE],
        imts: dict[str, IMT],
        ctxts: np.recarray) -> Iterable[tuple[str, np.ndarray, np.ndarray]]:
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
