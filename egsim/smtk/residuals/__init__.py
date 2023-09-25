"""
Residuals module
"""

from collections.abc import Iterable, Collection

from pandas import RangeIndex
from typing import Union

from math import sqrt

import numpy as np
import pandas as pd
from pandas.core.indexes.numeric import IntegerIndex

from scipy.special import erf

from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib import imt, const
from openquake.hazardlib.contexts import RuptureContext

from .. import check_gsim_list, get_gsim_name, get_SA_period  #, convert_accel_units
from ..flatfile.preparation import (get_event_id_column_names,
                                   get_station_id_column_names,
                                   setup_flatfile_for_residuals)
from ..flatfile.columns import InvalidColumn, MissingColumn, get_rupture_params


def get_sa_limits(gsim: GMPE) -> Union[tuple[float, float], None]:
    pers = None
    for c in dir(gsim):
        if 'COEFFS' in c:
            pers = [sa.period for sa in getattr(gsim, c).sa_coeffs]
            break
    return (min(pers), max(pers)) if pers is not None else None


def check_sa_limits(gsim: GMPE, im: str):  # FIXME remove? is it used?
    """Return False if the period defined for the SA given in `im` does not match the
    SA limits defined for the given model (`gsim`). Return True in any other case
    (period within limits, gsim not defining any SA limit, `im` not representing SA)
    """
    period = get_SA_period(im)
    if period is None:
        return True
    limits = get_sa_limits(gsim)
    if limits is None:
        return True
    return limits[0] < period < limits[1]


def get_residuals(gsims: Iterable[str], imts: Collection[str],
                  flatfile: pd.DataFrame, nodal_plane_index=1,
                  component="Geometric", likelihood=False,
                  normalise=True) -> pd.DataFrame:  # FIXME remove unused arguments?
    """
    Calculate the residuals from a given flatfile gsim(s) and imt(s). This function
    modifies the passed flatfile inplace (e.g. by adding all residuals-related computed
    columns, see :ref:`c_labels` for details)

    :poram: imts iterable of strings denoting intensity measures (Sa must be
        given with period, e.g. "SA(0.2)")
    :param likelihood: boolean telling if also the likelihood of the residuals
        (according to Equation 9 of Scherbaum et al (2004)) should be computed
    """
    gsims = check_gsim_list(gsims)
    flatfile2 = setup_flatfile_for_residuals(flatfile, gsims.values(), imts)
    # copy event columns (raises if columns not found):
    ev_cols = get_event_id_column_names(flatfile)
    flatfile2[ev_cols] = flatfile[ev_cols]
    # copy station columns (for the moment not used, so skip if no station columns)
    try:
        st_cols = get_station_id_column_names(flatfile)
        flatfile2[st_cols] = flatfile[st_cols]
    except InvalidColumn:
        pass
    # compute residuals:
    residuals = calculate_flatfile_residuals(gsims, imts, flatfile2,
                                             normalise=normalise)
    # concatenate expected in flatfile (add new columns):
    flatfile[list(residuals.columns)] = residuals
    if likelihood:
        get_residuals_likelihood(gsims, imts, flatfile)
    return flatfile


def calculate_flatfile_residuals(gsims: dict[str, GMPE], imts: Iterable[str],
                                 flatfile: pd.DataFrame, normalise=True) -> pd.DataFrame:
    residuals:pd.DataFrame = pd.DataFrame(index=flatfile.index)
    imts = list(imts)
    # computget the observations (compute the log for all once here):
    observations = pd.DataFrame(index=flatfile.index,
                                columns=imts,
                                data=np.log(flatfile[imts]))
    for context in yield_event_contexts(flatfile):
        # Get the expected ground motions by event
        expected = calculate_expected_motions(gsims.values(), imts, context)
        # Get residuals:
        res = calculate_residuals(gsims, imts, observations.loc[expected.index, :],
                                  expected, normalise=normalise)
        if residuals.empty:
            for col in list(expected.columns) + list(res.columns):
                residuals[col] = np.nan
        # copy values:
        residuals.loc[expected.index, expected.columns] = expected
        residuals.loc[res.index, res.columns] = res

    return residuals


