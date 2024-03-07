"""
Django Forms for eGSIM flatfile compilation (inspection, plot, upload)

@author: riccardo
"""
from typing import Union, Optional
from collections.abc import Iterable, Iterator

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
        c = next(Plotly.colors_cycle())
        if x and y:  # scatter plot
            xlabel, ylabel = cleaned_data['x'], cleaned_data['y']
            x, y = dataframe[xlabel], dataframe[ylabel]
            # x_na = na_values(x).sum()
            # y_na = na_values(y).sum()
            layout = {
                'xaxis': {
                    'title': xlabel
                },
                'yaxis': {
                    'title': ylabel
                }
            }
            plot = {
                'data': [Plotly.scatter_trace(c) | {
                    'x': Plotly.array2json(dataframe[xlabel]),
                    'y': Plotly.array2json(dataframe[ylabel])
                }],
                'params': {},
                'layout': Plotly.get_layout(x=x, y=y, **layout)
            }
        elif x:
            xlabel = cleaned_data['x']
            layout = {
                'xaxis': {
                    'title': xlabel
                },
                'yaxis': {
                    'title': 'Frequency',
                    'type': Plotly.AxisType.linear
                }
            }
            plot = {
                'data': [Plotly.histogram_trace(c) | {
                    'x': Plotly.array2json(dataframe[xlabel])
                }],
                'params': {},
                'layout': Plotly.get_layout(x=x, **layout)
            }
        else:  # y only provided
            ylabel = cleaned_data['y']
            layout = {
                'xaxis': {
                    'title': 'Frequency',
                    'type': Plotly.AxisType.linear
                },
                'yaxis': {
                    'title': ylabel
                }
            }
            plot = {
                'data': [Plotly.histogram_trace(c) | {
                    'y': Plotly.array2json(dataframe[ylabel])
                }],
                'params': {},
                'layout': Plotly.get_layout(y=y, **layout)
            }

        return {'plots': [plot]}


