"""Forms for the eGSIM app (web portal)"""
from egsim.api.forms.flatfile.management import Plotly
from egsim.api.forms.flatfile.residuals import ResidualsForm
from egsim.api.forms.predictions import PredictionsForm
from django.forms.fields import CharField


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

            default_layout = lambda: {
                'xaxis': {'title': x_label(imt)},
                'yaxis': {'title': y_label(imt)}
            }

            if not col_x:
                default_trace['xbins'] = { 'size': .5 }
                default_trace['histnorm'] = 'probability'
                default_trace['marker']['line'] = {
                    'color': color,
                    'width': 2
                }
                x = dataframe[col]
                y = None
                trace = Plotly.get_trace(x=x, **default_trace)
                data = [trace]
                def_layout = default_layout()
                def_layout['xaxis']['type'] = '-'
                def_layout['yaxis']['type'] = Plotly.AxisType.linear
                def_layout['yaxis']['range'] = [0, 1]
                # layout['xaxis']['type'] = Plotly.AxisType.infer  # disables log axis control
            else:
                default_trace['mode'] = 'markers'
                default_trace['marker']['size'] = 10
                x = self.cleaned_data['flatfile'][col_x]
                y = dataframe[col]
                trace = Plotly.get_trace(x=x, y=y, **default_trace)
                data = [trace]
                def_layout = default_layout()

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

        Plotly.harmonize_axis_ranges([p['layout']['xaxis'] for p in plots])
        Plotly.harmonize_axis_ranges([p['layout']['yaxis'] for p in plots])
        return {'plots': plots}

