"""Forms for the eGSIM app (web portal)"""
import numpy as np
import pandas as pd

from egsim.api.forms.flatfile.management import Plotly
from egsim.api.forms.flatfile.residuals import ResidualsForm
from egsim.api.forms.predictions import PredictionsForm
from django.forms.fields import ChoiceField, CharField

from egsim.smtk.flatfile import ColumnType
from egsim.smtk.residuals import c_labels
from egsim.smtk.trellis import labels
from egsim.smtk.validators import sa_period


class PredictionsPlotDataForm(PredictionsForm):
    """Form returning predictions in form of plots"""

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
                self.add_error('imt', 'You must specify only SA with period(s) '
                                       'as intensity measures')
        return cleaned_data

    def output(self) -> dict:
        dataframe = super().output()
        dist_col = None
        for c in dataframe.columns:
            if c[0] == labels.input_data and c[1] == ColumnType.distance.value:
                dist_col = c
                break
        mag_col = (labels.input_data, ColumnType.rupture.value, labels.MAG)

        plots = []
        colors_cycle = Plotly.colors_cycle()
        colors = {}
        mag_label = mag_col[-1].title()
        dist_label =  dist_col[-1].title()
        models = sorted(self.cleaned_data['gsim'])
        imts = sorted(self.cleaned_data['imt'])
        if self.cleaned_data['plot_type'] == 'm':
            x_label = mag_label
            y_label = lambda imt: f'Median {imt}'
            def groupby(dataframe):
                for d, dfr in dataframe.groupby([dist_col]):
                    yield {dist_label: d}, dfr[mag_col], dfr
        elif self.cleaned_data['plot_type'] == 'd':
            x_label = dist_label
            y_label = lambda imt: f'Median {imt}'
            def groupby(dataframe):
                for m, dfr in dataframe.groupby([mag_col]):
                    yield {mag_label: m}, dfr[dist_col], dfr
        else:
            x_label = 'Period (s)'
            y_label = lambda imt: 'SA (g)'
            sas = {c for c in dataframe.columns if sa_period(c[-1]) is not None}
            sas = sorted(sas, key=lambda s: sa_period(s))
            x_values = [float(sa_period(_)) for _ in sas]
            def groupby(dataframe):
                for (d, m), dfr in dataframe.groupby([dist_col, mag_col]):
                    ret = pd.DataFrame()
                    for m in models:
                        ret[('SA', labels.MEDIAN, m)] = dfr.loc[sas, labels.MEDIAN, m]
                        ret[('SA', labels.SIGMA, m)] = dfr.loc[sas, labels.SIGMA, m]

                    yield {mag_label: m, dist_label: d}, x_values, pd.DataFrame(ret)

        for params, x_values, dfr in groupby(dataframe):
            for imt in imts:
                for model in models:
                    try:
                        medians = dataframe[(imt, labels.MEDIAN, model)]
                        sigmas = dataframe[(imt, labels.SIGMA, model)]
                    except KeyError:
                        medians = []
                        sigmas = []
                    color = colors.setdefault(model, next(colors_cycle))
                    plots.append({
                        'data': [Plotly.line_trace(color) | {
                            'x': Plotly.array2json(x_values),
                            'y': Plotly.array2json(medians)
                        }],
                        'params': params | {
                            'imt': imt
                        },
                        'layout': {
                            'xaxis': {'title': x_label, 'type': 'linear'},
                            'yaxis': {'title': y_label(imt), 'type': 'log'}
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
            c_labels.total_res: 'Total',
            c_labels.intra_ev_res: 'Intra event',
            c_labels.inter_ev_res: 'Inter event'
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
                    c_labels.total_res_lh: 'Total',
                    c_labels.intra_ev_res_lh: 'Intra event',
                    c_labels.inter_ev_res_lh: 'Inter event'
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
                trace = Plotly.bar_trace(color) | {
                    'x': Plotly.array2json(bins[:-1]),
                    'y': Plotly.array2json(y),
                    'name': " ".join(col),
                    'legendgroup': model
                }
                data = [trace]

                if not likelihood:
                    mean, std = x.mean(), x.std()
                    x_ = np.arange(mean - 3 * std, mean + 3 * std, step / 10)
                    data.append(Plotly.line_trace(color) | {
                        'x': Plotly.array2json(x_),
                        'y': Plotly.array2json(norm_dist(x_, mean, std)),
                        'name': " ".join(col) + ' normal distribution',
                        'legendgroup': model + ' normal distribution',
                    })
                    data.append(Plotly.line_trace("rgba(120, 120, 120, 1)") | {
                        'x': Plotly.array2json(x_),
                        'y': Plotly.array2json(norm_dist(x_)),
                        'name': 'Normal distribution',
                        'legendgroup': 'Normal distribution (m=0, s=1)',
                    })
                    data[-1]['line']['dash'] = 'dot'
                def_layout = default_layout()
            else:
                x = self.cleaned_data['flatfile'][col_x]
                y = dataframe[col]
                trace = Plotly.scatter_trace(color) | {
                    'x': Plotly.array2json(x),
                    'y': Plotly.array2json(y),
                    'name': " ".join(col),
                    'legendgroup': model
                }
                data = [trace]
                def_layout = default_layout()

            # config layout based on the displayed data x, y. If not already set,
            # layout['xaxis']['type'] and layout['xaxis']['range'] will be inferred from
            # x (same for y and layout['xaxis']):
            layout = Plotly.get_layout(x = x, y = y, **def_layout)

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