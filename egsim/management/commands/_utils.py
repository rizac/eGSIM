"""
Utilities for the eGSIM custom commands (note the leading underscore
 to skip this module from the Django command collecting function)

For info see:
https://django.readthedocs.io/en/2.0.x/howto/custom-management-commands.html

Created on 7 Dec 2020

@author: riccardo
"""
import fnmatch
import os
import sys
from argparse import RawTextHelpFormatter
from collections import defaultdict

from django.core.management.base import BaseCommand


class EgsimBaseCommand(BaseCommand):
    """Simple abstract subclass of Django BaseCommand providing some shorthand
    utilities. All eGSIM commands should inherit from this class
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._warnings_and_count = defaultdict(int)

    def add_arguments(self, parser):
        # This option can be typed as '--noinput' or '--no-input' from the
        # command line, or passed as `call_command(..., interactive=[True|False]).
        # 'store_false' means that when the flag is passed then `interactive`
        # is set to False ('store_true' would do the opposite)
        parser.add_argument(
            '--noinput', '--no-input', action='store_false', dest='interactive',
            help='Tells Django to NOT prompt the user for input of any kind.',
        )

    def create_parser(self, *args, **kwargs):
        """Make help on the terminal retains formatting of all help text
        (class `help` attribute)
        """
        parser = super(EgsimBaseCommand, self).create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def printinfo(self, msg):
        """Print a message from a custom Command with no formatting"""
        self.stdout.write(msg)

    def printwarn(self, msg):
        """Print a message from a custom Command formatted as warning
        (Django error style. Printing errors is not contemplated as one should
        probably raise `CommandError`, se Django doc or examples here)
        """
        # show Django formatting for error:
        self.stdout.write(self.style.ERROR(msg))

    def printsoftwarn(self, msg):
        """Print a message from a custom Command formatted as soft warning
        (Django warning style)
        """
        # show Django formatting for error:
        self.stdout.write(self.style.WARNING(msg))

    def printsuccess(self, msg):
        """Print a message from a custom Command formatted as success"""
        self.stdout.write(self.style.SUCCESS(msg))

    def collect_warning(self, message):
        """Collect the given warning message and the number of times it has
        been issued.

        During the command execution (typically within loops), it might happen
        that the same warning message(s) are issued many times. To avoid making
        the output unreadable whilst still notifying the user, you should call
        this method instead of printing the message, and then
        :meth:`self.print_collected_warnings()` at the end of the command
        execution.
        This way, each distinct message will be printed only once (with its
        count in brackets).
        """
        self._warnings_and_count[message] += 1

    def print_collected_warnings(self, empty_warnings=True):
        """Prints the collected warnings and empties the internal counter.
        Does nothing if there are no collected warnings
        """
        if not self._warnings_and_count:
            return
        self.printsoftwarn('Summary of collected warnings:')
        for msg, count in self._warnings_and_count.items():
            num_times = " (issued %d times)" % count if count > 1 else ""
            self.printsoftwarn('   %s%s' % (msg, num_times))
        if empty_warnings:
            self._warnings_and_count.clear()


def get_command_datadir(command_module_name: str):
    """Returns the absolute path of the command data directory (CDD) of the
    given command module. A command module is a Python module implementing a
    Django custom command invokable via 'python manage.py <command>'
    (for info see https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/).
    Typical usage **from within a command module**:
    ```
    datadir = get_command_datadir(__name__)
    ```
    This function also provides meaningful messages to help the user when
    invoking the commands from the terminal.

    :param command_module_name: The `__name__` attribute of a given
        command module (str)
    """
    try:
        modfile = sys.modules[command_module_name].__file__
        if not os.path.isfile(modfile):
            raise FileNotFoundError()
    except (AttributeError, KeyError, FileNotFoundError):
        raise ValueError('Invalid command module name "%s" in '
                         '`get_datafile_paths`' % command_module_name)

    thisdir = os.path.abspath(os.path.dirname(__file__))
    if os.path.abspath(os.path.dirname(modfile)) != thisdir:
        raise ValueError('Error in "%s": you cannot invoke `get_datafile_paths` '
                         '(no command associated)' % modfile)

    datadir = os.path.join(thisdir, 'data', command_module_name.split('.')[-1])
    if not os.path.isdir(datadir):
        raise FileNotFoundError('No data directory "%s" defined in "%s"' %
                                (os.path.basename(datadir), os.path.dirname(datadir)))

    return datadir


def get_filepaths(directory,
                  pattern: str = None,
                  raise_on_emptylist: bool = True):
    """Returns a list of file absolute paths inside `directory`, optionally
    filtered by `pattern`

    :param directory: a directory (str)
    :param pattern: an optional matching pattern (str). See
        https://docs.python.org/3/library/fnmatch.html#fnmatch.fnmatch
        for details. Falsy value ('' or None) means: accept all files
    :param raise_on_emptylist: if True (the default) raises a FileNotFound
        exception if no file is found according to the given criteria. If
        False, no check is performed and empty lists can be returned
    """
    pattern = pattern or ''

    files = []
    for file in os.listdir(directory):
        if pattern and not fnmatch.fnmatch(file, pattern):
            continue
        files.append(os.path.abspath(os.path.join(directory, file)))

    if not files and raise_on_emptylist:
        nofilemsg = 'No file' if not pattern else 'No %s file' % pattern
        raise FileNotFoundError('%s in %s' % (nofilemsg, directory))

    return files
