## egsim commands readme

This directory contains Django custom management commands
for the eGSIM application. Django will register a manage.py
command for each Python module in this directory
("management/commands") whose name doesn't begin with an
underscore.
For details see the [Django documentation](https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/)


### How to execute the commands

Any command can be executed via `python manage.py <command_name>`. 
For all common maintenance operation, there is basically only one management
command to call `initdb`, which can be executed on the terminal as follows:
```
export DJANGO_SETTINGS_MODULE="egsim.settings_debug"; python manage.py initdb
```
(`DJANGO_SETTINGS_MODULE` value must be changed in production)

`initdb` is composed of several subcommands covering specific
management tasks described below
(for details, type `python manage.py initdb --help`. To list all
commands, type `python manage.py --help`)

### When to execute the commands

Management commands are supposed to be executed once
in a while to (re)initialize and populate the whole eGSIM database,
e.g.:

When we have | (sub)command
--- | ---
Upgraded OpenQuake (i.e. new models, IMTs, and so on) | `oq2db`
New regionalization (e.g. SHARE) | `reg2db`<br/>([details here](#Extending-existing-commands))
New Gsim selection (e.g. SHARE, ESHM) | `gsimsel2db`<br/>([details here](#Extending-existing-commands))
~~New Flatfile(s) (e.g. ESM_2018_SA)~~ | ~~not yet implemented~~

As many of these commands might be related
(e.g. `oq2db` empties all tables and thus
requires the other two commands to be called afterwards)
**we suggest in any case 
to simply execute `initdb` and be always safe**

### How to extend / create custom commands

#### Extending existing commands
 
The two commands `reg2db` and `gsimsel2db` can be extended when new
input data is available (new regionalizations and gsim selections, respectively)
in order to inlcude it in the database and make it available in eGSIM.
See the documentation of the two modules (`reg2db.py` and
`gsimsel2db.py`) for details

#### Creating new custom commands

To create a new command invokable via
```
python manage.py <command_name>
```
you have to:

1. Create a new Python module `<command_name>.py`
   in this directory ("management/commands") with no leading
   underscore (For details see  the [Django documentation](
   https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/)
   
2. Implement in the module a subclass of `_utils.EgsimBaseCommand`.
   `EgsimBaseCommand` is just a subclass of Django `BaseCommand`
   with some shorthand utilities (see implementation in `_utils.py` for details).
   For details on how to implement a `BaseCommand` see the
   other examples here or the [Django documentation](
   https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/)

3. (optional) If the command requires external data, create the
   directory `./data/<command_name>` and put therein whatever you
   need (organized in any tree structure you want) for the functionality of
   your command (*Note: Avoid committing large data files. In case, think about
   providing URLs instead and document how to download
   the data during installation*)

4. (optional) If the command has to be added to the chain of
   subcommand issued by the main command `initdb`, add it
   in the `initdb.py` module (see the module implementation) 
   <!-- Avoid trying to add (sub)commands automatically based on e.g., a
    scan of the commands directory: first you want to have control over the
    execution order, second you might want to implement some command
    that is not part of the main initialization chain -->

