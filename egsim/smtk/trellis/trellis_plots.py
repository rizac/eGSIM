# Copyright (C) 2014-2017 GEM Foundation and G. Weatherill

"""
Sets up a simple rupture-site configuration to allow for physical comparison
of GMPEs
"""
from collections.abc import Iterable
from copy import deepcopy

import numpy as np
from openquake.hazardlib import imt
from openquake.hazardlib.gsim.base import (RuptureContext, DistancesContext,
                                           SitesContext)
from openquake.hazardlib.scalerel.wc1994 import WC1994
from .. import check_gsim_list, n_jsonify
from .configure import GSIMRupture, DEFAULT_POINT

# Generic dictionary of parameters needed for a trellis calculation
PARAM_DICT = {
    'magnitudes': [],
    'distances': [],
    'distance_type': 'rjb',
    'vs30': [],
    'strike': None,
    'dip': None,
    'rake': None,
    'ztor': None,
    'hypocentre_location': (0.5, 0.5),
    'hypo_loc': (0.5, 0.5),
    'msr': WC1994()
}

# Defines the plotting units for given intensitiy measure type
PLOT_UNITS = {
    'PGA': 'g',
    'PGV': 'cm/s',
    'SA': 'g',
    'SD': 'cm',
    'IA': 'm/s',
    'CSV': 'g-sec',
    'RSD': 's',
    'MMI': ''
}

# Verbose label for each given distance type
DISTANCE_LABEL_MAP = {
    'repi': 'Epicentral Dist.',
    'rhypo': 'Hypocentral Dist.',
    'rjb': 'Joyner-Boore Dist.',
    'rrup': 'Rupture Dist.',
    'rx': 'Rx Dist.'
}


