'''
Core functions (decoupled from any web related stuff) calling the actual computation functions.
This module is basically a bridge between eGSIM and smtk.

Created on 31 May 2018

@author: riccardo
'''
from collections import defaultdict
import json
import re

import numpy as np
from smtk.trellis.trellis_plots import DistanceIMTTrellis, \
    MagnitudeIMTTrellis, DistanceSigmaIMTTrellis, MagnitudeSigmaIMTTrellis
from smtk.sm_table import GroundMotionTable, records_where
from smtk.residuals.gmpe_residuals import Residuals
from smtk.residuals.residual_plots import residuals_with_distance

from egsim.core.utils import vectorize, DISTANCE_LABEL, MOF


def _relabel_sa(string):
    '''Simplifies SA string representation removing redundant trailing zeros,
    if present
    Examples:
    'SA(1)' -> 'SA(1)' (unchanged)
    'SA(1.0)' -> 'SA(1.0)' (unchanged)
    'ASA(1.0)' -> 'ASA(1.0)' (unchanged)
    'SA(1.00)' -> 'SA(1.0)'
    'SA(1.000)' -> 'SA(1.0)'
    'SA(.000)' -> 'SA(.0)'
    '''
    return re.sub(r'((?:^|\s|\()SA\(\d*\.\d\d*?)0+(\))(?=($|\s|\)))', r"\1\2",
                  string)


def get_trellis(params):
    # param names:
    MAG = 'magnitude'  # pylint: disable=invalid-name
    DIST = 'distance'  # pylint: disable=invalid-name
    VS30 = 'vs30'  # pylint: disable=invalid-name
    Z1PT0 = 'z1pt0'  # pylint: disable=invalid-name
    Z2PT5 = 'z2pt5'  # pylint: disable=invalid-name
    GSIM = 'gsim'  # pylint: disable=invalid-name
    IMT = 'imt'  # pylint: disable=invalid-name

    # dip, aspect will be used below, we oparse them here because they are
    # mandatory (FIXME: are they?)
    magnitude, distance, vs30, z1pt0, z2pt5, gsim, imt = \
        params.pop(MAG), params.pop(DIST), params.pop(VS30), \
        params.pop(Z1PT0), params.pop(Z2PT5), params.pop(GSIM), params.pop(IMT)
    magnitudes = np.asarray(vectorize(magnitude))  # smtk wants numpy arrays
    distances = np.asarray(vectorize(distance))  # smtk wants numpy arrays

    vs30s = vectorize(vs30)
    z1pt0s = vectorize(z1pt0)
    z2pt5s = vectorize(z2pt5)

    trellisclass = params.pop('plot_type')
    isdist = trellisclass in (DistanceIMTTrellis, DistanceSigmaIMTTrellis)
    ismag = trellisclass in (MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis)
    if not isdist and not ismag:  # magnitudedistancetrellis:
        # imt is actually a vector of periods for the SA.
        # FIXME: PR to gmpe-smtk?
        imt = _default_periods_for_spectra()

    def jsonserialize(value):
        '''serializes a numpy scalr into python scalar, no-op if value is not
        a numpy number'''
        try:
            return value.item()
        except AttributeError:
            return value

    ret = None
    fig_key, col_key, row_key = 'figures', 'column', 'row'
    for vs30, z1pt0, z2pt5 in zip(vs30s, z1pt0s, z2pt5s):
        params[VS30] = vs30
        params[Z1PT0] = z1pt0
        params[Z2PT5] = z2pt5
        # Depending on `trellisclass` we might need to iterate over
        # `magnitudes`, or use `magnitudes` once (the same holds for
        # `distances`). In order to make code cleaner we define a magnitude
        # iterator which yields a two element tuple (m1, m2) where m1 is the
        # scalar value to be saved as json, and m2 is the value
        # (scalar or array) to be passed to the Trellis class:
        magiter = zip(magnitudes, magnitudes) if isdist else \
            zip([None], [magnitudes])
        for mag, mags in magiter:
            # same as magnitudes (see above):
            distiter = zip(distances, distances) if ismag else \
                zip([None], [distances])
            for dist, dists in distiter:
                func = trellisclass.from_rupture_properties
                data = func(params, mags, dists, gsim, imt).to_dict()
                if ret is None:
                    ret = {k: v for k, v in data.items() if k != fig_key}
                    ret[fig_key] = []
                    # change labels SA(1.0000) into SA(1.0):
                    if 'xlabel' in ret:
                        ret['xlabel'] = _relabel_sa(ret['xlabel'])
                dst_figures = ret[fig_key]
                src_figures = data[fig_key]
                for fig in src_figures:
                    fig.pop(col_key, None)
                    fig.pop(row_key, None)
                    fig[VS30] = jsonserialize(vs30)
                    fig[MAG] = jsonserialize(fig.get(MAG, mag))
                    fig[DIST] = jsonserialize(fig.get(DIST, dist))
                    # change labels SA(1.0000) into SA(1.0):
                    if 'ylabel' in fig:
                        fig['ylabel'] = _relabel_sa(fig['ylabel'])
                    dst_figures.append(fig)
    return ret


