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
from os.path import abspath, splitext, join, isfile
import json

from django.core.management import CommandError

from shapely import to_geojson  #, from_geojson
from shapely.geometry import shape
from shapely.ops import unary_union

from . import EgsimBaseCommand
from ... import models


SRC_DIR = EgsimBaseCommand.data_path('regionalizations')


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
        self.printinfo('Populating the database with Regionalization data:')
        self.empty_db_table(models.Regionalization, models.Regionalization)

        destdir = self.output_dir('regionalizations')

        for name, mapping_file, regionalization_file in self.get_data_files():
            self.printinfo(f'  Regionalization "{name}":')
            try:
                with open(regionalization_file, 'r') as _:
                    geometries = json.load(_)
                with open(mapping_file, 'r') as _:
                    mapping = json.load(_)
                regions = self.create_geojson(geometries, mapping)
                filepath = join(destdir, name) + ".geo.json"
                with open(filepath, 'w') as _:
                    json.dump(regions, _, separators=(',', ':'))
                # save db entry:
                refs = self.get_ref(mapping_file) or \
                           self.get_ref(regionalization_file)
                refs.setdefault('name', name)
                models.Regionalization.objects.create(filepath=filepath, **refs)

            except Exception as exc:
                raise CommandError(exc)

        saved_regs = models.Regionalization.objects.count()
        if saved_regs:
            self.printsuccess(f'{saved_regs} regionalization(s) saved to database')

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

    def create_geojson(self, geometries: dict, mapping: dict) -> dict:
        """"""
        regions = {}
        for region_name, models in mapping.items():
            geojson = {
                "type": "Feature",
                "geometry": {},  # will be populated below
                "properties": {
                    "models": [_['model'] for _ in models]
                }
            }
            geojson_geometries = []
            for geojson_feature in geometries.get('features', []):
                feature_region_name = geojson_feature.get('properties', {}).\
                    get('REGION', "")
                if feature_region_name != region_name:
                    continue
                geojson_geometries.append(geojson_feature['geometry'])
            if not geojson_geometries:
                self.printwarn(f'  Region "{region_name}" does not have '
                               f'geometries defined in the geojson file, skipping')
                continue
            geojson['geometry'] = merge_geojson_geometries(*geojson_geometries)
            regions[region_name] = geojson

        return regions

        # FIXME REMOVE
        #
        #
        # # a `reg` (regionalization) is composed of several regions. A region is a string
        # # mapped to a geographical geometry and 1 or more models.
        # # Build the dict of region -> geometry:
        # regions = defaultdict(list)
        # for geojson_feature in geometries.get('features', []):
        #     feature_properties = geojson_feature.get('properties', [])
        #     region = str(feature_properties['REGION'])
        #     geometry = geojson_feature['geometry']
        #     regions[region].append(geometry)
        # # merge all regions:
        # region_geometry:dict[str, dict] = {}
        # for region, geom_list in region_geometry.items():
        #     region_geometry[region] = merge_geojson_geometries(*geom_list)  # noqa
        # # Build the dict of region -> models
        # region_models:dict[str, set[str]] = defaultdict(set)
        # for region, models in mapping.items():
        #     region_models[region].update(_['model'] for _ in models)
        # # build and save to file:
        # printinfo, skipped = [], []
        # for gsim, regions in gsims2regions.items():
        #     geom = merge_geojson_geometries(*chain(*(region_geometry[r] for r in regions)))
        #     geom = round_geojson_geometry(geom)
        #     try:
        #         db_gsim = models.Gsim.objects.get(name=gsim)  # noqa
        #     except models.Gsim.DoesNotExist:  # noqa
        #         skipped.append(f"Region (type: {geom.get('type', 'unknown')}) "
        #                        f'skipped: associated model "{gsim}" not found in the '
        #                        f'database')
        #         continue
        #
        #     # if we do not have the regionalization, then compute the region geometry:
        #     r_name = regionalization_data_source['name']
        #     db_reg = models.Regionalization.objects.filter(name=r_name).first()
        #     if db_reg is None:
        #         reg_geometry = merge_geojson_geometries(*(r for rr in geometries.values()
        #                                                   for r in rr))
        #         reg_geometry = round_geojson_geometry(reg_geometry)
        #         db_reg = models.Regionalization.objects.\
        #             create(**regionalization_data_source, geometry=reg_geometry)
        #     models.GsimRegion.objects.create(regionalization=db_reg,
        #                                      gsim=db_gsim,  # noqa
        #                                      geometry=geom)
        #     # Print to screen:
        #     printinfo.append(f"{gsim} (Region of type {geom.get('type', 'unknown')})")
        #
        # if printinfo:
        #     self.printinfo(f' - Regionalization "{reg_name}"; {len(printinfo)} '
        #                    f"model{'' if len(printinfo) == 1 else 's'} written "
        #                    f'(number of associated GeoPolygons in brackets):\n'
        #                    f'   {", ".join(printinfo)}')
        # return skipped

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

# FIXME REMOVE

# def round_geojson_geometry(geometry: dict, decimal_digits=4):
#     def _round(val):
#         try:
#             return np.round(val, decimal_digits).tolist()
#         except ValueError:
#             # we might have problems with numpy shapes, e.g. [[[1,2]], [[1,2], [3,4]]]:
#             if isinstance(val, (list, tuple)) and \
#                     all(isinstance(v, (list, tuple)) for v in val):
#                 return [_round(v) for v in val]
#             raise
#     geometry['coordinates'] = _round(geometry['coordinates'])
#     return geometry

    # P, MP, C, T = "Polygon", "MultiPolygon", "coordinates", "type"  # noqa
    #
    # coordinates = []
    # types = []
    #
    # for geometry in geometries:
    #     if geometry:
    #         gtype, gcoords = geometry.get(T), geometry.get(C)
    #         if gtype in (P, MP) and isinstance(gcoords, (list, tuple)):
    #             coordinates.append(gcoords)
    #             types.append(gtype)
    #
    # if not coordinates:
    #     return {}
    # if len(coordinates) == 1:
    #     return {T: types[0], C: coordinates[0]}
    #
    # # merge and create a geojson multipolygon object:
    # new_coords = []
    # for gtype, gcoords in zip(types, coordinates):
    #     if gtype == P:   # polygon
    #         new_coords.append(gcoords)
    #     else: # multi polygon
    #         new_coords.extend(gcoords)
    #
    # return {T: MP, C: new_coords}

