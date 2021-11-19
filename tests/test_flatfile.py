from os.path import dirname, join
from typing import Union, Any

import pandas as pd
import time
import numpy as np
import yaml

from egsim.core.modelparams import read_model_params, Prop, default_dtype
# from egsim.management.commands import EgsimBaseCommand
from egsim.models import FlatfileField
from smtk import sm_utils


# def test_esm_convert():
#     t = time.time()
#     dfr = read_esm(filename)
#     print('esm loaded in %f' % (time.time() - t))
#
#     unique = []
#     for c in dfr.columns:
#         unique.append({'c': len(pd.unique(dfr[c]))})
#     dfr = pd.DataFrame(unique, index=dfr.columns)
#
#     parse_dates = [n for n, f in flatfile.items() if f['type'] == 'datetime64']
#     dtype = dtype = {n: f['type'] for n, f in flatfile.items() if n not in parse_dates}
#
#     # parse_dates = ['event_time']
#     # parse_ints = ['npass']
#     # parse_bools = ['vs30_measured', 'digital_recording', 'backarc']
#     # parse_str = ['event_name', 'event_country', 'tectonic_environment', 'style_of_faulting', 'station_name', 'station_country', 'type_of_filter']
#     # parse_floats = ['event_latitude', 'event_longitude', 'hypocenter_depth', 'magnitude', 'magnitude_type', 'magnitude_uncertainty', 'strike_1', 'strike_2', 'dip_1', 'dip_2', 'rake_1', 'rake_2', 'depth_top_of_rupture', 'rupture_length', 'rupture_width', 'station_latitude', 'station_longitude', 'station_elevation', 'vs30', 'vs30_sigma', 'depth_to_basement', 'z1', 'z2pt5', 'repi', 'rrup', 'rjb', 'rhypo', 'rx', 'ry0', 'azimuth', 'nroll', 'hp_h1', 'hp_h2', 'lp_h1', 'lp_h2', 'factor', 'lowest_usable_frequency_h1', 'lowest_usable_frequency_h2', 'lowest_usable_frequency_avg', 'highest_usable_frequency_h1', 'highest_usable_frequency_h2', 'highest_usable_frequency_avg']
#
#     dfr = pd.read_csv(filename, sep=';', dtype=dtype, parse_dates=parse_dates)
#
#     dtypes = {n: 'float' if 'type' not in f else f['type'] for n, f in fields.items()}
#
#     from egsim.models import Flatfile
#     fields = Flatfile.fields
#     asd = 9


# def test_speed():
#     # this checks that the Python engine does not actually infer automatically the
#     # separator:
#     print('pandas read_csv:')
#     print('================')
#     print()
#     # normal read_csv, but separator is wrong:
#     t = time.time()
#     dfr = pd.read_csv(filename, engine='c')
#     print("With c engine (sep default) %f secs, %d columns" %
#           ((time.time() - t), len(dfr.columns)))
#     # read_csv with python engine, separator is inferred but takes time:
#     t = time.time()
#     dfr = pd.read_csv(filename, engine='python', sep=None)
#     print("With python engine (sep inferred) %f secs, %d columns" %
#           ((time.time() - t), len(dfr.columns)))
#     # custom method:
#     t = time.time()
#     dfr, param = None, None
#     for param_ in [{'sep': ','}, {'sep': ';'}, {'delim_whitespace': True}]:
#         dfr_ = pd.read_csv(filename, nrows=0, **param_)
#         if dfr is None or len(dfr_.columns) > len(dfr.columns):
#             dfr = pd.read_csv(filename, **param_)
#     print("With our method (sep inferred) %f secs, %d columns" %
#           ((time.time() - t), len(dfr.columns)))


