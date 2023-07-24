"""
Django Forms for eGSIM flatfile compilation (inspection, plot, upload)

@author: riccardo
"""
from itertools import chain
from typing import Iterable, Any, Union

import numpy as np
import pandas as pd
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms.fields import CharField

from egsim.smtk.flatfile import ColumnType, column_dtype
from egsim.api import models
from egsim.api.forms import APIForm, GsimImtForm
from egsim.api.forms.flatfile import FlatfileForm, get_gsims_from_flatfile


class FlatfileRequiredColumnsForm(GsimImtForm, APIForm):
    """Form for querying the necessary metadata columns from a given list of Gsims"""

    accept_empty_gsim_list = True  # see GsimImtForm
    accept_empty_imt_list = True

    def clean(self):
        return super().clean()

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        query = models.FlatfileColumn.objects  # noqa

        condition = Q(data_properties__required=True)
        if cleaned_data.get('gsim', []):
            condition |= Q(gsims__name__in=cleaned_data['gsim'],
                           type__in=(ColumnType.rupture_parameter,
                                     ColumnType.site_parameter,
                                     ColumnType.distance_measure))

        if cleaned_data.get('imt', []):
            # we could simply skip querying imts as we already have them, but we need
            # helpvand dtype info:
            imts = cleaned_data['imt']
            imts_to_query = set('SA' if _.startswith('SA(') else _ for _ in imts)
            condition |= Q(name__in=imts_to_query, type=ColumnType.imt)

        columns = {}
        attrs = 'name', 'help', 'type', 'dtype'
        for name, help, type, dtype in query.filter(condition).values_list(*attrs):
            if name in columns:  # could be (we query with m2m relationship)
                continue
            if name == 'SA' and type == ColumnType.imt:
                names = [col for col in cleaned_data.get('imt', [])
                         if col.startswith('SA(')]
            else:
                names = [name]
            for name in names:
                columns[name] = {
                    'help': help,
                    'type': ColumnType(type).name.replace("_", " "),
                    'dtype': dtype or 'any'
                }

        return columns

    @classmethod
    def csv_rows(cls, processed_data: dict) -> Iterable[Iterable[Any]]:
        """Yield CSV rows, where each row is an iterables of Python objects
        representing a cell value. Each row doesn't need to contain the same
        number of elements, the caller function `self.to_csv_buffer` will pad
        columns with Nones, in case (note that None is rendered as "", any other
        value using its string representation).

        :param processed_data: dict resulting from `self.process_data`
        """
        names = processed_data.keys()
        yield names
        yield (processed_data[n].get('help', '') for n in names)
        yield (processed_data[n].get('dtype', '') for n in names)


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
            self.add_error("x", ValidationError('with no "y" specified, this '
                                                'parameter is required',
                                                code='required'))
            self.add_error("y", ValidationError('with no "x" specified, this '
                                                'parameter is required',
                                                code='required'))

        if not self.has_error('flatfile'):
            cols = cleaned_data['flatfile'].columns
            if x and x not in cols:
                self.add_error("x", ValidationError(f'"{x}" is not a flatfile'
                                                    'column', code='invalid'))
            if y and y not in cols:
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
            xnan = cls._isna(xvalues)
            ynan = cls._isna(yvalues)
            plot = dict(
                xvalues=cls.tolist(xvalues[~(xnan | ynan)]),
                yvalues=cls.tolist(yvalues[~(xnan | ynan)]),
                xlabel=xlabel,
                ylabel=ylabel,
                stats={
                    xlabel: {'N/A count': int(xnan.sum()),
                             **cls._get_stats(xvalues.values[~xnan])},
                    ylabel: {'N/A count': int(ynan.sum()),
                             **cls._get_stats(yvalues.values[~ynan])}
                }
            )
        else:
            label = x or y
            na_values = cls._isna(dataframe[label])
            dataframe = dataframe.loc[~na_values, :]
            series = dataframe[label]
            na_count = int(na_values.sum())
            if x:
                plot = dict(
                    xvalues=cls.tolist(series),
                    xlabel=label,
                    stats={
                        label: {
                            'N/A count': na_count,
                            **cls._get_stats(series.values)
                        }
                    }
                )
            else:
                plot = dict(
                    yvalues=cls.tolist(series),
                    ylabel=label,
                    stats={
                        label: {
                            'N/A count': na_count,
                            **cls._get_stats(series.values)
                        }
                    }
                )
        return plot

    @classmethod
    def tolist(cls, series_with_no_na: pd.Series):
        if str(series_with_no_na.dtype).startswith('datetime'):
            return pd.to_datetime(series_with_no_na.values).\
                strftime('%Y-%m-%dT%H:%M:%S').tolist()
        else:
            return series_with_no_na.values.tolist()

    @classmethod
    def _isna(cls, values):
        with pd.option_context('mode.use_inf_as_na', True):
            return pd.isna(values).values

    @classmethod
    def _get_stats(cls, finite_values) -> dict[str, Union[float, None]]:
        values = np.asarray(finite_values)
        try:
            return {
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'median': float(np.median(values)),
                'mean': float(np.mean(values)),
                '0.25quantile': float(np.quantile(values, 0.25)),
                '0.75quantile': float(np.quantile(values, 0.75))
            }
        except (ValueError, TypeError):
            # ValueError if values is empty. TypeError if values contains mixed types
            return {
                'min': None,
                'max': None,
                'median': None,
                'mean': None,
                '0.25quantile': None,
                '0.75quantile': None
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

        if self.has_error('flatfile'):
            return cleaned_data
        dataframe = cleaned_data['flatfile']

        cleaned_data['flatfile_dtypes'] = self.get_flatfile_dtypes(dataframe)
        gsims = list(get_gsims_from_flatfile(dataframe.columns))
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
        return {
            'columns': cleaned_data['flatfile_dtypes'],
            'default_columns': column_dtype,
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