class BaseTrellis(object):
    """
    Base class for holding functions related to the trellis plotting
    :param list or np.ndarray magnitudes:
        List of rupture magnitudes
    :param dict distances:
        Dictionary of distance measures as a set of np.ndarrays -
        {'repi', np.ndarray,
         'rjb': np.ndarray,
         'rrup': np.ndarray,
         'rhypo': np.ndarray}
        The number of elements in all arrays must be equal
    :param list gsims:
        List of strings or instance of the openquake.hazardlib.gsim classes
        to representing GMPE names or GMPEs
    :param list imts:
        List of intensity measures
    :param str stddev:
        Standard deviation type
    :param str distance_type:
        Type of source-site distance to be used in distances trellis
    """
    magdist = False

    def __init__(self, magnitudes, distances, gsims, imts, params,
                 stddev="Total", distance_type="rjb"):
        self.magnitudes = magnitudes
        self.distances = distances
        self.gsims:dict = check_gsim_list(gsims)
        self.params = params
        self.imts = imts
        self.dctx = []
        self.rctx = []
        self.sctx = None
        self.nsites = 0
        self._build_ctxs()
        self.stddev = stddev
        self.distance_type = distance_type

    def _build_ctxs(self):

        if not self.magdist:
            dctx = DistancesContext()
            required_dists = []
            for gmpe_name, gmpe in self.gsims.items():
                gsim_distances = [dist for dist in gmpe.REQUIRES_DISTANCES]
                for dist in gsim_distances:
                    if dist not in self.distances:
                        raise ValueError('GMPE %s requires distance type %s'
                                         % (gmpe_name, dist))
                    if dist not in required_dists:
                        required_dists.append(dist)
            dist_check = False
            for dist in required_dists:
                if dist_check and len(self.distances[dist]) != self.nsites:
                    raise ValueError("Distances arrays not equal length!")
                else:
                    self.nsites = len(self.distances[dist])
                    dist_check = True
                setattr(dctx, dist, self.distances[dist])
            self.dctx = [dctx for _ in self.magnitudes]
        else:
            # magdist case: there is a distance dictionary for each magnitude
            if isinstance(self.distances, dict):
                # Copy the same distances across
                self.distances = [deepcopy(self.distances) for _ in self.magnitudes]

            # Distances should be a list of dictionaries
            self.dctx = []
            required_distances = []
            for gmpe_name, gmpe in self.gsims.items():
                gsim_distances = [dist for dist in gmpe.REQUIRES_DISTANCES]
                for mag_distances in self.distances:
                    for dist in gsim_distances:
                        if dist not in mag_distances:
                            raise ValueError(
                                'GMPE %s requires distance type %s'
                                % (gmpe_name, dist))

                        if dist not in required_distances:
                            required_distances.append(dist)

            for distance in self.distances:
                dctx = DistancesContext()
                dist_check = False
                for dist in required_distances:
                    if dist_check and not (len(distance[dist]) == self.nsites):
                        raise ValueError("Distances arrays not equal length!")
                    else:
                        self.nsites = len(distance[dist])
                        dist_check = True
                    setattr(dctx, dist, distance[dist])
                self.dctx.append(dctx)

        # If magnitudes was provided with a list of RuptureContexts
        if all([isinstance(mag, RuptureContext) for mag in self.magnitudes]):
            # Get all required rupture attributes
            self.rctx = [mag for mag in self.magnitudes]
            for gmpe_name, gmpe in self.gsims.items():
                rup_params = [param
                              for param in gmpe.REQUIRES_RUPTURE_PARAMETERS]
                for rctx in self.rctx:
                    for param in rup_params:
                        if param not in rctx.__dict__:
                            raise ValueError(
                                "GMPE %s requires rupture parameter %s"
                                % (gmpe_name, param))
        else:
            self.rctx = []
            if (not isinstance(self.magnitudes, list) and not
                    isinstance(self.magnitudes, np.ndarray)):
                self.magnitudes = np.array(self.magnitudes)
            # Get all required rupture attributes
            required_attributes = []
            for gmpe_name, gmpe in self.gsims.items():
                rup_params = [param for param in
                              gmpe.REQUIRES_RUPTURE_PARAMETERS]
                for param in rup_params:
                    if param == 'mag':
                        continue
                    elif param not in self.params:
                        raise ValueError(
                            "GMPE %s requires rupture parameter %s"
                            % (gmpe_name, param))
                    elif param not in required_attributes:
                        required_attributes.append(param)
                    else:
                        pass
            for mag in self.magnitudes:
                rup = RuptureContext()
                rup.mag = mag
                for attr in required_attributes:
                    setattr(rup, attr, self.params[attr])
                self.rctx.append(rup)

        # sites
        slots = set()
        for gmpe in self.gsims.values():
            slots.update(gmpe.REQUIRES_SITES_PARAMETERS)
        self.sctx = SitesContext(slots=slots)
        self.sctx.sids = np.arange(self.nsites)
        required_attributes = []
        for gmpe_name, gmpe in self.gsims.items():
            site_params = [param for param in gmpe.REQUIRES_SITES_PARAMETERS]
            for param in site_params:
                if param not in self.params:
                    raise ValueError("GMPE %s requires site parameter %s"
                                     % (gmpe_name, param))
                elif param not in required_attributes:
                    required_attributes.append(param)
                else:
                    pass
        for param in required_attributes:
            if isinstance(self.params[param], float):
                setattr(self.sctx, param,
                        self.params[param] * np.ones(self.nsites, dtype=float))

            if isinstance(self.params[param], bool):
                if self.params[param]:
                    setattr(self.sctx, param, self.params[param] *
                            np.ones(self.nsites, dtype=bool))
                else:
                    setattr(self.sctx, param, self.params[param] *
                            np.zeros(self.nsites, dtype=bool))
            elif isinstance(self.params[param], Iterable):
                if not len(self.params[param]) == self.nsites:
                    raise ValueError("Length of sites value %s not equal to "
                                     "number of sites %s" %
                                     (param, self.nsites))
                setattr(self.sctx, param, self.params[param])
            else:
                pass

    def get_ground_motion_values(self):
        """
        Runs the GMPE calculations to retrieve ground motion values
        :returns:
            Nested dictionary of values
            {'GMPE1': {'IM1': , 'IM2': },
             'GMPE2': {'IM1': , 'IM2': }}
        """
        gmvs = {}
        for gmpe_name, gmpe in self.gsims.items():
            gmvs[gmpe_name] = {}
            for i_m in self.imts:
                gmvs[gmpe_name][i_m] = np.zeros(
                    [len(self.rctx), self.nsites], dtype=float)
                for iloc, (rct, dct) in enumerate(zip(self.rctx, self.dctx)):
                    try:
                        means, _ = gmpe.get_mean_and_stddevs(
                            self.sctx,
                            rct,
                            dct,
                            imt.from_string(i_m),
                            [self.stddev])

                        gmvs[gmpe_name][i_m][iloc, :] = np.exp(means)
                    except (KeyError, ValueError):
                        gmvs[gmpe_name][i_m] = np.array([])
                        break
        return gmvs

    def _get_ylabel(self, imt):
        """Returns the label for plotting on a y axis"""
        raise NotImplementedError


