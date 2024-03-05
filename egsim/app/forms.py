"""Forms for the eGSIM app (web portal)"""
from egsim.api.forms.flatfile.management import Plotly
from egsim.api.forms.flatfile.residuals import ResidualsForm
from egsim.api.forms.predictions import PredictionsForm
from django.forms.fields import CharField
import numpy as np

from egsim.smtk.residuals import c_labels


class PredictionsPlotDataForm(PredictionsForm):
    pass


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
            # Set col_x as tuple (real dataframe column).
            # Not really elegant how to retrieve x, however:
            # for c in dataframe.columns:
            #     if c[0] == c_labels.input_data and c[-1] == col_x:
            #         col_x = c
            #         break

        plots = []
        colors_cycle = Plotly.colors_cycle()
        colors = {}
        for col in [c for c in dataframe.columns if c[1] in df_labels]:
            imt, res_type, model = col
            color = colors.setdefault(model, next(colors_cycle))
            default_trace = {
                'marker': {
                    'color': color.replace(', 1)', ', 0.5)') # make semi transparent
                },
                'name': " ".join(col),
                'legendgroup': model
            }
            if not col_x:
                default_trace['xbins'] = { 'size': .1 }
                default_trace['histnorm'] = 'probability'
                default_trace['marker']['line'] = {
                    'color': color,
                    'width': 2
                }
                x = dataframe[col]
                y = None
                trace = Plotly.get_trace(x=x, **default_trace)
                # add normal distribution:
                # trace_n = default_trace | {
                #     'x': np.random.normal(loc=np.nanmean(x), scale=np.nanstd(x), size=100).tolist(),
                #     'name': default_trace['name'] + ' Normal distribution',
                #     'type': 'scatter',
                #     'legendgroup': model + ' Normal distribution',
                # }
                # trace_n_0_1 = default_trace | {
                #     'x': np.random.normal(loc=0.0, scale=1.0, size=100).tolist(),
                #     'name': 'Normal distribution (m=0, s=1)',
                #     'type': 'scatter',
                #     'legendgroup': 'Normal distribution (m=0, s=1)',
                # }
                data = [trace]
            else:
                default_trace['mode'] = 'markers'
                default_trace['marker']['size'] = 10
                x = self.cleaned_data['flatfile'][col_x]
                y = dataframe[col]
                trace = Plotly.get_trace(x=x, y=y, **default_trace)
                data = [trace]
            layout = Plotly.get_layout(
                x = x,
                y = y,
                xaxis = { 'title': x_label(imt) },
                yaxis = { 'title': y_label(imt) }
            )

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

