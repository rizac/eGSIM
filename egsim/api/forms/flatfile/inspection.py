"""
Django Forms for eGSIM flatfile plot generator

@author: riccardo
"""
from itertools import chain
from typing import Iterable, Any

import pandas as pd
from django.core.exceptions import ValidationError

from . import FlatfileForm
from .. import APIForm
from ..fields import ChoiceField

from ..flatfile import flatfile_colnames


class FlatfileInspectionForm(APIForm, FlatfileForm):
    """Form for flatfile inspection, return stats from a given flatfile"""

    # Set the public names of this Form Fields as `public_name: attribute_name`
    # mappings. Superclass mappings are merged into this one. An attribute name
    # can be keyed by several names, and will be keyed by itself anyway if not
    # done here (see `egsim.forms.EgsimFormMeta` for details)
    public_field_names = {}


    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        dataframe = cleaned_data['flatfile']
        columns = dataframe.columns
        missing_columns = set(flatfile_colnames()) - set(columns)
        columns = sorted(columns)
        stats = {c: cls.create_col_stats(dataframe, c) for c in columns}
        # flatfile columns not present in this flatfile are set as {}:
        for c in missing_columns:
            stats[c] = {}
        return {
            'rows': len(dataframe),
            'events': len(pd.unique(dataframe.event_id)),
            'columns': stats
        }

    @classmethod
    def create_col_stats(cls, dataframe: pd.DataFrame, col: str):
        """Creates a stat JSON serializable dict"""
        series = dataframe[col] if col in dataframe.columns else None
        no_data = series is None
        series_notna = None if no_data else series[pd.notna(series)]
        na = len(dataframe) if no_data else len(series) - len(series_notna)
        try:
            min_ = None if no_data else series.min()
        except TypeError:  # categorical?
            try:
                min_ = series.dtype.categories.min()  # categorical
            except AttributeError:
                min_ = None  # give up: min is None
        try:
            max_ = None if no_data else series.max()
        except TypeError:  # categorical?
            try:
                max_ = series.dtype.categories.max()  # categorical
            except AttributeError:
                max_ = None  # give up: min is None
        dtype = None if no_data else str(series.dtype)
        try:
            quantiles = [None] * 3 if no_data else series.quantile([0.05, 0.5, 0.95]).values
        except TypeError:
            # boolean series, string series and so on
            quantiles = [None] * 3
        ret = {
            'distinct values': None if no_data else len(pd.unique(series_notna)),
            'missing values': na,
            'values type': None if no_data else dtype,
            'median': None if no_data else quantiles[1],
            'min': min_,
            'max': max_,
            'quantile(0.05)': None if no_data else quantiles[0],
            'quantile(0.95)': None if no_data else quantiles[2],
        }
        # json serialize:
        for key, val in ret.items():
            if val is not None and pd.isna(val):
                ret[key] = None
            elif hasattr(val, 'item'):
                ret[key] = val.item()
        return ret

    @classmethod
    def csv_rows(cls, processed_data: dict) -> Iterable[Iterable[Any]]:
        """Yield CSV rows, where each row is an iterables of Python objects
        representing a cell value. Each row doesn't need to contain the same
        number of elements, the caller function `self.to_csv_buffer` will pad
        columns with Nones, in case (note that None is rendered as "", any other
        value using its string representation).

        :param processed_data: dict resulting from `self.process_data`
        """
        col_names = processed_data['columns'].keys()
        yield chain([''], col_names)
        col_stats = processed_data['columns'].values()
        for stat_name in next(iter(col_stats)).keys():
            yield chain([stat_name], (s.get(stat_name, None) for s in col_stats))
        yield ['rows:', processed_data['rows']]
        yield ['events:', processed_data['events']]


class FlatfilePlotForm(APIForm, FlatfileForm):
    """Form for plotting flatfile columns"""

    # Set the public names of this Form Fields as `public_name: attribute_name`
    # mappings. Superclass mappings are merged into this one. An attribute name
    # can be keyed by several names, and will be keyed by itself anyway if not
    # done here (see `egsim.forms.EgsimFormMeta` for details)
    public_field_names = {}

    # plot_type = ChoiceField(required=True,
    #                         choices=[(k, v[0]) for k, v in PLOT_TYPE.items()])
    x = ChoiceField(label='X', help_text="The flatfile column for the x values",
                    required=False, choices=flatfile_colnames)
    y = ChoiceField(label='Y', help_text="The flatfile column for the y values",
                    required=False, choices=flatfile_colnames)

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
        elif isinstance(cleaned_data.get('dataframe'), pd.DataFrame):
            cols = cleaned_data['dataframe']
            if 'x' in cleaned_data and x not in cols:
                self.add_error("x", ValidationError('"x" value is not a flatfile'
                                                    'column name',
                                                    code='invalid'))
            if 'y' in cleaned_data and y not in cols:
                self.add_error("y", ValidationError('"y" value is not a flatfile'
                                                    'column name',
                                                    code='invalid'))

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
        if x and y:
            xlabel, ylabel = cleaned_data['x'], cleaned_data['y']
            xvalues, yvalues = dataframe[xlabel], dataframe[ylabel]
            xnan, ynan = pd.isna(xvalues), pd.isna(yvalues)
            all_finite = ~(xnan | ynan)
            plot = dict(
                xvalues=xvalues[all_finite].values.tolist(),
                yvalues=yvalues[all_finite].values.tolist(),
                xlabel=xlabel,
                ylabel=ylabel,
                nan_count=all_finite.sum()
            )
        else:
            xlabel = x or y
            series = dataframe[xlabel]
            num = 20
            uniques = pd.unique(series)
            if len(uniques) <= num:
                uniques.sort()
                xvalues = uniques
                yvalues = [(series == x).sum() for x in xvalues]  # noqa
            else:
                res = dataframe.groupby(pd.cut(series, num)).count()
                xvalues = [str(_) for _ in res.index]
                yvalues = res[res.columns[0]].tolist()

            plot = dict(
                xvalues=xvalues,
                yvalues=yvalues,
                xlabel=xlabel,
                ylabel='count',
                nan_count=pd.isna(yvalues).sum()
            )

        return plot

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
