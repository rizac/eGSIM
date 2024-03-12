"""
Residuals module
"""
from __future__ import annotations  # https://peps.python.org/pep-0563/

from itertools import product

from collections.abc import Iterable, Container
from typing import Union
from math import sqrt

import numpy as np
import pandas as pd
from pandas.core.indexes.numeric import IntegerIndex
from scipy.special import erf
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib import imt, const
from openquake.hazardlib.contexts import RuptureContext, ContextMaker

from ..validators import (validate_inputs, harmonize_input_gsims,
                          harmonize_input_imts, validate_imt_sa_periods)
from ..registry import get_ground_motion_values
from ..flatfile.residuals import (get_event_id_column_names,
                                  get_station_id_column_names,
                                  get_flatfile_for_residual_analysis)
from ..flatfile import InvalidColumn, MissingColumn, ColumnsRegistry


def get_residuals(
        gsims: Iterable[Union[str, GMPE]],
        imts: Iterable[Union[str, imt.IMT]],
        flatfile: pd.DataFrame,
        likelihood=False,
        normalise=True) -> pd.DataFrame:
    # FIXME removed unused arguments: # nodal_plane_index=1,
    #   component="Geometric", (the latter I guess is ok, we do not have
    #   components anymore, but the former?)
    """
    Calculate the residuals from a given flatfile gsim(s) and imt(s)

    :param imts: iterable of strings denoting intensity measures (Sa must be
        given with period, e.g. "SA(0.2)")
    :param likelihood: boolean telling if also the likelihood of the residuals
        (according to Equation 9 of Scherbaum et al (2004)) should be computed
    """
    # 1. prepare models and imts:
    gsims = harmonize_input_gsims(gsims)
    imts = harmonize_input_imts(imts)
    validate_inputs(gsims, imts)
    # 2. prepare flatfile:
    flatfile_r = prepare_flatfile(flatfile, gsims, imts)
    # 3. compute residuals:
    residuals = get_residuals_from_validated_inputs(
        gsims, imts, flatfile_r, normalise=normalise)
    labels = [c_labels.total_res, c_labels.inter_ev_res, c_labels.intra_ev_res]
    if likelihood:
        residuals = get_residuals_likelihood(residuals)
        labels = [c_labels.total_res_lh,
                  c_labels.inter_ev_res_lh,
                  c_labels.intra_ev_res_lh]
    # sort columns:
    original_cols = set(residuals.columns)
    sorted_cols = product(imts, labels, gsims)
    residuals = residuals[[c for c in sorted_cols if c in original_cols]]
    # concat:
    col_mapping = {}
    for c in flatfile_r.columns:
        c_type = ColumnsRegistry.get_type(c)
        col_mapping[c] = (c_labels.input_data, c_type.value if c_type else 'misc', c)
    flatfile_r.rename(columns=col_mapping, inplace=True)
    # sort columns:
    flatfile_r.sort_index(axis=1, inplace=True)
    # concat residuals and observations
    residuals = pd.concat([residuals, flatfile_r], axis=1)
    residuals.columns = pd.MultiIndex.from_tuples(residuals.columns)
    return residuals


def prepare_flatfile(flatfile: pd.DataFrame,
                     gsims: dict[str, GMPE],
                     imts: dict[str, imt.IMT]) -> pd.DataFrame:
    """Return a version of flatfile ready for residuals computation with
    the given gsims and imts
    """
    flatfile_r = get_flatfile_for_residual_analysis(flatfile, gsims.values(), imts)
    # copy event columns (raises if columns not found):
    ev_cols = get_event_id_column_names(flatfile)
    flatfile_r[ev_cols] = flatfile[ev_cols]
    # copy station columns (for the moment not used, so skip if no station columns)
    try:
        st_cols = get_station_id_column_names(flatfile)
        flatfile_r[st_cols] = flatfile[st_cols]
    except InvalidColumn:
        pass
    return flatfile_r


