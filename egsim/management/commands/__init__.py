import os
import sys
from argparse import RawTextHelpFormatter

from django.core.management.base import BaseCommand


class EgsimBaseCommand(BaseCommand):
    """Simple abstract subclass of Django BaseCommand providing some shorthand
    utilities. All eGSIM commands should inherit from this class
    """

    def add_arguments(self, parser):
        """Called automatically by the superclass, implements specific options"""
        # This option can be typed as '--noinput' or '--no-input' from the
        # command line, or passed as `call_command(..., interactive=[True|False]).
        # 'store_false' means that when the flag is passed then `interactive`
        # is set to False ('store_true' would do the opposite)
        parser.add_argument(
            '--noinput', '--no-input', action='store_false', dest='interactive',
            help='Tells Django to NOT prompt the user for input of any kind.',
        )

    def create_parser(self, *args, **kwargs):
        """Called automatically by the superclass, configures the parser used"""
        # Preserve the formatting of the text in the `help` attribute of this
        # class (if given) on screen (option "--help" on the terminal):
        parser = super(EgsimBaseCommand, self).create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

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

    def data_dir(self, *paths):
        """Return a data directory path. This method follows the same logic of
        `os.path.join` but uses the internal 'commands/data' directory as root
        """
        return os.path.join(os.path.dirname(__file__), 'data', *paths)