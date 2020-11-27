'''
Core functions (decoupled from any web related stuff) calling the actual
computation functions of the gmpe-smtk package.

Created on 31 May 2018

@author: riccardo
'''
from collections import defaultdict
import re

import numpy as np
from smtk.trellis.trellis_plots import (DistanceIMTTrellis,
                                        MagnitudeIMTTrellis,
                                        DistanceSigmaIMTTrellis,
                                        MagnitudeSigmaIMTTrellis,
                                        MagnitudeDistanceSpectraTrellis,
                                        MagnitudeDistanceSpectraSigmaTrellis)
from smtk.sm_table import GroundMotionTable
from smtk.residuals.gmpe_residuals import Residuals

from egsim.core.utils import (vectorize, DISTANCE_LABEL, MOF, OQ,
                              GSIM_REQUIRED_ATTRS)



class P:  # noqa
    '''container class for input param names (avoid typos throughout the code)
    '''
    # (enums are an overkill for such  a simple case)
    GSIM = 'gsim'
    IMT = 'imt'
    MAG = 'magnitude'
    DIST = 'distance'
    STDEV = 'stdev'
    PLOT_TYPE = 'plot_type'
    FIT_M = 'fit_measure'
    CONFIG = 'config'
    SELEXP = 'selexpr'
    GMDB = 'gmdb'
    VS30 = 'vs30'
    Z1PT0 = 'z1pt0'
    Z2PT5 = 'z2pt5'
    DIST_TYPE = 'distance_type'


def get_trellis(params):
    '''Core method to compute trellis plots data

    :param params: dict with the request parameters

    :return: json serializable dict to be passed into a Response object
    '''
    gsim, imt, magnitudes, distances, trellisclass, stdev_trellisclass = \
        _extract_params(params)

    # Returns True if trellisclass is a Distance-based Trellis class:
    _isdist = trellisclass in (DistanceIMTTrellis, DistanceSigmaIMTTrellis)
    # Returns True if trellisclass is a Magnitude-based Trellis class:
    _ismag = trellisclass in (MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis)

    xdata = None
    figures = defaultdict(list)  # imt name -> list of dicts (1 dict=1 plot)
    for vs30, z1pt0, z2pt5 in zip(vectorize(params.pop(P.VS30)),
                                  vectorize(params.pop(P.Z1PT0)),
                                  vectorize(params.pop(P.Z2PT5))):
        params[P.VS30] = vs30
        params[P.Z1PT0] = z1pt0
        params[P.Z2PT5] = z2pt5
        # Depending on `trellisclass` we might need to iterate over
        # `magnitudes`, or use `magnitudes` once (the same holds for
        # `distances`). In order to make code cleaner we define a magnitude
        # iterator which yields a two element tuple (m1, m2) where m1 is the
        # scalar value to be saved as json, and m2 is the value
        # (scalar or array) to be passed to the Trellis class:
        for mag, mags in zip(magnitudes, magnitudes) \
                if _isdist else zip([None], [magnitudes]):
            # same as magnitudes (see above):
            for dist, dists in zip(distances, distances) \
                    if _ismag else zip([None], [distances]):

                data = _get_trellis_dict(trellisclass, params, mags, dists,
                                         gsim, imt)

                if xdata is None:
                    xdata = {
                        'xlabel': _relabel_sa(data['xlabel']),
                        'xvalues': data['xvalues']
                    }

                _add_stdev(data, None if stdev_trellisclass is None
                           else _get_trellis_dict(stdev_trellisclass,
                                                  params, mags, dists,
                                                  gsim, imt))

                for fig in data['figures']:
                    # 'fig' represents a plot. It is a dict of this type:
                    # (see method `_get_trellis_dict` and `_add_stdev` above):
                    #    {
                    #        ylabel: str
                    #        stdvalues: {} or dict gsimname -> list of numbers
                    #        stdlabel: str (might be empty str)
                    #        imt: str (the imt)
                    #        yvalues: dict (gsim name -> list of numbers)
                    #    }
                    # Add some keys to 'fig':
                    fig[P.VS30] = _jsonserialize(vs30)
                    fig[P.MAG] = _jsonserialize(fig.get(P.MAG, mag))
                    fig[P.DIST] = _jsonserialize(fig.get(P.DIST, dist))
                    # And add `fig` to `figures`, which is a dict of this type:
                    #    {
                    #        <imt:str>: [<plot:dict>, ..., <plot:ditc>],
                    #        ...
                    #        <imt:str>: [<plot:dict>, ..., <plot:ditc>],
                    #    }
                    # (The plot-dicts count mapped to each imt will depend on
                    # the product of the chosen vs30, mag and dist):
                    figures[fig.pop('imt')].append(fig)

    # imt is a list of the imts given as input, or None for "spectra" Trellis
    # (in this latter case just get the figures keys, which should be populated
    # of a single key 'SA')
    return {
        **xdata,
        'imts': imt or list(figures.keys()),
        **figures
    }


