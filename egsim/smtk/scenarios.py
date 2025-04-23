"""module for computing ground motion values from different scenarios"""
from itertools import product
from collections.abc import Collection, Iterable
from typing import Union, Optional
from dataclasses import dataclass, field, asdict
from math import sqrt, pi, sin, cos, fabs

import numpy as np
import pandas as pd
from openquake.hazardlib.scalerel import BaseMSR
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.imt import IMT
from openquake.hazardlib.scalerel.wc1994 import WC1994
from openquake.hazardlib.geo import Point, Mesh, PlanarSurface
from openquake.hazardlib.site import Site, SiteCollection
from openquake.hazardlib.source.rupture import BaseRupture
from openquake.hazardlib.source.point import PointSource

from .registry import get_ground_motion_values, Clabel, init_context_maker
from .flatfile import FlatfileMetadata
from .converters import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14
from .validation import (validate_inputs, harmonize_input_gsims,
                         harmonize_input_imts, validate_imt_sa_limits, ModelError)


@dataclass
class RuptureProperties:
    dip: float = 90.
    aspect: float = 1.0
    tectonic_region: str = "Active Shallow Crust"
    rake: float = 0.
    ztor: float = 0.
    strike: float = 0.
    hypocenter_location: Optional[tuple[float, float]] = None
    msr: BaseMSR = field(default_factory=WC1994)
    # set initial_point as a random location on Earth
    initial_point: Point = field(default_factory=lambda: Point(45.18333, 9.15, 0.))


@dataclass
class SiteProperties:
    vs30: float = 760.0
    line_azimuth: float = 90.0
    distance_type: str = "rrup"
    origin_point: tuple[float, float] = (0.5, 0.0)
    vs30measured: bool = True
    z1pt0: Optional[float] = None
    z2pt5: Optional[float] = None
    backarc: bool = False
    xvf: float = 150.0
    region: int = 0


