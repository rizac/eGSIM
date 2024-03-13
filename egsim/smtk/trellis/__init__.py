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
                          harmonize_input_imts, validate_imt_sa_limits)

@dataclass
class RuptureProperties:
    dip:float = 90.
    aspect:float = 1.0
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
        rupture_properties: Optional[RuptureProperties] = None,
        site_properties: Optional[SiteProperties] = None) -> pd.DataFrame:
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
    if rupture_properties is None:
        rupture_properties = RuptureProperties()
    if site_properties is None:
        site_properties = SiteProperties()
    ctxts = build_contexts(
        gsims, magnitudes, distances, rupture_properties, site_properties)

    # Get the ground motion values
    data = []
    columns = []
    for gsim_label, gsim in gsims.items():
        imts_ok = validate_imt_sa_limits(gsim, imts)
        if not imts_ok:
            continue
        imt_names, imt_vals = list(imts_ok.keys()), list(imts_ok.values())
        try:
            median, sigma, tau, phi = get_ground_motion_values(gsim, imt_vals, ctxts)
            median = np.exp(median)  # FIXME ask Graeme: is this a Trellis feature or a prediction feature?
            data.append(median)
            columns.extend((i, labels.MEDIAN, gsim_label) for i in imt_names)
            data.append(sigma)
            columns.extend((i, labels.SIGMA, gsim_label) for i in imt_names)
        except Exception as exc:
            raise ValueError(f'Error in {gsim_label}: {str(exc)}')

    # distances:
    columns.append((
        labels.input_data,
        str(ColumnsRegistry.get_type(site_properties.distance_type).value),
        site_properties.distance_type
    ))
    # values: [d1...dN, ..., d1...dN], (concat [d1...dN] len(magnitudes) times)
    data.append(np.tile(distances, len(magnitudes)).reshape(len(ctxts), 1))
    # magnitudes:
    columns.append((
        labels.input_data,
        str(ColumnsRegistry.get_type(labels.MAG).value),
        labels.MAG
    ))
    # values: [M1, ..., M1, Mn, ... Mn] (repeating each Mi len(distances) times)
    data.append(np.repeat(magnitudes, len(distances)).reshape(len(ctxts), 1))

    # compute final DataFrame:
    trellis_df = pd.DataFrame(columns=columns, data=np.hstack(data))
    # sort columns (maybe we could use reindex but let's be more explicit):
    computed_cols = set(trellis_df.columns)
    expected_cols = \
        list(product(imts, [labels.MEDIAN, labels.SIGMA], gsims)) + columns[-2:]
    return trellis_df[[c for c in expected_cols if c in computed_cols]]


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


class labels:  # noqa (keep it simple, no Enum/dataclass needed)
    """computed column labels"""
    MEDIAN = "median"
    SIGMA = "stddev"
    MAG = "mag"
    input_data = 'input_data'
