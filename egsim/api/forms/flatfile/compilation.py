"""
Django Forms for eGSIM flatfile compilation (inspection, plot, upload)

@author: riccardo
"""
from typing import Union

import numpy as np
import pandas as pd
from django.core.exceptions import ValidationError
from django.forms.fields import CharField

from egsim.api import models
from egsim.api.forms import APIForm, GsimImtForm
from egsim.api.forms.flatfile import FlatfileForm, get_gsims_from_flatfile
from egsim.smtk import (ground_motion_properties_required_by,
                        intensity_measures_defined_for)
from egsim.smtk.flatfile import get_dtypes_and_defaults
from egsim.smtk.flatfile.columns import load_from_yaml


class FlatfileRequiredColumnsForm(GsimImtForm, APIForm):
    """Form for querying the necessary metadata columns from a given list of Gsims"""

    accept_empty_gsim_list = True  # see GsimImtForm
    accept_empty_imt_list = True

    @classmethod
    def response_data(cls, cleaned_data: dict) -> dict:
        """Return the API response for data requested in JSON format"""
        gsims = cleaned_data.get('gsim', [])
        if not models:
            gsims = list(models.Gsim.objects.filter(hidden=False).only('name').
                         values_list('name', flat=True))
        gm_props = ground_motion_properties_required_by(*gsims, as_ff_column=True)
        imts = cleaned_data.get('imt', [])

        if not imts:
            imts = set()
            for m in gsims:
                imts |= intensity_measures_defined_for(m)

        col_registry = load_from_yaml()
        columns = {}
        for col_name in sorted(set(gm_props) | set(imts)):
            columns[col_name] = {
                'help': str(col_registry.get(col_name, {}).get('help', 'unspecified')),
                'type': str(col_registry.get(col_name, {}).get('type', 'unspecified')),
                'dtype': str(col_registry.get(col_name, {}).get('dtype', 'unspecified'))
            }
        return columns


class FlatfilePlotForm(APIForm, FlatfileForm):
    """Form for plotting flatfile columns"""

    x = CharField(label='X', help_text="The flatfile column for the x values",
                  required=False)
    y = CharField(label='Y', help_text="The flatfile column for the y values",
                  required=False)

    def clean(self):
        """Call `super.clean()` and handle the flatfile"""
        cleaned_data = super().clean()
        x, y = cleaned_data.get('x', None), cleaned_data.get('y', None)
        if not x and not y:
            self.add_error("x", ValidationError('with no "y" specified, this '
                                                'parameter is required',
                                                code='required'))
            self.add_error("y", ValidationError('with no "x" specified, this '
                                                'parameter is required',
                                                code='required'))

        if not self.has_error('flatfile'):
            cols = cleaned_data['flatfile'].columns
            if x and x not in cols:
                self.add_error("x", ValidationError(f'"{x}" is not a flatfile'
                                                    'column', code='invalid'))
            if y and y not in cols:
                self.add_error("y", ValidationError(f'"{y}" is not a flatfile'
                                                    'column', code='invalid'))

        return cleaned_data

    @classmethod
    def response_data(cls, cleaned_data: dict) -> dict:
        """Return the API response for data requested in JSON format"""
        dataframe = cleaned_data['flatfile']
        x, y = cleaned_data.get('x', None), cleaned_data.get('y', None)
        if x and y:  # scatter plot
            xlabel, ylabel = cleaned_data['x'], cleaned_data['y']
            xvalues = dataframe[xlabel]
            yvalues = dataframe[ylabel]
            xnan = cls._isna(xvalues)
            ynan = cls._isna(yvalues)
            plot = dict(
                xvalues=cls._tolist(xvalues[~(xnan | ynan)]),
                yvalues=cls._tolist(yvalues[~(xnan | ynan)]),
                xlabel=xlabel,
                ylabel=ylabel,
                stats={
                    xlabel: {'N/A count': int(xnan.sum()),
                             **cls._get_stats(xvalues.values[~xnan])},
                    ylabel: {'N/A count': int(ynan.sum()),
                             **cls._get_stats(yvalues.values[~ynan])}
                }
            )
        else:
            label = x or y
            na_values = cls._isna(dataframe[label])
            dataframe = dataframe.loc[~na_values, :]
            series = dataframe[label]
            na_count = int(na_values.sum())
            if x:
                plot = dict(
                    xvalues=cls._tolist(series),
                    xlabel=label,
                    stats={
                        label: {
                            'N/A count': na_count,
                            **cls._get_stats(series.values)
                        }
                    }
                )
            else:
                plot = dict(
                    yvalues=cls._tolist(series),
                    ylabel=label,
                    stats={
                        label: {
                            'N/A count': na_count,
                            **cls._get_stats(series.values)
                        }
                    }
                )
        return plot

    @classmethod
    def _tolist(cls, values: pd.Series):  # values does not have NA
        if str(values.dtype).startswith('datetime'):
            # convert values to DatetimeIndex (note:
            # to_datetime(series) -> series, to_datetime(ndarray) -> DatetimeIndex)
            # and then to a pandas Index of ISO formatted strings
            values = pd.to_datetime(values.values).\
                strftime('%Y-%m-%dT%H:%M:%S')
        return values.tolist()

    @classmethod
    def _isna(cls, values: pd.Series) -> np.ndarray:
        filt = pd.isna(values) | values.isin([-np.inf, np.inf])
        return values[filt].values

    @classmethod
    def _get_stats(cls, finite_values) -> dict[str, Union[float, None]]:
        values = np.asarray(finite_values)
        try:
            return {
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'median': float(np.median(values)),
                'mean': float(np.mean(values)),
                '0.25quantile': float(np.quantile(values, 0.25)),
                '0.75quantile': float(np.quantile(values, 0.75))
            }
        except (ValueError, TypeError):
            # ValueError if values is empty. TypeError if values contains mixed types
            return {
                'min': None,
                'max': None,
                'median': None,
                'mean': None,
                '0.25quantile': None,
                '0.75quantile': None
            }


class FlatfileInspectionForm(APIForm, FlatfileForm):
    """Form for flatfile inspection, return info from a given flatfile"""

    # Set the public names of this Form Fields as `public_name: attribute_name`
    # mappings. Superclass mappings are merged into this one. An attribute name
    # can be keyed by several names, and will be keyed by itself anyway if not
    # done here (see `egsim.forms.EgsimFormMeta` for details)
    public_field_names = {}

    def clean(self):
        cleaned_data = super().clean()

        if self.has_error('flatfile'):
            return cleaned_data
        dataframe = cleaned_data['flatfile']
        gsims = list(get_gsims_from_flatfile(dataframe.columns))
        if not gsims:
            self.add_error("flatfile",
                           ValidationError("Invalid or missing column names",
                                           code='invalid'))
        cleaned_data['gsim'] = gsims
        cleaned_data['flatfile_dtypes'] = self.get_flatfile_dtypes(dataframe)
        return cleaned_data

    @classmethod
    def response_data(cls, cleaned_data: dict) -> dict:
        """Return the API response for data requested in JSON format"""
        return {
            'columns': cleaned_data['flatfile_dtypes'],
            'default_columns': get_dtypes_and_defaults()[0],
            'gsim': cleaned_data['gsim']
        }