def get_scenarios_predictions(
        gsims: Iterable[Union[str, GMPE]],
        imts: Iterable[Union[str, IMT]],
        magnitudes: Union[float, Collection[float]],
        distances: Union[float, Collection[float]],
        rupture_properties: Optional[RuptureProperties] = None,
        site_properties: Optional[SiteProperties] = None,
        header_sep: Union[str, None] = Clabel.sep
) -> pd.DataFrame:
    """
    Calculate the ground motion values from different scenarios to be used, e.g.
    in trellis plots

    :param gsims: Iterable of Ground shaking intensity models or their names (str)
    :param imts: Iterable of Intensity measure types or their names (str)
    :param magnitudes: list or numpy array of magnitudes
    :param distances: list or numpy array of distances
    :param rupture_properties: the optional Rupture properties (see
        class RuptureProperties)
    :param site_properties: the optional Site properties (see class
        SiteProperties)
    :param header_sep: str or None (default: " "): the separator used to concatenate
        each column header into one string (e.g. "PGA median BindiEtAl2014Rjb"). Set
        to "" or None to return a multi-level column header composed of the first 3
        dataframe rows (e.g. ("PGA", "median", "BindiEtAl2014Rjb"). See
        "MultiIndex / advanced indexing" in the pandas doc for details)

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
        gsims, imts, magnitudes, distances, rupture_properties, site_properties)

    # Get the ground motion values
    data = []
    columns = []
    for gsim_name, gsim in gsims.items():
        imts_ok = validate_imt_sa_limits(gsim, imts)
        if not imts_ok:
            continue
        imt_names, imt_vals = list(imts_ok.keys()), list(imts_ok.values())
        try:
            median, sigma, tau, phi = get_ground_motion_values(gsim, imt_vals, ctxts)
            data.append(median)
            columns.extend((i, Clabel.median, gsim_name) for i in imt_names)
            data.append(sigma)
            columns.extend((i, Clabel.std, gsim_name) for i in imt_names)
        except Exception as exc:
            raise ModelError(f'{gsim_name}: ({exc.__class__.__name__}) {str(exc)}')

    # distances:
    columns.append((
        Clabel.input,
        str(FlatfileMetadata.get_type(site_properties.distance_type).value),
        site_properties.distance_type
    ))
    # values: [d1...dN, ..., d1...dN], (concat [d1...dN] len(magnitudes) times)
    data.append(np.tile(distances, len(magnitudes)).reshape(len(ctxts), 1))
    # magnitudes:
    columns.append((
        Clabel.input,
        str(FlatfileMetadata.get_type(Clabel.mag).value),
        Clabel.mag
    ))
    # values: [M1, ..., M1, Mn, ... Mn] (repeating each Mi len(distances) times)
    data.append(np.repeat(magnitudes, len(distances)).reshape(len(ctxts), 1))

    # compute final DataFrame:
    output = pd.DataFrame(columns=columns, data=np.hstack(data))
    # sort columns (maybe we could use reindex but let's be more explicit):
    computed_cols = set(output.columns)
    expected_cols = \
        list(product(imts, [Clabel.median, Clabel.std], gsims)) + columns[-2:]
    output = output[[c for c in expected_cols if c in computed_cols]].copy()
    if header_sep:
        output.columns = [header_sep.join(c) for c in output.columns]
    else:
        output.columns = pd.MultiIndex.from_tuples(output.columns)  # noqa
    return output


def build_contexts(
        gsims: dict[str, GMPE],
        imts: dict[str, IMT],
        magnitudes: Collection[float],
        distances: Collection[float],
        r_props: RuptureProperties,
        s_props: SiteProperties) -> np.recarray:
    """Build the context objects from the set of magnitudes and distances and
    then returns them as a numpy recarray

    :param gsims: dict of GSIM names mapped to a GSIM instance (class `GMPE`)
    :param magnitudes: the magnitudes
    :param distances: the distances
    :param r_props: a `RuptureContext` object defining the Rupture properties
    :param s_props: a `SiteProperties` object defining the Site properties

    :return: Context objects in the form of a single numpy recarray of length:
        len(magnitudes) * len(distances)
    """
    cmaker = init_context_maker(gsims.values(), imts, magnitudes,
                                tectonic_region=r_props.tectonic_region)
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
        rec_array = cmaker.recarray([ctx])
        rec_array["occurrence_rate"] = 0.0  # only needed in PSHA calculation
        ctxts.append(rec_array)

    # Convert to recarray:
    return np.hstack(ctxts).view(np.recarray)


# utilities:


def create_rupture(
        id: int, magnitude, rake, tectonic_region, hypocenter, surface  # noqa
) -> BaseRupture:
    rupture = BaseRupture(
        magnitude, rake, tectonic_region, hypocenter, surface, PointSource
    )
    rupture.rup_id = id
    return rupture


def create_planar_surface(
        top_centroid: Point,
        strike: float,
        dip: float,
        area: float,
        aspect: float,
        ztor: float
) -> PlanarSurface:
    """
    Given a central location, create a simple planar rupture

    :param top_centroid: Centroid of trace of the rupture, as instance of
        :class:`openquake.hazardlib.geo.point.Point`
    :param strike: (float) Strike of rupture (Degrees)
    :param dip: (float) Dip of rupture (degrees)
    :param area: Area of rupture (km^2)
    :param aspect: Aspect ratio of rupture
    :param ztor: top of rupture depth, in km

    :return: Rupture as an instance of
        :class:`openquake.hazardlib.geo.surface.planar.PlanarSurface`
    """
    # If the top of rupture depth in the initial
    if fabs(top_centroid.depth - ztor) > 1E-9:
        top_centroid.depth = ztor
    rad_dip = dip * pi / 180.
    width = sqrt(area / aspect)
    length = aspect * width
    # Get end points by moving the top_centroid along strike
    top_right = top_centroid.point_at(length / 2., 0., strike)
    top_left = top_centroid.point_at(length / 2.,
                                     0.,
                                     (strike + 180.) % 360.)
    # Along surface width
    surface_width = width * cos(rad_dip)
    vertical_depth = width * sin(rad_dip)
    dip_direction = (strike + 90.) % 360.

    bottom_right = top_right.point_at(surface_width,
                                      vertical_depth,
                                      dip_direction)
    bottom_left = top_left.point_at(surface_width,
                                    vertical_depth,
                                    dip_direction)

    # Create the rupture
    return PlanarSurface(strike, dip, top_left, top_right,
                         bottom_right, bottom_left)


def get_target_sites(
        hypocenter: Point,
        surface: PlanarSurface,
        distances: Iterable[float],
        vs30: float,
        line_azimuth=90.0,
        origin_point=(0.5, 0.0),
        distance_type="rrup",
        z1pt0=None, z2pt5=None, **extras
):
    """Sets a set of target sites in the class"""
    # Get the site locations
    site_locations = sites_at_distance(hypocenter, surface, distances,
                                       line_azimuth, origin_point, distance_type)
    # Turn them into OpenQuake Site objects, adding in the site properties
    if z1pt0 is None:
        z1pt0 = vs30_to_z1pt0_cy14(vs30)
    if z2pt5 is None:
        z2pt5 = vs30_to_z2pt5_cb14(vs30)
    target_sites = []
    for locn in site_locations:
        target_sites.append(Site(locn, vs30=vs30, z1pt0=z1pt0, z2pt5=z2pt5, **extras))
    # Convert to a SiteCollection
    return SiteCollection(target_sites)


def sites_at_distance(
        hypocenter: Point,
        surface: PlanarSurface,
        distances: Iterable[float],
        azimuth: float,
        origin_point: tuple[float, float],
        dist_type: str = "rrup") -> list[Point]:
    """Determine the locations of the target sites according to their specified
    distances and distance configuration
    """
    azimuth = (surface.get_strike() + azimuth) % 360.
    origin_location = get_hypocentre_on_planar_surface(surface,
                                                       origin_point)
    # origin_depth = deepcopy(origin_location.depth)
    origin_location.depth = 0.0
    locations = []
    for dist in distances:
        if dist_type == "repi":
            locations.append(hypocenter.point_at(dist, 0.0, azimuth))
        elif dist_type == "rhypo":
            if dist < hypocenter.depth:
                raise ValueError(
                    "Required hypocentral distance %.1f km less than "
                    "hypocentral depth (%.1f km)" % (dist, hypocenter.depth)
                )
            xdist = sqrt(dist ** 2. - hypocenter.depth ** 2.)
            locations.append(
                hypocenter.point_at(xdist, - hypocenter.depth, azimuth)
            )
        elif dist_type == "rjb":
            locations.append(
                _rup_to_point(dist, surface, origin_location, azimuth, 'rjb')
            )
        elif dist_type == "rrup":
            # FIXME (horrible hack): dist 0 is buggy, set it to 0.0075 (the smallest
            #  dist which gives results consistent with cloe by distances
            dist = max(dist, 0.0075)
            locations.append(
                _rup_to_point(dist, surface, origin_location, azimuth, 'rrup')
            )
        else:
            raise ValueError(f"Unsupported distance type '{dist_type}'")
    return locations


def get_hypocentre_on_planar_surface(
        plane: PlanarSurface,
        hypo_loc: Optional[tuple[float, float]] = None) -> Point:
    """
    Determine the location of the hypocentre within the plane

    :param plane: Rupture plane as instance of
        :class:`openquake.hazardlib.geo.surface.planar.PlanarSurface`
    :param tuple hypo_loc: Hypocentre location as fraction of rupture plane,
        as a tuple of (Along Strike, Down Dip), e.g. a hypocentre located in
        the centroid of the rupture plane would be input as (0.5, 0.5), whereas
        a hypocentre located in a position 3/4 along the length, and 1/4 of the
        way down dip of the rupture plane would be entered as (0.75, 0.25)

    :return: Hypocentre location as instance of
        :class:`openquake.hazardlib.geo.point.Point`
    """
    centroid = plane.get_middle_point()
    if hypo_loc is None:
        return centroid

    along_strike_dist = (hypo_loc[0] * plane.length) - (0.5 * plane.length)
    down_dip_dist = (hypo_loc[1] * plane.width) - (0.5 * plane.width)
    if along_strike_dist >= 0.:
        along_strike_azimuth = plane.strike
    else:
        along_strike_azimuth = (plane.strike + 180.) % 360.
        along_strike_dist = (0.5 - hypo_loc[0]) * plane.length
    # Translate along strike
    hypocentre = centroid.point_at(along_strike_dist, 0.,
                                   along_strike_azimuth)
    # Translate down dip
    TO_RAD = pi / 180.  # noqa
    horizontal_dist = down_dip_dist * cos(TO_RAD * plane.dip)
    vertical_dist = down_dip_dist * sin(TO_RAD * plane.dip)
    if down_dip_dist >= 0.:
        down_dip_azimuth = (plane.strike + 90.) % 360.
    else:
        down_dip_azimuth = (plane.strike - 90.) % 360.
        down_dip_dist = (0.5 - hypo_loc[1]) * plane.width
        horizontal_dist = down_dip_dist * cos(TO_RAD * plane.dip)

    return hypocentre.point_at(horizontal_dist,
                               vertical_dist,
                               down_dip_azimuth)


def _rup_to_point(
        distance: float, surface: PlanarSurface, origin: Point, azimuth: float,
        distance_type: str = 'rjb', iter_stop: float = 1E-3, maxiter: int = 1000)\
        -> Point:
    """
    Place a point at a given distance from a rupture along a specified azimuth
    """
    pt1 = origin.point_at(distance, 0., azimuth)
    r_diff = np.inf
    dip = surface.dip
    sin_dip = np.sin(np.radians(dip))
    dist_sin_dip = distance / sin_dip
    iterval = 0
    while (np.fabs(r_diff) >= iter_stop) and (iterval <= maxiter):
        pt1mesh = Mesh(np.array([pt1.longitude]),
                       np.array([pt1.latitude]),
                       None)
        if distance_type == 'rjb' or np.fabs(dip - 90.0) < 1.0E-3:
            r_diff = (distance -
                      surface.get_joyner_boore_distance(pt1mesh)).flatten()
            pt0 = Point(pt1.longitude, pt1.latitude)
            if r_diff > 0.:
                pt1 = pt0.point_at(r_diff, 0., azimuth)
            else:
                pt1 = pt0.point_at(np.fabs(r_diff), 0.,
                                   (azimuth + 180.) % 360.)
        elif distance_type == 'rrup':
            rrup = surface.get_min_distance(pt1mesh).flatten()
            if 0.0 <= azimuth <= 180.0:
                # On hanging wall
                r_diff = dist_sin_dip - (rrup / sin_dip)
            else:
                # On foot wall
                r_diff = distance - rrup
            pt0 = Point(pt1.longitude, pt1.latitude)
            if r_diff > 0.:
                pt1 = pt0.point_at(r_diff, 0., azimuth)
            else:
                pt1 = pt0.point_at(np.fabs(r_diff), 0.,
                                   (azimuth + 180.) % 360.)
        else:
            raise ValueError('Distance type must be rrup or rjb')
        iterval += 1
    return pt1