class Plotly:
    """
    Plotly utilities o create plots from pandas DataFrames.
    For ref, see: https://plotly.com/javascript/reference/
    """

    @classmethod
    def array2json(cls, values: Union[list, np.ndarray, pd.Series]) -> list:
        """Converter from python/numpy/pandas array to plotly compatible list"""
        if get_dtype_of(values) == ColumnDtype.datetime:  # date times as ISO strings
            if isinstance(values, pd.Series):
                values = values.values
            # Note: to_datetime(series) > series,
            # to_datetime(ndarray or list) > DatetimeIndex.
            # In the latter case we can use strftime (which will also preserve
            # NAs, so pd.isna will work on it):
            values = pd.to_datetime(values).strftime('%Y-%m-%dT%H:%M:%S')
        return array2json(values)

    @classmethod
    def get_layout(
            cls,
            x: Optional[Union[np.ndarray, pd.Series]] = None,
            y: Optional[Union[np.ndarray, pd.Series]] = None,
            **kwargs
    ) -> dict:
        """Return a dict representing a Plotly layout in Javascript. The dict keys
        `xaxis`, `yaxis` will be set according to the passed `x` and `y` pandas
        Series, which represent the plotted data. In paticular the 'xaxis' and
        'yaxis' 'type' key will be set to 'category', 'linear', 'date' or '-' (infer)
        For ref (to provide additional `kwargs`), see:
        https://plotly.com/javascript/reference/layout/
        """
        layout = {k: v for k, v in kwargs.items()}
        layout.setdefault('xaxis', {})
        cls.set_axis(layout['xaxis'], x)
        layout.setdefault('yaxis', {})
        cls.set_axis(layout['yaxis'], y)
        return layout

    @classmethod
    def set_axis(cls, axis: dict, values: Optional[Union[np.ndarray, pd.Series]] = None):
        axis.setdefault('title', '')
        axis.setdefault('autorange', True)  # same as missing, but provide it explicitly
        if values is not None:
            categories = cls.get_categories(values)
            computed_range = None
            if categories:
                axis.setdefault('type', cls.AxisType.category)
                axis.setdefault('categoryarray', categories)
                axis.setdefault('categoryorder', 'array')
            elif get_dtype_of(values) == ColumnDtype.datetime:
                axis.setdefault('type', cls.AxisType.date)
                computed_range = [values.min(), values.max()]
            elif get_dtype_of(values) in (ColumnDtype.int, ColumnDtype.float):
                axis.setdefault('type', cls.AxisType.linear)
                computed_range = [values.min(), values.max()]
            else:
                axis.setdefault('type', cls.AxisType.infer)  # infer from data
            if computed_range is not None and pd.notna(computed_range).all():
                delta = 0.02 * (computed_range[1] - computed_range[0])
                computed_range = [computed_range[0] - delta, computed_range[1] + delta]
                axis.setdefault('range', cls.array2json(computed_range))

    class AxisType:
        linear = 'linear'
        log = 'log'
        date = 'date'
        category = 'category'
        infer = '-'  # FIXME REF

    @classmethod
    def get_categories(cls, values:pd.Series) -> list:
        """Return the categories (as list) of the given values. This includes
        the given categories in case of pandas categorical data, but also
        the unique values in case of strings, and the list [False, True] in
        case of bool"""
        categ_dtype = get_dtype_of(values)
        if categ_dtype == ColumnDtype.bool:
            return [False, True]
        elif categ_dtype == ColumnDtype.str:
            categs = pd.unique(values)
            categs = categs[~na_values(categs)]
            return sorted(categs.tolist())
        elif categ_dtype == ColumnDtype.category:
            return sorted(values.dtype.categories.tolist())  # noqa
        return []

    @classmethod
    def colors_cycle(cls, hex_colors: Optional[Iterable[str]] = None) -> Iterator[str]:
        """endless iterator providing colors in `rgba(...)` form """

        values = []
        if hex_colors is None:
            hex_colors = [
                '#1f77b4',  # muted blue
                '#ff7f0e',  # safety orange
                '#2ca02c',  # cooked asparagus green
                '#d62728',  # brick red
                '#9467bd',  # muted purple
                '#8c564b',  # chestnut brown
                '#e377c2',  # raspberry yogurt pink
                '#7f7f7f',  # middle gray
                '#bcbd22',  # curry yellow-green
                '#17becf'  # blue-teal
            ]
        for hex_c in hex_colors:
            rgba = [int(hex_c[1:][i:i + 2], 16) for i in (0, 2, 4)]
            rgba = ", ".join(str(_) for _ in rgba)
            values.append(f'rgba({rgba}, 1)')
        from itertools import cycle
        return cycle(values)

    @classmethod
    def scatter_trace(cls, rgba_color: str) -> dict:
        """Return the properties and style for a trace of type scatter (no lines)"""
        return {
            'type': 'scatter',
            'mode': 'markers',
            'marker': {
                'size': 10,
                'color': rgba_color.replace(', 1)', ', 0.5)'),
                'symbol': "circle",
                'line': {
                    'width': 0,
                    'color': rgba_color,
                    'dash': 'solid'
                }
            }
        }

    @classmethod
    def line_trace(cls, rgba_color: str) -> dict:
        """Return the properties and style for a trace of type scatter (lines only)"""
        return {
            'type': 'scatter',
            'mode': 'lines',
            'line': {
                'width': 2,
                'color': rgba_color,
                'dash': 'dot'
            },
        }

    @classmethod
    def bar_trace(cls, rgba_color:str) -> dict:
        """Return the properties and style for a trace of type bar"""
        return cls._bar_like_trace(rgba_color, 'bar')

    @classmethod
    def histogram_trace(cls, rgba_color: str) -> dict:
        """Return the properties and style for a trace of type histogram"""
        return cls._bar_like_trace(rgba_color, 'histogram')

    @classmethod
    def _bar_like_trace(cls, rgba_color: str, type: str) -> dict:

        return {
            'type': type,
            'marker': {
                'color': rgba_color.replace(', 1)', ', 0.5)'),
                'line': {
                    'width': 2,
                    'color': rgba_color,
                    'dash': 'solid'
                }
            }
       }


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
