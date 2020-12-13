## egsim commands readme

This directory contains Django custom management commands
for the eGSIM application, in most cases for initializing and populating the
eGSIM database. Django will register a manage.py
command for each Python module in this directory
("management/commands") whose name doesn't begin with an
underscore.
For details see the [Django documentation](https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/)


### How to execute the commands

Any command can be executed via `python manage.py <command_name>`. One command,
`initdb`, wraps them all, and is supposed to be used for all
management operation (at the cost of some potential redundancy) as follows:
```
export DJANGO_SETTINGS_MODULE="egsim.settings_debug"; python manage.py initdb
```
(`DJANGO_SETTINGS_MODULE` value must be changed in production.
For `initdb` subcommand details, type `python manage.py initdb --help`.
To list all commands, type `python manage.py --help`)

### When to execute the commands

Management commands are supposed to be executed once
in a while in these circumstances:

When we have | command
--- | ---
upgraded OpenQuake<br/>(and thus the list of GSIMs, IMTs and so on) | `oq2db`
New regionalization<br/>(e.g. SHARE) | `reg2db`<br/>([details here](#Extending-existing-commands))
New Gsim selection<br/>(e.g. SHARE, ESHM) | `gsimsel2db`<br/>([details here](#Extending-existing-commands))
~~New Flatfile(s)<br/>(e.g. ESM_2018_SA)~~ | ~~not yet implemented~~
Any of the above cases | `initdb`

As said, **we strongly recommend for simplicity to always execute
`initdb` after any change above** (sometimes it is not safe
to execute the other commands alone. E.g., `oq2db` empties all
tables and thus requires the other sub-commands
to be called afterwards)

### How to extend / create custom commands

#### Extending existing commands

The two commands `reg2db` and `gsimsel2db` are specifically designed to handle
easily the addition of new input data in the
future (new regionalizations and gsim selections, respectively).
See the documentation in the two modules (`reg2db.py` and
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
   To implement a `EgsimBaseCommand`/`BaseCommand` subclass see the
   other commands in this directory or the [Django documentation](
   https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/)

3. (optional) If the command requires external data, create the
   directory `./data/<command_name>` and put therein whatever you
   need (organized in any tree structure you want) for the functionality of
   your command (*Note: Avoid committing large data files.
   Think about providing URLs in case and document how to download the data
   during installation*)

4. (optional) If the command has to be added to the chain of
   subcommand issued by the main command `initdb`, add it
   in the `initdb.py` module (see the module implementation) 
   <!-- Avoid trying to add (sub)commands automatically based on e.g., a
    scan of the commands directory: first you want to have control over the
    execution order, second you might want to implement some command
    that is not part of the main initialization chain -->
    
5. List the command in this README

