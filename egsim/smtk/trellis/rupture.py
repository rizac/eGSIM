"""
source and site configuration functions for comparing the trellis plots
"""
from __future__ import annotations
from collections.abc import Iterable

from math import sqrt, pi, sin, cos, fabs
from copy import deepcopy
from typing import Optional
import numpy as np

from openquake.hazardlib.geo import Point, Mesh, PlanarSurface  # Line, Polygon,
from openquake.hazardlib.site import Site, SiteCollection
from openquake.hazardlib.source.rupture import BaseRupture
from openquake.hazardlib.source.point import PointSource

from egsim.smtk import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14

# Default point - some random location on Earth
DEFAULT_POINT = Point(45.18333, 9.15, 0.)


def create_rupture(id:int, magnitude, rake, tectonic_region, hypocenter, surface) \
        -> BaseRupture:
    rupture = BaseRupture(magnitude, rake, tectonic_region, hypocenter,
                       surface, PointSource)
    rupture.rup_id = id
    return rupture


def create_planar_surface(top_centroid: Point, strike: float, dip: float,
                          area: float, aspect: float, ztor: float) -> PlanarSurface:
    """
    Given a central location, create a simple planar rupture

    :param top_centroid: Centroid of trace of the rupture, as instance of
        :class:`openquake.hazardlib.geo.point.Point`
    :param strike: (float) Strike of rupture(Degrees)
    :param dip: (float) Dip of rupture (degrees)
    :param area: Area of rupture (km^2)
    :param aspect: Aspect ratio of rupture

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


def get_target_sites(hypocenter: Point,
        surface: PlanarSurface,
        distances: Iterable[float],
        vs30: float,
        **properties: dict):
    """Sets a set of target sites in the class"""
    site_properties = {**properties, 'vs30': vs30}
    # Extract the target information related to the configuration
    line_azimuth = site_properties.pop("line_azimuth", 90.0)
    origin_point = site_properties.pop("origin_point", (0.5, 0.0))
    as_log = site_properties.pop("as_log", "False")
    dist_type = site_properties.pop("distance_type", "rrup")
    # ... this leaves site_properties as only containing site attributes
    if "z1pt0" not in site_properties or site_properties["z1pt0"] is None:
        site_properties["z1pt0"] = vs30_to_z1pt0_cy14(site_properties["vs30"])
    if "z2pt5" not in site_properties or site_properties["z2pt5"] is None:
        site_properties["z2pt5"] = vs30_to_z2pt5_cb14(site_properties["vs30"])

    # Get the site locations
    site_locations = sites_at_distance(hypocenter, surface, distances,
                                       line_azimuth, origin_point, dist_type)
    # Turn them into OpenQuake Site objects, adding in the site properties
    target_sites = []
    for locn in site_locations:
        target_sites.append(Site(locn, **site_properties))
    # Convert to a SiteCollection
    return SiteCollection(target_sites)


def sites_at_distance(
        hypocenter: Point,
        surface: PlanarSurface,
        distances: Iterable[float], azimuth: float,
        origin_point: tuple[float, float], dist_type: str = "rrup") -> list:
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
            # dist which gives results consistent with cloe by distances
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
    pt0 = deepcopy(origin)
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