def get_residuals_from_validated_inputs(
        gsims: dict[str, GMPE],
        imts: dict[str, imt.IMT],
        flatfile: pd.DataFrame,
        normalise=True) -> pd.DataFrame:
    residuals:pd.DataFrame = None  # noqa
    # compute the observations (compute the log for all once here):
    observed = get_observed_motions(flatfile, imts, True)
    for context in yield_event_contexts(flatfile):
        # Get the expected ground motions by event
        expected = get_expected_motions(gsims, imts, context)
        # Get residuals:
        res = get_residuals_from_expected_and_observed_motions(
            expected,
            observed.loc[expected.index, :],
            normalise=normalise)
        # init `residuals` if needed (only once operation):
        if residuals is None:
            # Note: setting data=np.nan will force columns dtype to float
            residuals = pd.DataFrame(index=flatfile.index, columns=res.columns,
                                     data=np.nan)
        # copy values (note that res.index == context.sids):
        residuals.loc[res.index, res.columns] = res
    return residuals


def get_observed_motions(flatfile: pd.DataFrame, imts: Container[str], log=True):
    """Return the observed motions from the given flatfile. Basically copies
    the flatfile with only the given IMTs, and by default computes the log of all
    values"""
    observed = flatfile[[c for c in flatfile.columns if c in imts]]
    if log:
        return np.log(observed)
    return observed.copy()


def yield_event_contexts(flatfile: pd.DataFrame) -> Iterable[EventContext]:
    """Group the flatfile by events, and yield `EventContext`s objects, one for
    each event"""
    # check event id column or use the event location to group events:
    # group flatfile by events. Use ev. id (_EVENT_COLUMNS[0]) or, when
    # no ID found, event spatio-temporal coordinates (_EVENT_COLUMNS[1:])
    ev_id_cols = get_event_id_column_names(flatfile)
    ev_sub_flatfiles = flatfile.groupby(  # https://stackoverflow.com/a/75478319
        ev_id_cols[0] if len(ev_id_cols) == 1 else ev_id_cols
    )
    for ev_id, dfr in ev_sub_flatfiles:
        if not dfr.empty:  # for safety ...
            yield EventContext(dfr)


class EventContext(RuptureContext):
    """A RuptureContext accepting a flatfile (pandas DataFrame) as input"""

    rupture_params:set[str] = None

    def __init__(self, flatfile: pd.DataFrame):
        super().__init__()
        if not isinstance(flatfile.index, IntegerIndex):
            raise ValueError('flatfile index should be made of integers')
        self._flatfile = flatfile
        if self.__class__.rupture_params is None:
            # get rupture params once for all instances the first time only:
            self.__class__.rupture_params = ColumnsRegistry.get_rupture_params()

    def __eq__(self, other):
        """Overwrite `BaseContext.__eq__` method"""
        assert isinstance(other, EventContext) and \
               self._flatfile.equals(other._flatfile)

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


def get_expected_motions(
        gsims: dict[str, GMPE],
        imts: dict[str, imt.IMT],
        ctx: EventContext) -> pd.DataFrame:
    """
    Calculate the expected ground motions from the context
    """
    expected = []
    # Period range for GSIM
    for gsim_name, gsim in gsims.items():
        # validate SA periods:
        imts_ok = validate_imt_sa_periods(gsim, imts)
        if not imts_ok:
            continue
        imt_names, imt_vals = list(imts_ok.keys()), list(imts_ok.values())
        cmaker = ContextMaker('*', [gsim], {'imtls': {i: [0] for i in imt_names}})
        # FIXME above is imtls relevant, or should we use PGA: [0] as in trellis?
        mean, total, inter, intra = get_ground_motion_values(
            gsim, imt_vals, cmaker.recarray([ctx]))
        # assign to dataframe. Build a numpy matrix + columns and create a new Df:
        columns = list(product(imt_names, [c_labels.mean], [gsim_name]))
        data = [mean]
        stddev_types = gsim.DEFINED_FOR_STANDARD_DEVIATION_TYPES
        if const.StdDev.TOTAL in stddev_types:
            columns.extend((i, c_labels.total_std, gsim_name) for i in imt_names)
            data.append(total)
        if const.StdDev.INTER_EVENT in stddev_types:
            columns.extend((i, c_labels.inter_ev_std, gsim_name) for i in imt_names)
            data.append(inter)
            # dfr[:(imt_names, c_labels.inter_ev_std, gsim_name)] = inter
        if const.StdDev.INTRA_EVENT in stddev_types:
            columns.extend((i, c_labels.intra_ev_std, gsim_name) for i in imt_names)
            data.append(intra)
            # expected.loc[:(imt_names, c_labels.intra_ev_std, gsim_name)] = intra

        dfr = pd.DataFrame(
            columns=pd.MultiIndex.from_tuples(columns),
            data=np.hstack(data), index=ctx.sids)

        expected.append(dfr)

    # return DataFrame by groping next to each other all total, inter intra columns
    # (see `reindex`):
    return pd.concat(expected, axis='columns').reindex(
        [c_labels.mean,
         c_labels.total_std,
         c_labels.inter_ev_std,
         c_labels.intra_ev_std],
        axis='columns',
        level=1)


