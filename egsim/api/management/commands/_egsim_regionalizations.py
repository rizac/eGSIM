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
from os.path import join
import json

from django.core.management import CommandError

from . import EgsimBaseCommand
from ... import models
from ...data.regionalizations import get_regionalizations, REFS


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
        self.empty_db_table(models.Regionalization)

        destdir = self.output_dir('regionalizations')

        for name, regionalization in get_regionalizations():
            refs = REFS.get('name', {})
            refs['name'] = name
            self.printinfo(f'  Regionalization "{name}":')
            try:
                filepath = join(destdir, name) + ".geo.json"
                with open(filepath, 'w') as _:
                    json.dump(regionalization, _, separators=(',', ':'))
                models.Regionalization.objects.create(filepath=filepath, **refs)

            except Exception as exc:
                raise CommandError(exc)

        saved_regs = models.Regionalization.objects.count()
        if saved_regs:
            self.printsuccess(f'{saved_regs} regionalization(s) saved to database')
