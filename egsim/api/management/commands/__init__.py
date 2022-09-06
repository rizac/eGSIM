from os.path import abspath, join, dirname
import yaml

from argparse import RawTextHelpFormatter, SUPPRESS

from django.core.management.base import BaseCommand, CommandError


class EgsimBaseCommand(BaseCommand):  # noqa
    """Simple abstract subclass of Django BaseCommand providing some shorthand
    utilities. All eGSIM commands should inherit from this class and implement,
    as usual the :meth:`handle` method
    """

    @staticmethod
    def data_path(*paths) -> str:
        """Return the full absolute path to a data file. Same as:
        ```
        os.path.join("./data", *paths)
        ```
        :param paths: a series of paths relative to "./data"
        """
        return join(abspath(dirname(__file__)), 'data', *paths)

    @staticmethod
    def data_source(datafile_path) -> dict:
        """Return a data source information from the given data file"""
        base_dir = EgsimBaseCommand.data_path()
        with open(join(base_dir, 'data_sources.yaml')) as _:
            data_sources = yaml.safe_load(_)

        datafile_abspath = abspath(datafile_path)
        for path, data_source in data_sources.items():
            if datafile_abspath == abspath(join(base_dir, path)):
                return data_source
        return {}

    @staticmethod
    def empty_db_table(*models):
        """Delete all rows of the given database table(s).

        :param models: the Django model(s) representing the db tables to empty

        :raise: CommandError if any model have some row
        """
        items2delete = sum(_.objects.count() for _ in models)  # noqa

        if items2delete:
            for model in models:
                model.objects.all().delete()  # noqa
                if model.objects.count() > 0:  # noqa
                    raise CommandError('Could not delete all rows in table "%s"' %
                                       str(model))

    def printinfo(self, msg):
        """Shortcut for `self.stdout.write(msg)`"""
        self.stdout.write(msg)

    def printwarn(self, msg):
        """Shortcut for `self.stdout.write(self.style.ERROR(msg))`"""
        self.stdout.write(self.style.ERROR(msg))

    def printsoftwarn(self, msg):
        """Shortcut for `self.stdout.write(self.style.WARNING(msg))`"""
        self.stdout.write(self.style.WARNING(msg))

    def printsuccess(self, msg):
        """Shortcut for `self.stdout.write(self.style.SUCCESS(msg))`"""
        self.stdout.write(self.style.SUCCESS(msg))

    def create_parser(self, *args, **kwargs):
        """Called automatically by the superclass, configures the parser used"""
        # We want to show on screen (option "--help" on the terminal) *exactly*
        # the same text and newlines given in this class `help` attribute:
        parser = super(EgsimBaseCommand, self).create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser
