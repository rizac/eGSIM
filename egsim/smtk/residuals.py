"""
Residuals module
"""
from __future__ import annotations  # https://peps.python.org/pep-0563/

from itertools import product

from collections.abc import Iterable, Container, Collection
from pandas import Index
from typing import Union
from math import sqrt

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.special import erf
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib import imt, const
from openquake.hazardlib.contexts import RuptureContext, ContextMaker
from openquake.hazardlib.scalerel import PeerMSR

from .flatfile import (FlatfileError, MissingColumnError, FlatfileMetadata,
                       ColumnDataError, IncompatibleColumnError, EVENT_ID_COLUMN_NAME)
from .validation import (validate_inputs, harmonize_input_gsims,
                         harmonize_input_imts, validate_imt_sa_limits, ModelError)
from .registry import (get_ground_motion_values, Clabel, sa_period,
                       ground_motion_properties_required_by)
from .converters import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14


def get_residuals(
        gsims: Iterable[Union[str, GMPE]],
        imts: Iterable[Union[str, imt.IMT]],
        flatfile: pd.DataFrame,
        likelihood=False,
        normalise=True,
        mean=False,
        header_sep: Union[str, None] = Clabel.sep
) -> pd.DataFrame:
    """
    Calculate the residuals from a given flatfile gsim(s) and imt(s)

    :param gsims: iterable of strings or ``GMPE`` instances
        denoting Ground shaking intensity models
    :param imts: iterable of strings or ``imt.IMT`` instances
        denoting intensity measures (Sa must be given with period, e.g. "SA(0.2)")
    :param flatfile: pandas DataFrame with the values
        of the ground motion properties required by the given models (param.
        `gsims`) and the observed intensity measures arranged in columns
    :param likelihood: boolean telling if also the likelihood of the residuals
        (according to Equation 9 of Scherbaum et al. (2004)) should be computed
        and returned
    :param mean: boolean telling if also the models mean (used to compute residuals)
        should be returned
    :param normalise: boolean (default True) normalize the random effects residuals
        (calculated using the inter-event residual formula described in
         Abrahamson & Youngs (1992) Eq. 10)
    :param header_sep: str or None (default: " "): the separator used to concatenate
        each column header into one string (e.g. "PGA median BindiEtAl2014Rjb"). Set
        to "" or None to return a multi-level column header composed of the first 3
        dataframe rows (e.g. ("PGA", "median", "BindiEtAl2014Rjb"). See
        "MultiIndex / advanced indexing" in the pandas doc for details)

    :return: pandas DataFrame
    """
    # 1. prepare models and imts:
    gsims = harmonize_input_gsims(gsims)
    imts = harmonize_input_imts(imts)
    validate_inputs(gsims, imts)
    # 2. prepare flatfile:
    flatfile_r = prepare_flatfile(flatfile, gsims, imts)
    # 3. compute residuals:
    residuals = get_residuals_from_validated_inputs(
        gsims, imts, flatfile_r, normalise=normalise, return_mean=mean)
    labels = [Clabel.total_res, Clabel.inter_ev_res, Clabel.intra_ev_res]
    if mean:
        labels += [Clabel.mean]
    if likelihood:
        residuals = get_residuals_likelihood(residuals)
        labels += [Clabel.total_lh, Clabel.inter_ev_lh, Clabel.intra_ev_lh]
    # sort columns (kind of reindex, more verbose for safety):
    original_cols = set(residuals.columns)
    sorted_cols = product(imts, labels, gsims)
    residuals = residuals[[c for c in sorted_cols if c in original_cols]]
    # concat:
    col_mapping = {}
    for c in flatfile_r.columns:
        c_type = FlatfileMetadata.get_type(c)
        col_mapping[c] = (
            Clabel.input,
            c_type.value if c_type else Clabel.uncategorized_input,
            c)
    flatfile_r.rename(columns=col_mapping, inplace=True)
    # sort columns:
    flatfile_r.sort_index(axis=1, inplace=True)
    # concat residuals and observations
    residuals = pd.concat([residuals, flatfile_r], axis=1)
    if header_sep:
        residuals.columns = [header_sep.join(c) for c in residuals.columns]
    else:
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
    # copy station columns (for the moment not used, so do not raise if no columns)
    try:
        st_cols = get_station_id_column_names(flatfile)
        flatfile_r[st_cols] = flatfile[st_cols]
    except FlatfileError:
        pass
    if flatfile_r.empty:
        raise FlatfileError('empty flatfile')
    return flatfile_r


def get_residuals_from_validated_inputs(
        gsims: dict[str, GMPE],
        imts: dict[str, imt.IMT],
        flatfile: pd.DataFrame,
        normalise=True,
        return_mean=False) -> pd.DataFrame:
    residuals = []
    # compute the observations (compute the log for all once here):
    observed = get_observed_motions(flatfile, imts, True)
    for context in yield_event_contexts(flatfile):
        # Get the expected ground motions by event
        expected = get_expected_motions(gsims, imts, context)
        # Get residuals:
        res = get_residuals_from_expected_and_observed_motions(
            expected,
            observed.loc[expected.index, :],
            normalise=normalise,
            return_mean=return_mean)
        residuals.append(res)
    # concat preserving index (last arg. is False by default but set anyway for safety):
    return pd.concat(residuals, axis='index', ignore_index=False)


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
        ev_id_cols[0] if len(ev_id_cols) == 1 else ev_id_cols,
        observed=False
    )
    for ev_id, dfr in ev_sub_flatfiles:
        if not dfr.empty:  # for safety ...
            yield EventContext(dfr)


class EventContext(RuptureContext):
    """A RuptureContext accepting a flatfile (pandas DataFrame) as input"""

    rupture_params: set[str] = None

    def __init__(self, flatfile: pd.DataFrame):
        super().__init__()
        if not pd.api.types.is_integer_dtype(flatfile.index.dtype):
            raise ValueError('flatfile index must be made of integers')
        self._flatfile = flatfile
        if self.__class__.rupture_params is None:
            # get rupture params once for all instances the first time only:
            self.__class__.rupture_params = FlatfileMetadata.get_rupture_params()

    def __eq__(self, other):
        """Overwrite `BaseContext.__eq__` method"""
        assert isinstance(other, EventContext) and \
               self._flatfile.equals(other._flatfile)

    @property
    def sids(self) -> Index:
        """Return the ids (iterable of integers) of the records (or sites) used to build
        this context. The returned pandas `Index` must have unique values so that
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
            raise MissingColumnError(column_name)
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
    data = []
    columns = []
    # Period range for GSIM
    for gsim_name, gsim in gsims.items():
        try:
            # validate SA periods:
            imts_ok = validate_imt_sa_limits(gsim, imts)
            if not imts_ok:
                continue
            imt_names, imt_vals = list(imts_ok.keys()), list(imts_ok.values())
            cmaker = ContextMaker('*', [gsim], {'imtls': {i: [0] for i in imt_names}})
            # TODO above is imtls relevant, or should we use PGA: [0] as in trellis?
            #  maybe harmonize and document why we do the line above?
            mean, total, inter, intra = get_ground_motion_values(
                gsim, imt_vals, cmaker.recarray([ctx]))
            # assign data to our tmp lists:
            columns.extend(product(imt_names, [Clabel.mean], [gsim_name]))
            data.append(mean)
            stddev_types = gsim.DEFINED_FOR_STANDARD_DEVIATION_TYPES
            if const.StdDev.TOTAL in stddev_types:
                columns.extend((i, Clabel.total_std, gsim_name) for i in imt_names)
                data.append(total)
            if const.StdDev.INTER_EVENT in stddev_types:
                columns.extend((i, Clabel.inter_ev_std, gsim_name) for i in imt_names)
                data.append(inter)
            if const.StdDev.INTRA_EVENT in stddev_types:
                columns.extend((i, Clabel.intra_ev_std, gsim_name) for i in imt_names)
                data.append(intra)
        except Exception as exc:
            raise ModelError(f'{gsim_name}: ({exc.__class__.__name__}) {str(exc)}')

    return pd.DataFrame(columns=pd.MultiIndex.from_tuples(columns),
                        data=np.hstack(data), index=ctx.sids)


def get_residuals_from_expected_and_observed_motions(
        expected: pd.DataFrame,
        observed: pd.DataFrame,
        normalise=True,
        return_mean=False) -> pd.DataFrame:
    """
    Calculate the residual terms, returning a new DataFrame

    :param expected: the DataFrame returned from `get_expected_motions`
    :param observed: the DataFame of the (natural logarithm of) the
        observed ground motion
    :param normalise: boolean (default True) normalize the random effects residuals
        (calculated using the inter-event residual formula described in
         Abrahamson & Youngs (1992) Eq. 10)
    :param return_mean: boolean (default False) include the predicted values
        (models computed mean) in the dataframe columns
    """
    residuals: pd.DataFrame = pd.DataFrame(index=expected.index)
    mean_cols = expected.columns[expected.columns.get_level_values(1) == Clabel.mean]
    for (imtx, label, gsim) in mean_cols:
        obs = observed.get(imtx)
        if obs is None:
            continue
        mean = expected.get((imtx, Clabel.mean, gsim))
        if mean is None:
            continue
        if return_mean:
            residuals[(imtx, Clabel.mean, gsim)] = mean
        # compute total residuals:
        total_stddev = expected.get((imtx, Clabel.total_std, gsim))
        if total_stddev is None:
            continue
        residuals[(imtx, Clabel.total_res, gsim)] = \
            (obs - mean) / total_stddev
        # compute inter- and intra-event residuals:
        inter_ev = expected.get((imtx, Clabel.inter_ev_std, gsim))
        intra_ev = expected.get((imtx, Clabel.intra_ev_std, gsim))
        if inter_ev is None or intra_ev is None:
            continue
        inter, intra = _get_random_effects_residuals(obs, mean, inter_ev,
                                                     intra_ev, normalise)
        residuals[(imtx, Clabel.inter_ev_res, gsim)] = inter
        residuals[(imtx, Clabel.intra_ev_res, gsim)] = intra
    return residuals


def _get_random_effects_residuals(obs, mean, inter, intra, normalise=True):
    """
    Calculate the random effects residuals using the inter-event
    residual formula described in Abrahamson & Youngs (1992) Eq. 10
    """
    # TODO this is the only part where grouping by event is relevant: maybe
    #  move groupby here?
    nvals = float(len(mean))
    inter_res = ((inter ** 2.) * sum(obs - mean)) /\
        (nvals * (inter ** 2.) + (intra ** 2.))
    intra_res = obs - (mean + inter_res)
    if normalise:
        return inter_res / inter, intra_res / intra
    return inter_res, intra_res


def get_residuals_likelihood(residuals: pd.DataFrame, inplace=True) -> pd.DataFrame:
    """
    Return the likelihood values for the residuals column found in `residuals`
    (e.g. Total, inter- intra-event) according to Equation 9 of Scherbaum et al. (2004)

    :param residuals: a pandas DataFrame resulting from :ref:`get_residuals`
    :param inplace: if True (the default) append likelihoods to the given residuals
        and return a copy of it. If False, return a new dataframe with the
        likelihoods only
    """
    if inplace:
        likelihoods = residuals.copy()
    else:
        likelihoods = pd.DataFrame(index=residuals.index.copy())
    col_list = list(residuals.columns)
    residuals_columns = {
        Clabel.total_res: Clabel.total_lh,
        Clabel.inter_ev_res: Clabel.inter_ev_lh,
        Clabel.intra_ev_res: Clabel.intra_ev_lh
    }
    for col in col_list:
        (imtx, label, gsim) = col
        lh_label = residuals_columns.get(label, None)
        if lh_label is not None:
            likelihoods[(imtx, lh_label, gsim)] = get_likelihood(residuals[col])
    return likelihoods


def get_likelihood(values: Union[np.ndarray, pd.Series]) -> Union[np.ndarray, pd.Series]:
    """
    Return the likelihood of the given values according to Equation 9 of
    Scherbaum et al. (2004)
    """
    zvals = np.fabs(values)
    return 1.0 - erf(zvals / sqrt(2.))


# utilities:

def get_column_name(flatfile: pd.DataFrame, column: str) -> Union[str, None]:
    """Return the flatfile column matching `column`. This could be `column`
     itself, or any of its aliases (see `columns` module and YAML file)
     Returns None if no column is found, raise `IncompatibleColumnError` if more than
     a matching column is found"""
    ff_cols = set(flatfile.columns)
    cols = set(FlatfileMetadata.get_aliases(column)) & ff_cols
    if len(cols) > 1:
        raise IncompatibleColumnError(cols)
    elif len(cols) == 0:
        return None
    else:
        return next(iter(cols))


def get_event_id_column_names(flatfile: pd.DataFrame) -> list[str]:
    col_name = get_column_name(flatfile, EVENT_ID_COLUMN_NAME)
    if col_name is not None:
        return [col_name]
    cols = ['event_latitude', 'event_longitude', 'event_depth', 'event_time']
    col_names = [get_column_name(flatfile, c) for c in cols]
    if any(c is None for c in col_names):
        raise MissingColumnError(EVENT_ID_COLUMN_NAME)
    return col_names


def get_station_id_column_names(flatfile: pd.DataFrame) -> list[str]:
    default_col_name = 'station_id'
    col_name = get_column_name(flatfile, default_col_name)
    if col_name is not None:
        return [col_name]
    cols = ['station_latitude', 'station_longitude']
    col_names = [get_column_name(flatfile, c) for c in cols]
    if any(c is None for c in col_names):
        raise MissingColumnError(default_col_name)
    return col_names


def get_flatfile_for_residual_analysis(
        flatfile: pd.DataFrame,
        gsims: Collection[GMPE],
        imts: Collection[str]) -> pd.DataFrame:
    """Return a new dataframe with all columns required to compute residuals
    from the given models (`gsim`) and intensity measures (`imts`) given with
    periods, when needed (e.g. "SA(0.2)")
    """
    # Note: dat validation (e.g. check that all models are defined for the given
    # imts) is assumed to be already performed

    # concat all new dataframes in this list, then return a new one from it:
    new_dataframes = []
    # prepare the flatfile for the required imts:
    imts_flatfile = get_required_imts(flatfile, imts)
    if not imts_flatfile.empty:
        new_dataframes.append(imts_flatfile)
    # prepare the flatfile for the required ground motion properties:
    props_flatfile = get_required_ground_motion_properties(flatfile, gsims)
    if not props_flatfile.empty:
        new_dataframes.append(props_flatfile)

    # return the new dataframe or an empty one:
    if not new_dataframes:
        return pd.DataFrame(columns=flatfile.columns)  # empty dataframe
    return pd.concat(new_dataframes, axis=1)


def get_required_imts(flatfile: pd.DataFrame, imts: Collection[str]) -> pd.DataFrame:
    """Return a new dataframe with all columns required to compute residuals
    for the given intensity measures (`imts`) given with
    periods, when needed (e.g. "SA(0.2)")
    """
    # concat all new dataframes in this list, then return a new one from it:
    new_dataframes = []
    imts = set(imts)
    non_sa_imts = {_ for _ in imts if sa_period(_) is None}
    sa_imts = imts - non_sa_imts
    # get supported imts but does not allow 'SA' alone to be valid:
    if non_sa_imts:
        # some IMT(s) (non SA) not found in the flatfile columns:
        if non_sa_imts - set(flatfile.columns):
            raise MissingColumnError(*list(non_sa_imts - set(flatfile.columns)))
        # add non SA imts:
        new_dataframes.append(flatfile[sorted(non_sa_imts)])
    # prepare the flatfile for SA (create new columns by interpolation if necessary):
    if sa_imts:
        sa_dataframe = get_required_sa(flatfile, sa_imts)
        if not sa_dataframe.empty:
            new_dataframes.append(sa_dataframe)
    if not new_dataframes:
        return pd.DataFrame(columns=flatfile.columns)  # empty dataframe
    return pd.concat(new_dataframes, axis=1)


def get_required_sa(flatfile: pd.DataFrame, sa_imts: Iterable[str]) -> pd.DataFrame:
    """Return a new Dataframe with the SA columns defined in `sa_imts`
    The returned DataFrame will have all strings supplied in `sa_imts` as columns,
    with relative values copied (or inferred via interpolation) from the given flatfile

    :param flatfile: the flatfile
    :param sa_imts: Iterable of strings denoting SA (e.g. "SA(0.2)")
    Return the newly created Sa columns, as tuple of strings
    """
    new_flatfile = pd.DataFrame(index=flatfile.index)

    source_periods: dict[float, str] = {}  # period [float] -> IMT name (str)
    for c in flatfile.columns:
        p = sa_period(c)
        if p is not None:
            source_periods[p] = c

    target_periods: dict[float, str] = {}  # period [float] -> IMT name (str)
    invalid_sa = []
    for i in sa_imts:
        p = sa_period(i)
        if p is None:
            invalid_sa.append(i)
            continue
        if p not in source_periods:
            target_periods[p] = i
        else:
            new_flatfile[i] = flatfile[source_periods[p]]
    if invalid_sa:
        raise ColumnDataError(*invalid_sa)

    if target_periods:  # need to find some SA by interpolation (row-wise)

        # check we can interpolate:
        if set(target_periods) - set(source_periods):  # interpolation needed
            if len(source_periods) < 2:
                raise MissingColumnError(f'SA(period_in_s) '
                                         f'(columns found: {len(source_periods)}, '
                                         f'at least two are required)')

        # sort source periods:
        source_periods = {p: source_periods[p] for p in sorted(source_periods.keys())}
        # Take the log10 of all SA in the source flatfile:
        source_spectrum = np.log10(flatfile[list(source_periods.values())])
        # build the interpolation function:
        interp = interp1d(list(source_periods), source_spectrum, axis=1)
        # sort target periods
        target_periods = {p: target_periods[p] for p in sorted(target_periods.keys())}
        # interpolate using the created function `interp`:
        values = 10 ** interp(list(target_periods))
        # values is a matrix where each column represents the values of the
        # target period. Add it to the dataframe:
        new_flatfile[list(target_periods.values())] = values

    # return dataframe with sorted periods (for safety):
    return new_flatfile[sorted(new_flatfile.columns, key=sa_period)]


def get_required_ground_motion_properties(
        flatfile: pd.DataFrame,
        gsims: Iterable[GMPE]) -> pd.DataFrame:
    """Return a new dataframe with all columns required to compute residuals
    from the given models (`gsim`), i.e. all columns denoting ground motion
    properties required by the passed models
    """
    required_props_flatfile = pd.DataFrame(index=flatfile.index)
    required_props = ground_motion_properties_required_by(*gsims)

    # REQUIRES_DISTANCES is empty when gsims = [FromFile]: in this case, add a
    # default 'rrup' (see openquake,hazardlib.contexts.ContextMaker.__init__):
    if 'rrup' not in required_props and \
            any(len(g.REQUIRES_DISTANCES) == 0 for g in gsims):
        required_props |= {'rrup'}

    missing_flatfile_columns = set()
    for p in required_props:
        try:
            # https://stackoverflow.com/a/29706954
            # `required_props_flatfile` is a dataframe with a specific index (see above).
            # Adding a Series to it might result in NaNs where the Series index
            # does not match the DataFrame index. As such, assign the series.values to
            # the DataFrame (see test_residuals.test_assign_series to assure this is ok)
            required_props_flatfile[p] = \
                get_ground_motion_property_values(flatfile, p).values
        except MissingColumnError:
            missing_flatfile_columns.add(p)
    if missing_flatfile_columns:
        raise MissingColumnError(*list(missing_flatfile_columns))

    return required_props_flatfile


DEFAULT_MSR = PeerMSR()


def get_ground_motion_property_values(
        flatfile: pd.DataFrame,
        gm_property: str) -> pd.Series:
    """Get the values (pandas Series) relative to the ground motion property
    (rupture or sites parameter, distance measure) extracted from the given
    flatfile.
    The returned value might be a column of the flatfile or a new pandas Series
    depending on missing-data replacement rules hardcoded in this function and
    documented in the associated YAML file.
    If the column cannot be retrieved or created, this function
    raises :ref:`MissingColumn` error notifying the required missing column
    """
    column_name = get_column_name(flatfile, gm_property)
    series = None if column_name is None else flatfile[column_name]
    if gm_property == 'ztor':
        series = fill_na(flatfile, 'hypo_depth', series)
    elif gm_property == 'width':  # rupture_width
        # Use the PeerMSR to define the area and assuming an aspect ratio
        # of 1 get the width
        mag = get_column_name(flatfile, 'mag')
        if mag is not None:
            mag = flatfile[mag]  # convert string to column (pd.Series)
            if series is None:
                series = pd.Series(np.sqrt(DEFAULT_MSR.get_median_area(mag, 0)))
            else:
                na = pd.isna(series)
                if na.any():  # noqa (silent incorrect lint errors)
                    series = series.copy()
                    series[na] = np.sqrt(DEFAULT_MSR.get_median_area(mag[na], 0))
    elif gm_property in ['rjb', 'ry0']:
        series = fill_na(flatfile, 'repi', series)
    elif gm_property == 'rx':  # same as above, but -repi
        series = fill_na(flatfile, 'repi', series)
        if series is not None:
            series = -series
    elif gm_property == 'rrup':
        series = fill_na(flatfile, 'rhypo', series)
    elif gm_property == 'z1pt0':
        vs30 = get_column_name(flatfile, 'vs30')
        if vs30 is not None:
            vs30 = flatfile[vs30]  # convert string to column (pd.Series)
            if series is None:
                series = pd.Series(vs30_to_z1pt0_cy14(vs30))
            else:
                na = pd.isna(series)
                if na.any():  # noqa (silent incorrect lint errors)
                    series = series.copy()
                    series[na] = vs30_to_z1pt0_cy14(vs30[na])
    elif gm_property == 'z2pt5':
        vs30 = get_column_name(flatfile, 'vs30')
        if vs30 is not None:
            vs30 = flatfile[vs30]  # convert string to column (pd.Series)
            if series is None:
                series = pd.Series(vs30_to_z2pt5_cb14(vs30))
            else:
                na = pd.isna(series)
                if na.any():  # noqa (silent incorrect lint errors)
                    series = series.copy()
                    series[na] = vs30_to_z2pt5_cb14(vs30[na])
    elif gm_property == 'backarc' and series is None:
        series = pd.Series(np.full(len(flatfile), fill_value=False))
    elif gm_property == 'rvolc' and series is None:
        series = pd.Series(np.full(len(flatfile), fill_value=0, dtype=int))
    if series is None:
        raise MissingColumnError(gm_property)
    return series


def fill_na(
        flatfile: pd.DataFrame,
        src_col: str,
        dest: Union[None, np.ndarray, pd.Series]) -> Union[None, np.ndarray, pd.Series]:
    """Fill NAs (NaNs/Nulls) of `dest` with relative values from `src`.
    :return: a numpy array or pandas Series (the same type of `dest`, whenever
        possible) which might be a new object or `dest`, unchanged
    """
    col_name = get_column_name(flatfile, src_col)
    if col_name is None:
        return dest
    src = flatfile[col_name]
    if dest is None:
        return src.copy()
    na = pd.isna(dest)
    if na.any():
        dest = dest.copy()
        dest[na] = src[na]
    return dest
