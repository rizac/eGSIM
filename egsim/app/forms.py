"""Forms for the eGSIM app (web portal)"""
import numpy as np

from egsim.api.forms.flatfile.management import Plotly
from egsim.api.forms.flatfile.residuals import ResidualsForm
from egsim.api.forms.scenarios import PredictionsForm
from django.forms.fields import ChoiceField, CharField

from egsim.smtk.flatfile import ColumnType
from egsim.smtk.registry import Clabel
from egsim.smtk.validators import sa_period


class PredictionsPlotDataForm(PredictionsForm):
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
        if cleaned_data['plot_type'] == 's':
            if not (all(_.startswith('SA(') for _ in cleaned_data['imt'])):
                self.add_error('imt', 'Only SA with period(s) allowed')
        return cleaned_data

    def output(self) -> dict:
        dataframe = super().output()
        dist_col = None
        for c in dataframe.columns:
            if c[0] == Clabel.input_data and c[1] == ColumnType.distance.value:
                dist_col = c
                break
        mag_col = (Clabel.input_data, ColumnType.rupture.value, Clabel.mag)

        plots = []
        colors_cycle = Plotly.colors_cycle()
        colors = {}
        mag_label = mag_col[-1].title()
        dist_label = dist_col[-1].title()
        imt_label = 'Imt'
        models = sorted(self.cleaned_data['gsim'])
        imts = sorted(self.cleaned_data['imt'])

        if self.cleaned_data['plot_type'] == 'm':
            x_label = mag_label
            y_label = lambda imt: f'Median {imt}'

            def groupby(dataframe):
                for dist, dfr in dataframe.groupby(dist_col):
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
            y_label = lambda imt: f'Median {imt}'

            def groupby(dataframe):
                for mag, dfr in dataframe.groupby(mag_col):
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
            y_label = lambda imt: 'SA (g)'
            sas = sorted(imts, key=lambda s: sa_period(s))  # FIXME sort imts in one place
            x_values = [float(sa_period(_)) for _ in sas]
            i = 'SA'

            def groupby(dataframe):
                for (d, mag), dfr in dataframe.groupby([dist_col, mag_col]):
                    p = {mag_label: mag, dist_label: d, imt_label: i}
                    data = {}
                    for m in models:
                        data[m] = (
                            dfr.loc[:, (sas, Clabel.median, m)].iloc[0, :].values,
                            dfr.loc[:, (sas, Clabel.std, m)].iloc[0,:].values
                        )
                    yield i, p, x_values, data

        for params, x_values, data in groupby(dataframe):
            traces = []
            y_mins =[]
            y_maxs = []
            for model, [medians, sigmas] in data.items():
                color = colors.setdefault(model, next(colors_cycle))
                color_transparent = color.replace(', 1)', ', 0.2)')
                legendgroup = model
                traces.extend([
                    Plotly.line_trace(
                        color=color,
                        x=x_values,
                        y=medians,
                        name=model,
                        legendgroup=legendgroup
                    ),
                    Plotly.line_trace(
                        width=0,
                        color=color_transparent,
                        fillcolor=color_transparent,
                        x=x_values,
                        y=medians * np.exp(sigmas),
                        name=model + ' stddev',
                        legendgroup=legendgroup + ' stddev'
                    ),
                    Plotly.line_trace(
                        width=0,
                        color=color_transparent,
                        fillcolor=color_transparent,
                        fill='tonexty',  # https://plotly.com/javascript/reference/scatter/#scatter-fill  # noqa
                        x=x_values,
                        y=medians * np.exp(-sigmas),
                        name=model + ' stddev',
                        legendgroup=legendgroup + ' stddev'
                    )]
                )
                y_mins.append(min(traces[-1]['y']))
                y_maxs.append(max(traces[-2]['y']))

            plots.append({
                'data':traces,
                'params': params,
                'layout': {
                    'xaxis': {
                        'title': x_label,
                        'type': 'linear',
                        'autorange': True,
                        'range': [float(x_values.min()), float(x_values.max())]
                    },
                    'yaxis': {
                        'title': y_label(params['imt']),
                        'type': 'log',
                        'autorange': True,
                        'range': [float(min(y_mins)), float(max(y_maxs))],
                    }
                }
            })

        return {'plots': plots}


class ResidualsPlotDataForm(ResidualsForm):
    """Form returning residuals in form of plots"""

    x = CharField(required=False, initial=None,
                  help_text='the flatfile field to use for plot, or None/null: in '
                            'this latter case a histogram will be returned '
                            'depending on the value of the param. likelihood '
                            '(True: LH values, else: residuals Z values)')

    def output(self) -> dict:

        # residuals (x y): Frequency Z(<imt>)
        # likelihood (x y): Frequency LH(<imt>)
        # <ff_column> (x y): Z(<imt>) <ff_column>

        # remember: on the frontend:
        # - to enable the xaxis type checkbox: layoyt.xaxis.type must be 'log' or 'linear'
        # (same for layout.yaxis)
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
                y_label = lambda imt: 'Frequency'
                x_label = lambda imt: f'Z ({str(imt)})'
            else:
                y_label = lambda imt: 'Frequency'
                df_labels = {
                    Clabel.total_lh: 'Total',
                    Clabel.intra_ev_lh: 'Intra event',
                    Clabel.inter_ev_lh: 'Inter event'
                }
                x_label = lambda imt: f'Likelihood ({str(imt)})'
        else:
            y_label = lambda imt: f'Z ({str(imt)})'
            x_label = lambda imt: self.cleaned_data['x']

        plots = []
        colors_cycle = Plotly.colors_cycle()
        colors = {}
        for col in [c for c in dataframe.columns if c[1] in df_labels]:
            imt, res_type, model = col
            color = colors.setdefault(model, next(colors_cycle))
            color_transparent = color.replace(', 1)', ', 0.5)')
            default_layout = lambda: {
                'xaxis': {'title': x_label(imt)},
                'yaxis': {'title': y_label(imt)}
            }

            if not col_x:
                x = dataframe[col]
                if not likelihood:
                    step = 0.5
                else:
                    step = 0.1
                bins = np.arange(x.min(), x.max() + step, step)
                y = np.histogram(x, bins, density=True)[0]
                trace = Plotly.bar_trace(
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
                    data.append(Plotly.line_trace(
                        color=color,
                        x=x_,
                        y=norm_dist(x_, mean, std),
                        name=" ".join(col) + ' normal distribution',
                        legendgroup=model + ' normal distribution',
                    ))
                    data.append(
                        Plotly.line_trace(
                            color="rgba(120, 120, 120, 1)",
                            dash='dot',
                            x=x_,
                            y=norm_dist(x_),
                            name='Normal distribution',
                            legendgroup='Normal distribution (m=0, s=1)',
                    ))
                def_layout = default_layout()
            else:
                x = self.cleaned_data['flatfile'][col_x]
                y = dataframe[col]
                trace = Plotly.scatter_trace(
                    color=color_transparent,
                    x=x,
                    y=y,
                    name=" ".join(col),
                    legendgroup=model
                )
                data = [trace]
                def_layout = default_layout()

            # config layout based on the displayed data x, y. If not already set,
            # layout['xaxis']['type'] and layout['xaxis']['range'] will be inferred from
            # x (same for y and layout['xaxis']):
            layout = Plotly.layout(x = x, y = y, **def_layout)

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