"""
Plotly utilities o create JavaScript plots from pandas DataFrames.
For ref, see: https://plotly.com/javascript/reference/
"""
import pandas as pd
import numpy as np
from typing import Optional, Union
from collections.abc import Iterable, Iterator

from egsim.smtk.converters import array2json, datetime2str
from egsim.smtk.flatfile import ColumnDtype, get_dtype_of


class AxisType:
    """Container for Plotly axis types supported by this program. For info see:
    https://plotly.com/javascript/reference/layout/xaxis/#layout-xaxis-type
    """
    linear = 'linear'
    log = 'log'
    date = 'date'
    category = 'category'
    infer = '-'


def axis_type(values: Optional[Union[np.ndarray, pd.Series]]) -> str:
    """Return the Plotly axis type (str) to display the given values. See `AxisType`"""
    dtype = get_dtype_of(values)
    if dtype in (ColumnDtype.int, ColumnDtype.float):
        return AxisType.linear
    elif dtype in (ColumnDtype.bool, ColumnDtype.category, ColumnDtype.str):
        return AxisType.category
    elif dtype == ColumnDtype.datetime:
        return AxisType.date
    return AxisType.infer


def colors_cycle(hex_colors: Optional[Iterable[str]] = None) -> Iterator[str]:
    """endless iterator cycling through default colors in `rgba(...)` form """
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


def values2json(values: Union[np.ndarray, pd.Series]) -> list:
    """Converter from numpy/pandas array to plotly compatible list"""
    if axis_type(values) == AxisType.date:  # plotly wants ISO strings
        values = datetime2str(values, '%Y-%m-%dT%H:%M:%S')
    return array2json(values)


def axis_range(
        values: Union[np.ndarray, pd.Series],
        margin=0.1) -> Union[list, None]:
    """Compute the optimal axis range for the given values

    :param values: the numpy array / pandas Series whose values should be
        displayed on the given axis
    :param margin: optional margin to slightly expand computed min and max for
        better visualization of data, in [0, 1] which is a sort of fraction of
        the data range
    """
    min_, max_ = np.inf, -np.inf
    atype = axis_type(values)
    if atype not in (AxisType.linear, AxisType.log, AxisType.date):
        return None
    if len(values):
        # use nanmin/max if available (numpy), and min otherwise (pandas):
        min_ = getattr(values, 'nanmin', getattr(values, 'min'))()
        max_ = getattr(values, 'nanmax', getattr(values, 'max'))()
        if margin > 0:
            if atype == AxisType.date:
                margin *= (max_ - min_)/2.0
            else:
                # avoid crossing the 0-axis which might lead to problems in log display:
                if np.abs(min_) < np.abs(max_):  # min is closest to zero
                    margin *= min_
                else:  # max is closest to zero:
                    margin *= max_
            min_ -= margin
            max_ += margin
    if min_ >= max_:
        return None
    return values2json(pd.Series([min_, max_], dtype=values.dtype))


def scatter_trace(
        *,
        color: str,
        size=10,
        symbol='circle',
        line_color=None,
        line_width=0,
        # line_dash='solid',
        **kwargs) -> dict:
    """Return the properties and style for a trace of type scatter"""
    if 'x' in kwargs:
        kwargs['x'] = values2json(kwargs['x'])
    if 'y' in kwargs:
        kwargs['y'] = values2json(kwargs['y'])
    return {
        'type': 'scatter',
        'mode': 'markers',
        'marker': {
            'size': size,
            'color': color,
            'symbol': symbol,
            'line': {
                'width': line_width,
                'color': line_color or color,
                # 'dash': line_dash  # invalid in marker.Line (Python)
            }
        }
    } | kwargs


def line_trace(*, color: str, width=2, dash='solid', **kwargs) -> dict:
    """Return the properties and style for a trace of type scatter (lines only)"""
    if 'x' in kwargs:
        kwargs['x'] = values2json(kwargs['x'])
    if 'y' in kwargs:
        kwargs['y'] = values2json(kwargs['y'])
    return {
        'type': 'scatter',
        'mode': 'lines',
        'line': {
            'width': width,
            'color': color,
            'dash': dash
        },
    } | kwargs


def bar_trace(
        *,
        color: str,
        line_width=2,
        line_dash='solid',
        line_color=None,
        **kwargs) -> dict:
    """Return the properties and style for a trace of type bar"""
    return _bar_like_trace(
        color, 'bar', line_width, line_dash, line_color, **kwargs)


def histogram_trace(
        *,
        color: str,
        line_width=2,
        line_dash='solid',
        line_color=None,
        **kwargs) -> dict:
    """Return the properties and style for a trace of type histogram"""
    return _bar_like_trace(
        color, 'histogram', line_width, line_dash, line_color, **kwargs)


def _bar_like_trace(
        color: str,
        typ: str,
        width: float,
        dash: str,
        line_color=None,
        **kwargs) -> dict:
    if 'x' in kwargs:
        kwargs['x'] = values2json(kwargs['x'])
    if 'y' in kwargs:
        kwargs['y'] = values2json(kwargs['y'])
    return {
        'type': typ,
        'marker': {
            'color': color,
            'line': {
                'width': width,
                'color': line_color or color,
                # 'dash': dash   # invalid in marker.Line (Python)
            }
        }
    } | kwargs