class MagnitudeIMTTrellis(BaseTrellis):
    """
    Class to generate plots showing the scaling of a set of IMTs with
    magnitude
    """
    def __init__(self, magnitudes, distances, gsims, imts, params,
                 stddev="Total", distance_type='rjb'):
        """
        Instantiate with list of magnitude and the corresponding distances
        given in a dictionary
        """
        for key in distances:
            if isinstance(distances[key], float):
                distances[key] = np.array([distances[key]])
        super().__init__(magnitudes, distances, gsims, imts, params, stddev,
                         distance_type=distance_type)

    @classmethod
    def from_rupture_properties(cls, properties, magnitudes, distance,
                                gsims, imts, stddev='Total', distance_type="rjb"):
        """Constructs the Base Trellis Class from a dictionary of
        properties. In this class, this method is simply an alias of
        `from_rupture_model`
        """
        return cls.from_rupture_model(properties, magnitudes, distance,
                                      gsims, imts, stddev=stddev,
                                      distance_type=distance_type)

    @classmethod
    def from_rupture_model(cls, properties, magnitudes, distance, gsims, imts,
                           stddev='Total', distance_type='rjb'):
        """
        Implements the magnitude trellis from a dictionary of properties,
        magnitudes and distance
        """
        # Properties
        properties.setdefault("tectonic_region", "Active Shallow Crust")
        properties.setdefault("rake", 0.)
        properties.setdefault("ztor", 0.)
        properties.setdefault("strike", 0.)
        properties.setdefault("msr", WC1994())
        properties.setdefault("initial_point", DEFAULT_POINT)
        properties.setdefault("hypocentre_location", None)
        properties.setdefault("line_azimuth", 90.)
        properties.setdefault("origin_point", (0.5, 0.5))
        properties.setdefault("vs30measured", True)
        properties.setdefault("z1pt0", None)
        properties.setdefault("z2pt5", None)
        properties.setdefault("backarc", False)
        properties.setdefault("distance_type", "rrup")
        # Define a basic rupture configuration
        rup = GSIMRupture(magnitudes[0], properties["dip"],
                          properties["aspect"], properties["tectonic_region"],
                          properties["rake"], properties["ztor"],
                          properties["strike"], properties["msr"],
                          properties["initial_point"],
                          properties["hypocentre_location"])
        # Add the target sites
        _ = rup.get_target_sites_point(distance, properties['distance_type'],
                                       properties["vs30"],
                                       properties["line_azimuth"],
                                       properties["origin_point"],
                                       properties["vs30measured"],
                                       properties["z1pt0"],
                                       properties["z2pt5"],
                                       properties["backarc"])
        # Get the contexts
        sctx, rctx, dctx = rup.get_gsim_contexts()
        # Create an equivalent 'params' dictionary by merging the site and
        # rupture properties
        sctx.__dict__.update(rctx.__dict__)
        for val in dctx.__dict__:
            if getattr(dctx, val) is not None:
                setattr(dctx, val, getattr(dctx, val)[0])
        return cls(magnitudes, dctx.__dict__, gsims, imts, sctx.__dict__,
                   distance_type=distance_type)

    def _get_ylabel(self, i_m):
        """
        Return the y-label for the magnitude IMT trellis
        """
        if 'SA(' in i_m:
            units = PLOT_UNITS['SA']
        else:
            units = PLOT_UNITS[i_m]
        return "Median {:s} ({:s})".format(i_m, units)

    def to_dict(self):
        """
        Parse the ground motion values to a dictionary
        """
        gmvs = self.get_ground_motion_values()
        gmv_dict = {
            "xvalues": self.magnitudes.tolist(),
            "xlabel": "Magnitude",
            "figures": []
        }
        for im in self.imts:
            ydict = {
                "ylabel": self._get_ylabel(im),
                "imt": im,
                "yvalues": {g: n_jsonify(gmvs[g][im].flatten()) for g in gmvs}
            }
            gmv_dict["figures"].append(ydict)
        return gmv_dict