class EventContext(RuptureContext):
    """A RuptureContext accepting a flatfile (pandas DataFrame) as input"""

    rupture_params:set[str] = None

    def __init__(self, flatfile: pd.DataFrame):
        super().__init__()
        if not isinstance(flatfile.index, IntegerIndex):
            raise ValueError('flatfile index should be made of unique integers')
        self._flatfile = flatfile
        if self.__class__.rupture_params is None:
            # get rupture params once for all instances the first time only:
            self.__class__.rupture_params = get_rupture_params()

    def __eq__(self, other):  # FIXME: legacy code, is it still used?
        assert isinstance(other, EventContext) and \
               self._flatfile is other._flatfile

    @property
    def sids(self) -> IntegerIndex:
        """Return the ids (iterable of integers) of the records (or sites) used to build
        this context. The returned pandas `IntegerIndex` must have unique values so that
        the records (flatfile rows) can always be retrieved from the source flatfile via
        `flatfile.loc[self.sids, :]`
        """
        # note that this attribute is used also when calculating `len(self)` so do not
        # delete or rename. See superclass for details
        return self._flatfile.index


    def __getattr__(self, column_name):
        """Return a non-found Context attribute by searching in the underlying
        flatfile column. Raises AttributeError (as usual) if `item` is not found
        """
        try:
            values = self._flatfile[column_name].values
        except KeyError:
            raise MissingColumn(column_name)
        if column_name in self.rupture_params:
            values = values[0]
        return values


def yield_event_contexts(flatfile: pd.DataFrame) -> Iterable[EventContext]:
    """Group the flatfile by events, and yield `EventContext`s objects, one for
    each event"""
    # assure each row has a unique int id from 0 until row_count-1:
    if not isinstance(flatfile.index, RangeIndex):
        flatfile.reset_index(drop=True, inplace=True)

    # check event id column or use the event location to group events:
    # group flatfile by events. Use ev. id (_EVENT_COLUMNS[0]) or, when
    # no ID found, event spatio-temporal coordinates (_EVENT_COLUMNS[1:])
    ev_sub_flatfiles = flatfile.groupby(get_event_id_column_names(flatfile))

    for ev_id, dfr in ev_sub_flatfiles:
        if not dfr.empty:  # for safety ...
            yield EventContext(dfr)


def calculate_expected_motions(gsims: Iterable[GMPE], imts: Iterable[str],
                               ctx: EventContext) -> pd.DataFrame:
    """
    Calculate the expected ground motions from the context
    """
    expected:pd.DataFrame = pd.DataFrame(index=ctx.sids)
    label_of = {
        const.StdDev.TOTAL: c_labels.total,
        const.StdDev.INTER_EVENT: c_labels.inter_ev,
        const.StdDev.INTRA_EVENT: c_labels.intra_ev
    }
    imts_dict = {i: imt.from_string(i) for i in imts}
    # Period range for GSIM
    for gsim in gsims:
        types = gsim.DEFINED_FOR_STANDARD_DEVIATION_TYPES
        for imt_name, imtx in imts_dict.items():
            period = get_SA_period(imtx)
            if period is not None:
                sa_period_limits = get_sa_limits(gsim)
                if sa_period_limits is not None and not \
                        (sa_period_limits[0] < period < sa_period_limits[1]):
                    continue
            mean, stddev = gsim.get_mean_and_stddevs(ctx, ctx, ctx, imtx, types)
            expected[column_label(gsim, imt_name, c_labels.mean)] = mean
            for std_type, values in zip(types, stddev):
                expected[column_label(gsim, imt_name, label_of[std_type])] = values
    return expected


def calculate_residuals(gsims: Iterable[str], imts: Iterable[str],
                        observations: pd.DataFrame, expected_motions: pd.DataFrame,
                        normalise=True):
    """
    Calculate the residual terms, modifies `flatfile` inplace

    :param observations: the flatfile of the (natural logarithm of) the
        observed ground motions
    """
    residuals: pd.DataFrame = pd.DataFrame(index=observations.index)
    for gsim in gsims:
        for imtx in imts:
            obs = observations.get(imtx)
            if obs is None:
                continue
            mean = expected_motions.get(column_label(gsim, imtx, c_labels.mean))
            total_stddev = expected_motions.get(column_label(gsim, imtx, c_labels.total))
            if mean is None or total_stddev is None:
                continue
            residuals[column_label(gsim, imtx, c_labels.total_res)] = \
                (obs - mean) / total_stddev
            inter_ev = expected_motions.get(column_label(gsim, imtx, c_labels.inter_ev))
            intra_ev = expected_motions.get(column_label(gsim, imtx, c_labels.intra_ev))
            if inter_ev is None or intra_ev is None:
                continue
            inter, intra = _get_random_effects_residuals(obs, mean, inter_ev,
                                                         intra_ev, normalise)
            residuals[column_label(gsim, imtx, c_labels.inter_ev_res)] = inter
            residuals[column_label(gsim, imtx, c_labels.intra_ev_res)] = intra
    return residuals


