"""Forms handling data (flatfiles)"""
import numpy as np
import pandas as pd
from scipy.stats import linregress

from egsim.api.forms import APIForm
from egsim.api.forms.flatfile import FlatfileForm
from egsim.api.forms.residuals import ResidualsForm
from egsim.api.forms.scenarios import PredictionsForm
from django.forms.fields import ChoiceField, CharField

from egsim.smtk.flatfile import ColumnType
from egsim.smtk.registry import Clabel
from egsim.smtk.validators import sa_period
from .plotly import (colors_cycle, axis_type, axis_range, scatter_trace,
                     bar_trace, line_trace, histogram_trace, AxisType)
from ..smtk.converters import datetime2float


class PredictionsVisualizeForm(PredictionsForm):
    """Form returning predictions from configured scenarios in form of plots"""

    plot_type = ChoiceField(
        required=True, initial=None,
        choices=[
            ('m', 'IMT vs. Magnitude'),
            ('d', 'IMT vs. Distance'),
            ('s', 'Magnitude-Distance Spectra')
        ],
        help_text='the plot type to be displayed: ')

    def clean(self):
        cleaned_data = super().clean()
        if not self.has_error('plot_type') and cleaned_data['plot_type'] == 's':
            if not (all(_.startswith('SA(') for _ in cleaned_data['imt'])):
                self.add_error('imt', 'Only SA with period(s) allowed')
        return cleaned_data

    def output(self) -> dict:
        dataframe = super().output()
        dist_col_lbl_selector = (
            Clabel.input_data,
            ColumnType.distance.value,
            slice(None)
        )
        dist_col = dataframe.loc[:, dist_col_lbl_selector].columns[0]
        mag_col = (Clabel.input_data, ColumnType.rupture.value, Clabel.mag)
        mag_label = mag_col[-1].title()
        dist_label = dist_col[-1].title()
        imt_label = 'Imt'
        models = self.cleaned_data['gsim'].keys()  # sorted (see super.clean_gsim)
        imts = self.cleaned_data['imt'].keys()  # sorted (see super.clean_imt)

        if self.cleaned_data['plot_type'] == 'm':
            x_label = mag_label

            def y_label(imt):
                return f'Median {imt}'

            def groupby(dframe: pd.DataFrame):
                for dist, dfr in dframe.groupby(dist_col):
                    x = dfr[mag_col]
                    for i in imts:
                        p = {dist_label: dist, imt_label: i}
                        data = {}
                        for m in models:
                            if (i, Clabel.median, m) in dfr.columns:
                                data[m] = (
                                    dfr.loc[:, (i, Clabel.median, m)].values,
                                    dfr.loc[:, (i, Clabel.std, m)].values
                                )
                        yield p, x, data

        elif self.cleaned_data['plot_type'] == 'd':
            x_label = dist_label

            def y_label(imt):
                return f'Median {imt}'

            def groupby(dframe: pd.DataFrame):
                for mag, dfr in dframe.groupby(mag_col):
                    x = dfr[dist_col]
                    for i in imts:
                        p = {mag_label: mag, imt_label: i}
                        data = {}
                        for m in models:
                            if (i, Clabel.median, m) in dfr.columns:
                                data[m] = (
                                    dfr.loc[:, (i, Clabel.median, m)].values,
                                    dfr.loc[:, (i, Clabel.std, m)].values
                                )
                        yield p, x, data

        else:
            x_label = 'Period (s)'

            def y_label(imt):  # noqa
                return 'SA (g)'

            # imts is a dict[str, IMT] of sorted SA(p) (see super.clean_imt and
            # self.clean) rename it as `sas` just for clarity:
            sas = imts

            x_values = [float(sa_period(_)) for _ in sas]

            def groupby(dframe: pd.DataFrame):
                for (d, mag), dfr in dframe.groupby([dist_col, mag_col]):
                    p = {mag_label: mag, dist_label: d, imt_label: 'SA'}
                    data = {}
                    for m in models:
                        data[m] = (
                            dfr.loc[:, (sas, Clabel.median, m)].iloc[0, :].values,
                            dfr.loc[:, (sas, Clabel.std, m)].iloc[0, :].values
                        )
                    yield p, x_values, data

        c_cycle = colors_cycle()
        colors = {m: next(c_cycle) for m in sorted(set(models))}
        plots = []
        for params, x_values, plot_data in groupby(dataframe):
            traces, layout = self.get_plot_traces_and_layout(
                x_values, plot_data, x_label, y_label(params[imt_label]),
                colors)
            plots.append({
                'data': traces,
                'params': params,
                'layout': layout
            })

        return {'plots': plots}

    @staticmethod
    def get_plot_traces_and_layout(x, y: dict[str, tuple], x_label, y_label,
                                   colors: dict[str, str]) -> tuple[list[dict], dict]:
        """
        Return the traces and layout for displaying prediction plots (using the
        JavaScript Plotly library). Traces is a list, where each Trace is a dict
        holding the data points and other data info (e.g. legend name, data name),
        layout is a dict of layout configuration, such as plot title, x- or y-axis
        range and type (log/linear)

        :param x: the x values (common to all traces)
        :param y: the y values, as dict. Each dict key is a model name (str) and it's
            mapped to the model y values, as tuple of two elements: (medians, stddev),
            where medians and stddev are numeric arrays of the same length as `x`
        :param x_label: the x label (str)
        :param y_label: the y label (str)
        :param colors: a dict of model names mapped to their rgba color (str). Each
            color must be a str in the form "rgba(<r>, <g>, <b>, 1)"
            (as returned e.g. by `plotly.colors_cycle`)
        """
        traces = []
        ys = []
        for model, [medians, sigmas] in y.items():
            color = colors[model]
            color_transparent = color.replace(', 1)', ', 0.1)')
            legendgroup = model
            # first add all values to list so that we can compute ranges later
            # TODO add Graeme if this is ok (np.exp I mean, legacy code from smtk)
            ys.append(np.exp(medians))
            ys.append(np.exp(medians + sigmas))
            ys.append(np.exp(medians - sigmas))
            # now add those values to plotly traces:
            traces.extend([
                line_trace(
                    color=color,
                    x=x,
                    y=ys[-3],
                    name=model,
                    legendgroup=legendgroup
                ),
                line_trace(
                    width=0,
                    color=color_transparent,
                    fillcolor=color_transparent,
                    x=x,
                    y=ys[-2],
                    name=model + ' stddev',
                    legendgroup=legendgroup + ' stddev'
                ),
                line_trace(
                    width=0,
                    color=color_transparent,
                    fillcolor=color_transparent,
                    fill='tonexty',
                    # https://plotly.com/javascript/reference/scatter/#scatter-fill  # noqa
                    x=x,
                    y=ys[-1],
                    name=model + ' stddev',
                    legendgroup=legendgroup + ' stddev'
                )]
            )

        layout = {
            'xaxis': {
                'title': x_label,
                'type': 'linear',
                'autorange': True
            },
            'yaxis': {
                'title': y_label,
                'type': 'log',
                'autorange': True,
                'range': axis_range(np.concatenate(ys).ravel()),
            }
        }

        return traces, layout


class ResidualsVisualizeForm(ResidualsForm):
    """Form returning residuals in form of plots"""

    x = CharField(required=False, initial=None,
                  help_text='the flatfile field to use for plot, or None/null: in '
                            'this latter case a histogram will be returned '
                            'depending on the value of the param. likelihood '
                            '(True: LH values, else: residuals Z values)')

    def clean(self):
        cleaned_data = super().clean()
        if not self.has_error('flatfile') and cleaned_data.get('x', None) \
                and cleaned_data['x'] not in cleaned_data['flatfile'].columns:
            self.add_error('x', 'not a flatfile column')
        return cleaned_data

    def output(self) -> dict:
        """
        produce the plot output (see superclass method doc).
        On Flatfile errors, return None and add register the error
        (see `self.errors_json_data` for details) so that `self.is_valid=False`.
        """
        # residuals (x y): Frequency Z(<imt>)
        # likelihood (x y): Frequency LH(<imt>)
        # <ff_column> (x y): Z(<imt>) <ff_column>

        # remember: on the frontend:
        # - to enable the xaxis type checkbox: layoyt.xaxis.type must be 'log' or
        # 'linear' (same for layout.yaxis)
        # - to enable the xaxis sameRange checkbox: layout.xaxis.range must be defined
        # as 2-element list (same for yaxis)
        # Plotly.get_layout (see below) handles this automatically

        dataframe = super().output()
        col_x = self.cleaned_data.get('x', "")
        likelihood = self.cleaned_data.get('likelihood', False)
        c_cycle = colors_cycle()
        colors = {}

        plots = {}  # will be returned as list (taking the dict values)

        total_res, intra_res, inter_res = \
            (Clabel.total_res, Clabel.intra_ev_res, Clabel.inter_ev_res)
        if likelihood:
            total_res, intra_res, inter_res = \
                (Clabel.total_lh, Clabel.intra_ev_lh, Clabel.inter_ev_lh)
        res_columns = {total_res, intra_res, inter_res}
        residual_label = {
            total_res: 'Total',
            intra_res: 'Intra event',
            inter_res: 'Inter event'
        }

        for col in dataframe.columns:
            if col[1] not in res_columns:
                continue
            imt, res_type, model = col

            if not col_x:  # histogram (residuals or LH):
                x = dataframe[col]
                y = None
            else:
                x = self.cleaned_data['flatfile'][col_x]
                y = dataframe[col]

            color = colors.setdefault(model, next(c_cycle))
            data, layout = self.get_plot_traces_and_layout(model, imt, x, y,
                                                           likelihood, col_x, color)

            # provide a key that is comparable for sorting the plots. Note that imt
            # is separated into name and period (so that "SA(9)" < "SA(10)") and that
            # "Total" residual is set as "" to appear in front of all other residuals:
            key = [
                imt if sa_period(imt) is None else 'SA',  # imt name
                sa_period(imt) or -1,  # SA period (or -1 for all others)
                model,  # model name
                '' if res_type == total_res else res_type  # resid. type ("Total"="")
            ]
            plots[tuple(key)] = {
                'data': data,
                'params': {
                    'model': model,
                    'imt': imt,
                    'residual type': residual_label[res_type]
                },
                'layout': layout
            }

            # if we are processing total residuals, also set intra and inter
            # defaults as empty plot. If intra and inter were already (or will be )
            # processed, the  skip this
            if res_type == total_res:
                for r_type in (intra_res, inter_res):
                    key[-1] = r_type
                    plots.setdefault(tuple(key), {
                        'data': [{}],
                        'params': {
                            'model': model,
                            'imt': imt,
                            'residual type': residual_label[r_type]
                        },
                        'layout': dict(layout)
                    })

        # return keys sorted so that the frontend displays them accordingly:
        return {'plots': [plots[key] for key in sorted(plots.keys())]}

    @staticmethod
    def get_plot_traces_and_layout(model: str, imt: str, x, y, likelihood: bool,
                                   xlabel: str, color: str) -> tuple[list[dict], dict]:
        """
        Return the traces and layout for displaying prediction plots (using the
        JavaScript Plotly library). Traces is a list, where each Trace is a dict
        holding the data points and other data info (e.g. legend name, data name),
        layout is a dict of layout configuration, such as plot title,
        x- y-axis range and type (log/linear)

        :param model: the ground motion model name (str)
        :param imt: the intensity measure type (str)
        :param x: the x values
        :param y: the y values. If none, the plot type will be a histogram (display data
            distribution as bars). Otherwise, data will be displayed as scatter plot (a
            point for each (x, y) pair)
        :param likelihood: boolean denoting the histogram type:  likelihood (True) or
            standard residuals (False, the default)
        :param xlabel: the x-axis label (str). Only used for scatter plots
        :param color: a color (str) in the form "rgba(<r>, <g>, <b>, 1)"
            (as returned e.g. by `plotly.colors_cycle`)
        """
        if y is None:  # hist (residuals or LH)
            if not likelihood:

                def x_label(imt_):
                    return f'Z ({str(imt_)})'

                def y_label(imt_):  # noqa
                    return 'Frequency'

            else:

                def x_label(imt_):
                    return f'LH ({str(imt_)})'

                def y_label(imt_):  # noqa
                    return 'Frequency'

        else:
            def x_label(imt_):  # noqa
                return xlabel

            def y_label(imt_):
                return f'Z ({str(imt_)})'

        # c_cycle = colors_cycle()
        # colors = {}
        # color = colors.setdefault(model, next(c_cycle))
        color_transparent = color.replace(', 1)', ', 0.5)')
        layout = {
            'xaxis': {
                'title': x_label(imt),
                'autorange': True
            },
            'yaxis': {
                'title': y_label(imt),
                'autorange': True
            }
        }
        trace_name = f'{imt} {model}'
        if y is None:  # residuals hist or likelihood hist
            if not likelihood:
                step = 0.5
            else:
                step = 0.1
            bins = np.arange(x.min(), x.max() + step, step)
            y = np.histogram(x, bins, density=True)[0]
            data = [bar_trace(
                color=color_transparent,
                line_color=color,
                x=bins[:-1],
                y=y,
                name=trace_name,
                legendgroup=model
            )]

            if not likelihood:
                mean, std = x.mean(), x.std(ddof=0)
                x_ = np.arange(mean - 3 * std, mean + 3 * std, step / 10)
                data.append(
                    line_trace(
                        color=color,
                        x=x_,
                        y=normal_dist(x_, mean, std),
                        name=f'{trace_name} normal distribution',
                        legendgroup=f'{model} normal distribution',
                    )
                )
                data.append(
                    line_trace(
                        color="rgba(120, 120, 120, 1)",
                        dash='dot',
                        x=x_,
                        y=normal_dist(x_),
                        name='Standard normal distribution (m=0, s=1)',
                        legendgroup='Standard normal distribution',
                    )
                )
        else:
            data = [scatter_trace(
                color=color_transparent,
                x=x,
                y=y,
                name=trace_name,
                legendgroup=model
            )]
            linreg = lin_regr(x, y)
            if linreg:
                data.append(
                    line_trace(
                        color="rgba(120, 120, 120, 1)",
                        dash='dot',
                        width=3,
                        x=linreg["x"],
                        y=linreg["y"],
                        name=f'Slope: {linreg["slope"]:.2f}<br>'
                             f'P-value: {linreg["pvalue"]:.2f} ',
                        legendgroup='Linear regression',
                    )
                )

        # config layout axis based on the displayed values:
        for values, axis in ((x, layout['xaxis']), (y, layout['yaxis'])):
            axis['type'] = axis_type(values)
            rng = axis_range(values)
            if rng is not None:
                axis['range'] = rng

        return data, layout