# _DTYPES = {
#     # 'event_name': 'category',
#     'event_id': 'category', 'station_id': 'category',
#     'event_country': 'category', 'event_latitude': 'float',
#     'event_longitude': 'float', 'hypocenter_depth': 'float', 'magnitude': 'float',
#     'magnitude_type': 'float', 'magnitude_uncertainty': 'float',
#     'tectonic_environment': 'str', 'strike_1': 'float', 'strike_2': 'float',
#     'dip_1': 'float', 'dip_2': 'float', 'rake_1': 'float', 'rake_2': 'float',
#     'style_of_faulting': 'category', 'depth_top_of_rupture': 'float',
#     'rupture_length': 'float', 'rupture_width': 'float',
#     'station_country': 'category', 'station_latitude': 'float', 'station_longitude': 'float',
#     'station_elevation': 'float', 'vs30': 'float', 'vs30_measured': 'bool',
#     'vs30_sigma': 'float', 'depth_to_basement': 'float', 'z1': 'float', 'z2pt5': 'float',
#     'repi': 'float', 'rrup': 'float', 'rjb': 'float', 'rhypo': 'float', 'rx': 'float',
#     'ry0': 'float', 'azimuth': 'float', 'digital_recording': 'bool',
#     'type_of_filter': 'str', 'npass': 'int', 'nroll': 'float', 'hp_h1': 'float',
#     'hp_h2': 'float', 'lp_h1': 'float', 'lp_h2': 'float', 'factor': 'float',
#     'lowest_usable_frequency_h1': 'float', 'lowest_usable_frequency_h2': 'float',
#     'lowest_usable_frequency_avg': 'float', 'highest_usable_frequency_h1': 'float',
#     'highest_usable_frequency_h2': 'float', 'highest_usable_frequency_avg': 'float',
#     'backarc': 'bool', 'network_code': 'category', 'station_code': 'category',
#     'location_code': 'category', 'channel_code': 'category'
# }
# _PARSE_DATES = {'event_time'}
from smtk.sm_utils import MECHANISM_TYPE, DIP_TYPE
from smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14


def _get_db_mappings() -> tuple[dict[str, str], list[str], dict[str, str]]:
    """
    Return the tuple:
    ```
    dtype, parse_dates, col_mapping
    ```
    i.e. the arguments needed by
    `read_flatfile`. The data is read from the eGSIM database
    """
    from egsim.models import FlatfileField
    dtype, parse_dates, col_mapping = {}, [], {}
    for (name, ffname, dtype) in GsimParameter.objects.exclude(
            flatfile_name__isnull=True).values_list('name', 'flatfile_name',
                                                    'data_type'):
        if dtype == 'datetime':
            parse_dates.append(ffname)
        else:
            dtype[ffname] = dtype
        col_mapping[ffname] = name

    return dtype or None, parse_dates or None, col_mapping or None


def _get_yaml_mappins() -> tuple[dict[str, str], list[str], dict[str, str]]:
    """
    Return the tuple:
    ```
    dtype, parse_dates, col_mapping
    ```
    i.e. the arguments needed by
    `read_flatfile`. The data is read from the eGSIM database
    """
    dtype, parse_dates, defaults, col_mappings = {}, [], {}, {}
    for (key, props) in read_model_params():
        ffname = props.get(Prop.ffname, None)
        if not ffname:
            continue
        dtyp = props.get(Prop.dtype, default_dtype)
        if dtyp == 'datetime':
            parse_dates.append(ffname)
        else:
            dtype[ffname] = dtyp
        if Prop.default in props:
            defaults[ffname] = props[Prop.default]

        col_mappings[ffname] = key.split('.', 1)[1]

    return dtypes, parse_dates, defaults, col_mappings


def read_flatfile(filepath: str,
                  sep: Union[None, str] = None,
                  col_mapping: Union[None, dict[str, str]] = None,
                  usecols: Union[None, list, "callable"] = None,
                  dtype: Union[None, dict[str, str]] = None,
                  parse_dates: Union[None, list[str]] = None,
                  **kwargs):
    """

    :param filepath: the CSV file path. Compressed files are also supported
        and inferred from the extension (e.g. 'gzip', 'zip')
    :param sep: the separator (or delimiter). None means 'infer'
    :param dtype: dict of flatfile column names mapped to the data type
        ('int' 'bool'). For date-times, use `parse_dates`.
    :param parse_dates: list of flatfile column names denoting date time
        columns
    :param usecols: flatfile column names to load, list or callable accepting
        a column name and returning True/False
    :param col_mapping: dict mapping flatfile names to OpenQuake Gsim
        parameter names. The dict will be used to rename the dataframe column
        after all other operations, just before returning
    """
    params = _infer_csv_sep(filepath) if sep is None else {'sep': sep}

    if (dtype or parse_dates or usecols) and col_mapping:
        newcol2oldcol = dict(zip(col_mapping.values(), col_mapping.keys()))

        if dtype:
            # map new names to old names
            # replace old names in dtype:
            dtype = {newcol2oldcol.get(k, k): v for k, v in dtype.items()}

        if parse_dates:
            parse_dates = [newcol2oldcol.get(k, k) for k in parse_dates]

    dfr = pd.read_csv(filepath, dtype=dtype, parse_dates=parse_dates,
                      usecols=usecols, **{**kwargs, **params})

    if col_mapping:
        dfr.rename(columns=col_mapping, inplace=True)

    return dfr