def _extract_params(params):
    '''Returns the basic parameters from a trellis `params` dict, converting
    them according to egsim needs. Returns the tuple:
    (gsim, imt, magnitudes, distances, trellisclass, stdev_trellisclass)
    where `trellis_class_for_stddev` can be None or the `trellis_class`
    counterpart for computing the standard deviations
    '''
    # NOTE: the `params` dict will be passed to smtk routines: we use 'pop'
    # whenever possible to avoid passing unwanted params:
    gsim = params.pop(P.GSIM)
    # imt might be None for "spectra" Trellis classes, thus provide None:
    imt = params.pop(P.IMT, None)
    magnitudes = np.asarray(vectorize(params.pop(P.MAG)))  # smtk wants np arrays
    distances = np.asarray(vectorize(params.pop(P.DIST)))  # smtk wants np arrays

    trellisclass = params.pop(P.PLOT_TYPE)
    # define stddev trellis class if the parameter stdev is true
    stdev_trellisclass = None  # do not compute stdev (default)
    if params.pop(P.STDEV, False):
        if trellisclass == DistanceIMTTrellis:
            stdev_trellisclass = DistanceSigmaIMTTrellis
        elif trellisclass == MagnitudeIMTTrellis:
            stdev_trellisclass = MagnitudeSigmaIMTTrellis
        elif trellisclass == MagnitudeDistanceSpectraTrellis:
            stdev_trellisclass = MagnitudeDistanceSpectraSigmaTrellis

    return gsim, imt, magnitudes, distances, trellisclass, stdev_trellisclass


def _get_trellis_dict(trellis_class, params, mags, dists, gsim, imt):  # noqa
    '''Compute the Trellis plot for a single set of eGSIM parameters
    '''
    isspectra = trellis_class in (MagnitudeDistanceSpectraTrellis,
                                  MagnitudeDistanceSpectraSigmaTrellis)
    trellis_obj = \
        trellis_class.from_rupture_properties(params,
                                              mags,
                                              dists,
                                              gsim,
                                              _default_periods_for_spectra()
                                              if isspectra else imt)
    data = trellis_obj.to_dict()
    # NOTE:
    # data = {
    #    xlabel: str
    #    xvalues: numeric_list
    #    figures: [
    #        {
    #            ylabel: str
    #            row: ? (will be removed)
    #            column: ? (will be removed)
    #            imt: str,
    #            yvalues: {
    #                gsim1 : numeric_list,
    #                ...
    #                gsimN: numeric_list
    #            }
    #        },
    #        ...
    #    ]
    # }

    # We want to get each `figure` element to be a dict of this type:
    #    {
    #        ylabel: str (same as above, but delete trailing zeroes in IMT)
    #        _key: tuple, str (depends on context): unique hashable id
    #        imt: str (the imt)
    #        yvalues: dict (same as above)
    #    }

    src_figures = data['figures']
    for fig in src_figures:
        fig.pop('column', None)
        fig.pop('row', None)
        # set a key to uniquely identify the figure: in case os spectra,
        # we trust the (magnitude, distance) pair. Otherwise, the IMT:
        fig['_key'] = (fig['magnitude'], fig['distance']) if isspectra else \
            fig['imt']
        # change labels SA(1.0000) into SA(1.0)
        fig['ylabel'] = _relabel_sa(fig['ylabel'])

    return data


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


def _default_periods_for_spectra():
    '''returns an array for the default periods for the magnitude distance
    spectra trellis.
    The returned numeric list will define the xvalues of each plot'''
    return [0.05, 0.075, 0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18,
            0.19, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34, 0.36, 0.38,
            0.40, 0.42, 0.44, 0.46, 0.48, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75,
            0.8, 0.85, 0.9, 0.95, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8,
            1.9, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0]


def _add_stdev(data, stdev_data=None):
    '''Adds to each element of data the standard deviations of
    stdev_data.

    :param data: the retuend value of `_get_trellis_dict`, called for a
        given trellis class (no standard deviation)
    :param data: the retuend value of `_get_trellis_dict`, called for the
        appropriate trellis standard deviation class
    '''
    if stdev_data is not None:
        # convert the list to a dict with keys the imt
        # (each list element is mapped to a specified imt so this
        # is safe):
        stdev_data['figures'] = {_['_key']: _
                                 for _ in stdev_data['figures']}

    for fig in data['figures']:
        # 'fig' is a dict of this type:
        # (see method `_get_trellis_dict`):
        #    {
        #        ylabel: str
        #        _key: hashable id (tuple, str...)
        #        imt: str (the imt)
        #        yvalues: dict (gsim name -> list of numbers)
        #    }
        fig['stdvalues'] = {}
        fig['stdlabel'] = ''
        # 2. Remove the key '_key' but store it as we might need it
        fig_key = fig.pop('_key')
        # 3. Add standard deviations, if computed (using 'fig_key')
        if stdev_data is not None:
            std_fig = stdev_data['figures'].get(fig_key, {})
            # ('std_fig' is of the same typ of 'fig')
            # Add to 'fig' the 'std_fig' values of interest
            # (renaming them):
            fig['stdvalues'] = std_fig.get('yvalues', {})
            fig['stdlabel'] = std_fig.get('ylabel', '')