def normal_dist(x, mean=0, sigma=1) -> np.ndarray:
    from scipy.constants import pi
    sigma_square_times_two = 2 * (sigma ** 2)
    norm = 1. / np.sqrt(pi * sigma_square_times_two)
    return norm * np.exp(-((x - mean) ** 2) / sigma_square_times_two)


def lin_regr(x, y, n_pts=10) -> dict:
    if len(x) < 2 or len(y) < 2:
        return {}
    x_type = axis_type(x)
    y_type = axis_type(y)
    x_ok = x_type in (AxisType.linear, AxisType.date)
    y_ok = y_type in (AxisType.linear, AxisType.date)
    if not y_ok or not x_ok:
        return {}
    x_ = datetime2float(x) if x_type == AxisType.date else x
    y_ = datetime2float(y) if y_type == AxisType.date else y
    finite = np.isfinite(x_) & np.isfinite(y_)
    if finite.sum() < 2:
        return {}
    result = linregress(x_[finite], y_[finite])
    xs = np.linspace(np.nanmin(x_), np.nanmax(x_), n_pts, endpoint=True)
    ys = [result.intercept + result.slope * x for x in xs]
    if x_type == AxisType.date:
        xs = pd.to_datetime(xs, unit='s')
    if y_type == AxisType.date:
        ys = pd.to_datetime(ys, unit='s')
    return {
        'slope': result.slope,
        'intercept': result.intercept,
        'x': xs,
        'y': ys,
        'pvalue': result.pvalue
    }


