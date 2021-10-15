## eGSIM commands README

This directory contains eGSIM-specific management commands to (re)populate
the backend database tables storing the API data (GSIMs, IMTs,
Regionalizations + GSIM mappings and, maybe in the future, flatfiles data).

Django will register a manage.py command for each Python module in this
directory ("management/commands") whose name doesn't begin with an underscore.
To list all commands, type `python manage.py --help`. For further details
see the [Django documentation](https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/).
The convention for eGSIM is to start any command with "egsim_" to avoid conflicts.

Any management command (including eGSIM commands) can be executed via
`python manage.py <command_name>` and its documentation shown via
`python manage.py <command_name> --help`.

### Executing eGSIM commands

**In a nutshell, all management operations can be performed via a single "main"
command** `egsim_init`:
```
export DJANGO_SETTINGS_MODULE="egsim.settings_debug"; python manage.py egsim_init
```
(NOTE: `DJANGO_SETTINGS_MODULE` value must be changed in production!)

Here a more detailed description of all eGSIM management commands (for further
details, see the relative Python modules):

 - `egsim_init`: Empties (`fluah` command) and repopulate from scratch all eGSIM 
   tables by calling all egsim commands in series. Useful after :
   - An OpenQuake upgrade
   - A database migration 
   - New external data (e.g., new regionalizations)
 - `egsim_reg`: Updates the db regionalizations and the associated GSIMs

### Creating a new custom command

1. Create a new Python module `<command_name>.py`
   in this directory ("management/commands") with no leading
   underscore. For details see  the [Django documentation](
   https://docs.djangoproject.com/en/stable/howto/custom-management-commands/)
   
2. (optional) If the command requires external data, put it in 
   the directory `.management/commands/data/`. E.g., if you have a bunch 
   of files inside `.management/commands/data/abc`, you can get the
   direcotry path from within the command using `self.data_dir('abc')`
   (see `EgsimBaseCommand.data_dir` for details. *Note: Avoid committing large 
   data files. Think about providing URLs in case and document how to download 
   the data during installation*)

3. Implement in the module a subclass of `management.commands.EgsimBaseCommand`,
   which is just a subclass of Django `BaseCommand`
   with some shorthand utilities (see source code for details).
   To implement a `EgsimBaseCommand`/`BaseCommand` you can simply copy and
   modify one of the other egsim commands in this directory or consult the 
   [Django documentation](https://docs.djangoproject.com/en/stable/howto/custom-management-commands/)
   
4. (optional, but very likely) If the command has to be added to the chain of
   subcommand issued by the main command `egsim_init`, add the module
   name in the `egsim_init.py` module (see the module implementation) 
    
5. Update this README with the new command description