def _jsonserialize(value):
    '''Simple serialization from numpy scalar into python scalar, no-op if
    value is not a numpy number'''
    try:
        return value.item()
    except AttributeError:
        return value


def get_gmdbplot(params):
    '''returns a dict of a ground motion database plot (distances vs
    magnitudes)'''
    # params:
    dist_type = params[P.DIST_TYPE]
    mags, dists, nan_count = \
        _get_magnitude_distances(get_gmdb(params).records, dist_type)
    return {
        'xvalues': dists,
        'yvalues': mags,
        # 'labels': [r.id for r in gmdb.records],
        'xlabel': DISTANCE_LABEL[dist_type],
        'ylabel': 'Magnitude',
        'nan_count': nan_count
    }


def _get_magnitude_distances(records, dist_type):
    """
    From the Strong Motion database, returns lists of magnitude and distance
    pairs
    """
    mags = []
    dists = []
    nan_count = 0
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
        else:
            nan_count += 1
    return mags, dists, nan_count


def get_gmdb(params):
    '''returns a GrounMotionTable from the given params dict, which must
    have specific keys. Currently, they are:
    'gmdb': the tuple (hdf file name, table name), and
    'selexpr': str
    (`selexpr` is OPTIONAL)
    '''
    gmdb = GroundMotionTable(*params[P.GMDB])
    if params.get(P.SELEXP, None):
        gmdb = gmdb.filter(params[P.SELEXP])
    return gmdb


# keep this variable global as it is accessed also from within views.py:
RESIDUALS_STATS = ('mean', 'stddev', 'median', 'slope', 'intercept',
                   'pvalue')


def get_residuals(params):
    '''Core method to compute residuals plots data

    :param params: dict with the request parameters

    :return: json serializable dict to be passed into a Response object
    '''
    func, kwargs = params[P.PLOT_TYPE]
    residuals = Residuals(params[P.GSIM], params[P.IMT])

    # Compute residuals.
    # params[GMDB] is the tuple (hdf file name, table name):
    gmdb = get_gmdb(params)
    residuals.get_residuals(gmdb)

    # statistics = residuals.get_residual_statistics()
    ret = defaultdict(lambda: defaultdict(lambda: {}))

    # extend keyword arguments:
    kwargs = dict(kwargs, residuals=residuals, as_json=True)
    # linestep = binwidth/10
    for gsim in residuals.residuals:
        for imt in residuals.residuals[gsim]:
            kwargs['gmpe'] = gsim
            kwargs['imt'] = imt
            imt2 = _relabel_sa(imt)
            res_plots = func(**kwargs)
            for res_type, res_plot in res_plots.items():
                for stat in RESIDUALS_STATS:
                    res_plot.setdefault(stat, None)
                if imt2 != imt:
                    res_plot['xlabel'] = _relabel_sa(res_plot['xlabel'])
                    res_plot['ylabel'] = _relabel_sa(res_plot['ylabel'])
                # make also x and y keys consistent with trellis response:
                res_plot['xvalues'] = res_plot.pop('x')
                res_plot['yvalues'] = res_plot.pop('y')
                ret[imt2][res_type][gsim] = res_plot

    return ret


def testing(params):
    '''Core method to compute testing data

    :param params: dict with the request parameters

    :return: json serializable dict to be passed into a Response object
    '''

    # params[GMDB] is the tuple (hdf file name, table name):
    gmdb_base = gmdb = get_gmdb(params)

    ret = {}
    obs_count = defaultdict(int)
    gsim_skipped = {}
    config = params.get(P.CONFIG, {})
    # columns: "Measure of fit" "imt" "gsim" "value(s)"
    for gsim in params[P.GSIM]:
        try:
            residuals = Residuals([gsim], params[P.IMT])

            gmdb = gmdb_base.filter(_get_selexpr(gsim,
                                                 params.get(P.SELEXP, '')))
            numrecords = _gmdb_records(residuals, gmdb)

            obs_count[gsim] = numrecords
            if not numrecords:
                gsim_skipped[gsim] = 'No matching db record found'
                continue

            gsim_values = []

            for key, name, func in params[P.FIT_M]:
                result = func(residuals, config)
                gsim_values.extend(_itervalues(gsim, key, name, result))

            for moffit, imt, value in gsim_values:
                # note: value isa Numpy scalar, but not ALL numpy scalar
                # are json serializable: only those that are equal to Python's
                ret.setdefault(moffit, {}).\
                                setdefault(imt, {})[gsim] = value.item()

        except Exception as exc:  # pylint: disable=broad-except
            gsim_skipped[gsim] = str(exc)

    return {'Measure of fit': ret, 'Db records': obs_count,
            'Gsim skipped': gsim_skipped}


