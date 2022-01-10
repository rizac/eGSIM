"""
Django Forms for eGSIM model-to-model comparison (Trellis plots)
"""
from collections import defaultdict
from typing import Iterable, Any

from shapely.geometry import Polygon, Point

from ..fields import FloatField, MultipleChoiceWildcardField
from .. import APIForm
from ... import models


def get_regionalization_names():
    return [(_,_) for _ in
            models.RegionalizationDataSource.objects.values_list('name')]


class ModelFromRegionForm(APIForm):
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
    regionalization = MultipleChoiceWildcardField(choices=get_regionalization_names,
                                                  label='Regionalization name',
                                                  required=False)

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        qry = models.GsimRegion.objects  # noqa
        rgnz = [_.name for _ in cleaned_data['regionalization']]
        if rgnz:
            qry = qry.filter(reionalization_in=rgnz)
        gsims = defaultdict(list)
        point = Point(cleaned_data['lon'], cleaned_data['lat'])
        for gsim_region in qry.all():
            gsim_name = gsim_region.gsim.name
            if gsim_name in gsims:
                continue
            geojson = gsim_region.geometry
            type, coords = geojson['type'], geojson['coordinates']
            for coord in coords if type == 'MultiPolygon' else [coords]:
                polygon = Polygon([tuple(l) for l in coord[0]])
                if polygon.contains(point):
                    gsims[gsim_name].append(gsim_region.regionalization.name)
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
