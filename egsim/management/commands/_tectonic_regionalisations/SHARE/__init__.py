'''module converting SHARE shape files into Tectonic Regions for the eGSIM
database'''

import os
import json

from shapefile import Reader
from shapely.geometry import Point, shape, Polygon, mapping
from openquake.hazardlib.const import TRT

from egsim.models import TectonicRegion


def create(trts):
    trts_d = {_.oq_name: _ for _ in trts}
    shapefiles = get_shapefiles()
    tecregions = []
    for shp in shapefiles:
        geojsonfeatures = to_geojson_features(shp)
        for feat in geojsonfeatures:
            props = feat['properties']
            try:
                oq_name = mappings[(props.get('TECTONICS', '') or
                                    props.get('TECREG', '')).lower()]
            except KeyError:
                continue
            if oq_name in trts_d:
                try:
                    trt = trts_d[oq_name]
                except KeyError:
                    continue
                # remove all properties (save space)
                # put here whatever you need to be accessible in the frontend
                # (the TRT information will be available in any case)
                feat['properties'] = {}
                # Note: the model attribute will be set in the caller
                # if not present:
                tecregions.append(TectonicRegion(geojson=json.dumps(feat),
                                                 type=trt))
    return tecregions


# maps a SHARE Tectonic region name to the OpenQuake equivalent
mappings = {
    'active shallow crust':  TRT.ACTIVE_SHALLOW_CRUST,  # 'Active Shallow Crust',
    'stable shallow crust': TRT.STABLE_CONTINENTAL,  # 'Stable Shallow Crust',
    'subduction interface': TRT.SUBDUCTION_INTERFACE,  # 'Subduction Interface',
    'subduction intraslab': TRT.SUBDUCTION_INTRASLAB,  # 'Subduction IntraSlab',
    "upper mantle": TRT. UPPER_MANTLE,  # "Upper Mantle",
    'volcanic': TRT.VOLCANIC,  # 'Volcanic',
    'geothermal': TRT.GEOTHERMAL,  # 'Geothermal',
    'induced': TRT.INDUCED,  # 'Induced',
    "subduction inslab": TRT.SUBDUCTION_INTRASLAB,  # "Subduction IntraSlab",
    "stable continental crust": TRT.STABLE_CONTINENTAL,  # 'Stable Shallow Crust',
    "inslab": TRT.SUBDUCTION_INTRASLAB,  # "Subduction IntraSlab",
    "subduciton inslab": TRT.SUBDUCTION_INTRASLAB  # typo ...
}


def get_shapefiles():
    root = os.path.dirname(os.path.abspath(__file__))
    return [os.path.join(root, _) for _ in os.listdir(root)
            if os.path.splitext(_)[1] == '.shp']


def to_geojson(*shapefiles):
    '''reads the given shape files ('.shp') and return them as a
    'FeatureCollection' geojson dict'''
    features = [feat for shapefile in shapefiles
                for feat in to_geojson_features(shapefile)]
    return {"type": "FeatureCollection", 'features': features}


def to_geojson_features(shapefilepath):
    '''reads the given shape file ('.shp') and returns it as a list of geojson
    features of the form:
    ```
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [125.6, 10.1]
                },
            "properties": {
                "name": "Dinagat Islands"
            }
        }
    ```
    '''
    shp = Reader(shapefilepath)  # open the shapefile
    shapes = shp.shapes()  # get all the polygons (class shapefile._Shape)
    records = shp.records()
    fields = [field[0] for field in shp.fields[1:]]
    assert len(shapes) == len(records)
    # Reminder: geojson syntax: http://geojson.org/:
    return [
        {
            "type": "Feature",
            'geometry': mapping(shape(s)),  # https://stackoverflow.com/a/40631091
            'properties': dict(zip(fields, r))
        }
        for s, r in zip(shapes, records)
    ]
