"""
Module for initializing the database with regionalizations provided from
external sources, to be used in the API and shown on the GUI map
(as of 2020, there is only one regionalization implemented: SHARE)


WORKFLOW for any new regionalization to be added
================================================

Choose a <source_id> name (e.g. research project name, area source model,
see e.g. "SHARE") and:

1. If needed for the regionalization, add external input data to the directory
    "./_data/reg2db/<source_id>"
2. implement in this module the regionalization as a subclass of
   :class:`Regionalization`. The subclass must:
       2a. implement the `get_regions` method (see docstring for details), and
       2b. have name <source_id> (you can name the class differently, but then
           you must write the class attribute `source_id="<source_id>"`).
See :class:`SHARE` for an example

Created on 7 Dec 2020

@author: riccardo
"""
import json
import os
import sys
import inspect

from django.core.management.base import CommandError
from openquake.hazardlib.const import TRT
from shapefile import Reader
from shapely.geometry import shape, mapping

from egsim.models import Trt, TectonicRegion
from ._utils import EgsimBaseCommand, get_command_datadir, get_filepaths


class Command(EgsimBaseCommand):  # <- see _utils.EgsimBaseCommand for details
    """Class defining the custom command to create a regionalization:
    ```
    export DJANGO_SETTINGS_MODULE="..."; python manage.py reg2db
    ```
    A regionalization is a set of Tectonic regions, i.e. geographic regions
    with an associated a Tectonic region type (Trt).
    The regionalization usually comes from a data source (e.g., research
    project, area source model) in form of shapefiles or anything describing
    a set of Polygon areas and their trt.

    See this module docstring for info on how to add new regionalizations from
    future research projects and the :class:`SHARE` for a concrete subclass of
    :class:`Regionalization` where geographic regions from the SHARE project
    data are created in order to be stored on the eGSIM database.
    """
    help = ('Fetches all regionalization(s) provided in the package input data '
            'and writes them on the database (one geographic region per table '
            'row). A regionalization is a set of Tectonic regions, i.e. '
            'geographic regions with an associated Tectonic Region Type (TRT)')

    def handle(self, *args, **options):
        try:
            trts = {_.oq_name: _ for _ in Trt.objects}
            if not len(trts):
                raise ValueError('No Tectonic region type found')
        except Exception as _exc:
            raise CommandError('%s.\nDid you create the db first?\n(for '
                               'info see: https://docs.djangoproject.'
                               'com/en/2.3/topics/migrations/#workflow)' %
                               str(_exc))

        self.printinfo('Deleting existing regions (AND REFERENCED DATA, TOO) '
                       'from db ')
        try:
            TectonicRegion.objects.all().delete()
        except Exception as _exc:
            raise CommandError('Unable to delete existing regions: %s' %
                               str(_exc))

        for source_id, regionalization in get_regionalizations():
            self.handle_regionalization(source_id, regionalization, trts)

    def handle_regionalization(self,
                               source_id: str,
                               regionalization: 'Regionalization',
                               trts: 'dict'):

        self.printinfo("Creating and saving to db '%s' regionalization" %
                       source_id)

        count = 0
        for count, region_dict in enumerate(regionalization.get_regions(), 1):
            region_dict.setdefault("source_id", source_id)
            trt_ = region_dict.get('trt', None)
            if trt_ in trts:
                region = TectonicRegion(**region_dict)
            else:
                self.printerr("skipping Region: "
                              "'%s' is not a valid TRT name" % trt_)
            region.save()

        if count:
            self.printsuccess("Saved %d regions" % count)
        else:
            self.printwarn('No region found')


######################################
# Regionalization class(es)
######################################


class Regionalization:
    """Abstract base class implementing a Regionalization, i.e. a collection of
    Geographic regions with associated Tectonic Region Type (TRT)
    """

    source_id = None  # source_id of this regionalization.
    # By default is falsy (e.g. None or ""), meaning that if it's not overwritten
    # in subclasses it will default to the (sub)class name (see e.g. SHARE below)

    @property
    def datadir(self):
        """Returns the given Regionalization data directory, currently at
        "./_data/<module_name>/<classname>". Raises FileNotFoundError (with a
        meaningful message for users executing a command from the terminal) if
        the returned value is not a valid existing directory on the OS"""
        return self._get_datadir()

    @classmethod
    def _get_datadir(cls, check_isdir: bool = True):
        """Private method returning the given Regionalization data directory
        with optional flag to turn off directory check"""
        cmd_path = get_command_datadir(__name__)
        regionalization_name = cls.source_id or cls.__name__
        path = os.path.join(cmd_path, regionalization_name)
        if check_isdir and not os.path.isdir(path):
            raise FileNotFoundError('No data directory found for '
                                    'Regionalization "%s" in "%s"' %
                                    (regionalization_name, cmd_path))
        return path

    def get_regions(self):
        """Yields an iterable (e.g. tuple, list, generator expression) of
        dicts representing a geographic region with associated Tectonic Region
        Type (TRT). Each dict must have the following fields:
        {
        "geojson": dict  # for info see https://geojson.org/
        "trt": str  # one of the attributes of openquake.hazardlib.const.TRT
        }
        """
        raise NotImplementedError('You must implement `get_regions`')


