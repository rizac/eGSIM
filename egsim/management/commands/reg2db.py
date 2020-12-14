"""
Module for initializing the database with regionalizations provided from
external sources, to be used in the API and shown on the GUI map
(as of 2020, there is only one regionalization implemented: SHARE)

WORKFLOW for any new regionalization to be added
================================================

Choose a <source_id> name (e.g. research project name, area source model,
see e.g. "SHARE") and:

1. If needed for the regionalization, add external input data to the directory
    "./data/reg2db/<source_id>"
2. implement in this module the regionalization as a subclass of
   :class:`Regionalization`. The subclass must:
       2a. implement the `get_regions` method (see docstring for details), and
       2b. have name <source_id> (you can name the class differently, but then
           you must write the class attribute `_source_id="<source_id>"`).
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
    """Class defining the custom command to write all available
    regionalization(s) to db:
    ```
    export DJANGO_SETTINGS_MODULE="..."; python manage.py reg2db
    ```
    A regionalization is a set of Tectonic regions, i.e. geographic regions
    with an associated Tectonic region type (Trt).
    The regionalization usually comes from a data source (e.g., research
    project, area source model) in form of shapefiles or anything describing
    a set of Polygon areas and their trt.

    See this module docstring for info on how to add a new regionalization in
    the future and the :class:`SHARE` for a concrete subclass of
    :class:`Regionalization`.
    """

    # The formatting of the help text below (e.g. newlines) will be preserved
    # in the terminal output. All text after "Notes:" will be skipped from the
    # help of the wrapper/main command 'initdb'
    help = "\n".join([
        'Fetches all regionalization(s) from external data sources',
        '(\'commands/data\' directory) and writes them on the database.',
        'A regionalization is a set of Tectonic regions, i.e. geographic',
        'regions with an associated TRT.',
        'Notes:',
        '- TRT: Tectonic Region Type',
        '- Each region will correspond to a database table row. All',
        '  existing rows will be deleted from the database and overwritten'
    ])


    def handle(self, *args, **options):
        """Executes the command

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        try:
            trts = {_.oq_name: _ for _ in Trt.objects}  # noqa
            if not len(trts):
                raise ValueError('No Tectonic region type found')
        except Exception as _exc:
            raise CommandError('%s.\nDid you create the db first?\n(for '
                               'info see: https://docs.djangoproject.'
                               'com/en/2.2/topics/migrations/#workflow)' %
                               str(_exc))

        self.printinfo('Deleting existing regions (AND REFERENCED DATA, TOO) '
                       'from db')
        try:
            TectonicRegion.objects.all().delete()  # noqa
        except Exception as _exc:
            raise CommandError('Unable to delete existing regions: %s' %
                               str(_exc))

        for source_id, regionalization in get_regionalizations():
            self.handle_regionalization(source_id, regionalization, trts)
            self.printinfo('')

    def handle_regionalization(self,
                               source_id: str,
                               regionalization: 'Regionalization',
                               trts: 'dict'):

        self.printinfo("Creating and saving to db '%s' regionalization" %
                       source_id)

        count, saved = 0, 0
        for region_dict in regionalization.get_regions(self):
            count += 1
            region_dict.setdefault("source_id", source_id)
            # region_dict['trt'] is a str, replace it with the associated
            # Trt db object (if a mapping is found in `trts`):
            trt = region_dict.get('trt', None)
            if trt not in trts:
                msg = 'No TRT found' if not trt else ("'%s' is not a known "
                                                      "TRT in OpenQuake" % trt)
                self.collect_warning("Skipping region: %s" % msg)
                continue
            try:
                region_dict[trt] = trts[trt]  # replace str with Model instance
                region_dict['geojson'] = json.dumps(region_dict['geojson'])
                region = TectonicRegion({**region_dict, 'trt': trts[trt]})
                region.save()
                saved += 1
            except Exception as exc:
                self.collect_warning("Skipping region, error while saving: "
                                     "%s" % str(exc))

        self.print_collected_warnings()
        if saved:
            self.printsuccess("Done: %d of %d regions saved" % (saved, count))
        else:
            self.printwarn('Error: no region found')


######################################
# Regionalization class(es)
######################################


class Regionalization:
    """Abstract base class implementing a Regionalization, i.e. a collection of
    Geographic regions with associated Tectonic Region Type (TRT)
    """

    _source_id = None  # Overwrite this in subclasses providing a non empty str
    # if the the source_id you want to use is not the class name (e.g.,
    # it's an invalid Python class name). See source_id below

    @property
    def source_id(self):
        """Returns this instance source_id"""
        return self._source_id or self.__class__.__name__

    @property
    def datadir(self):
        """Returns the given Regionalization data directory, currently at
        "./data/<module_name>/<source_id>". Raises FileNotFoundError (with a
        meaningful message for users executing a command from the terminal) if
        the returned value is not a valid existing directory"""
        return self._get_datadir()

    def _get_datadir(self, check_isdir: bool = True):
        """Private method returning the given Regionalization data directory
        with optional flag to turn off directory check"""
        cmd_path = get_command_datadir(__name__)
        source_id = self.source_id
        path = os.path.join(cmd_path, source_id)
        if check_isdir and not os.path.isdir(path):
            raise FileNotFoundError('No data directory found for '
                                    'Regionalization "%s" in "%s"' %
                                    (source_id, cmd_path))
        return path

    def get_regions(self, calling_cmd: EgsimBaseCommand):
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
    """Implements the 'SHARE' Regionalization"""

    # maps a SHARE Tectonic region type to the OpenQuake equivalent:
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

    def get_regions(self, calling_cmd: EgsimBaseCommand):
        """Yields an iterable (e.g. tuple, list, generator expression) of
        dicts representing a geographic region with associated Tectonic Region
        Type (TRT). Each dict must have the following fields:
        {
        "geojson": dict  # for info see https://geojson.org/
        "trt": str  # one of the attributes of openquake.hazardlib.const.TRT
        }
        """
        for shp_path in get_filepaths(self.datadir, pattern='*.shp'):
            for feat in to_geojson_features(shp_path):
                props = feat['properties']
                trt = props.get('TECTONICS', None) or props.get('TECREG', None)
                if trt is not None and trt.lower() in self.mappings:
                    # try to get the Openquake tectonic region name from
                    # self.mappings, if not found move on, `calling_cmd` will skip
                    # teh region if the trt is invalid (and collect the warning)
                    trt = self.mappings[trt]
                # feat['properties'] can have whatever we might need to be
                # accessible in the frontend. Here we remove all properties
                # (save space):
                feat['properties'] = {}
                # Note: the model attribute will be set in the caller
                # if not present:
                yield {
                        'geojson': feat,
                        'trt': trt
                    }

#############
# Utilities #
#############


def get_regionalizations():
    """Returns a list of source_id names (str) mapped to the relative
    Regionalization instance
    """
    # we could write this as one-line expression but let's be explicit:
    ret = {}
    for classname, class_ in inspect.getmembers(sys.modules[__name__],
                                                _is_regionalization_class):
        regionalization_instance = class_()
        ret[regionalization_instance.source_id] = regionalization_instance
    return ret


def _is_regionalization_class(obj):
    return inspect.isclass(obj) and obj.__module__ == __name__ \
        and obj is not Regionalization and issubclass(obj, Regionalization)


def to_geojson(*shapefiles):
    """Reads the given shape files ('.shp') and return them joined in a
    'FeatureCollection' geojson dict. Example:
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
                "name": "whatever"
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