class MagnitudeSigmaIMTTrellis(MagnitudeIMTTrellis):
    """
    Creates the Trellis plot for the standard deviations
    """

    def get_ground_motion_values(self):
        """
        Runs the GMPE calculations to retreive ground motion values
        :returns:
            Nested dictionary of values
            {'GMPE1': {'IM1': , 'IM2': },
             'GMPE2': {'IM1': , 'IM2': }}
        """
        gmvs = {}
        for gmpe_name, gmpe in self.gsims.items():
            gmvs[gmpe_name] = {}
            for i_m in self.imts:
                gmvs[gmpe_name][i_m] = np.zeros([len(self.rctx),
                                                 self.nsites],
                                                dtype=float)
                for iloc, (rct, dct) in enumerate(zip(self.rctx, self.dctx)):
                    try:
                        _, sigmas = gmpe.get_mean_and_stddevs(
                             self.sctx,
                             rct,
                             dct,
                             imt.from_string(i_m),
                             [self.stddev])
                        gmvs[gmpe_name][i_m][iloc, :] = sigmas[0]
                    except KeyError:
                        gmvs[gmpe_name][i_m] = np.array([], dtype=float)
                        break

        return gmvs

    def _get_ylabel(self, i_m):
        """
        """
        return self.stddev + " Std. Dev. ({:s})".format(str(i_m))


