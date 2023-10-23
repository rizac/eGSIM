eGSIM is a web service for selecting and testing  ground shaking models (GSIM) 
in Europe, developed a the [GFZ](https://www.gfz-potsdam.de/) in the framework of the Thematic Core Services for 
Seismology of [EPOS](https://www.epos-eu.org/) under the umbrella of 
[EFEHR](http://www.efehr.org/en/home/)

<p align="middle">
    <a title='EFEHR' href='www.efehr.org'><img height='50' src='http://www.efehr.org/export/system/modules/ch.ethz.sed.bootstrap.efehr2021/resources/img/logos/efehr.png'></a>
    &nbsp;&nbsp;
    <a title='GFZ' href='https://www.gfz-potsdam.de/'><img height='50' src='https://www.gfz-potsdam.de/fileadmin/gfz/GFZ.svg'></a>
    &nbsp;&nbsp;
    <a title='EPOS' href='https://www.epos-eu.org/'><img height='50' src='https://www.epos-eu.org/themes/epos/logo.svg'></a>
    <br>
</p>

The web portal (and API documentation) is available at:

# https://egsim.gfz-potsdam.de

## Citation

> Zaccarelli, Riccardo; Weatherill, Graeme (2020): eGSIM - a Python library and web application to select and test Ground Motion models. GFZ Data Services. https://doi.org/10.5880/GFZ.2.6.2023.007

# Table of contents

   * [Installation](#installation)
   * [Usage](#usage)
   * [Maintenance](#maintenance)
     * [Starting a Python terminal shell](#starting-a-python-terminal-shell)
     * [Complete DB reset](#Complete-DB-reset)
     * [Repopulate the DB](#Repopulate-the-DB)
     * [Admin panel](#admin-panel)
     * [Create a custom management command](#Create-a-custom-management-command)  
     * [Add new predefined flatfiles](#Add-new-predefined-flatfiles)
     * [Add new regionalization](#Add-new-regionalization)
     * [Dependencies upgrade](#Dependencies-upgrade)

     
# Installation

DISCLAIMER: **This document covers installation in development (or debug) 
mode, i.e. when the program is deployed locally, usually for testing, 
fixing bug or adding features.**

For installation in **production** mode, see `deploy.html`

## Requirements

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


## Clone repository

Select a `root directory` (e.g. `/root/path/to/egsim`), and clone egsim into the
so-called egsim directory:

```bash
git clone https://github.com/rizac/eGSIM.git egsim
```

## Create and activate Python virtual env

Move to whatever directory you want (usually the egsim directory above) and then:

```bash
python3 -m venv .env/<ENVNAME>  # create python virtual environment (venv)
source .env/<ENVNAME>/bin/activate  # activate venv
```

**NOTE: From now on, all following operations must have the virtualenv 
activated FIRST**

## Install

*Note: if the installation is done for upgrading all dependencies and 
`pip freeze` into new requirements files,
please go to [dependency upgrade](#dependencies-upgrade)*

On the terminal, execute:
```bash
pip install --upgrade pip setuptools && pip install -r requirements.dev.txt
```
(use `requirements.txt` if you don't need to run tests, e.g. you are not 
installing as developer)

## Run Test

**Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below
must be changed in production**

Move in the `egsim directory` and type:

```bash
export DJANGO_SETTINGS_MODULE=egsim.settings_debug; pytest -xvvv --ds=egsim.settings_debug ./tests/
```
(x=stop at first error, v*=increase verbosity). 

For **PyCharm users**, you need to configure the environment variable
for all tests. Go to:
  Run -> Edit Configurations -> Edit Configurations templates -> 
  Python tests -> pytests -> ENVIRONMENT VARIABLES

and add there the environment variable DJANGO_SETTINGS_MODULE

Other test options from the command line: with coverage (
showing the amount of code hit by tests):

```bash
export DJANGO_SETTINGS_MODULE=egsim.settings_debug; pytest --ignore=./tests/tmp/ -xvvv --cov=./egsim/ --cov-report=html ./tests/
```

(you can also invoke the commands without `export ...` but 
using the `--ds` option: `pytest -xvvv --ds=egsim.settings_debug ./tests/`)


# Usage

**Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below
must be changed in production**

If you didn't do already, perform 
a [Complete DB reset](#Complete-DB-reset)
(**one-time only operation**)

If you want to access the admin panel, see [the admin panel](#admin-panel).

**To run the program in your local browser**, type:

```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py runserver 
```

(you can also invoke the commands without `export ...` but using the 
`--settings` option: 
`python manage.py --settings=egsim.settings_debug [command]`)


# Maintenance

<details>
<summary>
Brief Introduction to some important concepts and key terms (click to show)
</summary>

 - [Settings file](https://docs.djangoproject.com/en/stable/topics/settings/): 
   A Django settings file contains all the configuration of your Django 
   installation. The settings file referred in this document, 
   included in this git repo, is for debug and local deployment only.
   On production, a separate settings file is used, located on the server 
   outside the git repo and **not shared for security reasons**.

   
 - [manage.py](https://docs.djangoproject.com/en/stable/ref/django-admin/) or
   `django-admin` is Django’s command-line utility for administrative tasks.
   It is invoked from the terminal within your Python virtualenv (see examples
   in this document) by providing the settings file via:
   ```bash
   export DJANGO_SETTINGS_MODULE=<settings_file_path> python manage.py <command>
   ```
   Django allows also the implementation of custom management commands.
   eGSIM implements `egsim-init` in order to populate the db (more details 
   below)


 - [app](https://docs.djangoproject.com/en/stable/intro/reusable-apps/) a 
   Django app is a Python package that is specifically intended for use in 
   a Django project. An application may use common Django conventions, such as 
   having models, tests, urls, and views submodules. In our case, the Django
   project is the egsim root directory (created with the command
   `django-admin startproject egsim`), and the *Django apps* inside it are 
   "api" (the core web API) and "app" (the *web app*, i.e. the part of eGSIM
   delivered over the Internet through a browser interface), that relies on 
   the "api" code.
   Inside the settings file (variable `INSTALLED_APPS`) is configured the list 
   of all applications that are enabled in the eGSIM project. This includes not 
   only our "api" app, that tells Django to create the eGISM tables when
   initializing the database, but also several builtin Django apps, e.g. the 
   Django `admin` app, visible through the [Admin panel](#admin-panel)).

</details>

## Starting a Python terminal shell

**Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below
must be changed in production**

Typing `python` on the terminal does not work if you need to import django
stuff, as there are things to be initialized beforehand. The Django `shell`
command does this:

```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py shell 
```

## Complete DB reset

**Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below
must be changed in production**

We perform a complete DB reset every time we change something in the Database 
schema (see `egsim.api.models.py`), e.g. a table, a column, a constraint.

<details>
<summary>(if you wonder why we do not use DB migrations, click here</summary>

The usual way to change a DB in a web app is to create and run
migrations ([Django full details here](https://docs.djangoproject.com/en/stable/topics/migrations/)),
which allow to keep track of all changes (moving back and forth if necessary) 
whilst preserving the data stored in the DB. 
However, none of those features is required in eGSIM: DB data is predefined
and would be regenerated from scratch in any case after any new migration.
Consequently, **upon changes in the DB, a complete DB reset is an easier procedure**.

In any case (**just for reference**), the steps to create and run migrations 
in eGSIM are the following:

```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py makemigrations egsim --name <migration_name>
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py migrate egsim
```
And then remember to [Repopulate the db](#Repopulate-the-DB)

Notes: 
  - The `make_migration` command just generates a migration file, it doesn't 
    change the db. The `migrate` command does that, by means of the migration 
    files generated. For details on Django migrations, see:
    - https://realpython.com/django-migrations-a-primer/#changing-models
    - https://docs.djangoproject.com/en/3.2/topics/migrations/#workflow 
  - <migration_name> will be a suffix appended to the migration file, use it
    like you would use a commit message in `git`).
  - When running `migrate`, if the migration 
    will introduce new non-nullable fields, maybe better to run 
    `manage.py flush` first to empty all tables, to avoid conflicts
    "egsim" above is the app name. If you omit the app, all apps will be 
    migrated. The command `migrate` does nothing if it detects that there is 
    nothing to migrate
</details>

To perform a complete db reset:

 - delete or rename `db.sqlite3` (or wherever the database is. See settings file in case)
 - [**Optional: skip if the db schema hasn't changed**] delete all migrations,
   i.e. all `*.py` files except `__init__.py` currently under `egsim/api/migrations`, 
   and re-generate the initial (and only) migration file:
   ```bash
   export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py makemigrations
   ```
 - Run migrations (re-create the DB via the generated migration file):

   ```bash
   export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py migrate
   ```
 - [Repopulate the db](#Repopulate-the-DB)
 
 - [**Optional**] re-add the Django admin superuser(s) as explained in the
   [admin panel](#admin-panel) above
   

## Repopulate the DB

NOTE: If you don't have created and initialized the db yet, go to 
[Complete DB reset](#Complete-DB-reset)

When the db is created for the first time or reset, 
OpenQuake is upgraded, or new data is implemented (new regionalization 
or flatfile), you need to repopulate the database and the filesystem, 
to make changes available to eGSIM users.
Execute the custom management command `egsim_init`:

```bash
   export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py egsim_init
```



## Admin panel

**Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below
must be changed in production**

This command allows the user to check database data from the 
web browser. For further details, check the 
[Django doc](https://docs.djangoproject.com/en/stable/ref/django-admin/)

The database must have been created and populated (see [Usage](#usage)). 

Create a super user (to be done **once only** ):
```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py createsuperuser
```
and follow the instructions.

Start the program (see [Usage](Usage)) and then navigate in the browser to 
`[SITE_URL]/admin` (in development mode, `http://127.0.0.1:8000/admin/`)

*Note: Theoretically, you can modify db data from the browser, but to make 
changes persistent after a database reset you should implement them in 
the management command `egsim_init` (see [Repopulate the DB](#Repopulate-the-DB))*


## Create a custom management command

See `egsim/api/management/commands/README.md`.

The next two sections will describe how to store
new data (regionalizations and flatfiles) that will be
made available in eGSIM when [repopulating the db](#Repopulate-the-DB)


## Add new predefined flatfiles

- Add the file (CSV or zipped CSV) in
  `managements/commands/data/predefined_flatfiles`. 
  Do **not** commit files too big (**max few tens of Mb**). When zipping in 
  macOS you will probably need to
  [exclude or remove (after zipping) the ___MACOSX folder](https://stackoverflow.com/q/10924236)
  
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

Implemented flatfiles sources (click on the items below to expand)

<details>
<summary>ESM 2018 flatfile</summary>

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
</details>


## Add new regionalization

- Add two files *with the same basename* and extensions 
  - .geojson (regionalization, aka regions collection) and
  - .json (region -> gsim mapping)
  
  in `managements/commands/data/regionalization_files`. Usually, these files 
  are copied and pasted from the `shakyground2` project (see GFZ gitlab), but 
  if you neeed to implement your own see examples in the given directory 
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


## Dependencies upgrade

Please note that it is safer (even 
[mandatory](https://stackoverflow.com/questions/63277123/what-is-use-feature-2020-resolver-error-message-with-jupyter-installation-on)
with `pip`) to upgrade all dependencies
instead of single packages in order to avoid conflicts.

Consequently, **we recommend to follow this procedure also
in case of a GitHub security issue (or dependency alert) on a single package**.

First create a new virtual env (in the example below,
in the git-ignored `.env` inside
the eGSIM root directory, 
but you can also create it wherever you want)

```bash
python3 -m venv .env/<ENVNAME>  # create python virtual environment (venv)
source .env/<ENVNAME>/bin/activate  # activate venv
pip install --upgrade pip setuptools
```

Then `cd` into eGSIM if you are not there already 
(basically, the directory where `setup.py` is located), 
install and freeze 
the installed packages into a `requirements.txt` file:
```bash
pip install -e .
pip freeze > requirements.txt
```

Do the same for testing:
```bash
pip install -e ".[test]"
pip freeze > requirements.dev.txt
```

Run tests (see above) to check that everything wortks as expected, and then
commit and push.
