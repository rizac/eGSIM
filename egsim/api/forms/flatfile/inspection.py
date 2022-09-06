"""
Django Forms for eGSIM flatfile plot generator

@author: riccardo
"""
from itertools import chain
from typing import Iterable, Any

import numpy as np
import pandas as pd
from django.core.exceptions import ValidationError

from . import FlatfileForm, flatfile_supported_gsims
from .. import APIForm
from ..fields import CharField

from ... import models


class FlatfilePlotForm(APIForm, FlatfileForm):
    """Form for plotting flatfile columns"""

    # Set the public names of this Form Fields as `public_name: attribute_name`
    # mappings. Superclass mappings are merged into this one. An attribute name
    # can be keyed by several names, and will be keyed by itself anyway if not
    # done here (see `egsim.forms.EgsimFormMeta` for details)
    public_field_names = {}

    x = CharField(label='X', help_text="The flatfile column for the x values",
                  required=False)
    y = CharField(label='Y', help_text="The flatfile column for the y values",
                  required=False)

    def clean(self):
        """Call `super.clean()` and handle the flatfile"""
        cleaned_data = super().clean()
        x, y = cleaned_data.get('x', None), cleaned_data.get('y', None)
        if not x and not y:
            self.add_error("x", ValidationError('with no "y" specfied, this '
                                                'parameter is required',
                                                code='required'))
            self.add_error("y", ValidationError('with no "x" specfied, this '
                                                'parameter is required',
                                                code='required'))

        cols = cleaned_data['flatfile']
        if x is not None and x not in cols:
            self.add_error("x", ValidationError(f'"{x}" is not a flatfile'
                                                'column', code='invalid'))
        if y is not None and y not in cols:
            self.add_error("y", ValidationError(f'"{y}" is not a flatfile'
                                                'column', code='invalid'))

        return cleaned_data

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        dataframe = cleaned_data['flatfile']
        x, y = cleaned_data.get('x', None), cleaned_data.get('y', None)
        if x and y:  # scatter plot
            xlabel, ylabel = cleaned_data['x'], cleaned_data['y']
            xvalues = dataframe[xlabel]
            yvalues = dataframe[ylabel]
            with pd.use_inf_as_na():
                xnan = pd.isna(xvalues)
                ynan = pd.isna(yvalues)
            xvalues = xvalues[~(xnan | ynan)]
            yvalues = yvalues[~(xnan | ynan)]
            plot = dict(
                xvalues=xvalues.values.tolist(),
                yvalues=yvalues.values.tolist(),
                xlabel=xlabel,
                ylabel=ylabel,
                stats={xlabel: cls._get_stats(xvalues),
                       ylabel: cls._get_stats(yvalues)}
            )
        else:  # histogram
            xlabel = x or y
            na_values = cls._isna(dataframe[xlabel])
            num_na_values = na_values.sum()
            if num_na_values > 0:
                dataframe = dataframe.loc[~na_values, :]
            series = dataframe[xlabel]
            res = dataframe.groupby(xlabel)
            bins_count = len(res)
            max_bins_count = 100
            if bins_count > 1.5 * max_bins_count:
                res = dataframe.groupby(pd.cut(series, max_bins_count))
            res = res.count()
            xvalues = ['N/A'] + [str(_) for _ in res.index]
            yvalues = [num_na_values] + res[res.columns[0]].tolist()

            plot = dict(
                xvalues=xvalues,
                yvalues=yvalues,
                xlabel=xlabel,
                ylabel='count',
                stats={xlabel: cls._get_stats(series.values, na_values)}
            )

        return plot

    @classmethod
    def _isna(cls, values):
        with pd.option_context('mode.use_inf_as_na', True):
            return pd.isna(values)

    @classmethod
    def _get_stats(cls, values, na_values=None):
        if na_values is None:
            na_values = cls._isna(values)
        values = np.asarray(values)
        if na_values.any():
            values = values[~na_values]
        try:
            return {
                'min': np.min(values),
                'max': np.max(values),
                'median': np.median(values),
                'mean': np.mean(values),
                '0.25quantile': np.quantile(values, 0.25),
                '0.75quantile': np.quantile(values, 0.75),
                'N/A count': na_values.sum()
            }
        except (ValueError, TypeError):
            # ValueError if values is empty. TypeError if values contains mixed types
            return {
                'min': None,
                'max': None,
                'median': None,
                'mean': None,
                '0.25quantile': None,
                '0.75quantile': None,
                'N/A count': na_values.sum()
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
        yield chain([processed_data['xlabel']], processed_data['x'])
        yield chain([processed_data['ylabel']], processed_data['y'])


class FlatfileInspectionForm(APIForm, FlatfileForm):
    """Form for flatfile inspection, return info from a given flatfile"""

    # Set the public names of this Form Fields as `public_name: attribute_name`
    # mappings. Superclass mappings are merged into this one. An attribute name
    # can be keyed by several names, and will be keyed by itself anyway if not
    # done here (see `egsim.forms.EgsimFormMeta` for details)
    public_field_names = {}

    def clean(self):
        cleaned_data = super().clean()

        if 'flatfile' not in cleaned_data:  # has errors FIXME: HOW TO HANDLE
            return cleaned_data

        dataframe = cleaned_data['flatfile']

        # get data types and raise if some data type is unknown:
        try:
            cleaned_data['flatfile_dtypes'] = self.get_flatfile_dtypes(dataframe)
        except Exception as exc:
            self.add_error("flatfile",
                           ValidationError(str(exc), code='invalid'))

        invalid_cols = super().get_flatfile_columns_with_invalid_dtypes()
        if invalid_cols:
            self.add_error("flatfile",
                           ValidationError(f"{len(invalid_cols)} columns have "
                                           f"unexpected data type (e.g. str "
                                           f"instead of float): "
                                           f"{', '.join(_[0] for _ in invalid_cols)}",
                                           code='invalid'))
        gsims = list(flatfile_supported_gsims(dataframe.columns))

        if not gsims:
            self.add_error("flatfile",
                           ValidationError("No GSIM can work with the "
                                           "provided columns. Rename or add "
                                           "new columns", code='invalid'))
        cleaned_data['gsim'] = gsims

        return cleaned_data

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        dtype, defaults = models.FlatfileColumn.get_dtype_and_defaults()
        return {
            'dtypes': cleaned_data['flatfile_dtypes'],
            'default_dtype': dtype,
            'gsim': cleaned_data['gsim']
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
        # NOT IMPLEMENTED. THIS SHOULD RAISE:
        return super().csv_rows(processed_data)
