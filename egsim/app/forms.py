"""Forms handling data (flatfiles)"""
import numpy as np
import pandas as pd

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
            sas = imts.keys()

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
        colors = {}
        plots = []
        for params, x_values, plot_data in groupby(dataframe):
            traces = []
            ys = []
            for model, [medians, sigmas] in plot_data.items():
                color = colors.setdefault(model, next(c_cycle))
                color_transparent = color.replace(', 1)', ', 0.2)')
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
                        x=x_values,
                        y=ys[-3],
                        name=model,
                        legendgroup=legendgroup
                    ),
                    line_trace(
                        width=0,
                        color=color_transparent,
                        fillcolor=color_transparent,
                        x=x_values,
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
                        x=x_values,
                        y=ys[-1],
                        name=model + ' stddev',
                        legendgroup=legendgroup + ' stddev'
                    )]
                )

            plots.append({
                'data': traces,
                'params': params,
                'layout': {
                    'xaxis': {
                        'title': x_label,
                        'type': 'linear',
                        # 'autorange': True,
                        # 'range': axis_range(x_values)
                    },
                    'yaxis': {
                        'title': y_label(params[imt_label]),
                        'type': 'log',
                        # 'autorange': True,
                        'range': axis_range(np.concatenate(ys).ravel()),
                    }
                }
            })

        return {'plots': plots}


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
        """produce the plot output (see superclass method doc)"""
        # residuals (x y): Frequency Z(<imt>)
        # likelihood (x y): Frequency LH(<imt>)
        # <ff_column> (x y): Z(<imt>) <ff_column>

        # remember: on the frontend:
        # - to enable the xaxis type checkbox: layoyt.xaxis.type must be 'log' or
        # 'linear' (same for layout.yaxis)
        # - to enable the xaxis sameRange checkbox: layout.xaxis.range must be defined
        # as 2-element list (same for yaxis)
        # Plotly.get_layout (see below) handles this automatically
        df_labels = {
            Clabel.total_res: 'Total',
            Clabel.intra_ev_res: 'Intra event',
            Clabel.inter_ev_res: 'Inter event'
        }
        dataframe = super().output()
        col_x = self.cleaned_data.get('x', None)
        likelihood = self.cleaned_data.get('likelihood', False)
        if not col_x:
            if not likelihood:

                def x_label(imt_):
                    return f'Z ({str(imt_)})'

                def y_label(imt_):  # noqa
                    return 'Frequency'

            else:

                def x_label(imt_):
                    return f'Likelihood ({str(imt_)})'

                def y_label(imt_):  # noqa
                    return 'Frequency'

                df_labels = {
                    Clabel.total_lh: 'Total',
                    Clabel.intra_ev_lh: 'Intra event',
                    Clabel.inter_ev_lh: 'Inter event'
                }

        else:

            def x_label(imt_):  # noqa
                return self.cleaned_data['x']

            def y_label(imt_):
                return f'Z ({str(imt_)})'

        plots = []
        c_cycle = colors_cycle()
        colors = {}
        for col in [c for c in dataframe.columns if c[1] in df_labels]:
            imt, res_type, model = col
            color = colors.setdefault(model, next(c_cycle))
            color_transparent = color.replace(', 1)', ', 0.5)')
            layout = {
                'xaxis': {
                    'title': x_label(imt)
                },
                'yaxis': {
                    'title': y_label(imt)
                }
            }

            if not col_x:  # residuals hist or likelihood hist
                x = dataframe[col]
                if not likelihood:
                    step = 0.5
                else:
                    step = 0.1
                bins = np.arange(x.min(), x.max() + step, step)
                y = np.histogram(x, bins, density=True)[0]
                trace = bar_trace(
                    color=color_transparent,
                    line_color=color,
                    x=bins[:-1],
                    y=y,
                    name=" ".join(col),
                    legendgroup=model
                )
                data = [trace]

                if not likelihood:
                    mean, std = x.mean(), x.std()
                    x_ = np.arange(mean - 3 * std, mean + 3 * std, step / 10)
                    data.append(
                        line_trace(
                            color=color,
                            x=x_,
                            y=norm_dist(x_, mean, std),
                            name=" ".join(col) + ' normal distribution',
                            legendgroup=model + ' normal distribution',
                        )
                    )
                    data.append(
                        line_trace(
                            color="rgba(120, 120, 120, 1)",
                            dash='dot',
                            x=x_,
                            y=norm_dist(x_),
                            name='Normal distribution',
                            legendgroup='Normal distribution (m=0, s=1)',
                        )
                    )
            else:
                x = self.cleaned_data['flatfile'][col_x]
                y = dataframe[col]
                trace = scatter_trace(
                    color=color_transparent,
                    x=x,
                    y=y,
                    name=" ".join(col),
                    legendgroup=model
                )
                data = [trace]

            # config layout axis based on the displayed values:
            for values, axis in ((x, layout['xaxis']), (y, layout['yaxis'])):
                axis['type'] = axis_type(values)
                rng = axis_range(values)
                if rng is not None:
                    axis['range'] = rng

            plots.append({
                'data': data,
                'params': {
                    'model': model,
                    'imt': imt,
                    'residual type': df_labels[res_type]
                },
                'layout': layout
            })

        return {'plots': plots}


def norm_dist(x, mean=0, sigma=1):
    from scipy.constants import pi
    sigma_square_times_two = 2 * (sigma ** 2)
    norm = 1. / np.sqrt(2 * pi * sigma_square_times_two)
    return norm * np.exp(-((x - mean) ** 2) / sigma_square_times_two)


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
        x, y = cleaned_data.get('x', None), cleaned_data.get('y', None)
        c = next(colors_cycle())
        c_transparent = c.replace(', 1)', ', 0.5)')
        if x and y:  # scatter plot
            xlabel, ylabel = cleaned_data['x'], cleaned_data['y']
            x, y = dataframe[xlabel], dataframe[ylabel]
            # x_na = na_values(x).sum()
            # y_na = na_values(y).sum()
            plot = {
                'data': [
                    scatter_trace(
                        color=c_transparent,
                        x=dataframe[xlabel],
                        y=dataframe[ylabel]
                    )
                ],
                'params': {},
                'layout': {
                    'xaxis': {
                        'title': xlabel,
                        'type': axis_type(x)
                    },
                    'yaxis': {
                        'title': ylabel,
                        'type': axis_type(y)
                    }
                }
            }
        elif x:
            xlabel = cleaned_data['x']
            plot = {
                'data': [
                    histogram_trace(
                        color=c_transparent,
                        line_color=c,
                        x=dataframe[xlabel]
                    )
                ],
                'params': {},
                'layout': {
                    'xaxis': {
                        'title': xlabel,
                        'type': axis_type(x)
                    },
                    'yaxis': {
                        'title': 'Frequency',
                        'type': AxisType.linear
                    }
                }
            }
        else:  # y only provided
            ylabel = cleaned_data['y']
            plot = {
                'data': [
                    histogram_trace(
                        color=c_transparent,
                        line_color=c,
                        y=dataframe[ylabel]
                    )
                ],
                'params': {},
                'layout': {
                    'xaxis': {
                        'title': 'Frequency',
                        'type': AxisType.linear
                    },
                    'yaxis': {
                        'title': ylabel,
                        'type': axis_type(y)
                    }
                }
            }

        return {'plots': [plot]}
