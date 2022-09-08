"""
Django Forms for eGSIM model-to-model comparison (Trellis plots)
"""
from collections import defaultdict
from typing import Iterable, Any

from shapely.geometry import Polygon, Point

from .fields import FloatField, MultipleChoiceWildcardField
from . import APIForm
from .. import models


def get_regionalizations() -> Iterable[tuple[str, str]]:
    return [(_.name, str(_)) for _ in models.Regionalization.objects.all()]


class GsimFromRegionForm(APIForm):
    """Form for Trellis plot generation"""

    # Set the public names of this Form Fields as `public_name: attribute_name`
    # mappings. Superclass mappings are merged into this one. An attribute name
    # can be keyed by several names, and will be keyed by itself anyway if not
    # done here (see `egsim.forms.EgsimFormMeta` for details)
    public_field_names = {
        'lat': 'lat',
        'latitude': 'lat',
        'lon': 'lon',
        'longitude': 'lon',
        'reg': 'regionalization'
    }

    lat = FloatField(label='Strike', min_value=-90., max_value=90.)
    lon = FloatField(label='Strike', min_value=-180., max_value=180.)
    regionalization = MultipleChoiceWildcardField(choices=get_regionalizations,
                                                  label='Regionalization name',
                                                  required=False)

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict[str, str]:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request, ie.e a dict of gsim name mapped to its
        regionalization name.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        fields = ('gsim__name', 'regionalization__name', 'geometry')
        qry = models.GsimRegion.objects.\
            select_related('gsim', 'regionalization').\
            only(*fields).values_list(*fields)
        rgnz = cleaned_data['regionalization'] or []
        if rgnz:
            qry = qry.filter(regionalization__name__in=rgnz)
        gsims = {}
        point = Point(cleaned_data['lon'], cleaned_data['lat'])
        for gsim_name, regionalization_name, geometry in qry.all():
            if gsim_name in gsims:
                continue
            type, coords = geometry['type'], geometry['coordinates']
            for coord in coords if type == 'MultiPolygon' else [coords]:
                polygon = Polygon((tuple(l) for l in coord[0]))
                if polygon.contains(point):
                    gsims[gsim_name] = regionalization_name
                    break

        return gsims

    @classmethod
    def csv_rows(cls, processed_data) -> Iterable[Iterable[Any]]:
        """Yield CSV rows, where each row is an iterables of Python objects
        representing a cell value. Each row doesn't need to contain the same
        number of elements, the caller function `self.to_csv_buffer` will pad
        columns with Nones, in case (note that None is rendered as "", any other
        value using its string representation).

        :param processed_data: dict resulting from `self.process_data`
        """
        yield from processed_data