class DistanceIMTTrellis(BaseTrellis):
    """
    Trellis class to generate a plot of the GMPE attenuation with distance
    """
    XLABEL = "%s (km)"
    YLABEL = "Median %s (%s)"

    def __init__(self, magnitudes, distances, gsims, imts, params, stddev="Total",
                 distance_type='rjb'):
        """
        Instantiation
        """
        if isinstance(magnitudes, float):
            magnitudes = [magnitudes]
        for key in distances:
            if isinstance(distances[key], float):
                distances[key] = np.array([distances[key]])
        super().__init__(magnitudes, distances, gsims, imts, params, stddev,
                         distance_type=distance_type)

    @classmethod
    def from_rupture_properties(cls, properties, magnitude, distances,
                                gsims, imts, stddev='Total', distance_type= "rjb"):
        """Constructs the Base Trellis Class from a rupture properties.
        It internally creates a Rupture object and calls
        `from_rupture_model`. When not listed, arguments take the same
        values as `from_rupture_model`

        :param distances: a numeric array of chosen distances
        """
        params = {k: properties[k] for k in ['rake', 'initial_point', 'ztor',
                                             'hypocentre_location', 'strike',
                                             'msr', 'tectonic_region']
                  if k in properties}
        rupture = GSIMRupture(magnitude, properties['dip'],
                              properties['aspect'], **params)

        params = {k: properties[k] for k in ['line_azimuth', 'as_log',
                                             'vs30measured', 'z1pt0', 'z2pt5',
                                             'origin_point', 'backarc']
                  if k in properties}
        rupture.get_target_sites_line_from_given_distances(distances,
                                                           properties['vs30'],
                                                           **params)

        return cls.from_rupture_model(rupture, gsims, imts,
                                      stddev=stddev, distance_type=distance_type)

    @classmethod
    def from_rupture_model(cls, rupture: GSIMRupture, gsims, imts, stddev='Total',
                           distance_type= "rjb"):
        """
        Constructs the Base Trellis Class from a rupture model
        :param rupture:
            Rupture as instance of the :class:
            smtk.trellis.configure.GSIMRupture
        """
        magnitudes = [rupture.magnitude]
        sctx, rctx, dctx = rupture.get_gsim_contexts()
        # Create distances dictionary
        distances = {}
        for key in dctx._slots_:
            distances[key] = getattr(dctx, key)
        # Add all other parameters to the dictionary
        params = {}
        for key in rctx._slots_:
            params[key] = getattr(rctx, key)
        for key in sctx._slots_:
            params[key] = getattr(sctx, key)
        return cls(magnitudes, distances, gsims, imts, params, stddev,
                   distance_type=distance_type)

    def _get_ylabel(self, i_m):
        """
        Returns the y-label for the given IMT
        """
        if 'SA(' in i_m:
            units = PLOT_UNITS['SA']
        else:
            units = PLOT_UNITS[i_m]
        return "Median {:s} ({:s})".format(i_m, units)

    def to_dict(self):
        """
        Parses the ground motion values to a dictionary
        """
        gmvs = self.get_ground_motion_values()
        dist_label = "{:s} (km)".format(DISTANCE_LABEL_MAP[self.distance_type])
        gmv_dict = {
            "xvalues": n_jsonify(self.distances[self.distance_type]),
            "xlabel": dist_label,
            "figures": []
        }
        for im in self.imts:
            # Set the dictionary of y-values
            ydict = {
                "ylabel": self._get_ylabel(im),
                "imt": im,
                "yvalues": {}
            }
            for gsim in gmvs:
                # data = [None if np.isnan(val) else val for val in gmvs[gsim][im].flatten()]
                ydict["yvalues"][gsim] = n_jsonify(gmvs[gsim][im].flatten())
            gmv_dict["figures"].append(ydict)
            # col_loc += 1
        return gmv_dict


class DistanceSigmaIMTTrellis(DistanceIMTTrellis):
    def get_ground_motion_values(self):
        """
        Runs the GMPE calculations to retreive ground motion values
        :returns:
            Nested dictionary of values
            {'GMPE1': {'IM1': , 'IM2': },
             'GMPE2': {'IM1': , 'IM2': }}
        """
        gmvs = {}
        for gmpe_name, gmpe in self.gsims.items():
            gmvs[gmpe_name] = {}
            for i_m in self.imts:
                gmvs[gmpe_name][i_m] = np.zeros([len(self.rctx),
                                                 self.nsites])
                for iloc, (rct, dct) in enumerate(zip(self.rctx, self.dctx)):
                    try:
                        _, sigmas = gmpe.get_mean_and_stddevs(
                             self.sctx,
                             rct,
                             dct,
                             imt.from_string(i_m),
                             [self.stddev])
                        gmvs[gmpe_name][i_m][iloc, :] = sigmas[0]
                    except (KeyError, ValueError):
                        gmvs[gmpe_name][i_m] = np.array([], dtype=float)
                        break
        return gmvs

    def _get_ylabel(self, i_m):
        """
        """
        return self.stddev + " Std. Dev. ({:s})".format(str(i_m))


