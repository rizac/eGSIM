"""
Django Forms for eGSIM flatfile compilation (inspection, plot, upload)

@author: riccardo
"""
from typing import Union

import numpy as np
import pandas as pd
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

    def response_data(self) -> dict:
        """Return the response data from this Form input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: a response data Python object (e.g., a JSON-serializable dict)
        """
        cleaned_data = self.cleaned_data
        gsims = cleaned_data.get('gsim', [])
        if not models:
            gsims = list(models.Gsim.names())
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
            self.add_error("x", 'either x or y is required')
            self.add_error("y", 'either x or y is required')

        if not self.has_error('flatfile'):
            cols = cleaned_data['flatfile'].columns
            if x and x not in cols:
                self.add_error("x", f'"{x}" is not a flatfile column')
            if y and y not in cols:
                self.add_error("y", f'"{y}"  is not a flatfile column')

        return cleaned_data

    def response_data(self) -> dict:
        cleaned_data = self.cleaned_data
        dataframe = cleaned_data['flatfile']
        x, y = cleaned_data.get('x', None), cleaned_data.get('y', None)
        if x and y:  # scatter plot
            xlabel, ylabel = cleaned_data['x'], cleaned_data['y']
            xvalues = dataframe[xlabel]
            yvalues = dataframe[ylabel]
            xnan = self._isna(xvalues)
            ynan = self._isna(yvalues)
            plot = dict(
                xvalues=self._tolist(xvalues[~(xnan | ynan)]),
                yvalues=self._tolist(yvalues[~(xnan | ynan)]),
                xlabel=xlabel,
                ylabel=ylabel,
                stats={
                    xlabel: {'N/A count': int(xnan.sum()),
                             **self._get_stats(xvalues.values[~xnan])},
                    ylabel: {'N/A count': int(ynan.sum()),
                             **self._get_stats(yvalues.values[~ynan])}
                }
            )
        else:
            label = x or y
            na_values = self._isna(dataframe[label])
            dataframe = dataframe.loc[~na_values, :]
            series = dataframe[label]
            na_count = int(na_values.sum())
            if x:
                plot = dict(
                    xvalues=self._tolist(series),
                    xlabel=label,
                    stats={
                        label: {
                            'N/A count': na_count,
                            **self._get_stats(series.values)
                        }
                    }
                )
            else:
                plot = dict(
                    yvalues=self._tolist(series),
                    ylabel=label,
                    stats={
                        label: {
                            'N/A count': na_count,
                            **self._get_stats(series.values)
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

    def clean(self):
        cleaned_data = super().clean()

        if self.has_error('flatfile'):
            return cleaned_data
        dataframe = cleaned_data['flatfile']
        gsims = list(get_gsims_from_flatfile(dataframe.columns))
        if not gsims:
            self.add_error("flatfile", f'missing columns required')
        cleaned_data['gsim'] = gsims
        cleaned_data['flatfile_dtypes'] = self.get_flatfile_dtypes(dataframe)
        return cleaned_data

    def response_data(self) -> dict:
        cleaned_data = self.cleaned_data
        return {
            'columns': cleaned_data['flatfile_dtypes'],
            'default_columns': get_dtypes_and_defaults()[0],
            'gsim': cleaned_data['gsim']
        }
