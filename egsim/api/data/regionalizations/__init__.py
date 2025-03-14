"""
Module parsing regionalization files in `sources` into a standardized `dict`
of region:str mapped to its geoJSON:dict object. The models associated to a
region can be retrieved in the ["properties"]["models'].
See `get_regionalizations` for usage

Created on 7 Dec 2020

@author: riccardo
"""
import warnings

from collections.abc import Iterable
from os.path import join, dirname
from typing import Any, Union

import json

from shapely import to_geojson
from shapely.geometry import shape
from shapely.ops import unary_union

from egsim.smtk import registered_gsims


def get_regionalizations() -> Iterable[str, list[dict[str, Any]]]:
    """Yield regionalizations stored in this package

    :return: a generator yielding tuples of the form `name:str, regionalization:dict`
        where the first item is the regionalization name and the second
        is a list of geoJSON Feature(s) (`dict`. see `get_regionalization` for details)
    """
    for name, data in DATA.items():
        yield name, get_regionalization(*data['sources'])


datadir = join(dirname(__file__), 'sources')


DATA = {
    'share': {
        'sources': [join(datadir, 'share.geo.json'),
                    join(datadir, 'share.json')],
        'display_name': "Seismic Hazard Harmonization in Europe (SHARE)",
        'url': "http://hazard.efehr.org/en/Documentation/specific-hazard-models/"
               "europe/overview/seismogenic-sources/",
        'license': "CC BY-SA 3.0 (unported) "
                   "[http://creativecommons.org/licenses/by-sa/3.0/]",
        'citation': "D. Giardini, J. Woessner, L. Danciu, H. Crowley, F. Cotton, "
                    "G. Grünthal, R. Pinho, G. Valensise, S. Akkar, R. Arvidsson, "
                    "R. Basili, T. Cameelbeeck, A. Campos-Costa, J. Douglas, "
                    "M. B. Demircioglu, M. Erdik, J. Fonseca, B. Glavatovic, "
                    "C. Lindholm, K. Makropoulos, C. Meletti, R. Musson, "
                    "K. Pitilakis, K. Sesetyan,  D. Stromeyer,  M. Stucchi, "
                    "A. Rovida, Seismic Hazard Harmonization in Europe (SHARE): "
                    "Online Data Resource, doi: 10.12686/SED-00000001-SHARE, 2013.",
        "doi": "10.12686/SED-00000001-SHARE"
    },
    'eshm20': {
        'display_name': 'The 2020 European Seismic Hazard Model',
        'sources': [join(datadir, 'eshm20.geo.json'),
                    join(datadir, 'eshm20.json')],
        'url': 'http://www.hazard.efehr.org/en/Documentation/'
               'specific-hazard-models/europe/eshm2020-overview/'
    },
    'germany': {
        'sources': [join(datadir, 'germany.geo.json'),
                    join(datadir, 'germany.json')],
    },
    'global_stable': {
        'sources': [join(datadir, 'global_stable.geo.json'),
                    join(datadir, 'global_stable.json')],
    },
    'global_volcanic': {
        'sources': [join(datadir, 'global_volcanic.geo.json'),
                    join(datadir, 'global_volcanic.json')],
    }
}


def get_regionalization(geometries: Union[str, dict],
                        mappings: Union[str, dict]) -> list[dict[str, Any]]:
    """Return a dict where a region name is mapped to a GEO-JSON formatted list
    of geoJSOn Features:
    ```
    {
        "type": "Feature",
        "geometry":dict,  # geoJSON geometry
        "properties": {
            "region":str  # the region name
            "models":list[str]  # the list of region-selected models
        }
    }
    ```

    :param geometries: a geojson dict or file (str) of type FeatureCollection, where each
        feature is a geoJSOn Feature with at least the following attributes:
        ```
        {
            "properties": {
                "REGION":str  # the polygon region name
            }
            "geometry": {
                # standard geoJSON geometry (https://geojson.org/)
            }
        }
        ```
        polygon containing the polygon region name in the
        `properties.REGION` attribute,
        and the polygon geometry in the "geometry"
    :param mappings: a JSON dict or file (str) where each region is mapped to a list
        of dicts denoting a mapped model. The model name can be retrieved in the
        "model" key of each dict
    """
    if not isinstance(geometries, dict):
        with open(geometries, 'r') as _:
            geometries = json.load(_)
    if not isinstance(mappings, dict):
        with open(mappings, 'r') as _:
            mappings = json.load(_)

    regions = []
    for region_name, models in mappings.items():
        model_names = sorted({_['model'] for _ in models})
        geojson = {
            "type": "Feature",
            "geometry": {},  # will be populated below
            "properties": {
                "region": region_name,
                "models": model_names
            }
        }
        unsupported_models = [m for m in model_names if m not in registered_gsims]
        if unsupported_models:
            warnings.warn(f'Region "{region_name}" is mapped to unsupported model(s): '
                          f'{unsupported_models}')
        geojson_geometries = []
        for geojson_feature in geometries.get('features', []):
            feature_region_name = geojson_feature.get('properties', {}).\
                get('REGION', "")
            if feature_region_name != region_name:
                continue
            geojson_geometries.append(geojson_feature['geometry'])
        if not geojson_geometries:
            warnings.warn(f'Region "{region_name}" does not have '
                          f'geometries defined in the geojson file, skipping')
            continue
        geojson['geometry'] = merge_geojson_geometries(*geojson_geometries)
        regions.append(geojson)

    return regions


def merge_geojson_geometries(*geometries: dict) -> dict:
    """Merge the given geoJSON Geometry objects (Python `dict`s) into a new
    geoJSON Geometry object of type "Multipolygon". If any of the two arguments
    is falsy, it is ignored. If all arguments are falsy (or no argument is
    provided) then the empty dict is returned

    :param geometries: dict of geoJSON geometry object of type either
        "Polygon" or "MultiPolygon"
    """
    shapes = [shape(g) for g in geometries]
    whole_shape = unary_union(shapes)
    return json.loads(to_geojson(whole_shape))
