'''
Utilities for the eGSIM custom commands (note the leading underscore
 to skip this module from the Django command collecting function)

For info see:
https://django.readthedocs.io/en/2.0.x/howto/custom-management-commands.html

Created on 7 Dec 2020

@author: riccardo
'''
import fnmatch
import os
import sys
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError


class EgsimBaseCommand(BaseCommand):
    """Simple subclass of Django BaseCommand providing some shorthand
    utilities"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.process_warning = defaultdict(int)

    def printinfo(self, msg):
        """prints a message from a custom Command with no formatting"""
        self.stdout.write(msg)

    def printwarn(self, msg):
        """prints a message from a custom Command formatted as warning"""
        # show Django formatting for error:
        self.stdout.write(self.style.ERROR(msg))

    def printsuccess(self, msg):
        """prints a message from a custom Command formatted as success"""
        self.stdout.write(self.style.SUCCESS(msg))

    def add_count_warn(self, message):
        """Adds a warning message whose purpose is to be printed only once.
        Call this method with often occurring messages (e.g. within a loop
        for database rows unsuccessfully written) that you want to print
        without polluting the terminal with redundant information.
        At the end of the process, you can then call
        :meth:`self.print_count_warns()` to show all distinct messages and
        their occurrences in brackets"""
        self._warnings[message] += 1

    def print_count_warns(self):
        try:
            print_header = True
            for msg, count in self._warnings.items():
                if print_header:
                    print_header = False
                    self.printwarn('Additional warnings '
                                   '(their occurrences in brackets):')
                self.printwarn('%s (%d)' % (count, msg))
        except AttributeError:
            pass


def get_command_datadir(command_module_name: str):
    """Returns the absolute path of the command data directory (CDD) of the
    given command module. A command module is a Python module implementing a
    Django custom command invokable via 'python manage.py <command>'.
    (for info see https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/).

    Example:
    **From within a command module** call:
    ```
    datadir=`get_cmd_datadir(__name__)`
    ```
    This function also provides meaningful messages to help the user invoking
    the commands from the terminal.

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
        raise ValueError('Error in "%s": you can not invoke `get_datafile_paths` '
                         '(no command associated)' % modfile)

    datadir = os.path.join(thisdir, '_data', command_module_name.split('.')[-1])
    if not os.path.isdir(datadir):
        raise FileNotFoundError('No data directory "%s" defined in "%s"' %
                                (os.path.basename(datadir), os.path.dirname(datadir)))

    return datadir


def get_filepaths(directory,
                  pattern:str = None,
                  raise_on_emptylist:bool = True):
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
        if True if not pattern else fnmatch.fnmatch(file, pattern):
            files.append(os.path.abspath(os.path.join(directory, file)))

    if not files and raise_on_emptylist:
        nofilemsg = 'No file' if not pattern else 'No %s file' % pattern
        raise FileNotFoundError('%s in %s' % (nofilemsg, directory))

    return files


# def get_datafile_paths(command_module_name: str,
#                        *subdirs: str,
#                        pattern: str = None):
#     """Returns the file absolute paths inside the command data directory (CDD)
#     of the given command module, optionally searching in the provided
#     subdirectories and with the given file pattern.
#     A command module is a Python module implementing a Django custom command
#     invokable via 'python manage.py <command>'.
#     (for info see https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/).
#
#     This function builds the CDD (for details see the tree structure
#     inside the `management/commands/_data` directory), and searches therein. In
#     addition, it provides meaningful messages to help the user invoking the
#     commands from the terminal.
#
#     **Examples**:
#
#     To search all "shp" files in the subdirectory "SHARE" of the CDD associated
#     to the command `reg2db` ("management/commands/_data/_data/reg2db/SHARE"),
#     from within 'reg2db.py' type `get_datafile_path(__name__, 'SHARE', '*.shp')`
#
#     :param command_module_name: The `__name__` attribute of a given
#         command module (str)
#     :param subdirs: (optional) sub-directories denoting the path
#         inside the command data directory (all strings)
#     :param pattern: an optional matching pattern (str). See
#         https://docs.python.org/3/library/fnmatch.html#fnmatch.fnmatch
#         for details. Falsy value ('' or None) means: accept all files
#     """
#     try:
#         modfile = sys.modules[command_module_name].__file__
#         if not os.path.isfile(modfile):
#             raise FileNotFoundError()
#     except (AttributeError, KeyError, FileNotFoundError):
#         raise ValueError('Invalid command module name "%s" in '
#                          '`get_datafile_paths`' % command_module_name)
#
#     thisdir = os.path.abspath(os.path.dirname(__file__))
#     if os.path.abspath(os.path.dirname(modfile)) != thisdir:
#         raise ValueError('Error in "%s": you can not invoke `get_datafile_paths` '
#                          '(no command associated)' % modfile)
#
#     datadir = os.path.join(thisdir, '_data', command_module_name.split('.')[-1])
#     if not os.path.isdir(datadir):
#         raise FileNotFoundError('No data directory "%s" defined in "%s"' %
#                                 (os.path.basename(datadir), os.path.dirname(datadir)))
#
#     if subdirs:
#         datadir2 = os.path.join(datadir, *subdirs)
#         if not os.path.isdir(datadir2):
#             raise FileNotFoundError('"%s" not found in "%s" (typo in "%s"?)' %
#                                     (os.path.join(*subdirs), datadir,
#                                      modfile))
#         datadir = datadir2
#
#     pattern = pattern or ''
#
#     files = []
#     for file in os.listdir(datadir):
#         if True if not pattern else fnmatch.fnmatch(file, pattern):
#             files.append(os.path.abspath(os.path.join(datadir, file)))
#
#     if not files:
#         nofilemsg = 'No file' if not pattern else 'No %s file' % pattern
#         raise FileNotFoundError('%s in %s' % (nofilemsg, datadir))
#
#     return files