def _get_selexpr(gsim, user_selexpr=None):
    '''builds a selection expression from a given gsim name concatenating
    the given `user_selexpr` (user defined selection expression with the
    expression obtained by inspecting the required arguments of the given
    gsim'''
    attrs = OQ.required_attrs(gsim)
    selexpr_chunks = []
    strike_dip_rake_found = False
    for att in attrs:
        if att in ('rake', 'strike', 'dip') and not strike_dip_rake_found:
            strike_dip_rake_found = True
            selexpr_chunks.append('(((dip_1 != nan) & '
                                  '(strike_1 != nan) & '
                                  '(rake_1 != nan)) | '
                                  '((dip_2 != nan) & '
                                  '(strike_2 != nan) & '
                                  '(rake_2 !=nan)))')
            continue
        (column, missing_val) = GSIM_REQUIRED_ATTRS.get(att, ['', ''])
        if column and missing_val:
            selexpr_chunks.append('(%s != %s)' % (column, missing_val))

    if not selexpr_chunks:
        return user_selexpr
    if user_selexpr:
        selexpr_chunks.insert(0, '(%s)' % user_selexpr)

    return " & ".join(selexpr_chunks)


def _gmdb_records(residuals, gm_table=None):
    '''Returns the number of the given GM Table records in the given
    `residuals` object.
    Example:

    residual = Residuals([gsims], [imts])
    gmdb = GroundMotionTable(path)
    gmdb_records(residual, gmdb)

    :param residuals: an instance of
        :class:`smtk.residuals.gmpe_residuals.Residuals`. Note that
        residuals.geT_residuals() must have been called on the instance if
        `gm_table` is None. Otherwise, it computes db residuals by calling
        `residuals.get_residuals(gm_table)`
    :param gm_table: optional, defaults to None if missing. A
        :class:`smtk.sm_table.GroundMotionTable` class to compute the
        db records before returning their count. If None, such a class must
        have been provided before this method call, otherwise 0 is returned
    '''
    if gm_table is not None:
        residuals.get_residuals(gm_table)
    # get number of records (observations) to be used. This avoids
    # opening the file twice, first for counting, then for calculating, as
    # we have the number of observations in each 'EventIndex' list of
    # each context element of residuals.contexts:
    numrecords = 0
    for context in residuals.contexts:
        numrecords += context.get('Num. Sites', 0)
    return numrecords


def _itervalues(gsim, key, name, result):
    '''Yields the tuples
        (Measure of fit, IMT, value)
    (str, str, numeric) by parsing `result`

    :param key: the key denoting a measure of fit
    :param name: a name denoting the measure of fit
    :param result: the result of the smtk computation of the given measure of
        fit on the given gsim
    '''

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

    gsim_result = result[gsim]
    if key == MOF.RES:
        for imt, imt_result in gsim_result.items():
            imt2 = _relabel_sa(imt)
            for type_, type_result in imt_result.items():
                for meas, value in type_result.items():
                    moffit = "%s %s %s" % (name, type_, meas)
                    yield _title(moffit), imt2, value
    elif key == MOF.LH:
        for imt, imt_result in gsim_result.items():
            imt2 = _relabel_sa(imt)
            for type_, values in imt_result.items():
                # change array value into Median and IQR:
                p25, p50, p75 = np.nanpercentile(values, [25, 50, 75])
                for kkk, vvv in (('Median', p50), ('IQR', p75-p25)):
                    moffit = "%s %s %s" % (name, type_, kkk)
                    yield _title(moffit), imt2, vvv
    elif key in (MOF.LLH, MOF.MLLH):
        for imt, value in gsim_result.items():
            imt2 = _relabel_sa(imt)
            moffit = name
            yield _title(moffit), imt2, value
    elif key == MOF.EDR:
        for type_, value in gsim_result.items():
            moffit = "%s %s" % (name, type_)
            imt = ""  # hack
            yield _title(moffit), imt, value


def _title(string):
    '''Makes the string with the first letter of the first word capitalized
    only and replaces 'std dev' with 'stddev' for consistency with
    residuals
    '''
    return (string[:1].upper() + string[1:].lower()).replace('std dev',
                                                             'stddev')
