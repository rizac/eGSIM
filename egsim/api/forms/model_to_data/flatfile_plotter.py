"""
Django Forms for eGSIM flatfile plot generator

@author: riccardo
"""
from typing import Iterable, Any

import pandas as pd

from . import FlatfileForm
from .. import APIForm
from ..fields import ChoiceField

from ... import models


def get_flatfile_column_choices() -> list[tuple[str, str]]:
    """Returns the choices for the x and y Fields"""
    qry = models.FlatfileColumn.objects
    return [(_, _) for _ in qry.only('name').values_list('name')]


class FlatfilePlotForm(APIForm, FlatfileForm):
    """Form for residual analysis"""

    # Set the public names of this Form Fields as `public_name: attribute_name`
    # mappings. Superclass mappings are merged into this one. An attribute name
    # can be keyed by several names, and will be keyed by itself anyway if not
    # done here (see `egsim.forms.EgsimFormMeta` for details)
    public_field_names = {}

    # plot_type = ChoiceField(required=True,
    #                         choices=[(k, v[0]) for k, v in PLOT_TYPE.items()])
    x = ChoiceField(label='X', help_text="Select a flatfile column for the x values",
                    required=True, choices=get_flatfile_column_choices)
    y = ChoiceField(label='Y', help_text="Select a flatfile column for the y values",
                    required=True, choices=get_flatfile_column_choices)

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        dataframe = cleaned_data['flatfile']
        xlabel, ylabel = cleaned_data['x'], cleaned_data['y']
        xvalues, yvalues = dataframe[xlabel], dataframe[ylabel]
        xnan, ynan = pd.isnan(xvalues), pd.isnan(yvalues)
        all_finite = ~(xnan | ynan)
        return {
            'xvalues': xvalues[all_finite].tolist(),
            'yvalues': yvalues[all_finite].tolist(),
            'xlabel': xlabel,
            'ylabel': ylabel,
            'nan_count': int(xnan.sum() + ynan.sum())
        }

    @classmethod
    def csv_rows(cls, processed_data: dict) -> Iterable[Iterable[Any]]:
        """Yield CSV rows, where each row is an iterables of Python objects
        representing a cell value. Each row doesn't need to contain the same
        number of elements, the caller function `self.to_csv_buffer` will pad
        columns with Nones, in case (note that None is rendered as "", any other
        value using its string representation).

        :param processed_data: dict resulting from `self.process_data`
        """
        yield [processed_data['xlabel'], processed_data['ylabel']]
        for x, y in zip(processed_data['x'], processed_data['y']):
            yield [x, y]
