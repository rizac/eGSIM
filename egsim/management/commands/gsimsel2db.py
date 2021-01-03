"""
Command to fetch all GSIMs selection(s) by TRT from external data sources
('commands/data' directory) and write them on the database (one row per
(GSIM, TRT) tuple). A GSIM selection is a set of relations between a TRT and a
list of associated GSIMs

Usage:
```
export DJANGO_SETTINGS_MODULE="..."; python manage.py gsimsel2db
```

====================================
WORKFLOW TO ADD A NEW GSIM SELECTION
====================================

Choose a <source_id> name (e.g. research project name, area source model,
see e.g. "SHARE") and add <source_id>.json to the data directory
"./data/gsimsel2db". The JSON file must be a dict[str, List[str]] where each
key is a Tectonic Region Type (one of the key or values of
"./data/oq2db/trt.yaml") mapped to a list of Gsims (class names of
OpenQuake Gsims)

Created on 9 Dec 2020

@author: riccardo
"""
import json
import os

from django.core.management.base import CommandError

from egsim.models import Trt, GsimTrtRelation, Gsim
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
            trts = get_trts()
        except Exception as _exc:
            raise CommandError(str(_exc))

        try:
            gsims = {_.key: _ for _ in Gsim.objects}  # noqa
            if not len(gsims):
                raise ValueError('No Gsim found')
        except Exception as _exc:
            raise CommandError('%s.\nDid you create the db first?\n(for '
                               'info see: https://docs.djangoproject.'
                               'com/en/2.2/topics/migrations/#workflow)' %
                               str(_exc))

        self.printinfo('Deleting existing Gsim selections from db')
        try:
            GsimTrtRelation.objects.all().delete()  # noqa
        except Exception as _exc:
            raise CommandError('Unable to delete existing Gsim selections: %s' %
                               str(_exc))

        for json_file in get_filepaths(get_command_datadir(__name__), '*.json'):
            self.printinfo('Processing %s' % json_file)
            filename = os.path.basename(json_file)
            source_id = os.path.splitext(filename)[0]
            with open(json_file) as _:
                json_dict = json.load(_)
            if not isinstance(json_dict, dict):
                raise CommandError('Content is not a JSON-formatted dict. '
                                   'File: "%s"' % filename)
            for (trt_str, gsim_list) in json_dict.items():
                trt = trts.geT(_, None)
                if trt is None:
                    raise CommandError('"%s" is not a valid TRT. File: "%s"' %
                                       (_, filename))
                valid_gsims = []
                for _ in gsim_list:
                    if _ not in gsims:
                        raise CommandError('Invalid "%s" (related to "%s"). '
                                           'File: "%s"' % (_, trt.key, filename))
                    valid_gsims.append(gsims[_])
                for gsim in valid_gsims:
                    inst = GsimTrtRelation(trt=trt, gsim=gsim, source_id=source_id)
                    GsimTrtRelation.objects.create(inst)

            self.printinfo('')
