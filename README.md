# eGSIM
A web service for selecting and testing  ground shaking models (GSIM) 
in Europe, developed in the framework of the Thematic Core Services for 
Seismology of [EPOS](https://www.epos-eu.org/) under the umbrella of 
[EFEHR](http://www.efehr.org/en/home/)

# Table of contents

   * [Installation](#installation)
   * [Usage](#usage)
   * [Maintenance](#maintenance)
     * [Starting a Python terminal shell](#starting-a-python-terminal-shell)
     * [Admin panel](#admin-panel)
     * [Complete DB reset](#Complete-DB-reset)
     * [Migrate and populate the db](#Migrate-and-populate-the-db)
     * [Add new predefined flatfiles](#Add-new-predefined-flatfiles)
     * [Add new regionalization](#Add-new-regionalization)
     * [Dependencies upgrade](#Dependencies-upgrade)
     * [Fix gmpe-smtk](#Fix-gmpe-smtk)

     
## Installation

DISCLAIMER: **This document covers installation in development (or debug) 
mode, i.e. when the program is deployed locally, usually for testing, 
fixing bug or adding features.**

The "formal" installation of eGSIM as web service (*production* or *deploy* 
mode) on a remote, publicly available server is covered in `deploy.html`.

### Requirements

```bash
sudo apt-get update # pre-requisite
sudo apt-get install gcc  # optional
sudo apt-get install git python3-venv python3-pip python3-dev
```

(The command above are Ubuntu specific, in macOS install brew and type
`brew install` instead of `apt-get install`. *Remove python3-dev as it does not
exist on macOS*).

This web service uses a *specific* version of Python (Open `setup.py` and 
check `python_requires=`. As of January 2022, it's 3.9.7) which you must 
install in addition to the Python version required by your system, and use
it. Any command `python3` hereafter will refer to the required Python version.


### Clone repository

Select a `root directory` (e.g. `/root/path/to/egsim`), and clone egsim into the
so-called egsim directory:

```bash
git clone https://github.com/rizac/eGSIM.git egsim
```

### Create and activate Python virtual env

Move to whatever directory you want (usually the egsim directory above) and then:

```bash
python3 -m venv .env/<ENVNAME>  # create python virtual environment (venv)
source .env/<ENVNAME>/bin/activate  # activate venv
```

**NOTE: From now on, all following operations must have the virtualenv activated FIRST**

### Install

*Note: if the installation is done for upgrading all dependencies and `pip freeze` into new requirements files,
please go to [dependency upgrade](#dependencies-upgrade)* 


On the terminal, execute:
```bash
pip install --upgrade pip setuptools && pip install -r requirements.dev.txt
```
(use `requirements.txt` if you don't need to run tests, e.g. you are not 
installing as developer).

<details>

<summary>
If you want also to be able to modify `gmpe-smtk`, e.g. 
fix bug, implement new features and issue Pull Requests to the master branch 
(click to expand): 
</summary>

Clone gmpe-smtk, usually on the same level
of the `egsim directory` into the so-called `smtk directory`:

```bash
git clone https://github.com/rizac/gmpe-smtk.git gmpe-smtk
```

**Note** that the current commit hash (`git log -1`) **should be the same** as
in `requirements.txt` (i.e., the string portion between '@' and '#' of the text line containing "smtk").

Then, (re)install smtk from the cloned directory:

```
cd ../gmpe-smtk # (or whatever you cloned the forked branch)
pip install -e .
```

and have a look at [Fixing gmpe-smtk](#Fix gmpe-smtk)
for the suggested workflow

</details>


### Run Test

Move in the `egsim directory` and type:

```bash
export DJANGO_SETTINGS_MODULE=egsim.settings_debug; pytest -xvvv --ds=egsim.settings_debug ./tests/
```
(x=stop at first error, v*=increase verbosity). 

Test with code coverage, i.e.
showing the amount of code hit by tests:

```bash
export DJANGO_SETTINGS_MODULE=egsim.settings_debug; pytest -xvvv --cov=./egsim/ --cov-report=html ./tests/
```

(you can also invoke the commands without `export ...` but 
using the `--ds` option: `pytest -xvvv --ds=egsim.settings_debug ./tests/`)


## Usage

(*NOTE: the settings module MUST be changed in production*!)

Initialize the database/db (**one-time only operation to be done 
before running the program for the first time**):

- Create db:

  ```console
  export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py migrate
  ```

- Populate db:

  ```console
  export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py egsim_init
  ``` 

If you want to access the admin panel, see [the admin panel](#admin-panel).
Otherwise, **to run the program in your local browser**, type:

```console
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py runserver 
```

(you can also invoke the commands without `export ...` but using the 
`--settings` option: 
`python manage.py --settings=egsim.settings_debug [command]`)


## Maintenance

Few remarks before proceeding: Django projects have two fundamental
organization structures:
	
1. the Django project itself in the base
   working directory (created with the command
   `django-admin startproject egsim`)
	
2. the app(s), usually organized in sub-directories, which are used to break
   a project's functionality down into logical units (For details, see
   https://ultimatedjango.com/learn-django/lessons/understanding-apps/)

In eGSIM we have a project (root directory) named "egsim" two apps: "api" and
"gui". Whereas the latter is simply a package housing frontedn code, urls
and view, the former also housed databse models and it is thus technically
speaking the only app of the project. Note that "api" is not the only used 
app (see `INSTALLED_APPS` in the settings file, among which we enabled the 
`admin` app visualizable through the [Admin panel](#admin-panel)).

Most ofthe management commands we are about to see are command line 
applications invokable from the terminal: remember that 
**The DJANGO_SETTINGS_MODULE environment variable 
in the examples below is not the value to be given in production**, where a 
new settings file has to be created with production specific settings such as, 
e.g. `debug=False` and a new `SECRET_KEY` (which needs to be secret and not 
git committed).


### Starting a Python terminal shell


Typing `python` on the terminal does not work if you need to import django
stuff, as there are things to be initialized beforehand. The Django `shell`
command does this:

```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py shell 
```

### Admin panel

(check or modify database data from the web browser)

The database must have been created and populated (see [Usage](#usage)). 
For further details: check [Django docs](https://docs.djangoproject.com/en/stable/ref/django-admin/))

Create a super user (to be done **once only** ):
```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py createsuperuser
```
and follow the instructions.

Then navigate in the browser to `[SITE_URL]/admin` (in development mode,
http://127.0.0.1:8000/admin/)


### Complete DB reset

As eGSIM does not need to store user data in the database, it might be
easier to throw everything away and regenerate all db schema and data 
(e.g., after changing the directory structure of the project).

To do this:
 - delete db.sqlite (or wherever the database is)
 - delete all migrations (currently under "egsim/api/migrations"), i.e.
   all all .py files except `__init__.py`
 - execute (change `DJANGO_SETTINGS_MODULE` value in production!):
   ```console
   export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py makemigrations
   export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py migrate
   ```
 - Re-add if needed the Django admin superuser(s) as explained in the
   [admin panel](#admin-panel) above
   

### Migrate and populate the db

Before reading, remember:

 - `DJANGO_SETTINGS_MODULE` value in the examples below must be changed 
   in production!
 - The `make_migration` command just generates a migration file, it doesn't 
   change the db. The `migrate` command does that, by means of the migration files
   generated. For details on Django migrations, see:
   - https://realpython.com/django-migrations-a-primer/#changing-models
   - https://docs.djangoproject.com/en/3.2/topics/migrations/#workflow

   
#### Steps:   

1. Edit the eGSIM models (module `egsim.models.py`. **In production,
   just run** `git pull`)
2. Make a migration (**This does not run a migration, see note above**):
   
   ```console
   export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py makemigrations egsim --name <migration_name>
   ```
   (<migration_name> will be a suffix appended to the migration file, use it
   like you would use a commit message in `git`).
   
   **NOTE**: Django might ask you how to fill non-nullable 
   fields (db columns), if added. Just provide whatever default, because a 
   migration is supposed to be followed by a `egsim_init` execution that will
   re-populate all egsim tables. However, you might need to empty
   the database manually before running `migrate` (see below), otherwise
   the migration might not work if e.g., the field is unique
   
3. Should the db be repopulated differently in account of the new 
   changes (probably yes)?
   Then implement these changes in the existing 
   commands, or create a new one, see `README.md` in 
   `egsim/management/commands`
   
4. Run `test_initdb` in `/tests/test_commands.py` (it re-creates
   from scratch a test db, runs all migrations and `egsim_init`)

4. (optional) Make a backup of the database
   
5. Run migration (command `migrate`). **Note**: if the migration 
   will introduce new non-nullable fields, maybe better to run 
   `manage.py flush` first to empty all tables, to avoid conflicts
   
   ```console
   export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py migrate egsim
   ```

   ("egsim" above is the app name. If you omit the app, all apps will be migrated.
   The command `migrate` does nothing if it detects that there is nothing to migrate)
   
6. Repopulate all eGSIM tables (command `egsim_init`)


### Add new predefined flatfiles

- Add the file (CSV or zipped CSV) in
  `managements/commands/data/predefined_flatfiles`
  
- Implement a new `FlatfileParser` class in 
  `management/commands/flatfile_parsers.py`
  The parser goal is to read the file and convert it into a harmonized HDF 
  table (see ESM parser in the Python file)

- Add binding file -> parser in the Python `dict`:
  `management.commands._egsim_flatfiles.Command.PARSER`

- (Optional) Add the file data source 
  in `management/commands/data/data_sources.yaml`, e.g. data reference, url, 
  (see examples in the YAML file). 

  *NOTE: In the data source you can also set the 
  data name, i.e. a unique, usually short alphanumeric string that will 
  identify the flatfile in user requests. If no 
  data source or name is provided, the public name will be the file name 
  before the first ".".*

- Repopulate all eGSIM tables (command `egsim_init`)


### Add new regionalization

- Add two files *with the same basename* and extensions 
  - .geojson (regionalization, aka regions collection) and
  - .json (region -> gsim mapping)
  
  in `managements/commands/data/regionalization_files`. Usually, these files are
  copied and pasted from the `shakyground2` project (see GFZ gitlab), but if
  you neeed to implement your own see examples in the given directory 
  or ask the developers

- (Optional) Add the file data source 
  in `management/commands/data/data_sources.yaml`, e.g. data reference, url, 
  (see examples in the YAML file). 

  *NOTE: In the data source you can also set the 
  data name, i.e. a unique, usually short alphanumeric string that will 
  identify the regionalization in user requests. If no 
  data source or name is provided, the public name will be the file name 
  before the first ".".*

- Repopulate all eGSIM tables (command `egsim_init`)


### Dependencies upgrade

Please note that it is safer (from now even 
[mandatory](https://stackoverflow.com/questions/63277123/what-is-use-feature-2020-resolver-error-message-with-jupyter-installation-on)
with `pip`) to upgrade all dependencies
instead of single packages in order to avoid conflicts.
Consequently, **follow the procedure below also in case of
Github single packages security issues or dependencies alert**.

To upgrade all dependencies, we just need to `pull` the newest version
of `smtk` and relaunch an installation from there (this will fetch
also OpenQuake newest version and all dependencies automatically)

First create and activate a new virtualenv:

```bash
python3 -m venv .env/<ENVNAME>  # create python virtual environment (venv)
source .env/<ENVNAME>/bin/activate  # activate venv
pip install --upgrade pip setuptools
```

Then install smtk and all dependencies:

```bash
cd ../gmpe-smtk # (or whatever you cloned the forked branch)
git checkout master && git pull
pip install -e . # (also installs openquake and django)
cd ../egsim. # (or wherever egsim is)
pip freeze > requirements.txt
```

And finally install the newset version of the test packages:

```
pip install pylint pytest-django pytest-cov
pip freeze > requirements.dev.txt
```

Finally, proceed with the normal workflow:
run tests, fix new bugs and eventually `git push`, as always.


### Fix gmpe-smtk

We will refer to smtk as the [forked branch](https://github.com/rizac/gmpe-smtk)
used by eGSIM. As we have seen during installation, it is a forked repository from the
[upstream branch](https://github.com/GEMScienceTools/gmpe-smtk.git).

By convention **the last commit of the `master` branch of smtk is the updated one which
can be used in production** (basically, the one written in the `requirements` text files).
Therefore, when fixing an smtk issue or implementing
a new feature, switch to a dev branch (we usually use the branch called ... "dev").

Then simply implement your changes, tests and issue a PR, as usual.
Meanwhile, because in dev mode smtk is usually installed as editable ('-e' flag),
you don't need to change anything locally, as the new features/fixes are already available in eGSIM.
Then, *once the PR is merged in the upstream branch*, you can switch back to the
"master" branch in smtk, and merge from the upstream branch, as follows:

<details>
	<summary>First make sure you added the upstream branch (once-only operation)</summary>

Type:

```bash
git remote -v
```

if you see these lines

```bash
upstream https://github.com/GEMScienceTools/gmpe-smtk.git (fetch)
upstream https://github.com/GEMScienceTools/gmpe-smtk.git (push)
```

skip the line below. Otherwise, add the upstream branch by typing:

```bash
git remote add upstream https://github.com/GEMScienceTools/gmpe-smtk.git
```
</details>

Then merge:

```bash
# Fetch all the branches of that remote into remote-tracking branches, such as upstream/master:
git fetch upstream

# Switch to master branch if you are not already there
git checkout master

# Merge:
git merge upstream/master
```

Finally, update the smtk version: issue a `git log -1` and copy the commit
hash into the two `requirements` text files.
Open them, find the line where `gmpe-smtk` is listed and replace the commit hash in
the portion of the line between '@' and '#'. Eventually, issue a `git push`
