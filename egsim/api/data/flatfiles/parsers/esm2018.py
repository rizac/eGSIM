"""Module to parse a published CSV flatfile into an eGSIM compatible flatfile.

To implement a new parser, copy this module, rename it as needed and change all
functions and global variables according to your needs **except the `parse` function**,
which is the only function intended to be publicly accessible

See `flatfile.parse_flatfile` for details
"""
import pandas as pd
import numpy as np


from egsim.smtk.converters import (vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14,
                                   convert_accel_units)
from egsim.smtk.flatfile import read_flatfile


def parse(file) -> pd.DataFrame:
    """Return a standard flatfile in form of pandas DataFrame from the input.
    This is the only function intended to be publicly accessible and **should not
    be changed**: to tune the parsing process, see all other global functions and
    variables of this module

    :param file: str, path object or file-like object denoting the input to be
        read and parsed
    """
    dfr = read_flatfile(file, sep=sep, rename=rename, dtypes=extra_dtype,
                        defaults={}, usecols=usecols)

    return post_process(dfr)


###################################################################
# tune `parse` by changing the following variables and functions: #
###################################################################


# csv separator:
sep = ';'


def usecols(colname):
    """Function used to define which CSV column should be loaded"""
    if colname.endswith('_ref') or colname.endswith("_housner"):
        return False
    if colname.startswith('rotD'):
        return colname in rename  # global var
    if colname in ("instrument_code", "U_channel_code",
                   "V_channel_code", "W_channel_code", "ec8_code_method",
                   "ec8_code_ref", "U_azimuth_deg", "V_azimuth_deg",
                   "EMEC_Mw_type", "installation_code", "proximity_code",
                   "late_triggered_flag_01", "W_hp", "W_lp",
                   "vs30_calc_method"):
        return False
    if colname.endswith('_id'):
        return colname == "event_id"
    return True


# CSV column -> flatfile column mapping:
rename = {
    'ev_nation_code': 'evt_country',
    'event_id': 'evt_id',
    'ev_latitude': 'evt_lat',
    'ev_longitude': 'evt_lon',
    'event_time': 'evt_time',
    'ev_depth_km': 'evt_depth',
    'fm_type_code': 'style_of_faulting',
    'st_nation_code': 'sta_nation_code',
    'st_latitude': 'sta_lat',
    'st_longitude': 'sta_lon',
    'network_code': 'net_code',
    'station_code': 'sta_code',
    'location_code': 'loc_code',
    'st_elevation': 'sta_elevation',
    'epi_dist': 'repi',
    'epi_az': 'azimuth',
    'JB_dist': 'rjb',
    'rup_dist': 'rrup',
    'Rx_dist': 'rx',
    'Ry0_dist': 'ry0',
    'es_strike': 'strike',
    'es_dip': 'dip',
    'es_rake': 'rake',
    'vs30_m_sec': 'vs30',
    'EMEC_Mw': 'mag',
    # 'magnitude_type': 'mag_type',
    'es_z_top': 'rup_top_depth',
    'es_length': 'rup_length',
    'es_width': 'rup_width',
    'U_hp': 'highpass_h1',
    'V_hp': 'highpass_h2',
    'U_lp': 'lowpass_h1',
    'V_lp': 'lowpass_h2',
    # IMTS:
    'rotD50_pga': 'PGA',
    'rotD50_pgv': 'PGV',
    'rotD50_pgd': 'PGD',
    'rotD50_CAV': 'CAV',
    'rotD50_ia': 'IA',
    'rotD50_T90': 'duration_5_95_components',
}


# additional data types for CSV columns that are not in `rename` and not standard
# flatfile columns:
extra_dtype = {
    'event_id': 'category',
    'ev_nation_code': 'category',
    'st_nation_code': 'category',
    'network_code': 'category',
    'station_code': 'category',
    'location_code': 'str',  # location_code is ambiguous ('00', '01',...).
                             # Force str and convert to category in post_process
    'housing_code': 'category',
    'ec8_code': 'category'
}