class FlatfileVisualizeForm(APIForm, FlatfileForm):
    """Form for plotting flatfile columns"""

    x = CharField(help_text="The flatfile column for the x values", required=False)
    y = CharField(help_text="The flatfile column for the y values", required=False)

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
        x_label, y_label = cleaned_data.get('x', None), cleaned_data.get('y', None)

        data, layout = self.get_plot_traces_and_layout(
            dataframe[x_label] if x_label else None,
            dataframe[y_label] if y_label else None,
            x_label, y_label, next(colors_cycle())
        )
        plot = {
            'data': data,
            'params': {},
            'layout': layout
        }

        return {'plots': [plot]}

    @staticmethod
    def get_plot_traces_and_layout(x, y, x_label: str, y_label: str,
                                   color: str) -> tuple[list[dict], dict]:
        """
        Return the traces and layout for displaying prediction plots (using the
        JavaScript Plotly library). Traces is a list, where each Trace is a dict
        holding the data points and other data info (e.g. legend name, data name),
        layout is a dict of layout configuration, such as plot title,
        x- y-axis range and type (log/linear)

        :param x: the x values. If None, the plot type will be a histogram (display data
            distribution as bars on the y-axis, i.e. horizontal bars). Otherwise,
            data will be displayed as scatter plot (a point for each (x, y) pair)
        :param y: the y values. If None, the plot type will be a histogram (display data
            distribution as bars on the x-axis, i.e. vertical bars). Otherwise,
            data will be displayed as scatter plot (a point for each (x, y) pair)
        :param x_label: the x-axis label (str). Unused if x is None
        :param y_label: the y-axis label (str). Unused if y is None
        :param color: a color (str) in the form "rgba(<r>, <g>, <b>, 1)"
            (as returned e.g. by `plotly.colors_cycle`)
        """
        c_transparent = color.replace(', 1)', ', 0.5)')
        if x is not None and y is not None:  # scatter plot
            traces = [
                scatter_trace(
                    color=c_transparent,
                    x=x,
                    y=y,
                    legendgroup=f'{y_label} vs. {x_label}',
                    name=f'{y_label} vs. {x_label}'
                )
            ]
            layout = {
                'xaxis': {
                    'title': x_label,
                    'type': axis_type(x)
                },
                'yaxis': {
                    'title': y_label,
                    'type': axis_type(y)
                }
            }
        elif y is None:
            traces = [
                histogram_trace(
                    color=c_transparent,
                    line_color=color,
                    x=x,
                    legendgroup=x_label,
                    name=x_label
                )
            ]
            layout = {
                'xaxis': {
                    'title': x_label,
                    # 'type': axis_type(x)  # let plotly infer the axis type.
                    # Also, no explicit type disables the log scale checkbox in the
                    # frontend, which does not work as expected with histograms
                },
                'yaxis': {
                    'title': 'Frequency',
                    'type': AxisType.linear
                }
            }
        else:  # y only provided
            traces = [
                histogram_trace(
                    color=c_transparent,
                    line_color=color,
                    y=y,
                    legendgroup=y_label,
                    name=y_label
                )
            ]
            layout = {
                'xaxis': {
                    'title': 'Frequency',
                    'type': AxisType.linear
                },
                'yaxis': {
                    'title': y_label,
                    # 'type': axis_type(x)  # let plotly infer the axis type.
                    # Also, no explicit type disables the log scale checkbox in the
                    # frontend, which does not work as expected with histograms
                }
            }

        return traces, layout