def _default_periods_for_spectra():
    '''returns an array for the default periods for the magnitude distance
    spectra trellis.
    The returned numeric list will define the xvalues of each plot'''
    return [0.05, 0.075, 0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18,
            0.19, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34, 0.36, 0.38,
            0.40, 0.42, 0.44, 0.46, 0.48, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75,
            0.8, 0.85, 0.9, 0.95, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8,
            1.9, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0]


def get_gmdbplot(params):
    '''returns a dict of a ground motion database plot (distances vs
    magnitudes)'''
    # params:
    DIST_TYPE = 'distance_type'  # pylint: disable=invalid-name

    dist_type = params[DIST_TYPE]
    mags, dists = get_magnitude_distances(records_iter(params), dist_type)
    return {'x': dists, 'y': mags,  # 'labels': [r.id for r in gmdb.records],
            'xlabel': DISTANCE_LABEL[dist_type], 'ylabel': 'Magnitude'}


def get_magnitude_distances(records, dist_type):
    """
    From the Strong Motion database, returns lists of magnitude and distance
    pairs
    """
    mags = []
    dists = []
    for record in records:
        mag = record['magnitude']
        dist = record[dist_type]
        if dist_type == "rjb" and np.isnan(dist):
            dist = record["repi"]
        elif dist_type == "rrup" and np.isnan(dist):
            dist = record["rhypo"]
        if not np.isnan(mag) and not np.isnan(dist):
            mags.append(mag)
            dists.append(dist)
    return mags, dists


def records_iter(params):
    '''Computes the selection from the given already validated params and
    returns a filtered GroundMotionDatabase object'''
    # params:
    GMDB = 'gmdb'  # pylint: disable=invalid-name
    SEL = 'selexpr'  # pylint: disable=invalid-name

    # params[GMDB] is the tuple (hdf file name, table name):
    with GroundMotionTable(*params[GMDB], mode='r') as gmdb:
        for rec in records_where(gmdb.table, params.get(SEL)):
            yield rec


def get_residuals(params):
    # params:
    GMDB = 'gmdb'  # pylint: disable=invalid-name
    GSIM = 'gsim'  # pylint: disable=invalid-name
    IMT = 'imt'  # pylint: disable=invalid-name
    DTYPE = 'distance_type'  # pylint: disable=invalid-name
    PLOTTYPE = 'plot_type'  # pylint: disable=invalid-name
    SEL = 'selexpr'  # pylint: disable=invalid-name

    func = params[PLOTTYPE]
    residuals = Residuals(params[GSIM], params[IMT])

    # Compute residuals.
    # params[GMDB] is the tuple (hdf file name, table name):
    gmdb = GroundMotionTable(*params[GMDB], mode='r')
    if params.get(SEL):
        gmdb = gmdb.filter(params[SEL])
    residuals.get_residuals(gmdb)

    # statistics = residuals.get_residual_statistics()
    ret = defaultdict(lambda: defaultdict(lambda: {}))
    distance_type = params[DTYPE]

    kwargs = dict(residuals=residuals, as_json=True)
    # linestep = binwidth/10
    for gsim in residuals.residuals:
        for imt in residuals.residuals[gsim]:
            kwargs['gmpe'] = gsim
            kwargs['imt'] = imt

            # convert nans. FIXME: Ask Graeme:
#             _data = residuals.residuals[gsim][imt]
#             for key in ['Total', 'Intra event', 'Inter event']:
#                 vals = _data[key]
#                 _data[key] = vals[np.isfinite(vals)]

            if func == residuals_with_distance:
                kwargs['distance_type'] = distance_type
            imt2 = _relabel_sa(imt)
            ret[gsim][imt2] = func(**kwargs)
            if imt2 != imt:
                for val in ret[gsim][imt2].values():
                    if 'xlabel' in val:
                        val['xlabel'] = _relabel_sa(val['xlabel'])
                    if 'ylabel' in val:
                        val['ylabel'] = _relabel_sa(val['ylabel'])

    return ret


