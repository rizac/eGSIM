## eGSIM commands README

This directory contains eGSIM-specific management commands to (re)populate
the backend database tables storing the API data (GSIMs, IMTs,
Regionalizations + GSIM mappings and, maybe in the future, flatfiles data).

Django will register a manage.py command for each Python module in this
directory ("management/commands") whose name doesn't begin with an underscore.
To list all commands, type `python manage.py --help`. For further details
see the [Django documentation](https://docs.djangoproject.com/en/stable/howto/custom-management-commands/).
The convention for eGSIM is to start any command with "egsim_" to avoid conflicts.

Any management command (including eGSIM commands) can be executed via
`python manage.py <command_name>` and its documentation shown via
`python manage.py <command_name> --help`.

### Testing commands

Run `export DJANGO_SETTINGS_MODULE="egsim.settings_debug"; pytest tests/test_commands.py`

(NOTE: `DJANGO_SETTINGS_MODULE` value must be changed in production!)

### Executing eGSIM commands

**In a nutshell, all management operations can be performed via a single "main"
command** `egsim_init`:
```
export DJANGO_SETTINGS_MODULE="egsim.settings_debug"; python manage.py egsim_init
```
(NOTE: `DJANGO_SETTINGS_MODULE` value must be changed in production!)

Here a more detailed description of all eGSIM management commands (for further
details, see the relative Python modules):

 - `egsim_init`. Empty and repopulate from scratch all eGSIM 
   tables. First calls Django's '`flush` command, and then all implemented egsim 
   commands in series. Useful after :
   - An OpenQuake upgrade
   - A database migration 
   - New external data (e.g., new regionalizations)
 - `egsim_reg`. Update the db regionalizations and the associated GSIMs. It is
    called by `egsim_init`

### Creating a new custom command

1. Create a new Python module `<command_name>.py`
   in this directory ("management/commands") with no leading
   underscore. You can also copy and rename an existing command module,
   it is usually easier than starting from scratch.
   The module must contain a subclass of `management.commands.EgsimBaseCommand`,
   and the command code must be implemented in its `handle` method (if the
   code needs to access external data, see next point).
   `EgsimBaseCommand` is simply a `django.core.management.base import BaseCommand`
   with shorthand utilities which you can inspect in `__init__.py`. For further
   details, see the [Django documentation](
   https://docs.djangoproject.com/en/stable/howto/custom-management-commands/).
   
2. (optional) If the command requires external data, put it in 
   the directory `.management/commands/data/`. E.g., if your data files are 
   inside `.management/commands/data/abc`, you can get the
   directory path calling `self.data_dir('abc')`
   (see `EgsimBaseCommand.data_dir` for details). *Note: Avoid committing large 
   data files. Think about providing URLs in case and document how to download 
   the data during installation*
   
4. (optional, but very likely) If the command has to be added to the chain of
   subcommand issued by the main command `egsim_init`, add the module
   name in the `egsim_init.py` module (see the module implementation) 
    
5. Update this README with the new command description

