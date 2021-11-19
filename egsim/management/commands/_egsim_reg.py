"""
Populate the database with regionalizations provided from
internal data in JSON and geoJSON format.

A regionalization is a set of Geographic regions with coordinates defined by
one or more Polygons, and a mapping is a list of GSIMs selected for a region

See package shakyground2 (ask maintainers) and copy its regionalization_files
folder in data. then re-run the command

Created on 7 Dec 2020

@author: riccardo
"""
import os
import json
from collections import defaultdict
from itertools import chain

from django.core.management.base import CommandError

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
        self.printinfo('Populating DB with Regionalization data:')

        models2empty = [models.GsimRegion]
        items2delete = sum(_.objects.count() for _ in models2empty)  # noqa

        if items2delete:
            for model in models2empty:
                model.objects.all().delete()  # noqa
                if model.object.count() > 0:  # noqa
                    raise CommandError('Could not delete all data in table %s' %
                                       str(model))

        datadir = self.data_dir('regionalization_files')
        done = set()
        skipped = defaultdict(list)  # regionalization name -> list of warnings
        for filename in os.listdir(datadir):
            name, ext = os.path.splitext(filename)
            if name in done:
                continue
            done.add(name)

            try:
                if ext.lower() not in ('.json', '.geojson'):
                    raise ValueError('invalid file extension "%s"' % ext)
                    # self.printwarn('Skipping regionalization "%s" (invalid file '
                    #                'extension "%s")' % (name, ext))
                    # continue

                regionalization_file = os.path.join(datadir, name + '.geojson')
                mapping_file = os.path.join(datadir, name + '.json')

                with open(regionalization_file, 'r') as _:
                    regionalization = json.load(_)
                with open(mapping_file, 'r') as _:
                    mapping = json.load(_)
                _skipped = self.populate_from_regionalization(name, regionalization,
                                                              mapping)
                if _skipped:
                    skipped[name].extend(_skipped)
            except Exception as exc:
                skipped[name].append('Skipping regionalization "%s": %s' % (name, str(exc)))
                # self.printwarn('Skipping regionalization "%s": %s' % (name, str(exc)))
                # continue

        if skipped:
            self.printwarn('WARNING:')
            for name, errs in skipped.items():
                self.printwarn(' - Regionalization "%s":' % name)
                for err in errs:
                    self.printwarn(err)

    def populate_from_regionalization(self, name: str, regionalization: dict,
                                      mapping: dict):
        """"""
        geometries = defaultdict(list)
        for geojson_feature in regionalization.get('features', []):
            feature_properties = geojson_feature.get('properties', [])
            region = str(feature_properties['REGION'])
            geometry = geojson_feature['geometry']
            geometries[region].append(geometry)

        gsims2regions = defaultdict(list)
        for region, gsims in mapping.items():
            # each gsim in gsims is a dict representing a GSIM with parameters
            # we just set here the base Gsim, so let's use a set to avoid
            # replicating the same base Gsim more than once
            base_gsims = set(_['model'] for _ in gsims)
            for base_gsim in base_gsims:
                gsims2regions[base_gsim].append(region)

        printinfo, skipped = [], []
        for gsim, regions in gsims2regions.items():
            geom = merge_geojson_geometries(*chain(*(geometries[r] for r in regions)))
            try:
                db_gsim = models.Gsim.objects.get(name=gsim)  # noqa
            except models.Gsim.DoesNotExist:  # noqa
                _nump = models.GsimRegion.num_polygons(geom)
                _poly = 'Polygon' if _nump == 1 else 'Polygons'
                skipped.append('   %d %s skipped: '
                               'associated Gsim "%s" unknown (not written to DB)'
                               % (_nump, _poly, gsim))
                continue

            models.GsimRegion.objects.create(regionalization=name, gsim=db_gsim,  # noqa
                                             geometry=geom)
            # Print to screen:
            printinfo.append('%s (%s)' % (gsim, models.GsimRegion.num_polygons(geom)))

        if printinfo:
            _gsim = "Gsim" if len(printinfo) == 1 else "Gsims"
            self.printinfo(' - Regionalization "%s"; %d %s written '
                           '(number of associated GeoPolygons in brackets):\n'
                           '   %s' % (name, len(printinfo), _gsim, ", ".join(printinfo)))
        return skipped


def merge_geojson_geometries(*geometries: dict) -> dict:
    """Merge the given geoJSON Geometry objects (Python `dict`s) into a new
    geoJSON Geometry object of type "Multipolygon". If any of the two arguments
    is falsy, it is ignored. If all arguments are falsy (or no argument is
    provided) then the empty dict is returned

    :param geometries: dict of geoJSON geometry object of type either
        "Polygon" or "MultiPolygon"
    """
    P, MP, C, T = "Polygon", "MultiPolygon", "coordinates", "type"  # noqa

    coordinates = []
    types = []

    for geometry in geometries:
        if geometry:
            gtype, gcoords = geometry.get(T), geometry.get(C)
            if gtype in (P, MP) and isinstance(gcoords, (list, tuple)):
                coordinates.append(gcoords)
                types.append(gtype)

    if not coordinates:
        return {}
    if len(coordinates) == 1:
        return {T: types[0], C: coordinates[0]}

    # merge and create a geojson multipolygon object:
    new_coords = []
    for gtype, gcoords in zip(types, coordinates):
        if gtype == P:   # polygon
            new_coords.append(gcoords)
        else: # multi polygon
            new_coords.extend(gcoords)

    return {T: MP, C: new_coords}