def _infer_csv_sep(filepath: str) -> dict[str, Any]:
    """Infer the CSV separator from `filepath`, return the arguments needed
    for pd.read_csv as dict (e.g. `{'sep': ','}`)"""
    # pandas suggests to use the engine='python' argument to infer `sep`,
    # but this takes approx 4.5 seconds with the ESM flatfile 2018
    # whereas the method below is around 1.5 (load headers and count).
    # So, try to read the headers only with comma and semicolon, and chose the
    # one producing more columns:
    comma_col_len = len(pd.read_csv(filepath, nrows=0, sep=',').columns)
    semicolon_col_len = len(pd.read_csv(filepath, nrows=0, sep=';').columns)
    if comma_col_len > 1 and comma_col_len >= semicolon_col_len:
        return {'sep': ','}
    if semicolon_col_len > 1:
        return {'sep': ';'}
    # try with spaces:
    params = {'sep': None, 'delim_whitespace': True}
    space_col_len = len(pd.read_csv(filepath, nrows=0, **params,).columns)
    if space_col_len > max(comma_col_len, semicolon_col_len):
        return params

    raise ValueError('CSV separator could not be inferred. Please re-edit and '
                     'provide either comma (preferred choice) semicolon or '
                     'and whitespace')


def read_userdefined_flatfile(filepath):
    dtype, parse_dates, col_mapping = _get_db_mappings()
    return read_flatfile(filepath, dtype=dtype, parse_dates=parse_dates,
                         col_mapping=col_mapping)
    # FIXME: todo : check IDs!!!
    if 'event_id' not in dfr:
        if 'event_time' not in dfr:
            raise ValueError('event_id')


def esm_usecols(colname):
    if colname.endswith('_ref'):
        return False
    if colname.startswith('rotD'):  # FIXME: check
        return False
    if colname in ("instrument_code", "U_channel_code",
                   "V_channel_code", "W_channel_code", "ec8_code_method",
                   "ec8_code_ref", "U_azimuth_deg", "V_azimuth_deg",
                   "EMEC_Mw_type", "installation_code"):
        return False
    if colname.endswith('_id'):
        return colname == "event_id"
    return True


esm_col_mapping = {
    'ev_nation_code': 'event_country',
    # 'event_id': 'event_name',
    'ev_latitude': 'event_latitude',
    'ev_longitude': 'event_longitude',
    'ev_depth_km': 'hypocenter_depth',
    'fm_type_code': 'style_of_faulting',
    'st_nation_code': 'station_country',
    'st_latitude': 'station_latitude',
    'st_longitude': 'station_longitude',
    'st_elevation': 'station_elevation',
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
    'EMEC_Mw': 'magnitude',
    'es_z_top': 'depth_top_of_rupture',
    'es_length': 'rupture_length',
    'es_width': 'rupture_width',
    'U_hp': 'hp_h1',
    'V_hp': 'hp_h2',
    'U_lp': 'lp_h1',
    'V_lp': 'lp_h2'
}

esm_dtypes = {
    'event_id': 'category'
}


