# eGSIM commands README

## Table of contents:
 - Introduction and basic usage
 - Creating a new custom command
 - Add a new predefined flat files
   - Added flatfiles (Reminder)


## Introduction and basic usage

This directory contains the user-defined Django-admin
command `egsim-init`. 

Django will register an admin command for each Python 
module in this directory ("management/commands") whose 
name doesn't begin with an underscore (for details 
see the [Django documentation](https://docs.djangoproject.com/en/stable/howto/custom-management-commands/)).

`egsim_init` (re)populates the
database tables with all available GSIMs, IMTs
and Regionalizations, and creates all predefined Flatfiles 
in separate HDF files.

To execute the `egsim_init` command:
```buildoutcfg
export DJANGO_SETTINGS_MODULE="egsim.settings_debug"; python manage.py egsim_init
```

To list all commands:

```buildoutcfg
export DJANGO_SETTINGS_MODULE="egsim.settings_debug"; `python manage.py --help`. 
```

To test the commands:
```buildoutcfg
export DJANGO_SETTINGS_MODULE="egsim.settings_debug"; pytest tests/test_commands.py`
```

(**NOTE**: `DJANGO_SETTINGS_MODULE` **value must be changed in production!**)


## Creating a new custom command

As you can see, in the "management/commands" directory most
Python modules start with an underscore.
These modules are hidden management commands called by `egsim_init` and
dealing with specific subtasks:

| Subcommand | Task |
|-----------|---------------------------------------------------------|
| _egsim_oq | populates the db tables with OpenQuake data (GSIM, IMT) |
| _egsim_reg | populates the db tables with all Regionalizations (Geographic regions mapped to GSIMs) |
| _egsim_flatfiles | Parses predefined flatfiles in their original format and creates more efficient HDF files for usage within the API |

The convention is to prefix any command name with "egsim_" to avoid 
conflicts.

The commands are hidden for simplicity
because there is no need to call them separately: `egsim_init` 
takes only few seconds and can be run after any of those command
has been modified.

---

That said, in order to add a new command:

**[1]** Create a new Python module `<command_name>.py` 
   in this directory ("management/commands"). **HINT**: *copy and 
   rename an existing command module, it is usually easier than 
   starting from scratch*.
    
   The module must contain a subclass of `management.commands.EgsimBaseCommand`,
   and the command code must be implemented in its `handle` method. If the
   code needs to access external data, see next point.

   *Note: `EgsimBaseCommand` is simply a `django.core.management.base.BaseCommand`
   with shorthand utilities which you can inspect in `__init__.py`. For further
   details, see the [Django documentation](
   https://docs.djangoproject.com/en/stable/howto/custom-management-commands/)*

**[2]** (optional) If the command requires external data, put it in 
   the directory "management/commands/data/". E.g., if your data files are 
   inside "management/commands/data/abc", your code would read:
   ```python
   def handle(self, *args, **klwargs):
        data_dir = self.data_dir('abc')
   ```
   (see `EgsimBaseCommand.data_dir` for details). 
   
   *Note: Avoid committing large 
   data files. Think about providing URLs in case and document how to download 
   the data during installation*
   
**[3]** (optional, but very likely) If the command has to be added to the chain of
   subcommand issued by the main command `egsim_init`, add the module
   name in the `egsim_init.py` module (see the module implementation)
   
## Add a new predefined flat files

*Predefined* flat files are parametric tables, usually coming from 
established research projects, that must be available to all eGSIM users.

To add a flatfile to the eGSIM API:

**[1]** Add the original file it in the "data/predefined_flatfiles" 
   direcotry, usually zipped (flatfils are quite big, pay attention
   to `git commit` huge files. If zipping in macOS, see NOTES below)

**[2]** Open the Python module "management.flatfile_parsers.py" and
   implement a new `FlatfileParser` (see `EsmFlatfileParser` as 
   example). The parser must convert whatever format the flatfile
   is, into a `pandas.DataFrame` in order to be saved in the more
   efficient HDF format

**[3]** Open `_egsim_flatfiles.py` and add to the `dict`
   `Command.PARSERS` a new (key, value) pair where the key is
   the source *file name* in 1, and the value is the 
   parser class implemented in 2.


NOTES:

To compress a file in macOS:

- Zip with macOS adds a kind of `__MACOSX` folder
  in the zip file (https://stackoverflow.com/q/10924236). 
  Pandas expects zips with only one item,
  so in order to remove that macOS specific folder
  zip **and afterwards type**:

  ```buildoutcfg
  zip -d <filename>.zip __MACOSX/\*
  ```
  
  OR ZIP like this (-9 is optional is the compression level):

  ```buildoutcfg
  zip ZIPFILE_PATH  CSV_FILEPATH -9 -x ".*" -x "__MACOSX"
  ```

### Added flatfiles (Reminder)

#### ESM 2018 flatfile

- Go to https://esm.mi.ingv.it//flatfile-2018/flatfile.php
(with username and password, you must be registered 
  beforehand it's relatively fast and simple)

- Download `ESM_flatfile_2018.zip`, uncompress and extract
  `ESM_flatfile_SA.csv` from there 
  
- `ESM_flatfile_SA.csv` is our raw flatfile, compress it 
  again (it's big) into this directory as 
  `ESM_flatfile_2018_SA.zip`
 
- If on macOS, type the command above to remove the
  macOS folder from the zip