"""flatfile functions for residuals analysis"""
from collections.abc import Collection, Iterable
from typing import Union

import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.scalerel import PeerMSR

from .columns import (get_all_names_of, get_intensity_measures, MissingColumn,
                      InvalidDataInColumn, InvalidColumnName, ConflictingColumns)
from ..validators import sa_period
from ..registry import (distances_required_by,
                        ground_motion_properties_required_by)
from ..converters import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14


def get_column_name(flatfile:pd.DataFrame, column:str) -> Union[str, None]:
    """Return the flatfile column matching `column`. This could be `column`
     itself, or any of its aliases (see `columns` module and YAML file)
     Returns None if no column is found, raise `ConflictingColumns` if more than
     a matching column is found"""
    ff_cols = set(flatfile.columns)
    cols = set(get_all_names_of(column)) & ff_cols
    if len(cols) > 1:
        raise ConflictingColumns(*cols)
    elif len(cols) == 0:
        return None
    else:
        return next(iter(cols))


def get_event_id_column_names(flatfile: pd.DataFrame) -> list[str, ...]:
    default_col_name = 'event_id'
    col_name = get_column_name(flatfile, default_col_name)
    if col_name is not None:
        return [col_name]
    cols = ['event_latitude', 'event_longitude', 'event_depth', 'event_time']
    col_names = [get_column_name(flatfile, c) for c in cols]
    if any(c is None for c in col_names):
        raise MissingColumn(default_col_name)
    return col_names


def get_station_id_column_names(flatfile: pd.DataFrame) -> list[str, ...]:
    default_col_name = 'station_id'
    col_name = get_column_name(flatfile, default_col_name)
    if col_name is not None:
        return [col_name]
    cols = ['station_latitude', 'station_longitude']
    col_names = [get_column_name(flatfile, c) for c in cols]
    if any(c is None for c in col_names):
        raise MissingColumn(default_col_name)
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

    # concat all new dataframes in this list, then return a ne one from it:
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
    # concat all new dataframes in this list, then return a ne one from it:
    new_dataframes = []
    imts = set(imts)
    non_sa_imts = {_ for _ in imts if sa_period(_) is None}
    sa_imts = imts - non_sa_imts
    # get supported imts but does not allow 'SA' alone to be valid:
    if non_sa_imts:
        # get the imts supported by this program, and raise if some unsupported IMT
        # was requested:
        supported_imts = get_intensity_measures() - {'SA'}
        if non_sa_imts - supported_imts:
            raise InvalidColumnName(*list(non_sa_imts - supported_imts))
        # from the requested imts, raise if some are not in the flatfile:
        if non_sa_imts - set(flatfile.columns):
            raise MissingColumn(*list(non_sa_imts - set(flatfile.columns)))
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
    src_sa = []
    for c in flatfile.columns:
        p = sa_period(c)
        if p is not None:
            src_sa.append((p, c))
    # source_sa: period [float] -> mapped to the relative column:
    source_sa: dict[float, str] = {p: c for p, c in sorted(src_sa, key=lambda t: t[0])}

    tgt_sa = []
    invalid_sa = []
    for i in sa_imts:
        p = sa_period(i)
        if p is None:
            invalid_sa.append(i)
            continue
        if p not in source_sa:
            tgt_sa.append((p, i))
    if invalid_sa:
        raise InvalidDataInColumn(*invalid_sa)

    # source_sa: period [float] -> mapped to the relative column:
    target_sa: dict[float, str] = {p: c for p, c in sorted(tgt_sa, key=lambda t: t[0])}

    source_sa_flatfile = flatfile[list(source_sa.values())]

    if not target_sa:
        return source_sa_flatfile

    # Take the log10 of all SA:
    source_spectrum = np.log10(source_sa_flatfile)
    # we need to interpolate row wise
    # build the interpolation function:
    interp = interp1d(list(source_sa), source_spectrum, axis=1)
    # and interpolate:
    values = 10 ** interp(list(target_sa))
    # values is a matrix where each column represents the values of the target period.
    # Add it to the dataframe:
    new_flatfile = pd.DataFrame(index=flatfile.index)
    new_flatfile[list(target_sa.values())] = values

    return new_flatfile


def get_required_ground_motion_properties(
        flatfile: pd.DataFrame,
        gsims: Iterable[GMPE]) -> pd.DataFrame:
    """Return a new dataframe with all columns required to compute residuals
    from the given models (`gsim`), i.e. all columns denoting ground motion
    properties required by the passed models
    """
    req_properties_flatfile = pd.DataFrame(index=flatfile.index)
    req_properties = ground_motion_properties_required_by(*gsims)

    # REQUIRES_DISTANCES is empty when gsims = [FromFile]: in this case, add a
    # default 'rrup' (see openquake,hazardlib.contexts.ContextMaker.__init__):
    if 'rrup' not in req_properties and \
            any(len(distances_required_by(g)) == 0 for g in gsims):
        req_properties |= {'rrup'}

    for p in req_properties:
        req_properties_flatfile[p] = get_ground_motion_property_values(flatfile, p)
    return req_properties_flatfile


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
    raises :ref:`MissingColumn` error notifying the required missing column.
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
                if na.any():
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
                if na.any():
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
                if na.any():
                    series = series.copy()
                    series[na] = vs30_to_z2pt5_cb14(vs30[na])
    elif gm_property == 'backarc' and series is None:
        series = pd.Series(np.full(len(flatfile), fill_value=False))
    elif gm_property == 'rvolc' and series is None:
        series = pd.Series(np.full(len(flatfile), fill_value=0, dtype=int))
    if series is None:
        raise MissingColumn(gm_property)
    return series


def fill_na(
        flatfile:pd.DataFrame,
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