def testing(params):
    GMDB = 'gmdb'  # pylint: disable=invalid-name
    GSIM = 'gsim'  # pylint: disable=invalid-name
    IMT = 'imt'  # pylint: disable=invalid-name
    FIT_M = 'fit_measure'  # pylint: disable=invalid-name
    CONFIG = 'config'  # pylint: disable=invalid-name
    SEL = 'selexpr'  # pylint: disable=invalid-name

    residuals = Residuals(params[GSIM], params[IMT])
    # Compute residuals.
    # params[GMDB] is the tuple (hdf file name, table name):
    gmdb = GroundMotionTable(*params[GMDB], mode='r')
    if params.get(SEL):
        gmdb = gmdb.filter(params[SEL])
    residuals.get_residuals(gmdb)
    # residuals = res.Residuals(self.gsims, self.imts)

    ret = {}
    config = params.get(CONFIG, {})
    # columns: "Measure of fit" "imt" "gsim" "value(s)"
    for key, name, func in params[FIT_M]:
        result = func(residuals, config)
        if isinstance(result, (list, tuple)):
            result = result[0]
        # Returned object are of this type (<GMPE>: any valid Gmpe as string,
        # <IMT>: any valid IMT as string, <TYPE>: str in "Total", "Inter event"
        # or "Intra event". <EDRTYPE>: string in "MDE Norm", "sqrt Kappa" or
        # "EDR"):
        #
        # Residuals:
        # {
        #   <GMPE>: {
        #      <IMT>: {
        #        <TYPE>: {
        #            "Mean": <float>,
        #            "Std Dev": <float>
        #        }
        #      }
        #   }
        # }
        #
        # Likelihood:
        # {
        #   <GMPE>: {
        #      <IMT>: {
        #        <TYPE>: <ndarray>
        #        }
        #      }
        #   }
        # }
        #
        # Log-Likelihood, Multivariate Log-Likelihood:
        # {
        #   <GMPE>: {
        #      <IMT>: <float>  # IMT includes the "All" key
        #   }
        # }
        #
        # EDR
        # {
        #   <GMPE>: {
        #      <EDRTYPE>: <float>
        #   }
        # }
        #
        # The code belows re-arranges the dicts flattening them like this:
        # "<Residual name> <residual type if any>":{
        #        <IMT>: {
        #           <GMPE>: float or ndarray
        #        }
        #     }
        # }

        if key == MOF.RES:
            for gsim, gsim_result in result.items():
                for imt, imt_result in gsim_result.items():
                    imt2 = _relabel_sa(imt)
                    for type_, type_result in imt_result.items():
                        for meas, value in type_result.items():
                            moffit = "%s %s %s" % (name, type_, meas)
                            ret.setdefault(moffit, {}).\
                                setdefault(imt2, {})[gsim] = _jsonify_num(value)
        elif key == MOF.LH:
            for gsim, gsim_result in result.items():
                for imt, imt_result in gsim_result.items():
                    imt2 = _relabel_sa(imt)
                    for type_, values in imt_result.items():
                        # change array value into:
                        p25, p50, p75 = np.nanpercentile(values, [25, 50, 75])
                        for kkk, vvv in (('Median', p50), ('IQR', p75-p25)):
                            moffit = "%s %s %s" % (name, type_, kkk)
                            ret.setdefault(moffit, {}).\
                                setdefault(imt2, {})[gsim] = _jsonify_num(vvv)
        elif key in (MOF.LLH, MOF.MLLH):
            for gsim, gsim_result in result.items():
                for imt, value in gsim_result.items():
                    imt2 = _relabel_sa(imt)
                    moffit = name
                    ret.setdefault(moffit, {}).\
                        setdefault(imt2, {})[gsim] = _jsonify_num(value)
        elif key == MOF.EDR:
            for gsim, gsim_result in result.items():
                for type_, value in gsim_result.items():
                    moffit = "%s %s" % (name, type_)
                    imt = ""  # hack
                    ret.setdefault(moffit, {}).\
                        setdefault(imt, {})[gsim] = _jsonify_num(value)

    return ret


def _jsonify_num(val):
    try:
        json.dumps(val)
    except Exception as exc:  # pylint: disable=broad-except
        try:  # try converting from numpy. If it fails, raise exc above
            pyval = val.tolist()
            # json.dumps(pyval)
            nans = np.argwhere(~np.isfinite(val)).flatten()
            if len(nans) == 1 and val.ndim == 0:
                pyval = None
            else:
                for idx in nans:
                    pyval[idx] = None
            val = pyval
        except:  #  @IgnorePep8 pylint: disable=broad-except
            raise exc

    return val
