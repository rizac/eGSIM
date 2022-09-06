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
from os import listdir
from os.path import abspath, dirname, splitext, join, basename, isfile
import json
from collections import defaultdict
from itertools import chain

from . import EgsimBaseCommand
from ... import models


SRC_DIR = EgsimBaseCommand.data_path('regionalization_files')


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
        self.empty_db_table(models.GsimRegion, models.RegionalizationDataSource)

        skipped = defaultdict(list)  # regionalization name -> list of warnings
        for name, mapping_file, regionalization_file in self.get_data_files():
            try:
                data_source = self.data_source(mapping_file) or \
                    self.data_source(regionalization_file)
                data_source.setdefault('name', name)

                with open(regionalization_file, 'r') as _:
                    regionalization = json.load(_)
                with open(mapping_file, 'r') as _:
                    mapping = json.load(_)
                _skipped = self.populate_from_regionalization(data_source,
                                                              regionalization,
                                                              mapping)
                if _skipped:
                    skipped[name].extend(_skipped)
            except Exception as exc:
                skipped[name].append('Skipping regionalization "%s": %s' % (name, str(exc)))

        if skipped:
            self.printwarn('WARNING:')
            for name, errs in skipped.items():
                self.printwarn(' - Regionalization "%s":' % name)
                for err in errs:
                    self.printwarn(err)

    @classmethod
    def get_data_files(cls) -> dict[str, list[str]]:
        datadir = SRC_DIR
        ret = set()
        for filename in listdir(datadir):
            name, ext = splitext(filename)
            if name in ret:
                continue
            ret.add(name)

            is_json = ext.lower() == '.json'
            mapping_file = abspath(join(datadir, name + '.json'))
            isfile1 = is_json or isfile(mapping_file)

            is_geojson = ext.lower() == '.geojson'
            regionalization_file = abspath(join(datadir, name + '.geojson'))
            isfile2 = is_geojson or isfile(regionalization_file)

            if isfile1 and isfile2:
                yield [name, mapping_file, regionalization_file]

    def populate_from_regionalization(self, regionalization_data_source: dict,
                                      regionalization: dict,
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

            rds, _ = models.RegionalizationDataSource.objects.\
                get_or_create(**regionalization_data_source)  # noqa
            models.GsimRegion.objects.create(regionalization=rds,
                                             gsim=db_gsim,  # noqa
                                             geometry=geom)
            # Print to screen:
            printinfo.append('%s (%s)' % (gsim, models.GsimRegion.num_polygons(geom)))

        if printinfo:
            _gsim = "Gsim" if len(printinfo) == 1 else "Gsims"
            name = rds.name
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

