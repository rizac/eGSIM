"""
Django Forms for eGSIM flatfile plot generator

@author: riccardo
"""
from typing import Iterable, Any

from django.db.models import Prefetch

from . import FlatfileForm
from .. import APIForm, MultipleChoiceWildcardField, get_gsim_choices

from .. import models
from ...flatfile import EVENT_ID_COL


class FlatfileColumnsForm(APIForm, FlatfileForm):
    """Form for flatfile compilation, return the necessary columns from a
    given list of Gsims"""

    # Set the public names of this Form Fields as `public_name: attribute_name`
    # mappings. Superclass mappings are merged into this one. An attribute name
    # can be keyed by several names, and will be keyed by itself anyway if not
    # done here (see `egsim.forms.EgsimFormMeta` for details)
    public_field_names = {}

    gsim = MultipleChoiceWildcardField(required=True, choices=get_gsim_choices,
                                       label='Ground Shaking Intensity Model(s)')


    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        # Try to perform everything in a single more efficient query. Use
        # prefetch_related for this. It Looks like we need to assign the imts to a
        # new attribute, the attribute "Gsim.imts" does not work as expected
        cols = Prefetch('imts', queryset=models.FlatfileColumn.objects.only('name'),
                        to_attr='ffcolumns')

        qry = models.Gsim.objects.only('name').prefetch_related(cols)

        columns = [EVENT_ID_COL]
        for model in qry:
            for col in model.ffcolumns:
                if col not in columns:
                    columns.append(col)

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
        return ([c] for c in processed_data)
