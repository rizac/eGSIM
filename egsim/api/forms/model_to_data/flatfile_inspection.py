"""
Django Forms for eGSIM flatfile plot generator

@author: riccardo
"""
from itertools import chain
from typing import Iterable, Any

import numpy as np
import pandas as pd

from . import FlatfileForm
from .. import APIForm
from ..fields import ChoiceField

from ... import models


def get_flatfile_column_choices() -> list[tuple[str, str]]:
    """Returns the choices for the x and y Fields"""
    qry = models.FlatfileColumn.objects
    return [(_, _) for _ in qry.only('name').values_list('name', flat=True)]


class FlatfileInspectionForm(APIForm, FlatfileForm):
    """Form for residual analysis"""

    # Set the public names of this Form Fields as `public_name: attribute_name`
    # mappings. Superclass mappings are merged into this one. An attribute name
    # can be keyed by several names, and will be keyed by itself anyway if not
    # done here (see `egsim.forms.EgsimFormMeta` for details)
    public_field_names = {}

    # plot_type = ChoiceField(required=True,
    #                         choices=[(k, v[0]) for k, v in PLOT_TYPE.items()])
    x = ChoiceField(label='X', help_text="The flatfile column for the x values",
                    required=False, choices=get_flatfile_column_choices)
    y = ChoiceField(label='Y', help_text="The flatfile column for the y values",
                    required=False, choices=get_flatfile_column_choices)

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        dataframe = cleaned_data['flatfile']

        all_cols = [_[0] for _ in cls.x.choices]
        all_cols.extend(_ for _ in dataframe.columns if _ not in all_cols)
        all_cols.sort()
        stats = {c: cls.create_col_stat(dataframe, c) for c in all_cols}

        x, y = cleaned_data.get('x', None), cleaned_data.get('y', None)
        ret = {
            'rows': len(dataframe),
            'columns': stats,
        }
        plot = None
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
            )
        elif x or y:
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
                ylabel='count'
            )

        if plot is not None:
            ret['plot'] = plot
        return ret

    @classmethod
    def create_col_stats(cls, dataframe: pd.DataFrame, col):
        """Creates a stat JSON serializable dict"""
        series = dataframe[col] if col in dataframe.columns else None
        quantiles = [None] * 3 if series is None else series.quantile([0.05, 0.5, 0.95])
        series_notna = None if series is None else series[pd.notna(series)]
        na = len(dataframe) if series is None else len(series) - len(series_notna)
        ret = {
            'missing values': na,
            'distinct values': None if series is None else len(pd.unique(series_notna)),
            'median': None if series is None else quantiles[1],
            'min': None if series is None else series.min(),
            'max': None if series is None else series.max(),
            'quantile(0.5)': None if series is None else quantiles[0],
            'quantile(0.95)': None if series is None else quantiles[2],
        }
        for key, val in ret.items():
            if val is not None and pd.isna(val):
                ret[key] = None
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
        yield ['rows']
        yield [processed_data['rows']]
        yield ['']
        yield ['columns']
        col_names = processed_data['columns'].keys()
        yield chain([''], col_names)
        col_stats = processed_data['columns'].values()
        for stat_name in next(iter(col_stats)).keys():
            yield chain([stat_name], (s[stat_name] for s in col_stats))

        if processed_data.get('plot', None):
            yield [""]
            yield['plot']
            yield chain(processed_data['xlabel'], processed_data['x'])
            yield chain(processed_data['ylabel'], processed_data['y'])

