import numpy as np
from math import sqrt, pi, sin, cos, fabs

from openquake.hazardlib.geo import Point, Mesh, PlanarSurface
from openquake.hazardlib.scalerel.wc1994 import WC1994
from openquake.hazardlib.site import Site, SiteCollection
from openquake.hazardlib.source.rupture import BaseRupture as Rupture
from openquake.hazardlib.source.point import PointSource
from openquake.hazardlib.gsim.base import (SitesContext, RuptureContext,
                                           DistancesContext)
from openquake.hazardlib.contexts import get_distances

from ...smtk import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14

TO_RAD = pi / 180.
FROM_RAD = 180. / pi
# Default point - some random location on Earth
DEFAULT_POINT = Point(45.18333, 9.15, 0.)


class GSIMRupture(object):
    """
    Defines a rupture plane consistent with the properties specified for
    the trellis plotting. Also contains methods for configuring the site
    locations
    """

    def __init__(self, magnitude, dip, aspect,
                 tectonic_region='Active Shallow Crust', rake=0., ztor=0.,
                 strike=0., msr=WC1994(), initial_point=DEFAULT_POINT,
                 hypocentre_location=None):
        """
        Instantiate the rupture - requires a minimum of a magnitude, dip
        and aspect ratio
        """
        self.magnitude = magnitude
        self.dip = dip
        self.aspect = aspect
        self.rake = rake
        self.strike = strike
        self.location = initial_point
        self.ztor = ztor
        self.trt = tectonic_region
        self.hypo_loc = hypocentre_location
        # If the top of rupture depth in the initial
        if fabs(self.location.depth - self.ztor) > 1E-9:
            self.location.depth = ztor
        self.msr = msr
        self.area = self.msr.get_median_area(self.magnitude, self.rake)
        self.surface = create_planar_surface(self.location,
                                             self.strike,
                                             self.dip,
                                             self.area,
                                             self.aspect)
        self.hypocentre = get_hypocentre_on_planar_surface(self.surface,
                                                           self.hypo_loc)
        self.rupture = self.get_rupture()
        self.target_sites_config = None
        self.target_sites = None

    def get_rupture(self):
        """
        Returns the rupture as an instance of the
        openquake.hazardlib.source.rupture.Rupture class
        """
        return Rupture(self.magnitude,
                       self.rake,
                       self.trt,
                       self.hypocentre,
                       self.surface,
                       PointSource)

    def get_gsim_contexts(self):
        """
        Returns a comprehensive set of GMPE contecxt objects
        """
        assert isinstance(self.rupture, Rupture)
        assert isinstance(self.target_sites, SiteCollection)
        # Distances
        dctx = DistancesContext()
        dctx.rrup = self.rupture.surface.get_min_distance(self.target_sites.mesh)
        dctx.rx = self.rupture.surface.get_rx_distance(self.target_sites.mesh)
        dctx.rjb = self.rupture.surface.get_joyner_boore_distance(self.target_sites.mesh)
        dctx.rhypo = self.rupture.hypocenter.distance_to_mesh(self.target_sites.mesh)
        dctx.repi = self.rupture.hypocenter.distance_to_mesh(self.target_sites.mesh,
                                                             with_depths=False)
        dctx.ry0 = self.rupture.surface.get_ry0_distance(self.target_sites.mesh)
        dctx.rcdpp = None  # ignored at present
        dctx.azimuth = get_distances(self.rupture, self.target_sites.mesh, 'azimuth')
        dctx.hanging_wall = None
        dctx.rvolc = np.zeros_like(self.target_sites.mesh.lons)
        # Sites
        sctx = SitesContext(slots=self.target_sites.array.dtype.names)
        for key in sctx._slots_:
            setattr(sctx, key, self.target_sites.array[key])

        # Rupture
        rctx = RuptureContext()
        rctx.sids = np.array(len(sctx.vs30), dtype=np.uint32)  # noqa
        rctx.mag = self.magnitude
        rctx.strike = self.strike
        rctx.dip = self.dip
        rctx.rake = self.rake
        rctx.ztor = self.ztor
        rctx.hypo_depth = self.rupture.hypocenter.depth
        rctx.hypo_lat = self.rupture.hypocenter.latitude
        rctx.hypo_lon = self.rupture.hypocenter.longitude
        rctx.hypo_loc = self.hypo_loc
        rctx.width = self.rupture.surface.get_width()
        return sctx, rctx, dctx

    def get_target_sites_line_from_given_distances(self, distances, vs30,
                                                   line_azimuth=90.,
                                                   origin_point=(0.5, 0.5), as_log=False,
                                                   vs30measured=True, z1pt0=None,
                                                   z2pt5=None, backarc=False):
        """
        Defines the target sites along a line with respect to the rupture from
        a given numeric array of distances
        """
        azimuth, origin_location, z1pt0, z2pt5 = \
            self._define_origin_target_site(vs30, line_azimuth, origin_point,
                                            vs30measured, z1pt0, z2pt5,
                                            backarc)

        distances = self._convert_distances(distances, as_log)

        return self._append_target_sites(distances, azimuth, origin_location,
                                         vs30, line_azimuth, origin_point,
                                         as_log, vs30measured, z1pt0, z2pt5,
                                         backarc)

    @staticmethod
    def _convert_distances(distances, as_log=False):
        """assures distances is a numpy numeric array, sorts it
        and converts its value to a logaritmic scale preserving the array
        bounds (min and max)"""
        dist = np.asarray(distances)
        dist.sort()
        if as_log:
            oldmin, oldmax = dist[0], dist[-1]
            dist = np.log1p(dist)  # avoid -inf @ zero in case
            newmin, newmax = dist[0], dist[-1]
            # re-map the space to be logarithmic between oldmin and oldmax:
            dist = oldmin + (oldmax - oldmin) * (dist - newmin) / (newmax - newmin)
        return dist

    def _define_origin_target_site(self, vs30, line_azimuth=90.,
                                   origin_point=(0.5, 0.5), vs30measured=True,
                                   z1pt0=None, z2pt5=None, backarc=False):
        """
        Defines the target site from an origin point
        """
        azimuth, origin_location, z1pt0, z2pt5 = _setup_site_peripherals(
            line_azimuth,
            origin_point,
            vs30,
            z1pt0,
            z2pt5,
            self.strike,
            self.surface)

        self.target_sites = [Site(origin_location,
                                  vs30,
                                  z1pt0,
                                  z2pt5,
                                  vs30measured=vs30measured,
                                  backarc=backarc)]
        return azimuth, origin_location, z1pt0, z2pt5

    def _append_target_sites(self, distances, azimuth, origin_location, vs30,
                             line_azimuth=90., origin_point=(0.5, 0.5),
                             as_log=False, vs30measured=True, z1pt0=None,
                             z2pt5=None, backarc=False):
        """
        Appends the target sites along a line with respect to the rupture,
        given an already set origin target site
        """
        for offset in distances:
            target_loc = origin_location.point_at(offset, 0., azimuth)
            self.target_sites.append(Site(target_loc,
                                          vs30,
                                          z1pt0,
                                          z2pt5,
                                          vs30measured=vs30measured,
                                          backarc=backarc))
        self.target_sites_config = {
            "TYPE": "Line",
            "RMAX": distances[-1],
            "SPACING": np.nan if len(distances) < 2 else
            distances[1] - distances[0],  # FIXME does it make sense?
            "AZIMUTH": line_azimuth,
            "ORIGIN": origin_point,
            "AS_LOG": as_log,
            "VS30": vs30,
            "VS30MEASURED": vs30measured,
            "Z1.0": z1pt0,
            "Z2.5": z2pt5,
            "BACKARC": backarc}
        self.target_sites = SiteCollection(self.target_sites)
        return self.target_sites

    def get_target_sites_point(
            self, distance, distance_type, vs30,
            line_azimuth=90, origin_point=(0.5, 0.5), vs30measured=True,
            z1pt0=None, z2pt5=None, backarc=False):
        """
        Returns a single target site at a fixed distance from the source,
        with distance defined according to a specific typology
        :param float distance:
            Distance (km) from the point to the source
        :param str distance_type:
            Type of distance {'rrup', 'rjb', 'repi', 'rhyp'}
        :param float vs30:
            Vs30 (m / s)
        :param float line_azimuth:
            Aziumth of the source-to-site line
        :param tuple origin_point:
            Location (along strike, down dip) of the origin of the source-site
            line within the rupture
        :param bool vs30measured:
            Is vs30 measured (True) or inferred (False)
        :param float z1pt0:
            Depth to 1 km/s interface
        :param floar z2pt5:
            Depth to 2.5 km/s interface
        """
        if not distance_type in list(POINT_AT_MAPPING.keys()):
            raise ValueError("Distance type must be one of: Rupture ('rrup'), "
                             "Joyner-Boore ('rjb'), Epicentral ('repi') or "
                             "Hypocentral ('rhyp')")

        azimuth, origin_location, z1pt0, z2pt5 = _setup_site_peripherals(
            line_azimuth,
            origin_point,
            vs30,
            z1pt0,
            z2pt5,
            self.strike,
            self.surface)
        self.target_sites_config = {
            "TYPE": "Point",
            "R": distance,
            "RTYPE": distance_type,
            "AZIMUTH": line_azimuth,
            "ORIGIN": origin_point,
            "VS30": vs30,
            "VS30MEASURED": vs30measured,
            "Z1.0": z1pt0,
            "Z2.5": z2pt5,
            "BACKARC": backarc}

        self.target_sites = POINT_AT_MAPPING[distance_type](
            self,
            distance,
            vs30,
            line_azimuth,
            origin_point,
            vs30measured,
            z1pt0,
            z2pt5,
            backarc=backarc)


