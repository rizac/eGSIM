import os

from argparse import RawTextHelpFormatter, SUPPRESS

from django.core.management.base import BaseCommand


class EgsimBaseCommand(BaseCommand):  # noqa
    """Simple abstract subclass of Django BaseCommand providing some shorthand
    utilities. All eGSIM commands should inherit from this class and implement,
    as usual the :meth:`handle` method
    """

    @staticmethod
    def data_dir(*paths):
        """Return a data directory path. The result will be the same as
        `os.path.join(*paths)` prefixed with the "./data" directory path
        """
        return os.path.join(os.path.dirname(__file__), 'data', *paths)

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
