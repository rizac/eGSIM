"""
Django Forms for eGSIM flatfile compilation (inspection, plot, upload)

@author: riccardo
"""
from django.forms.fields import CharField

from egsim.api import models
from egsim.api.forms import APIForm, GsimImtForm
from egsim.api.forms.flatfile import (FlatfileForm, get_registered_column_info,
                                      get_columns_info)
from egsim.api.forms.plotly import (AxisType, axis_type, colors_cycle,
                                    scatter_trace, histogram_trace)
from egsim.smtk import (ground_motion_properties_required_by,
                        intensity_measures_defined_for)
from egsim.smtk.flatfile import ColumnsRegistry


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
        ff_columns = {
            ColumnsRegistry.get_aliases(c)[0]
            for c in ground_motion_properties_required_by(*gsims)
        }
        imts = list(cleaned_data.get('imt', []))

        if not imts:
            imts = set()
            for m in gsims:
                imts |= intensity_measures_defined_for(m)

        return {
            'columns': [get_registered_column_info(c)
                        for c in sorted(ff_columns | set(imts))]
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
                    'yaxis':  {
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