def _get_random_effects_residuals(obs, mean, inter, intra, normalise=True):
    """
    Calculate the random effects residuals using the inter-event
    residual formula described in Abrahamson & Youngs (1992) Eq. 10
    """
    nvals = float(len(mean))
    inter_res = ((inter ** 2.) * sum(obs - mean)) /\
        (nvals * (inter ** 2.) + (intra ** 2.))
    intra_res = obs - (mean + inter_res)
    if normalise:
        return inter_res / inter, intra_res / intra
    return inter_res, intra_res


class c_labels:
    """Flatfile computed column labels (e.g. expected motion, residual)"""
    mean = "Mean"
    total = const.StdDev.TOTAL.capitalize()
    inter_ev = const.StdDev.INTER_EVENT.replace(" ", "-").capitalize()
    intra_ev = const.StdDev.INTRA_EVENT.replace(" ", "-").capitalize()
    expected_motion_column = {total, inter_ev, intra_ev}
    res = "residual"
    total_res = total + f" {res}"
    inter_ev_res = inter_ev + f" {res}"
    intra_ev_res = intra_ev + f" {res}"
    residuals_columns = {total_res, inter_ev_res, intra_ev_res}
    lh = "LH"  # likelihood
    total_lh = total + f" {lh}"
    inter_ev_lh = inter_ev + f" {lh}"
    intra_ev_lh = intra_ev + f" {lh}"
    lh_columns = {total_res, inter_ev_res, intra_ev_res}


def column_label(gsim: Union[str, GMPE], imtx: str, c_label: str):
    """
    Return the column label for the given Gsim, imt and type (e.g. "Mean",
    "Total-residuals", see :ref:`labels`). If residuals is True, the column is
    supposed to denote a residual computed with the observed IMT stored in another column
    """
    if isinstance(gsim, GMPE):
        gsim = get_gsim_name(gsim)
    return f"{gsim} {imtx} {c_label}"


def get_computed_columns(gsims: Union[None, Iterable[str]],
                         imts: Union[None, Iterable[str]],
                         flatfile: pd.DataFrame):
    """Yield tuples from columns of `flatfile` denoting computed columns
    (expected motions, residuals) for the given `gsims` and `imts`. A computed column
    name has the form: `model + " "+ imt + " " + label` (See :ref:`column_label`).
    Each yielded tuple is:
        `column name, gsim name, imt name, residual label`
    """
    if gsims is not None:
        gsims = set(gsims)
    if imts is not None:
        imts = set(imts)
    for col in flatfile.columns:
        chunks = col.split(" ", 2)
        if len(chunks) == 3 and \
                (gsims is None or chunks[0] in gsims) and \
                (imts is None or chunks[1] in imts):
            yield col, chunks[0], chunks[1], chunks[2]


def get_residuals_likelihood(gsims: Iterable[str], imts: Iterable[str],
                             flatfile: pd.DataFrame):
    """
    Return the likelihood values for the residuals column found in `flatfile`
    (e.g. Total, inter- intra-event) according to Equation 9 of Scherbaum et al (2004)

    :param flatfile: a pandas DataFrame resulting from :ref:`get_residuals`.
        NOTE: the flatfile might be modified inplace (new likelihood columns added)
    """
    ev_id_cols = None
    for col, gsim, imtx, label in get_computed_columns(gsims, imts, flatfile):
        if label not in c_labels.residuals_columns:
            continue
        # build label:
        lh_label = c_labels.total_lh
        if label == c_labels.inter_ev_res:
            lh_label = c_labels.inter_ev_lh
        elif label == c_labels.intra_ev_res:
            lh_label = c_labels.intra_ev_lh
        dest_label = column_label(gsim, imtx, lh_label)
        # compute values
        if c_labels.inter_ev in label:  # inter event, group by events
            flatfile[dest_label] = np.nan
            if ev_id_cols is None:  # lazy load
                ev_id_cols = get_event_id_column_names(flatfile)
            for ev_id, sub_flatfile in flatfile.groupby(ev_id_cols):
                lh_values = get_likelihood(sub_flatfile[col])
                flatfile.loc[sub_flatfile.index, dest_label] = lh_values
        else:
            flatfile[dest_label] = get_likelihood(flatfile[col])


def get_likelihood(values: Union[np.ndarray, pd.Series]) -> Union[np.ndarray, pd.Series]:
    """
    Returns the likelihood of the given values according to Equation 9 of
    Scherbaum et al (2004)
    """
    zvals = np.fabs(values)
    return 1.0 - erf(zvals / sqrt(2.))
