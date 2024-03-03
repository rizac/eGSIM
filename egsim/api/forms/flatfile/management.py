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
from egsim.api.forms.flatfile import (FlatfileForm, get_registered_column_info,
                                      get_columns_info)
from egsim.smtk import (ground_motion_properties_required_by,
                        intensity_measures_defined_for)
from egsim.smtk.converters import na_values, array2json
from egsim.smtk.flatfile import ColumnDtype, get_dtype_of


class FlatfileMetadataInfoForm(GsimImtForm, APIForm):
    """Form for querying the necessary metadata columns from a given list of Gsims"""

    accept_empty_gsim_list = True  # see GsimImtForm  # FIXME: remove class level attrs, simpler?  # noqa
    accept_empty_imt_list = True

    def output(self) -> dict:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        cleaned_data = self.cleaned_data
        gsims = list(cleaned_data.get('gsim', {}))
        if not gsims:
            gsims = list(models.Gsim.names())
        gm_props = ground_motion_properties_required_by(*gsims, as_ff_column=True)
        imts = list(cleaned_data.get('imt', []))

        if not imts:
            imts = set()
            for m in gsims:
                imts |= intensity_measures_defined_for(m)

        return {
            'columns': [get_registered_column_info(c)
                        for c in sorted(set(gm_props) | set(imts))]
        }


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

    def output(self) -> dict:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
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


class Plotly:
    """
    Plotly utilities. for ref, see:
    https://plotly.com/javascript/reference/
    """

    @classmethod
    def get_histogram_plot(
            cls,
            values: pd.Series,
            on_x=True,
            histnorm = '',  # "" | "percent" | "probability" | "density" | "probability density"
            max_bins=20
    ) -> tuple[list[dict], dict]:
        lbl = 'x' if on_x else 'y'
        data, layout = cls.get_default_data_and_layout(1)
        na_vals = na_values(values)
        vals = values[~na_vals]
        trace = data[0]
        trace[lbl] = cls.array2json(vals)
        trace['type'] = 'histogram'
        trace['histnorm']: histnorm
        if values.name:
            trace['name'] = values.name
            trace['legendgroup'] = values.name
        categories = cls.get_categories(vals)
        if categories:
            layout[f'{lbl}axis']['categoryarray'] = categories
            layout[f'{lbl}axis']['categoryorder'] = 'array'
        else:
            trace[f'nbins{lbl}'] = max_bins
        return data, layout

    @classmethod
    def get_scatter_plot(
            cls,
            x_values: pd.Series,
            y_values:pd.Series
    ) -> tuple[list[dict], dict]:
        data, layout = cls.get_default_data_and_layout(1)
        na_vals = na_values(x_values) | na_values(y_values)
        x_vals = x_values[~na_vals]
        categories = cls.get_categories(x_vals)
        if categories:
            layout['xaxis']['categoryarray'] = categories
            layout['xaxis']['categoryorder'] = 'array'
        y_vals = y_values[~na_vals]
        categories = cls.get_categories(y_vals)
        if categories:
            layout['yaxis']['categoryarray'] = categories
            layout['yaxis']['categoryorder'] = 'array'
        trace = data[0]
        trace['x'] = cls.array2json(x_vals)
        trace['y'] = cls.array2json(y_vals)
        trace['type'] = 'scatter'
        trace['mode'] = 'markers'
        if y_values.name:
            trace['name'] = y_values.name
            trace['legendgroup'] = y_values.name
        return data, layout

    @classmethod
    def get_line_plot(
            cls,
            x_values: pd.Series,  # <- must be sorted, must be numeric
            *y_values:pd.Series
    ) -> tuple[list[dict], dict]:
        data, layout = cls.get_default_data_and_layout(len(y_values))
        na_vals = na_values(x_values)
        for _ in y_values:
            na_vals |= na_values(_)
        x_vals = x_values[~na_vals]
        for trace, y_vals in zip(data, y_values):
            trace['x'] = cls.array2json(x_vals)
            y_vals = y_vals[~na_vals]
            trace['y'] = cls.array2json(y_vals)
            trace['type'] = 'scatter'
            trace['mode'] = 'markers' if len(y_vals) == 1 else 'lines'
            if y_vals.name:
                trace['name'] = y_vals.name
                trace['legendgroup'] = y_vals.name

        return data, layout

    @classmethod
    def get_default_data_and_layout(cls, n_traces=1) -> tuple[list[dict], dict]:
        layout = {
            'xaxis': {
                'title': '',
                'type': 'linear'
            },
            'yaxis': {
                'title': '',
                'type': 'linear'
            }
        }
        data = [{'x': [], 'y': [], 'type': ''}] * n_traces
        return data, layout

    @classmethod
    def array2json(cls, notna_values: pd.Series) -> list:
        if get_dtype_of(notna_values) == ColumnDtype.datetime:
            # make format recognizable by plotly:
            # (note: to_datetime(series) > series,
            # to_datetime(ndarray) > DatetimeIndex)
            values = pd.to_datetime(notna_values.values)
            return values.strftime('%Y-%m-%dT%H:%M:%S').tolist()
        return array2json(notna_values, False)

    @classmethod
    def get_categories(cls, notna_values:pd.Series) -> list:
        is_bool = get_dtype_of(notna_values) == ColumnDtype.bool
        is_categ = get_dtype_of(notna_values) == ColumnDtype.category
        is_str = get_dtype_of(notna_values) == ColumnDtype.str
        if is_categ or is_bool or is_str:
            if is_bool:
                return [False, True]
            elif is_str:
                return sorted(pd.unique(notna_values).tolist())
            else:
                return sorted(values.dtype.categories.tolist())  # noqa
        return []


class FlatfileValidationForm(APIForm, FlatfileForm):
    """Form for flatfile validation, on success
    return info from a given uploaded flatfile"""

    def clean(self):
        cleaned_data = super().clean()

        if self.has_error('flatfile'):
            return cleaned_data
        dataframe = cleaned_data['flatfile']
        # check invalid columns (FIXME: we could skip this, it's already checked? write a test):
        invalid = set(dataframe.columns) - \
                  set(_['name'] for _ in get_columns_info(dataframe))
        if invalid:
            self.add_error('flatfile',
                           f'Invalid data type in column(s):  {", ".join(invalid)}')
        return cleaned_data

    def output(self) -> dict:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        cleaned_data = self.cleaned_data
        dataframe = cleaned_data['flatfile']

        return {
            'columns': get_columns_info(dataframe)
        }
