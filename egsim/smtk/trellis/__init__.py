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
from ..registry import get_ground_motion_values
from ..flatfile import ColumnsRegistry
from ..validators import (validate_inputs, harmonize_input_gsims,
                          harmonize_input_imts, validate_imt_sa_periods)

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
    gsims = harmonize_input_gsims(gsims)
    imts = harmonize_input_imts(imts)
    validate_inputs(gsims, imts)

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
    for gsim_label, gsim in gsims.items():
        imts_ok = validate_imt_sa_periods(gsim, imts)
        if not imts_ok:
            continue
        imt_names, imt_vals = list(imts_ok.keys()), list(imts_ok.values())

        try:
            median, sigma, tau, phi = get_ground_motion_values(gsim, imt_vals, ctxts)
            median = np.exp(median)
            # both medians and spectra are numpy matrices of
            # `len(imt)` rows X `len(ctxts) columns`. Convert them to
            # `len(ctxts) rows X len(imt)`columns` matrices

            # FIXME REMOVE: this raises pandas warning:
            trellis_df.loc[:, (imt_names, labels.MEDIAN, gsim_label)] = median
            trellis_df.loc[:, (imt_names, labels.SIGMA, gsim_label)] = sigma
        except Exception as exc:
            raise ValueError(f'Error in {gsim_label}: {str(exc)}')

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


def prepare_dataframe(
        imts:dict[str, IMT],
        gsims:dict[str, GMPE],
        magnitudes,
        distances,
        dist_label:str):
    """prepare an empty dataframe for holding trellis plot data"""
    # get columns:
    dist_label = (
        labels.input_data,
        str(ColumnsRegistry.get_type(dist_label).value),
        dist_label
    )
    mag_label = (
        labels.input_data,
        str(ColumnsRegistry.get_type(labels.MAG).value),
        labels.MAG
    )
    columns = pd.MultiIndex.from_tuples(
        list(product(imts, [labels.MEDIAN, labels.SIGMA], gsims)) +
        [mag_label, dist_label]
    )
    ret = pd.DataFrame(columns=columns)
    # get the values for magnitudes, distances and periods:
    dists = np.tile(distances, len(magnitudes))
    mags = np.hstack(tuple(np.full(len(distances), m) for m in magnitudes))
    # assign:
    ret[dist_label] = dists
    ret[mag_label] = mags
    ret.index = range(len(ret))
    return ret


class labels:  # noqa (keep it simple, no Enum/dataclass needed)
    """computed column labels"""
    MEDIAN = "median"
    SIGMA = "stddev"
    MAG = "mag"
    input_data = 'input_data'