class MagnitudeDistanceSpectraTrellis(BaseTrellis):
    # In this case the preprocessor needs to be removed
    magdist = True

    def __init__(self, magnitudes, distances, gsims, imts, params,
                 stddev="Total", distance_type='rjb'):
        """
        Builds the trellis plots for variation in response spectra with
        magnitude and distance.

        In this case the class is instantiated with a set of magnitudes
        and a dictionary indicating the different distance types.

        :param imts: (numeric list or numpy array)
            the Spectral Acceleration's
            natural period(s) to be used
        """
        imts = ["SA(%s)" % i_m for i_m in imts]
        super().__init__(magnitudes, distances, gsims, imts, params,
                         stddev, distance_type=distance_type)

    @classmethod
    def from_rupture_properties(cls, properties, magnitudes, distance,
                                gsims, periods, stddev='Total', distance_type= "rjb"):
        """Constructs the Base Trellis Class from a dictionary of
        properties. In this class, this method is simply an alias of
        `from_rupture_model`

        :param periods: (numeric list or numpy array)
            the Spectral Acceleration's
            natural period(s) to be used. Note that this parameter
            is called `imt` in `from_rupture_model` where the name
            `imt` has been kept for legacy code compatibility
        """
        return cls.from_rupture_model(properties, magnitudes, distance,
                                      gsims, periods, stddev=stddev,
                                      distance_type=distance_type)

    @classmethod
    def from_rupture_model(cls, properties, magnitudes, distances,
                           gsims, imts, stddev='Total',
                           distance_type='rjb'):
        """
        Constructs the Base Trellis Class from a rupture model
        :param dict properties:
            Properties of the rupture and sites, including (* indicates
            required): *dip, *aspect, tectonic_region, rake, ztor, strike,
                       msr, initial_point, hypocentre_location, distance_type,
                       vs30, line_azimuth, origin_point, vs30measured, z1pt0,
                       z2pt5, backarc
        :param list magnitudes:
            List of magnitudes
        :param list distances:
            List of distances (the distance type should be specified in the
            properties dict - rrup, by default)
        """
        # Defaults for the properties of the rupture and site configuration
        properties.setdefault("tectonic_region", "Active Shallow Crust")
        properties.setdefault("rake", 0.)
        properties.setdefault("ztor", 0.)
        properties.setdefault("strike", 0.)
        properties.setdefault("msr", WC1994())
        properties.setdefault("initial_point", DEFAULT_POINT)
        properties.setdefault("hypocentre_location", None)
        properties.setdefault("line_azimuth", 90.)
        properties.setdefault("origin_point", (0.5, 0.5))
        properties.setdefault("vs30measured", True)
        properties.setdefault("z1pt0", None)
        properties.setdefault("z2pt5", None)
        properties.setdefault("backarc", False)
        properties.setdefault("distance_type", "rrup")
        distance_dicts = []
        rupture_dicts = []
        for magnitude in magnitudes:
            # Generate the rupture for the specific magnitude
            rup = GSIMRupture(magnitude, properties["dip"],
                              properties["aspect"],
                              properties["tectonic_region"],
                              properties["rake"], properties["ztor"],
                              properties["strike"], properties["msr"],
                              properties["initial_point"],
                              properties["hypocentre_location"])
            distance_dict = None
            for distance in distances:
                # Define the target sites with respect to the rupture
                _ = rup.get_target_sites_point(distance,
                                               properties["distance_type"],
                                               properties["vs30"],
                                               properties["line_azimuth"],
                                               properties["origin_point"],
                                               properties["vs30measured"],
                                               properties["z1pt0"],
                                               properties["z2pt5"],
                                               properties["backarc"])
                sctx, rctx, dctx = rup.get_gsim_contexts()
                if not distance_dict:
                    distance_dict = []
                    for (key, val) in dctx.__dict__.items():
                        distance_dict.append((key, val))
                    distance_dict = dict(distance_dict)
                else:
                    for (key, val) in dctx.__dict__.items():
                        distance_dict[key] = np.hstack([
                                distance_dict[key], val])
            distance_dicts.append(distance_dict)
            rupture_dicts.append(rctx)
        return cls(rupture_dicts, distance_dicts, gsims, imts, properties,
                   stddev, distance_type=distance_type)

    def get_ground_motion_values(self):
        """
        Runs the GMPE calculations to retrieve ground motion values
        :returns:
            Nested dictionary of values
            {'GMPE1': {'IM1': , 'IM2': },
             'GMPE2': {'IM1': , 'IM2': }}
        """
        gmvs = {}
        for gmpe_name, gmpe in self.gsims.items():
            gmvs[gmpe_name] = {}
            for i_m in self.imts:
                gmvs[gmpe_name][i_m] = np.zeros(
                    [len(self.rctx), self.nsites], dtype=float)
                for iloc, (rct, dct) in enumerate(zip(self.rctx, self.dctx)):
                    try:
                        means, _ = gmpe.get_mean_and_stddevs(
                            self.sctx, rct, dct,
                            imt.from_string(i_m),
                            [self.stddev])

                        gmvs[gmpe_name][i_m][iloc, :] = \
                            np.exp(means)
                    except (KeyError, ValueError):
                        gmvs[gmpe_name][i_m] = np.array([], dtype=float)
                        break
        return gmvs

    def to_dict(self):
        """
        Export ground motion values to a dictionary
        """
        gmvs = self.get_ground_motion_values()
        periods = [float(val.split("SA(")[1].rstrip(")")) for val in self.imts]
        gmv_dict = {
            "xlabel": "Period (s)",
            "xvalues": periods,
            "figures": []
        }
        mags = [rup.mag for rup in self.magnitudes]
        dists = self.distances[0][self.distance_type]
        for i, mag in enumerate(mags):
            for j, dist in enumerate(dists):
                ydict = {
                    "ylabel": self._get_ylabel(None),  # arg 'None' not used
                    "magnitude": mag,
                    "distance": np.around(dist, 3),
                    "imt": 'SA',
                    "yvalues": {gsim: [] for gsim in gmvs}
                }
                for gsim in gmvs:
                    for im in self.imts:
                        if len(gmvs[gsim][im]):
                            value = gmvs[gsim][im][i, j]
                            if np.isnan(value):
                                value = None
                            ydict["yvalues"][gsim].append(value)
                        else:
                            ydict["yvalues"][gsim].append(None)
                gmv_dict["figures"].append(ydict)
        return gmv_dict

    def _get_ylabel(self, i_m):
        """
        In this case only the spectra are being shown, so return only the
        Sa (g) label
        """
        return "Sa (g)"


