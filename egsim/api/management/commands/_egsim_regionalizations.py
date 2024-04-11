"""
eGSIM management command. See `Command.help` for details
"""
from os.path import join
import warnings
from django.core.management import BaseCommand, CommandError

from ... import models
from ...data.regionalizations import get_regionalizations, DATA


class Command(BaseCommand):

    help = "Parse of JSON+geoJSON regionalization files stored in the API source data " \
           "into single standardized regionalization files. Store each parsed file as " \
           "JSON in the API MEDIA directory and the file metadata in the Database"

    def handle(self, *args, **options):
        """Executes the command

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        self.stdout.write('Parsing Regionalizations from sources:')
        models.Regionalization.objects.all().delete()
        if models.Regionalization.objects.all().count():
            raise CommandError('Table is not empty (deletion failed?), check the DB')

        destdir = 'regionalizations'
        # redirect warning to self.printsoftwarn:
        with warnings.catch_warnings():
            warnings.showwarning = \
                lambda m, *k, **kw: self.stdout.write(self.style.WARNING(m))
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
                db_obj.write_to_filepath(regionalization)

                self.stdout.write(f'  Regionalization "{name}" ({db_obj.filepath}), '
                                  f'{len(regionalization)} region(s):')
                for feat in regionalization:
                    self.stdout.write(f"    {feat['properties']['region']}: "
                                      f"{len(feat['properties']['models'])} model(s), "
                                      f"geometry type: {feat['geometry']['type']}")

            saved_regs = models.Regionalization.objects.count()
            if saved_regs:
                self.stdout.write(self.style.SUCCESS(f'{saved_regs} regionalization(s) '
                                                     f'saved to {destdir}'))
