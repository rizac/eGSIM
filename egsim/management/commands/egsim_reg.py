"""
Populate the database with regionalizations and mappings provided from
internal data in JSON and geoJSON format.

A regionalization is a set of Geographic regions with coordinates defined by
one or more Polygons, and a mapping is a list of GSIMs selected for a region

Usage:
```
export DJANGO_SETTINGS_MODULE="..."; python manage.py egsim_sel
```

WORKFLOW for any new regionalization to be added
================================================

See package shakyground2 (ask maintainers) and copy its regionalization_files
folder in data. then re-run the command

Created on 7 Dec 2020

@author: riccardo
"""
import os
import json
from collections import defaultdict

from django.core.management.base import CommandError

from egsim.core.utils import yaml_load, get_classes
from egsim.management.commands import EgsimBaseCommand

import egsim.models as models


class Command(EgsimBaseCommand):  # <- see _utils.EgsimBaseCommand for details
    """Class implementing the command functionality"""

    # As help, use the module docstring (until the first empty line):
    help = globals()['__doc__'].split("\n\n")[0]

    def handle(self, *args, **options):
        """Executes the command

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        confirm = 'yes'
        interactive = options['interactive']
        count = sum(_.objects.count() for _ in
                    (models.Region, models.GeoPolygon, models.GsimMapping))
        if count and interactive:
            confirm = input("The affected tables have already data stored. "
                            "Type 'yes' if you want to add data on top of that. "
                            "Otherwise, exit and run `egsim_init` which "
                            "empties all tables and eventually runs this command")
        if confirm != 'yes':
            self.stdout.write('Operation cancelled.')
            return

        datadir = self.get_datadir('regionalization_files')

        for filename in os.listdir(datadir):
            name, ext = os.path.splitext(filename)
            if ext.lower() in ('json', 'geojson'):
                self.printwarn('Skipping regionalization "%s" (invalid file '
                               'extension "%s")' % (name, ext))
                continue

            regionalization_file = os.path.join(datadir, name + '.json')
            mapping_file = os.path.join(datadir, name + '.geojson')

            try:
                file = os.path.basename(regionalization_file)
                with open(regionalization_file, 'r') as _:
                    regionalization = json.load(_)
                file = os.path.basename(mapping_file)
                with open(mapping_file, 'r') as _:
                    mapping = json.load(_)
                regions = self.populate_regionalizations(regionalization, mapping)

            except Exception as exc:
                self.printwarn('Skipping regionalization "%s": %s' % (file, str(exc)))
                continue

    def populate_from_regionalization(self, name:str, regionalization:dict,
                                      mapping: dict):
        """"""
        count = 0
        geometries = defaultdict(list)
        for geojson_feature in regionalization.get('features', []):
            feature_properties = geojson_feature.get('properties', [])
            region = str(feature_properties['REGION'])
            geometry = feature_properties['geometry']
            geometries[region].append(geometry)
            # now process the json Gsim:


def merge_geojson_geometries(*geometries:dict) -> dict:
    """Merge the given geoJSON Geometry objects (Python `dict`s) into a new
    geoJSON Geometry object of type "Multipolygon". If any of the two arguments
    is falsy, it is ignored. If all arguments are falsy (or no argument is
    provided) then the empty dict is returned

    :param geometries: dict of geoJSON geometry object of type either
        "Polygon" or "MultiPolygon"
    """
    P, MP, C, T = "Polygon", "MultiPolygon", "coordinates", "type"  # noqa

    coords = []

    for geometry in geometries:

        geometry = geometry or {}

        # only Polygon and MultiPolygon types supported:
        gtype = geometry.get(T)
        if gtype not in (P, MP):
            continue

        # get coordinates (assuring the dict key exist, otherwise return {})
        gcoords = geometry.get(C)
        if not isinstance(gcoords, (list, tuple)):
            continue

        # merge:
        if gtype == P:   # If polygon, "convert" to multipolygon coordinates
            gcoords = [gcoords]

        coords.extend(gcoords)

    return {} if not coords else {T: MP, C: coords}
