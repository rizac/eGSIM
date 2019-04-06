'''
Shapes and geojson utilities

Created on 4 Jul 2018

@author: riccardo
'''
from os import walk
from os.path import join, splitext, dirname
import json
from collections import OrderedDict

from shapefile import Reader
from shapely.geometry import Point, shape, Polygon, mapping


# def find_shp(root):
#     '''finds all shape file ('.shp') in the specified directory `root` (recursive search)'''
#     shapefiles = []
#     for (dirpath, dirnames, filenames) in walk(root):
#         shapefiles.extend(join(dirpath, f) for f in filenames if splitext(f)[1] == '.shp')
#     return shapefiles


# def to_geojson(*shapefiles):
#     '''reads the given shape files ('.shp') and return them as a 'FeatureCollection'
#     geojson dict'''
#     features = [feat for shapefile in shapefiles for feat in to_geojson_features(shapefile)]
#     return {"type": "FeatureCollection", 'features': features}


# def to_geojson_features(shapefilepath):
#     '''reads the given shape file ('.shp') and returns it as a list of geojson
#     features of the form:
#     ```
#         {
#             "type": "Feature",
#             "geometry": {
#                 "type": "Point",
#                 "coordinates": [125.6, 10.1]
#                 },
#             "properties": {
#                 "name": "Dinagat Islands"
#             }
#         }
#     ```
#     '''
#     shp = Reader(shapefilepath)  # open the shapefile
#     shapes = shp.shapes()  # get all the polygons (class shapefile._Shape)
#     records = shp.records()
#     fields = [field[0] for field in shp.fields[1:]]
#     assert len(shapes) == len(records)
#     # Reminder: geojson syntax: http://geojson.org/:
#     return [{"type": "Feature",
#              'geometry': mapping(shape(s)),  # https://stackoverflow.com/a/40631091
#              'properties': OrderedDict(zip(fields, r))} for s, r in zip(shapes, records)]


def featuresiter(geojson):
    try:
        geojson = geojson['features']
    except TypeError:
        pass
    for feat in geojson:
        yield feat


def get_feature_properties(geojson, lon0, lat0, trts=None, lon1=None, lat1=None, key='OQ_TRT'):
    matching_trts = set()
    if trts is not None:
        trts = set(trts)

    ispoint = True
    nopoint = lon0 is None and lat0 is None
    if not nopoint:
        if lon1 is None or lat1 is None:
            point = Point([lon0, lat0])
        else:
            ispoint = False
            rect = Polygon([(lon0, lat0), (lon0, lat1), (lon1, lat1), (lon1, lat0)])

    for feat in featuresiter(geojson):
        trt = feat.get('properties', {}).get('OQ_TRT', '')
        if not trt or trt in matching_trts or (trts is not None and trt not in trts):
            continue
        if nopoint or (ispoint and shape(feat['geometry']).contains(point)) or \
                (not ispoint and shape(feat['geometry']).intersects(rect)):
            matching_trts.add(trt)

    return matching_trts


# def get_gsims(geojson, lon0, lat0, lon1, lat1, key='OQ_TRT'):
#     trts = get_feature_properties(geojson, lon0, lat0, lon1, lat1, key)
#     return [gsim for gsim in EGSIM.aval_gsims() if EGSIM.trtof(gsim) in trts]


def get_features_containing(geojson, lon, lat):
    '''returns the features of `geojson` whose geometry contains the given point identified
    by lon and lat

    :param geojson: dict or iterable. If dict it is a geojson `FeatureCollection` object,
        i.e. a dict in the form:
        ```
        {"type": "FeatureCollection", 'features': features}
        ```
        If list, it is the geojson `features`, i.e. a list of geojson objects of the form:
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
    :param lon: the longitude (or x) of the point (must be in the same unit of geojson
        features coordinates)
    :param lat: the latitude (or y) of the point (must be in the same unit of geojson
        features coordinates)

    :return: a list of geojson Features containing the point identified by lon and lat
    '''
    try:
        geojson = geojson['features']
    except TypeError:
        pass
    point = Point([lon, lat])
    return [f for f in geojson if shape(f['geometry']).contains(point)]


def get_features_intersecting(geojson, lon0, lat0, lon1, lat1):
    '''returns the features of `geojson` whose geometry intersects the given rectangle
    identified by lon0, lat0, lon1 and lat1.

    :param geojson: dict or iterable. If dict it is a geojson `FeatureCollection` object,
        i.e. a dict in the form:
        ```
        {"type": "FeatureCollection", 'features': features}
        ```
        If list, it is the geojson `features`, i.e. a list of geojson objects of the form:
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
    :param lon0: the longitude (or x) of the first point (must be in the same unit of geojson
        features coordinates)
    :param lat0: the latitude (or y) of the first point (must be in the same unit of geojson
        features coordinates)
    :param lon1: the longitude (or x) of the second point (must be in the same unit of
        geojson features coordinates)
    :param lat1: the latitude (or y) of the second point (must be in the same unit of geojson
        features coordinates)

    :return: a list of geojson Features containing the point identified by lon and lat
    '''
    try:
        geojson = geojson['features']
    except TypeError:
        pass
    rect = Polygon([(lon0, lat0), (lon0, lat1), (lon1, lat1), (lon1, lat0)])
    return [f for f in geojson if shape(f['geometry']).intersects(rect)]
