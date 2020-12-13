"""
Module for writing to db the Gsim selections (by tectonic region type, or TRT).
A Gsim selection is a set of relations between a TRT and a list of
associated Gsims

WORKFLOW for any new gsim selection to be added
================================================

Choose a <source_id> name (e.g. research project name, area source model,
see e.g. "SHARE") and add <source_id>.json to the data directory
"./data/gsimsel2db". The JSON file must be a dict where each key is a TRT (str)
mapped to a list of Gsims (str)

Created on 9 Dec 2020

@author: riccardo
"""
import json
import os

from django.core.management.base import CommandError

from egsim.models import Trt, GsimTrtRelation, Gsim
from ._utils import EgsimBaseCommand, get_command_datadir, get_filepaths


class Command(EgsimBaseCommand):  # <- see _utils.EgsimBaseCommand for details
    """Class defining the custom command to write all available
    Gsim selections (by tectonic region type, or TRT) to the database:
    ```
    export DJANGO_SETTINGS_MODULE="..."; python manage.py gsimsel2db
    ```
    """

    # The formatting of the help text below (e.g. newlines) will be preserved
    # in the terminal output. All text after "Note:" will be skipped from the
    # help of the wrapper/main command 'initdb'
    help = ('Fetches all Gsims selection(s) (by Tectonic region type, or TRT)\n'
            'provided in the package input data and writes them on the database\n'
            '(a Gsim selection is a set of relations between a TRT and a list\n'
            'of associated Gsims).\n'
            'Note: all existing selections will be deleted from the database\n'
            'and overwritten.')

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
            source_id = os.path.splitext(os.path.basename(json_file))[0]
            with open(json_file) as _:
                json_dict = json.load(_)
            if not isinstance(json_dict, dict):
                raise CommandError('"%s" content is not a JSON-formatted dict' %
                                   source_id)
            for (trt_str, gsim_list) in json_dict.items():
                if _ not in trts:
                    self.printwarn('"%s" is not a valid TRT' % _)
                    continue
                else:
                    trt = trts[_]
                valid_gsims = []
                for _ in gsim_list:
                    if _ not in gsims:
                        self.printwarn('"%s" (related to "%s") is not a valid '
                                       'Gsim' % (trt.oq_name, _))
                        continue
                    valid_gsims.append(gsims[_])
                for gsim in valid_gsims:
                    GsimTrtRelation.objects.create(GsimTrtRelation(trt=trt,
                                                                   gsim=gsim,
                                                                   source_id=source_id))

            self.printinfo('')
