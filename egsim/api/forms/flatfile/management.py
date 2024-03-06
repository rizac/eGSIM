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
    Plotly utilities o create plots from pandas DataFrames.
    For ref, see: https://plotly.com/javascript/reference/
    """

    @classmethod
    def get_trace(
            cls, *,
            x: Optional[pd.Series] = None,
            y: Optional[pd.Series] = None,
            **kwargs: Optional[dict]
    ) -> dict:
        """Return a dict representing a Plotly trace in Javascript. The dict keys
        `x`, `y` and `type` and `mode` set according to the passed `x` and `y` pandas
        Series, removing NaNs or Nones. In addition, the 'type' key will be set
        to 'histogram' if either `x` or `y` is None (but not both), and 'scatter'
        otherwise. For ref (to provide additional `kwargs`), see:
        https://plotly.com/javascript/reference/scatter/
        https://plotly.com/javascript/reference/histogram/
        """
        trace = {k: v for k, v in kwargs.items()}
        if x is None and y is None:
            trace.setdefault('x', [])
            trace.setdefault('y', [])
            trace.setdefault('type', 'scatter')
        elif x is not None and y is None:
            trace.setdefault('x', cls.array2json(x[~na_values(x)]))
            trace.setdefault('type', 'histogram')
        elif y is not None and x is None:
            trace.setdefault('y', cls.array2json(y[~na_values(y)]))
            trace.setdefault('type', 'histogram')
        else:
            na_vals = na_values(x) | na_values(y)
            trace.setdefault('x', cls.array2json(x[~na_vals]))
            trace.setdefault('y', cls.array2json(y[~na_vals]))
            trace.setdefault('type', 'scatter')
            trace.setdefault('mode', 'markers' if len(trace['x']) == 1 else 'lines')
        return trace

    @classmethod
    def get_layout(
            cls,
            x: Optional[pd.Series] = None,
            y: Optional[pd.Series] = None,
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
    def set_axis(cls, axis: dict, values: Optional[pd.Series] = None):
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
                axis.setdefault('range', computed_range)

    @classmethod
    def harmonize_axis_ranges(cls, axis: list[dict], margin=0.01):
        mins, maxs = [], []
        for axs in axis:
            range = axs.get('range', None)
            if range is None:
                return
            mins.append(range[0])
            maxs.append(range[1])

        min_ = min(mins)
        max_ = max(maxs)
        delta = margin * (max_ - min_)
        for axs in axis:
            axs['range'] = [min_ - delta, max_ + delta]

    class AxisType:
        linear = 'linear'
        log = 'log'
        date = 'date'
        category = 'category'
        infer = '-'  # FIXME REF

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


        # 		this.colors = {


# 			_i: -1,
# 			_values: [
# 				'#1f77b4',  // muted blue
# 				'#ff7f0e',  // safety orange
# 				'#2ca02c',  // cooked asparagus green
# 				'#d62728',  // brick red
# 				'#9467bd',  // muted purple
# 				'#8c564b',  // chestnut brown
# 				'#e377c2',  // raspberry yogurt pink
# 				'#7f7f7f',  // middle gray
# 				'#bcbd22',  // curry yellow-green
# 				'#17becf'   // blue-teal
# 			],
# 			_cmap: {},
# 			get(key){  // return a new color mapped to key. Subsequent calls with `key` as argument return the same color
# 				if (!(key in this._cmap)){
# 					this._cmap[key] = this._values[(++this._i) % this._values.length];
# 				}
# 				return this._cmap[key];
# 			},
# 			rgba(hexcolor, alpha) {
# 				// Returns the corresponding 'rgba' string of `hexcolor` with the given alpha channel ( in [0, 1], 1:opaque)
# 				if (hexcolor.length == 4){
# 					var [r, g, b] = Array.from(hexcolor.substring(1)).map(h => h+h);
# 				}else if(hexcolor.length == 7){
# 					var [r, g, b] = [hexcolor.substring(1, 3), hexcolor.substring(3, 5), hexcolor.substring(5, 7)];
# 				}else{
# 					return hexcolor;
# 				}
# 				var [r, g, b] = [parseInt(r, 16), parseInt(g, 16), parseInt(b, 16)];
# 				return `rgba(${r}, ${g}, ${b}, ${alpha})`;
# 			}
# 		};

    # FIXME REMOVE
    # @classmethod
    # def get_histogram_plot(
    #         cls,
    #         values: pd.Series,
    #         on_x=True,
    #         # histnorm = '',  # "" | "percent" | "probability" | "density" | "probability density"
    #         # max_bins=20,
    #         default_trace: Optional[dict] = None,
    #         default_layout: Optional[dict] = None
    # ) -> tuple[list[dict], dict]:
    #     trace = default_trace or {}
    #     layout = default_layout or {}
    #     lbl = 'x' if on_x else 'y'
    #     # data, layout = cls.get_default_data_and_layout(1)
    #     na_vals = na_values(values)
    #     vals = values[~na_vals]
    #     trace.setdefault(lbl, cls.array2json(vals))
    #     trace.setdefault('type', 'histogram')
    #     # trace.setdefault('histnorm', histnorm)
    #     # if values.name:
    #     #    trace['name'] = values.name
    #     #    trace['legendgroup'] = values.name
    #     categories = cls.get_categories(vals)
    #     if categories:
    #         layout.setdefault(f'{lbl}axis', {}).setdefault('categoryarray', categories)
    #         layout.setdefault(f'{lbl}axis', {}).setdefault('categoryorder', 'array')
    #     # else:
    #     #     trace[f'nbins{lbl}'] = max_bins
    #     return [trace], layout
    #
    # @classmethod
    # def get_scatter_plot(
    #         cls,
    #         x_values: pd.Series,
    #         y_values:pd.Series,
    #         default_trace: Optional[dict] = None,
    #         default_layout: Optional[dict] = None
    # ) -> tuple[list[dict], dict]:
    #     trace = default_trace or {}
    #     layout = default_layout or {}
    #     na_vals = na_values(x_values) | na_values(y_values)
    #     x_vals = x_values[~na_vals]
    #     categories = cls.get_categories(x_values)
    #     if categories:
    #         layout.setdefault('xaxis', {}).setdefault('categoryarray', categories)
    #         layout.setdefault('xaxis', {}).setdefault('categoryorder', 'array')
    #     y_vals = y_values[~na_vals]
    #     categories = cls.get_categories(y_vals)
    #     if categories:
    #         layout.setdefault('yaxis', {}).setdefault('categoryarray', categories)
    #         layout.setdefault('yaxis', {}).setdefault('categoryorder', 'array')
    #     trace.setdefault('x', cls.array2json(x_vals))
    #     trace.setdefault('y', cls.array2json(y_vals))
    #     trace.setdefault('type', 'scatter')
    #     trace.setdefault('mode', 'markers')
    #     return [trace], layout
    #
    # @classmethod
    # def get_line_plot(
    #         cls,
    #         x_values: pd.Series,  # <- must be sorted, must be numeric
    #         y_values:pd.Series,
    #         default_trace: Optional[dict] = None,
    #         default_layout: Optional[dict] = None
    # ) -> tuple[list[dict], dict]:
    #     # data, layout = cls.get_default_data_and_layout(len(y_values))
    #     trace = default_trace or {}
    #     layout = default_layout or {}
    #     na_vals = na_values(x_values) | na_values(y_values)
    #     # for _ in y_values:
    #     #     na_vals |= na_values(_)
    #     x_vals = x_values[~na_vals]
    #     # for trace, y_vals in zip(data, y_values):
    #     trace.setdefault('x', cls.array2json(x_vals))
    #     y_vals = y_values[~na_vals]
    #     trace.setdefault('y', cls.array2json(y_vals))
    #     trace.setdefault('type', 'scatter')
    #     trace.setdefault('mode', 'markers' if len(y_vals) == 1 else 'lines')
    #     return [trace], layout
    #
    # @classmethod
    # def get_default_data_and_layout(cls, n_traces=1) -> tuple[list[dict], dict]:
    #     layout = {
    #         'xaxis': {
    #             'title': '',
    #             'type': 'linear'
    #         },
    #         'yaxis': {
    #             'title': '',
    #             'type': 'linear'
    #         }
    #     }
    #     data = [{'x': [], 'y': [], 'type': ''}] * n_traces
    #     return data, layout


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