def get_residuals_from_expected_and_observed_motions(
        expected: pd.DataFrame,
        observed: pd.DataFrame,
        normalise=True):
    """
    Calculate the residual terms, modifies `flatfile` inplace

    :param expected: the DataFrame returned from `get_expected_motions`
    :param observed: the DataFame of the (natural logarithm of) the
        observed ground motion # FIXME check log
    """
    residuals: pd.DataFrame = pd.DataFrame(index=expected.index)
    for (imtx, label, gsim) in expected:
        if label != c_labels.mean:
            continue
        obs = observed.get(imtx)
        if obs is None:
            continue
        mean = expected[(imtx, c_labels.mean, gsim)]
        # compute total residuals:
        total_stddev = expected.get((imtx, c_labels.total_std, gsim))
        if total_stddev is None:
            continue
        residuals[(imtx, c_labels.total_res, gsim)] = \
            (obs - mean) / total_stddev
        # compute inter- and intra-event residuals:
        inter_ev = expected.get((imtx, c_labels.inter_ev_std, gsim))
        intra_ev = expected.get((imtx, c_labels.intra_ev_std, gsim))
        if inter_ev is None or intra_ev is None:
            continue
        inter, intra = _get_random_effects_residuals(obs, mean, inter_ev,
                                                     intra_ev, normalise)
        residuals[(imtx, c_labels.inter_ev_res, gsim)] = inter
        residuals[(imtx, c_labels.intra_ev_res, gsim)] = intra
    return residuals


def _get_random_effects_residuals(obs, mean, inter, intra, normalise=True):
    """
    Calculate the random effects residuals using the inter-event
    residual formula described in Abrahamson & Youngs (1992) Eq. 10
    """
    # FIXME this is the only part where grouping by event is relevant
    nvals = float(len(mean))
    inter_res = ((inter ** 2.) * sum(obs - mean)) /\
        (nvals * (inter ** 2.) + (intra ** 2.))
    intra_res = obs - (mean + inter_res)
    if normalise:
        return inter_res / inter, intra_res / intra
    return inter_res, intra_res


class c_labels: # noqa (keep it simple, no Enum/dataclass needed)
    """computed column labels"""
    mean = "mean"
    total_std = "total_stddev"
    inter_ev_std = "inter_event_stddev"
    intra_ev_std = "intra_event_stddev"
    # expected_motion_column = {total, inter_ev, intra_ev}
    total_res = "total_residual"
    inter_ev_res = "inter_event_residual"
    intra_ev_res = "intra_event_residual"
    total_res_lh = total_res + "_likelihood"
    inter_ev_res_lh = inter_ev_res + "_likelihood"
    intra_ev_res_lh = intra_ev_res + "_likelihood"
    input_data = 'input_data'


def get_residuals_likelihood(residuals: pd.DataFrame) -> pd.DataFrame:
    """
    Return the likelihood values for the residuals column found in `residuals`
    (e.g. Total, inter- intra-event) according to Equation 9 of Scherbaum et al (2004)

    :param residuals: a pandas DataFrame resulting from :ref:`get_residuals`
    """
    likelihoods = pd.DataFrame(index=residuals.index.copy())
    col_list = list(residuals.columns)
    residuals_columns = {
        c_labels.total_res: c_labels.total_res_lh,
        c_labels.inter_ev_res: c_labels.inter_ev_res_lh,
        c_labels.intra_ev_res: c_labels.intra_ev_res_lh
    }
    for col in col_list:
        (imtx, label, gsim) = col
        lh_label = residuals_columns.get(label, None)
        if lh_label is not None:
            likelihoods[(imtx, lh_label, gsim)] = get_likelihood(residuals[col])
    return likelihoods


def get_likelihood(values: Union[np.ndarray, pd.Series]) -> Union[np.ndarray, pd.Series]:
    """
    Returns the likelihood of the given values according to Equation 9 of
    Scherbaum et al (2004)
    """
    zvals = np.fabs(values)
    return 1.0 - erf(zvals / sqrt(2.))