def create_planar_surface(top_centroid, strike, dip, area, aspect):
    """
    Given a central location, create a simple planar rupture
    :param top_centroid:
        Centroid of trace of the rupture, as instance of :class:
            openquake.hazardlib.geo.point.Point
    :param float strike:
        Strike of rupture(Degrees)
    :param float dip:
        Dip of rupture (degrees)
    :param float area:
        Area of rupture (km^2)
    :param float aspect:
        Aspect ratio of rupture

    :returns: Rupture as an instance of the :class:
        openquake.hazardlib.geo.surface.planar.PlanarSurface
    """
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


def get_hypocentre_on_planar_surface(plane, hypo_loc=None):
    """
    Determines the location of the hypocentre within the plane
    :param plane:
        Rupture plane as instance of :class:
        openquake.hazardlib.geo.surface.planar.PlanarSurface
    :param tuple hypo_loc:
        Hypocentre location as fraction of rupture plane, as a tuple of
        (Along Strike, Down Dip), e.g. a hypocentre located in the centroid of
        the rupture plane would be input as (0.5, 0.5), whereas a hypocentre
        located in a position 3/4 along the length, and 1/4 of the way down
        dip of the rupture plane would be entered as (0.75, 0.25)
    :returns:
        Hypocentre location as instance of :class:
        openquake.hazardlib.geo.point.Point
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
    hypocentre = centroid.point_at(along_strike_dist,
                                   0.,
                                   along_strike_azimuth)
    # Translate down dip
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


def point_at_rupture_distance(model, distance, vs30, line_azimuth=90.,
                              origin_point=(0.5, 0.), vs30measured=True,
                              z1pt0=None, z2pt5=None, backarc=False):
    """
    Generates a site given a specified rupture distance from the
    rupture surface
    """
    azimuth, origin_location, z1pt0, z2pt5 = _setup_site_peripherals(
        line_azimuth, origin_point, vs30, z1pt0, z2pt5, model.strike,
        model.surface)
    selected_point = _rup_to_point(distance,
                                   model.surface,
                                   origin_location,
                                   azimuth,
                                   'rrup')
    target_sites = SiteCollection([Site(selected_point,
                                        vs30,
                                        z1pt0,
                                        z2pt5,
                                        vs30measured=vs30measured,
                                        backarc=backarc)])
    return target_sites


def point_at_joyner_boore_distance(model, distance, vs30, line_azimuth=90.,
                                   origin_point=(0.5, 0.),  vs30measured=True,
                                   z1pt0=None, z2pt5=None, backarc=False):
    """
    Generates a site given a specified rupture distance from the
    rupture surface
    """
    azimuth, origin_location, z1pt0, z2pt5 = _setup_site_peripherals(
        line_azimuth, origin_point, vs30, z1pt0, z2pt5, model.strike,
        model.surface)
    selected_point = _rup_to_point(distance,
                                   model.surface,
                                   origin_location,
                                   azimuth,
                                   'rjb')
    target_sites = SiteCollection([Site(selected_point,
                                        vs30,
                                        z1pt0,
                                        z2pt5,
                                        vs30measured=vs30measured,
                                        backarc=backarc)])
    return target_sites



def _rup_to_point(distance, surface, origin, azimuth, distance_type='rjb',
                  iter_stop=1E-3, maxiter=1000):
    """
    Place a point at a given distance from a rupture along a specified azimuth
    """
    pt0 = origin
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
            raise ValueError('Distance type must be rrup or rjb!')
        iterval += 1
    return pt1


def point_at_epicentral_distance(model, distance, vs30, line_azimuth=90.,
                                 origin_point=(0.5, 0.), vs30measured=True,
                                 z1pt0=None, z2pt5=None, backarc=False):
    """
    Generates a point at a given epicentral distance
    """
    azimuth, origin_point, z1pt0, z2pt5 = _setup_site_peripherals(
        line_azimuth, origin_point, vs30, z1pt0, z2pt5, model.strike,
        model.surface)
    return SiteCollection([Site(
        model.hypocentre.point_at(distance, 0., line_azimuth),
        vs30,
        z1pt0,
        z2pt5,
        vs30measured=vs30measured,
        backarc=backarc)])


def point_at_hypocentral_distance(model, distance, vs30, line_azimuth=90.,
                      origin_point=(0.5, 0.), vs30measured=True,
                      z1pt0=None, z2pt5=None, backarc=False):
    """
    Generates a point at a given hypocentral distance
    """
    azimuth, origin_point, z1pt0, z2pt5 = _setup_site_peripherals(
        line_azimuth, origin_point, vs30, z1pt0, z2pt5, model.strike,
        model.surface)

    xdist = sqrt(distance ** 2. - model.hypocentre.depth ** 2.)
    return SiteCollection([Site(
        model.hypocentre.point_at(xdist, -model.hypocentre.depth, azimuth),
        vs30,
        z1pt0,
        z2pt5,
        vs30measured=vs30measured,
        backarc=backarc)])



def _setup_site_peripherals(azimuth, origin_point, vs30, z1pt0, z2pt5, strike,
                            surface):
    """
    For a given configuration determine the site periferal values
    """
    if not z1pt0:
        z1pt0 = vs30_to_z1pt0_cy14(vs30)
    if not z2pt5:
        z2pt5 = vs30_to_z2pt5_cb14(vs30)
    azimuth = (strike + azimuth) % 360.
    origin_location = get_hypocentre_on_planar_surface(surface,
                                                       origin_point)
    origin_location.depth = 0.0
    return azimuth, origin_location, z1pt0, z2pt5


POINT_AT_MAPPING = {
    'rrup': point_at_rupture_distance,  # PointAtRuptureDistance(),
    'rjb': point_at_joyner_boore_distance,  # PointAtJoynerBooreDistance(),
    'repi': point_at_epicentral_distance,  # PointAtEpicentralDistance(),
    'rhypo': point_at_hypocentral_distance  # PointAtHypocentralDistance()
}
