import pandas as pd
import numpy as np

from ...smtk import convert_accel_units
from ...smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14

from ...smtk.flatfile import read_csv, column_dtype, column_default, column_required


# mean utilities (geometric, arithmetic, ...):
SCALAR_XY = {
    "Geometric": lambda x, y: np.sqrt(x * y),
    "Arithmetic": lambda x, y: (x + y) / 2.,
    "Larger": lambda x, y: np.max(np.array([x, y]), axis=0),
    "Vectorial": lambda x, y: np.sqrt(x ** 2. + y ** 2.)
}


MECHANISM_TYPE = {
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


DIP_TYPE = {
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

class FlatfileParser:
    """Base class for Flatfile parser (CSV -> HDF conversion)"""

    @classmethod
    def parse(cls, filepath) -> pd.DataFrame:
        raise NotImplementedError('parse not implemented')


class EsmFlatfileParser(FlatfileParser):
    """ESM flatfile parser"""

    @classmethod
    def esm_usecols(cls, colname):
        """Function used to define which columns should be loaded"""
        if colname.endswith('_ref') or colname.endswith("_housner"):
            return False
        if colname.startswith('rotD'):
            return colname in cls.esm_col_mapping
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

    esm_col_mapping = {
        'ev_nation_code': 'event_country',
        # 'event_id': 'event_name',
        'ev_latitude': 'event_latitude',
        'ev_longitude': 'event_longitude',
        'ev_depth_km': 'event_depth',
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
        'rotD50_T90': 'duration_5_95_components',  # FIXME: IMT???
    }

    esm_dtypes = {
        'event_id': 'category',
        'event_country': 'category',
        'event_time': 'datetime',
        'network_code': 'category',
        'station_code': 'category',
        'location_code': 'category',
        'station_country': 'category',
        'housing_code': 'category',
        'ec8_code': 'category'
    }

    @classmethod
    def parse(cls, filepath: str) -> pd.DataFrame:
        """Parse ESM flatfile (CSV) and return the pandas DataFrame"""
        dtype = dict(cls.esm_dtypes)
        required = set()
        defaults= {}
        for esm_col, ff_col in cls.esm_col_mapping.items():
            if ff_col in column_default:
                defaults[esm_col] = column_default[ff_col]
            if ff_col in column_required:
                required.add(esm_col)
            if ff_col in column_dtype:
                dtype[esm_col] = column_dtype[ff_col]

        dfr = read_csv(filepath, sep=';', required=required, defaults=defaults,
                       dtype=dtype, usecols=cls.esm_usecols)

        dfr.rename(columns=cls.esm_col_mapping, inplace=True)

        dfr['station_id'] = \
            dfr['network_code'].str.cat(dfr['station_code'], sep='.').\
                astype('category').cat.codes

        # Post process:
        # -------------
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
        dfr.loc[mag_na, 'magnitude_type'] = 'Ms'
        # Set Ml where magnitude is na:
        mag_na = pd.isna(dfr['magnitude'])
        new_mag = dfr.pop('ML')
        dfr.loc[mag_na, 'magnitude'] = new_mag
        dfr.loc[mag_na, 'magnitude_type'] = 'ML'

        # Use focal mechanism for those cases where All strike dip rake is NaN
        # (see smtk.sm_table.update_rupture_context)
        # FIXME: before we replaced if ANY was NaN, but it makes no sense to me
        # (why replacing  dip, strike and rake if e.g. only the latter is NaN?)
        sofs = dfr.pop('style_of_faulting')
        is_na = dfr[['strike', 'dip', 'rake']].isna().any(axis=1)
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
        dfr['z1pt0'] = vs30_to_z1pt0_cy14(dfr['vs30'])
        dfr['z2pt5'] = vs30_to_z2pt5_cb14(dfr['vs30'])

        # rhyopo is sqrt of repi**2 + event_depth**2 (basic Pitagora)
        dfr['rhypo'] = np.sqrt((dfr['repi'] ** 2) + dfr['event_depth'] ** 2)

        # digital_recording is True <=> instrument_type_code is D
        dfr['digital_recording'] = dfr.pop('instrument_type_code') == 'D'

        # IMTS:
        geom_mean = SCALAR_XY['Geometric']

        # Note: ESM not reporting correctly some values: PGA, PGV, PGD and SA
        # should always be positive (absolute value)

        # Scalar IMTs should be there ('pga' from "rot50D_pga", 'pgv' from
        # "rot50D_pgv" and so on, see `cls.esm_col_mapping`): if not, compute
        # the geometric mean of `U_*` and `V_*` columns (e.g. 'U_pga', 'V_pga')
        # FIXME: IT IS SUPPOSED TO BE ALREADY IN CM/S/S

        # _supported_imts = set(Imt.objects.values_list('name', flat=True))
        for col in (_ for _ in cls.esm_col_mapping if _.startswith('rotD50_')):
            esm_imt_name = col.split('_', 1)[-1]
            imt_components = dfr.pop('U_' + esm_imt_name), \
                dfr.pop('V_' + esm_imt_name), dfr.pop('W_' + esm_imt_name)
            imt_name = cls.esm_col_mapping[col]
            # if imt_name not in _supported_imts:
            #     raise ValueError('%s.esm_col_mapping["%s"]="%s" is not a valid IMT' %
            #                      (cls.__name__, col, cls.esm_col_mapping[col]))
            if imt_name not in dfr.columns:
                dfr[imt_name] = geom_mean(imt_components[0], imt_components[1])

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
            sa_columns['SA(%s)' % period] = geom_mean(imt_components[0],
                                                      imt_components[1])
        # concat (side by side "horizontally") `dfr` with the newly created SA dataframe:
        dfr = pd.concat((dfr, pd.DataFrame(sa_columns)), axis=1)
        return dfr