def post_process(flatfile: pd.DataFrame) -> pd.DataFrame:
    """Defines post process on an already parsed flatfile, just before returning it.
    Implement here any complex operation that are not possible with eGSIM
    `parse_flatfile`
    """

    dfr = flatfile  # legacy code below use `dfr`, too tired to rename

    # loc code a scategorical:
    dfr['loc_code'] = dfr['loc_code'].astype('category')

    # set station id as int:
    dfr['sta_id'] = \
        dfr['net_code'].str.cat(dfr['sta_code'], sep='.'). \
        astype('category').cat.codes

    # magnitude: complete it with
    # Mw -> Ms -> Ml (in this order) where standard mag is NA
    dfr['mag_type'] = 'Mw'
    # convert to categorical (save space):
    dfr['mag_type'] = dfr['mag_type'].astype(
        pd.CategoricalDtype(('ML', 'Mw', 'Ms')))

    # Set Mw where magnitude is na:
    new_mag = dfr.pop('Mw')
    idxs = new_mag.notna() & dfr['mag'].isna()
    dfr.loc[idxs, 'mag'] = new_mag[idxs]
    # Set Ms where magnitude is still na:
    new_mag = dfr.pop('Ms')
    idxs = new_mag.notna() & dfr['mag'].isna()
    dfr.loc[idxs, 'mag'] = new_mag[idxs]
    dfr.loc[idxs, 'mag_type'] = 'Ms'
    # Set Ml where magnitude is still na:
    new_mag = dfr.pop('ML')
    idxs = new_mag.notna() & dfr['mag'].isna()
    dfr.loc[idxs, 'mag'] = new_mag[idxs]
    dfr.loc[idxs, 'mag_type'] = 'ML'

    # Use focal mechanism for those cases where any strike dip rake is NaN
    mechanism_type = {
        "Normal": -90.0,
        "Strike-Slip": 0.0,
        "Reverse": 90.0,
        "Oblique": 0.0,
        "Unknown": 0.0,
        "N": -90.0,  # Flatfile conventions
        "S": 0.0,
        "R": 90.0,
        "U": 0.0,
        "NF": -90.,  # ESM flatfile conventions
        "SS": 0.,
        "TF": 90.,
        "NS": -45.,  # Normal with strike-slip component
        "TS": 45.,  # Reverse with strike-slip component
        "O": 0.0
    }
    dip_type = {
        "Normal": 60.0,
        "Strike-Slip": 90.0,
        "Reverse": 35.0,
        "Oblique": 60.0,
        "Unknown": 90.0,
        "N": 60.0,  # Flatfile conventions
        "S": 90.0,
        "R": 35.0,
        "U": 90.0,
        "NF": 60.,  # ESM flatfile conventions
        "SS": 90.,
        "TF": 35.,
        "NS": 70.,  # Normal with strike-slip component
        "TS": 45.,  # Reverse with strike-slip component
        "O": 90.0
    }
    sofs = dfr.pop('style_of_faulting')
    is_na = dfr[['strike', 'dip', 'rake']].isna().any(axis=1)
    if is_na.any():
        for sof in pd.unique(sofs):
            rake = mechanism_type.get(sof, 0.0)
            strike = 0.0
            dip = dip_type.get(sof, 90.0)
            filter_ = is_na & (sofs == sof)
            if filter_.any():
                dfr.loc[filter_, 'rake'] = rake
                dfr.loc[filter_, 'strike'] = strike
                dfr.loc[filter_, 'dip'] = dip

    # if vs30_meas_type is not empty  then vs30_measured is True else False
    # rowdict['vs30_measured'] = bool(rowdict.get('vs30_meas_type', '')
    dfr['vs30measured'] = ~pd.isna(dfr.pop('vs30_meas_type'))

    # if vs30_meas_sec has value, then vs30 is that value, vs30_measured
    # is True
    # Otherwise if vs30_sec_WA has value, then vs30 is that value and
    # vs30_measure is False
    # Othersie, vs30 is obviously missing and vs30 measured is not given
    # (check needs to be False by default)

    dfr.loc[pd.notna(dfr['vs30']), 'vs30measured'] = True
    vs30_wa = dfr.pop('vs30_m_sec_WA')
    filter_ = pd.isna(dfr['vs30']) & pd.notna(vs30_wa)
    dfr.loc[filter_, 'vs30'] = vs30_wa[filter_]
    dfr.loc[filter_, 'vs30measured'] = False

    # set z1 and z2:
    dfr['z1pt0'] = vs30_to_z1pt0_cy14(dfr['vs30'])
    dfr['z2pt5'] = vs30_to_z2pt5_cb14(dfr['vs30'])

    # rhyopo is sqrt of repi**2 + event_depth**2 (basic Pitagora)
    dfr['rhypo'] = np.sqrt((dfr['repi'] ** 2) + dfr['evt_depth'] ** 2)

    # digital_recording is True <=> instrument_type_code is D
    dfr['digital_recording'] = dfr.pop('instrument_type_code') == 'D'

    # IMTS:
    # Note: ESM not reporting correctly some values: PGA, PGV, PGD and SA
    # should always be positive (absolute value)

    # Scalar IMTs should be there ('pga' from "rot50D_pga", 'pgv' from
    # "rot50D_pgv" and so on, see `cls.esm_col_mapping`): if not, compute
    # the geometric mean of `U_*` and `V_*` columns (e.g. 'U_pga', 'V_pga')
    for col in (c for c in rename if c.startswith('rotD50_')):  # rename is global var
        esm_imt_name = col.split('_', 1)[-1]
        imt_components = dfr.pop('U_' + esm_imt_name), \
            dfr.pop('V_' + esm_imt_name), dfr.pop('W_' + esm_imt_name)
        imt_name = rename[col]
        if imt_name not in dfr.columns:
            # geometric mean:
            dfr[imt_name] = np.sqrt(imt_components[0] * imt_components[1])

    # convert PGA from cm/s^2 to g:
    dfr['PGA'] = convert_accel_units(dfr['PGA'], "cm/s^2", "g")

    # SA
    sa_suffixes = ('_T0_010', '_T0_025', '_T0_040', '_T0_050',
                   '_T0_070', '_T0_100', '_T0_150', '_T0_200',
                   '_T0_250', '_T0_300', '_T0_350', '_T0_400',
                   '_T0_450', '_T0_500', '_T0_600', '_T0_700',
                   '_T0_750', '_T0_800', '_T0_900', '_T1_000',
                   '_T1_200', '_T1_400', '_T1_600', '_T1_800',
                   '_T2_000', '_T2_500', '_T3_000', '_T3_500',
                   '_T4_000', '_T4_500', '_T5_000', '_T6_000',
                   '_T7_000', '_T8_000', '_T9_000', '_T10_000')

    # Store all SA columns in a dict and add them to `dfr` once at the end
    # (should avoid PandasPerformanceWarning):
    sa_columns = {}
    for sa_sfx in sa_suffixes:
        imt_components = \
            dfr.pop('U' + sa_sfx), dfr.pop('V' + sa_sfx), dfr.pop('W' + sa_sfx)
        period = sa_sfx[2:].replace('_', '.')
        float(period)  # just a check
        # geometric mean:
        sa_columns[f'SA({period})'] = convert_accel_units(
            np.sqrt(imt_components[0] * imt_components[1]), "cm/s^2", "g"
        )
    # concat (side by side "horizontally") `dfr` with the newly created SA dataframe:
    dfr = pd.concat((dfr, pd.DataFrame(sa_columns)), axis=1)
    return dfr


