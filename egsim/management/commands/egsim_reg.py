"""
Populate the database with regionalizations provided from external sources
(commands 'data' directory. As of 2020, there is only one regionalization
implemented: SHARE).
A regionalization is a set of Geographic regions with an associated
Tectonic region type (TRT). Each (region, TRT) tuple will correspond to a
new database table row

All existing rows will be deleted and overwritten.

Usage:
```
export DJANGO_SETTINGS_MODULE="..."; python manage.py egsim_sel
```



WORKFLOW for any new regionalization to be added
================================================

Choose a <source_id> name (e.g. research project name, area source model,
see e.g. "SHARE") and:

1. If needed for the regionalization, add external input data to the directory
    "./data/reg2db/<source_id>"
2. Implement in this module the regionalization as a subclass of
   :class:`Regionalization`. The subclass must:
       2a. Implement the `get_regions` method (see docstring for details), and
       2b. Have name <source_id> (you can name the class differently, but then
           you must write the class attribute `_source_id="<source_id>"`)

See :class:`SHARE` for an example

Created on 7 Dec 2020

@author: riccardo
"""
import os
import json

from django.core.management.base import CommandError

from egsim.models import GeographicRegion
from egsim.core.utils import yaml_load, get_classes
from ._utils import EgsimBaseCommand, get_command_datadir, get_filepaths, get_trts


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
        try:
            trts = get_trts()  # noqa
        except Exception as _exc:
            raise CommandError(str(_exc))

        # clear existing data (_meta.db_table is the model table name on the db)
        self.flush(*args, **{**options, 'tables': GeographicRegion._meta.db_table})

        for source_id, regionalization in get_classes(__name__, Regionalization):
            if regionalization is Regionalization:  # abstract class, skip:
                continue
            self.handle_regionalization(source_id, regionalization, trts)
            self.printinfo('')

    def handle_regionalization(self,
                               source_id: str,
                               regionalization: 'Regionalization',
                               trts: 'dict'):

        self.printinfo("Creating and saving to db '%s' regionalization" %
                       source_id)

        count, saved = 0, 0
        for count, region_dict in enumerate(regionalization.get_regions(self), 1):
            region_dict.setdefault("source_id", source_id)
            # region_dict['trt'] is a str, replace it with the associated
            # Trt db object (if a mapping is found in `trts`):
            trt = region_dict.get('trt', None)
            if trt not in trts:
                msg = 'No TRT found' if not trt \
                    else ('TRT name "%s"" unknown' % trt)
                # OLD: self.collect_warning("Skipping region: %s" % msg). NOW:
                raise CommandError("Region #%d: %s" % (count, msg))
            try:
                region_dict[trt] = trts[trt]  # replace str with Model instance
                region_dict['geojson'] = json.dumps(region_dict['geojson'])
                region = GeographicRegion({**region_dict, 'trt': trts[trt]})
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
        "geojson": dict  # for the dict format info see https://geojson.org/
        "trt": str  # a valid Trt name (see `oq2db` cmd and oq2db/trt.yaml file)
        }
        """
        raise NotImplementedError('You must implement `get_regions`')


class SHARE(Regionalization):
    """Implements the 'SHARE' Regionalization"""

    def get_regions(self, calling_cmd: EgsimBaseCommand):
        """Yields an iterable (e.g. tuple, list, generator expression) of
        dicts representing a geographic region with associated Tectonic Region
        Type (TRT). Each dict must have the following fields:
        {
        "geojson": dict  # for the dict format info see https://geojson.org/
        "trt": str  # a valid Trt name (see `oq2db` cmd and oq2db/trt.yaml file)
        }
        """
        for shp_path in get_filepaths(self.datadir, pattern='*.geojson'):
            shp_name = os.path.basename(shp_path)
            try:
                # find the Trt attribute:
                trt_attname = {
                    'share_subduction_interface': 'TECREG',
                    'share_model_area_regions': 'trt'
                }[os.path.splitext(shp_name)[0]]
            except KeyError:
                raise CommandError('"%s" has no associated Trt attribute in "%s"' %
                                   (shp_name, __file__))

            feat_collection = yaml_load(shp_path)  # dict of this type:
            # https://rdrr.io/cran/geoops/man/FeatureCollection.html
            for feat in feat_collection['features']:
                props = feat['properties']
                # Get the Trt name. if not found move on, `calling_cmd` will
                # raise (or print a warning, depending on the implementation)
                trt_name = props.get(trt_attname, None)
                # feat['properties'] can have whatever we might need to be
                # accessible in the frontend. Here we remove all properties
                # (save space):
                feat['properties'] = {}
                # Note: the model attribute will be set in the caller
                # if not present:
                yield {
                    'geojson': feat,
                    'trt': trt_name
                }