class SHARE(Regionalization):
    """Implements the 'SHARE' RegionsCollection"""

    # maps a SHARE Tectonic region name to the OpenQuake equivalent
    mappings = {
        'active shallow crust': TRT.ACTIVE_SHALLOW_CRUST,  # 'Active Shallow Crust',
        'stable shallow crust': TRT.STABLE_CONTINENTAL,  # 'Stable Shallow Crust',
        'subduction interface': TRT.SUBDUCTION_INTERFACE,  # 'Subduction Interface',
        'subduction intraslab': TRT.SUBDUCTION_INTRASLAB,  # 'Subduction IntraSlab',
        "upper mantle": TRT.UPPER_MANTLE,  # "Upper Mantle",
        'volcanic': TRT.VOLCANIC,  # 'Volcanic',
        'geothermal': TRT.GEOTHERMAL,  # 'Geothermal',
        'induced': TRT.INDUCED,  # 'Induced',
        "subduction inslab": TRT.SUBDUCTION_INTRASLAB,  # "Subduction IntraSlab",
        "stable continental crust": TRT.STABLE_CONTINENTAL,  # 'Stable Shallow Crust',
        "inslab": TRT.SUBDUCTION_INTRASLAB,  # "Subduction IntraSlab",
        "subduciton inslab": TRT.SUBDUCTION_INTRASLAB  # typo ...
    }

    def get_regions(self):
        """Yields an iterable (e.g. tuple, list, generator expression) of
        dicts representing a geographic region with associated Tectonic Region
        Type (TRT). Each dict must have the following fields:
        {
        "geojson": dict  # for info see https://geojson.org/
        "trt": str  # one of the attributes of openquake.hazardlib.const.TRT
        }
        """
        for shppath in get_filepaths(self.datadir, pattern='*.shp'):
            geojsonfeatures = to_geojson_features(shppath)
            for feat in geojsonfeatures:
                props = feat['properties']
                key_ = props.get('TECTONICS', None) or \
                    props.get('TECREG', None)
                try:
                    trt_oq_name = self.mappings[(props.get('TECTONICS', '') or
                                            props.get('TECREG', '')).lower()]

                    # feat['properties'] can have whatever we might need to be
                    # accessible in the frontend. Here we remove all properties
                    # (save space):
                    feat['properties'] = {}
                    # Note: the model attribute will be set in the caller
                    # if not present:
                    yield {
                        'geojson': json.dumps(feat),
                        'trt': trt_oq_name
                    }
                except KeyError:
                    continue


#############
# Utilities #
#############

def get_regionalizations():
    """Returns a list of source_id names (str) mapped to the relative
    Regionalization instance"""
    # we could write this as one-line expression but let's be explicit:
    ret = {}
    for classname, class_ in inspect.getmembers(sys.module[__name__],
                                                _is_regionalization_class):
        source_id = class_.source_id or class_.__name__
        ret[source_id] = class_()
    return ret


def _is_regionalization_class(obj):
    return inspect.isclass(obj) and obj.__module__ == __name__ \
        and obj is not Regionalization and issubclass(obj, Regionalization)


def to_geojson(*shapefiles):
    """Reads the given shape files ('.shp') and return them joined in a
    'FeatureCollection' geojson dict:
    ```
    {
       "type": "FeatureCollection",
       "features": [
           {
               "type": "Feature",
               "geometry": {
                   "type": "Polygon",
                   "coordinates": [
                       [
                           [100.0, 0.0],
                           [101.0, 0.0],
                           ...
                       ]
                   ]
               },
               "properties": {
                   "prop0": "value0",
                   "prop1": {
                       "this": "that"
                   }
               }
           },
           ...
       ]
    }
    ```
    """
    features = [feat for shapefile in shapefiles
                for feat in to_geojson_features(shapefile)]
    return {"type": "FeatureCollection", 'features': features}


def to_geojson_features(shapefilepath):
    """Reads the given shape file ('.shp') and returns it as a list of geojson
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
    """
    shp = Reader(shapefilepath)  # open the shapefile
    shapes = shp.shapes()  # get all the polygons (class shapefile._Shape)
    records = shp.records()
    fields = [field[0] for field in shp.fields[1:]]
    if len(shapes) != len(records):
        raise ValueError('Number of shapefile shapes and dbf file records '
                         'mismatch (file: %s)' % shapefilepath)
    # Reminder: geojson syntax: http://geojson.org/:
    for shp, rec in zip(shapes, records):
        yield {
            "type": "Feature",
            'geometry': mapping(shape(shp)),  # https://stackoverflow.com/a/40631091
            'properties': dict(zip(fields, rec))
        }
