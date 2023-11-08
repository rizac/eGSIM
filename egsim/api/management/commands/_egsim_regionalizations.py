"""
Populate the database with regionalizations provided from
internal data in JSON and geoJSON format.

A regionalization is a set of Geographic regions with coordinates defined by
one or more Polygons, and a mapping is a list of GSIMs selected for a region

Created on 7 Dec 2020

@author: riccardo
"""
from os.path import join, dirname, isdir
from os import makedirs
import json
import warnings

from . import EgsimBaseCommand
from ... import models
from ...data.regionalizations import get_regionalizations, DATA


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
        self.printinfo('Parsing Regionalizations from sources:')
        self.empty_db_table(models.Regionalization)
        destdir = 'regionalizations'
        # redirect warning to self.printsoftwarn:
        showwarning = warnings.showwarning
        warnings.showwarning = lambda m, *k, **kw: self.printwarn(m)
        # warnings.simplefilter("ignore")
        for name, regionalization in get_regionalizations():
            # save object metadata to db:
            relpath = join(destdir, name) + ".geo.json"
            # store object refs, if any:
            ref_keys = set(DATA.get(name, {})) & \
                       set(f.name for f in models.Reference._meta.get_fields())  # noqa
            refs = {f: DATA[name][f] for f in ref_keys}
            db_obj = models.Regionalization.objects.create(name=name,
                                                           media_root_path=relpath,
                                                           **refs)
            # save object to disk:
            filepath = db_obj.filepath  # abspath
            if not isdir(dirname(filepath)):
                makedirs(dirname(filepath))
            with open(filepath, 'w') as _:
                json.dump(regionalization, _, separators=(',', ':'))

            self.printinfo(f'  Regionalization "{name}" ({filepath}), '
                           f'{len(regionalization)} region(s):')
            for region, val in regionalization.items():
                self.printinfo(f"    {region}: "
                               f"{len(val['properties']['models'])} model(s), "
                               f"geometry type: {val['geometry']['type']}")


        saved_regs = models.Regionalization.objects.count()
        if saved_regs:
            self.printsuccess(f'{saved_regs} regionalization(s) saved to {destdir}')
        # restore default func
        warnings.showwarning = showwarning