class MagnitudeDistanceSpectraSigmaTrellis(MagnitudeDistanceSpectraTrellis):

    def get_ground_motion_values(self):
        """
        Runs the GMPE calculations to retreive ground motion values
        :returns:
            Nested dictionary of values
            {'GMPE1': {'IM1': , 'IM2': },
             'GMPE2': {'IM1': , 'IM2': }}
        """
        gmvs = {}
        for gmpe_name, gmpe in self.gsims.items():
            gmvs[gmpe_name] = {}
            for i_m in self.imts:
                gmvs[gmpe_name][i_m] = np.zeros([len(self.rctx), self.nsites],
                                                dtype=float)
                for iloc, (rct, dct) in enumerate(zip(self.rctx, self.dctx)):
                    try:
                        _, sigmas = gmpe.get_mean_and_stddevs(
                             self.sctx, rct, dct,
                             imt.from_string(i_m),
                             [self.stddev])
                        gmvs[gmpe_name][i_m][iloc, :] = sigmas[0]
                    except (KeyError, ValueError):
                        gmvs[gmpe_name][i_m] = np.array([], dtype=float)
                        break
        return gmvs

    def _get_ylabel(self, i_m):
        """
        Returns the standard deviation term (specific to the standard deviation
        type specified for the class)
        """
        return "{:s} Std. Dev.".format(self.stddev)
