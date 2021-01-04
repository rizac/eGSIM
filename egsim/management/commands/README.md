## eGSIM commands README

This directory contains eGSIM-specific management commands to (re)populate
the backend database tables storing the API data (GSIMs, IMTs,
Regionalizations, GSIM selections and, soon, flatfiles data).

Django will register a manage.py command for each Python module in this
directory ("management/commands") whose name doesn't begin with an underscore.
To list all commands, type `python manage.py --help`. For further details
see the [Django documentation](https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/).
The convention for eGSIM is to start any command with "egsim_" to avoid conflicts.


### Executing eGSIM commands

Any management command (including eGSIM commands) can be executed via
```
python manage.py <command_name>
```
and its documentation shown via `python manage.py <command_name> --help`.

**TL/DR: in all management operations where you want to (re)populate
the whole eGSIM database from scratch just run** `egsim_init`:
```
export DJANGO_SETTINGS_MODULE="egsim.settings_debug"; python manage.py egsim_init
```
NOTE: `DJANGO_SETTINGS_MODULE` value must be changed in production

#### Detailed commands description 

Below a description of all eGSIM management commands run automatically
by `egsim_init`:

Command | When we want to | E.g.
--- | --- | ---
`egsim_init` | (Re)populate from scratch all eGSIM tables:<br/>call `egsim_flush`, add OpenQuake data (GSIMs, IMTs ...) and call all remaining commands below in series | We upgraded OpenQuake, we performed a db a migration, we have new external data (see any of the cases below)
`egsim_flush` | Empty all rows in all tables | After modifying the models, to run smoothly `makemigrations` afterwards
`egsim_reg` | Update the db regionalizations | A new regionalization model (e.g. SHARE) is available<br/>([see below how to add it in eGSIM](#Extending-existing-commands))
`egsim_sel` | Update the db Gsim selection | A new selection model (e.g. SHARE, ESHM) is available<br/>([see below how to add it in eGSIM](#Extending-existing-commands))
~~Not implemented yet~~ | ~~Update the ESM Ground motion DB for residuals computation~~ | ~~A new flatfile (ESM_2018_SA) is available~~

Note that, albeit rare, there might be cases where we want to run only a subset
of these (sub)commands. See e.g. `egsim_flush` in 
[how modify a model and repopulate the db](#Modifying-a-Model-class-and-repopulating-the-database)

### Common workflows

#### Modifying a Model and repopulating the database

- [a] Edit the eGSIM model(s) (module `egsim.models.py`)
- [b] Implement in `egsim_init` (or some subcommand) how to populate the model(s).
- [c] (optional) Empty the eGSIM tables (command `egsim-flush`) [see Note below]
- [d] Make a migration (command `makemigrations`)
- [e] Run migration (command `migrate`)
- [f] Repopulate all eGSIM tables (command `egsim_init`)

Note: the step [c] makes migrations smoother in [d]. E.g. it prevents Django to ask
how to fill missing values of existing rows, if any, avoiding an unnecessary operation
because all tables rows are eventually deleted and recreated in `egsim_init` ([f])

#### Extending existing commands

The two commands `egsim_reg` and `egsim_sel` are specifically designed to handle
easily the addition of new input data in the future (new regionalizations and
gsim selections, respectively).

See the documentation in the two modules (`<command_name>.py`) for details

#### Creating a new custom command

1. Create a new Python module `<command_name>.py`
   in this directory ("management/commands") with no leading
   underscore. For details see  the [Django documentation](
   https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/)
   
2. Implement in the module a subclass of `_utils.EgsimBaseCommand`.
   `EgsimBaseCommand` is just a subclass of Django `BaseCommand`
   with some shorthand utilities (see implementation in `_utils.py` for details).
   To implement a `EgsimBaseCommand`/`BaseCommand` you can simply copy and
   modify one of the other commands in this directory or see the [Django documentation](
   https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/)

3. (optional) If the command requires external data, create the
   directory `./data/<command_name>` and put therein whatever you
   need (organized in any tree structure you want) for the functionality of
   your command (*Note: Avoid committing large data files.
   Think about providing URLs in case and document how to download the data
   during installation*)

4. (optional) If the command has to be added to the chain of
   subcommand issued by the main command `egsim_init`, add it
   in the `egsim_init.py` module (see the module implementation) 
    
5. List the command in this README

