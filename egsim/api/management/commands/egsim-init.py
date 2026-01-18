"""
eGSIM management command. See `Command.help` for details
"""
import warnings
from os.path import join, expanduser, abspath, isfile, dirname, basename

import yaml
from django.core.management import BaseCommand, CommandError
from egsim.smtk import (registered_gsims, gsim, intensity_measures_defined_for,
                        ground_motion_properties_required_by, get_sa_limits)
from egsim.smtk.flatfile import column_exists
from ... import models
from django.conf import settings


if any(_['ENGINE'] == 'django.db.backends.sqlite3' for _ in settings.DATABASES.values()):
    # check JSON1 extension (it should be enabled in all newest OSs and Python versions):
    # Note that Django does also this (JSONField) but for safety we do it here again
    try:
        import sqlite3
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('SELECT JSON(\'{"a": "b"}\')')
    except Exception:
        raise ValueError(
            'JSON not supported in this SQLite version. To fix it, '
            'visit: https://code.djangoproject.com/wiki/JSON1Extension'
        )


class Command(BaseCommand):

    help = """Empty and repopulates the eGSIM database"""

    def add_arguments(self, parser):
        """Implement here specific command options (this method is called
        automatically by the superclass)
        :param parser: :class:`argparse.ArgumentParser` instance
        """
        # For compatibility with the `flush` command (=empty db tables) which
        # is called first, add the flag(s) '--noinput' (or '--no-input'), and
        # store it in the variable `interactive`. This means that the flag
        # value will be accessible in `self.handle(... options)` via
        # `options["interactive"]`. `action='store_false'` means that the flag
        # value is False when *present*, and thus `options["interactive"]` is
        # True by default.
        parser.add_argument(
            '--noinput', '--no-input', action='store_false', dest='interactive',
            help='Do NOT prompt the user for input of any kind.',
        )

    def handle(self, *args, **options):
        """Execute the command"""
        self.stdout.write('')
        self.stdout.write('Empty and populating the eGSIM database')
        self.stdout.write('Remember that you can always inspect the database on '
                          'the browser via the Django admin panel (see README '
                          'file for info)')
        # remove interactive
        if options.pop('interactive', False) and \
                input('Do you want to continue (y/n)?') != 'y':
            return
        self.handle_openquake(*args, **options)
        self.handle_media_files(*args, **options)

    def handle_openquake(self, *args, **options):
        """Register openquake data to DB

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        self.stdout.write('Populating the database with OpenQuake models')
        db_model = models.Gsim
        empty_table(db_model)
        ok = 0
        with warnings.catch_warnings():
            for name, model_cls in registered_gsims.items():
                if model_cls.superseded_by:
                    continue
                if model_cls.experimental or model_cls.non_verified or \
                        model_cls.adapted:
                    warnings.simplefilter('ignore')
                else:
                    warnings.simplefilter('error')

                # try to see if we can initialize it:
                ok += self.write_model(name, model_cls)

        discarded = len(registered_gsims) - ok
        self.stdout.write(self.style.SUCCESS(f'Models saved: {ok}, '
                                             f'discarded: {discarded}'))

    def write_model(self, name, cls):
        """Write a GMM entry to DB"""
        prefix = 'Discarding'
        try:
            _ = gsim(name)  # check we can initialize the model
            imtz = intensity_measures_defined_for(_)
            if not imtz:
                self.stdout.write(f"  {prefix} {name}. No intensity measure defined")
                return False
            gmp = ground_motion_properties_required_by(_)
            if not gmp:
                self.stdout.write(f"  {prefix} {name}. No ground motion property "
                                  f"defined")
                return False
            invalid = sorted(c for c in gmp if not column_exists(c))
            if invalid:
                self.stdout.write(f"  {prefix} {name}. Unregistered "
                                  f"ground motion properties: {invalid}")
                return False
            sa_lim = get_sa_limits(_)
            models.Gsim.objects.create(
                name=name,
                imts=" ".join(sorted(imtz)),
                min_sa_period=None if sa_lim is None else sa_lim[0],
                max_sa_period=None if sa_lim is None else sa_lim[1],
                unverified=cls.non_verified,
                adapted=cls.adapted,
                experimental=cls.experimental)
        except (TypeError, KeyError, IndexError, ValueError, AttributeError) as exc:
            self.stdout.write(f"  {prefix} {name}. Initialization error: "
                              f"{str(exc)}")
            return False
        return True

    def handle_media_files(self, *args, **options):
        """Register media files data to DB

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        empty_table(models.Flatfile)
        empty_table(models.Regionalization)
        dir2model = {
            'flatfiles': models.Flatfile,
            'regionalizations': models.Regionalization
        }
        count = {
            'flatfiles': 0,
            'regionalizations': 0
        }
        for abs_path, data in read_media_files().items():
            dir_basename = basename(dirname(abs_path))
            db_model = dir2model.get(dir_basename)
            if db_model is None:
                continue
            self.write_media_file(db_model, abs_path, data)
            count[dir_basename] += 1

        self.stdout.write(self.style.SUCCESS(
            f'{count["flatfiles"]} flatfile(s) registered to DB'
        ))
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'{count["regionalizations"]} regionalization(s) registered to DB'
        ))

    def write_media_file(self, db_model, path, data):
        """Write a media file entry to DB"""
        data['filepath'] = abspath(path)
        db_field_names = get_fieldnames(db_model)
        db_model.objects.create(**{k: data[k] for k in data if k in db_field_names})


def empty_table(db_model):
    db_model.objects.all().delete()
    if db_model.objects.all().count():
        raise CommandError(f'"{db_model.__name__}" db table is not empty '
                           f'(deletion failed?), check the DB')


def get_fieldnames(db_model) -> set[str]:
    return set(f.name for f in db_model._meta.get_fields())  # noqa


def read_media_files() -> dict[str, dict[str, str]]:
    media_root = abspath(expanduser(settings.MEDIA_ROOT))
    with open(join(media_root, "media_files.yml")) as _:
        data = yaml.safe_load(_)
    for k in list(data):
        file = abspath(join(media_root, k))
        assert isfile(file)
        data[file] = data.pop(k)
    return data