def read_esm(filepath):

    dfr = read_flatfile(filepath, col_mapping=esm_col_mapping, sep=';',
                        parse_dates=['event_time'],
                        usecols=esm_usecols)

    # Post process:

    # magnitude: complete it with
    # Mw -> Ms -> Ml (in this order) where standard mag is NA
    dfr['magnitude_type'] = 'Mw'
    mag_types = ('ML', 'Mw', 'Ms')
    # convert to categorical (save space):
    dfr['magnitude_type'] = dfr['magnitude_type'].astype(
        pd.CategoricalDtype(mag_types))
    # Set Mw where magnitude is na:
    mag_na = pd.isna(dfr['magnitude'])
    new_mag = dfr.pop('Mw')
    dfr.loc[mag_na, 'magnitude'] = new_mag
    # Set Ms where magnitude is na:
    mag_na = pd.isna(dfr['magnitude'])
    new_mag = dfr.pop('Ms')
    dfr.loc[mag_na, 'magnitude'] = new_mag
    dfr.loc[mag_na, 'magnitude'] = 'Ms'
    # Set Ml where magnitude is na:
    mag_na = pd.isna(dfr['magnitude'])
    new_mag = dfr.pop('ML')
    dfr.loc[mag_na, 'magnitude'] = new_mag
    dfr.loc[mag_na, 'magnitude'] = 'Ml'

    # Use focal mechanism for those cases where All strike dip rake is NaN
    # (see smtk.sm_table.update_rupture_context)
    # FIXME: before we replaced if ANY was NaN, but it makes no sense to me
    # (why replacing  dip, strike and rake if e.g. only the latter is NaN?)
    sofs = dfr.pop('style_of_faulting')
    is_na = dfr[['strike', 'dip', 'rake']].isna().all(axis=1)
    if is_na.any():
        for sof in pd.unique(sofs):
            rake = MECHANISM_TYPE.get(sof, 0.0)
            strike = 0.0
            dip = DIP_TYPE.get(sof, 90.0)
            filter_ = is_na & (sofs == sof)
            if filter_.any():
                dfr.loc[filter_, 'rake'] = rake
                dfr.loc[filter_, 'strike'] = strike
                dfr.loc[filter_, 'dip'] = dip

    # if vs30_meas_type is not empty  then vs30_measured is True else False
    # rowdict['vs30_measured'] = bool(rowdict.get('vs30_meas_type', ''))
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
    dfr['z1'] = vs30_to_z1pt0_cy14(dfr['vs30'])
    dfr['z2pt5'] = vs30_to_z2pt5_cb14(dfr['vs30'])

    # rhyopo is sqrt of repi**2 + event_depth**2 (basic Pitagora)
    dfr['rhypo'] = np.sqrt((dfr['repi'] ** 2) + dfr['hypocenter_depth'] ** 2)

    # digital_recording is True <=> instrument_type_code is D
    dfr['digital_recording'] = dfr.pop('instrument_type_code') == 'D'

    # IMTS:
    geom_mean = sm_utils.SCALAR_XY['Geometric']

    # Note: ESM not reporting correctly some values: PGA, PGV, PGD and SA
    # should always be positive (absolute value)

    # U_pga    V_pga    W_pga are the three components of pga
    # IT IS SUPPOSED TO BE ALREADY IN CM/S/S
    imt_components = dfr.pop('U_pga'), dfr.pop('V_pga'), dfr.pop('W_pga')
    dfr['pga'] = geom_mean(imt_components[0], imt_components[1])

    imt_components = dfr.pop('U_pgv'), dfr.pop('V_pgv'), dfr.pop('W_pgv')
    dfr['pgv'] = geom_mean(imt_components[0], imt_components[1])

    imt_components = dfr.pop('U_pgd'), dfr.pop('V_pgd'), dfr.pop('W_pgd')
    dfr['pgd'] = geom_mean(imt_components[0], imt_components[1])

    imt_components = dfr.pop('U_T90'), dfr.pop('V_T90'), dfr.pop('W_T90')
    dfr['duration_5_95_components'] = geom_mean(imt_components[0], imt_components[1])

    imt_components = dfr.pop('U_CAV'), dfr.pop('V_CAV'), dfr.pop('W_CAV')
    dfr['cav'] = geom_mean(imt_components[0], imt_components[1])

    imt_components = dfr.pop('U_ia'), dfr.pop('V_ia'), dfr.pop('W_ia')
    dfr['arias_intensity'] = geom_mean(imt_components[0], imt_components[1])

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

    for sa_sfx in sa_suffixes:
        imt_components = \
            dfr.pop('U'+sa_sfx), dfr.pop('V'+sa_sfx), dfr.pop('W'+sa_sfx)
        period = sa_sfx[2:].replace('_', '.')
        float(period)  # just a check
        dfr['sa(%s)' % period] = geom_mean(imt_components[0], imt_components[1])

    return dfr


def test_esm_read():
    dfr = read_esm('/Users/rizac/work/gfz/projects/sources/python/egsim/egsim/'
                   'management/commands/data/raw_flatfiles/ESM_flatfile_2018_SA.csv.zip')
    params = read_param_props('/Users/rizac/work/gfz/projects/sources/python'
                              '/egsim/egsim/core/modelparams.yaml')

    rename = {v['flatfile_name']: k for k, v in params.items() if v.get('flatfile_name', None)}
    unknown_cols = set(rename) - set(dfr.columns)
    # dfr2 = dfr.reanme(columns=rename)
    extra_cols = set(dfr.columns) - set(rename)
    asd = 9
    catagorical_cols = []
    for _ in dfr.columns:
        if len(pd.unique(dfr[_])) < len(dfr) /5:
            catagorical_cols.append(_)
    asd = 9


def test_gain():
    N = 1000000
    dfr = pd.DataFrame(N)
