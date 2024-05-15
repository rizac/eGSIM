eGSIM is a web service for selecting and testing  ground shaking models (GSIM) 
in Europe, developed by the [GFZ](https://www.gfz-potsdam.de/) 
in the framework of the Thematic Core Services for Seismology of 
[EPOS](https://www.epos-eu.org/) under the umbrella of 
[EFEHR](http://www.efehr.org/en/home/)

<p align="middle">
    <a title='EFEHR' href='www.efehr.org'><img height='50' src='http://www.efehr.org/export/system/modules/ch.ethz.sed.bootstrap.efehr2021/resources/img/logos/efehr.png'></a>
    &nbsp;
    <a title='GFZ' href='https://www.gfz-potsdam.de/'><img height='50' src='https://www.gfz-potsdam.de/fileadmin/gfz/GFZ.svg'></a>
    &nbsp;
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
   * [Packages upgrade](#packages-upgrade)
   * [Django](#django)
     * [Starting a Python terminal shell](#starting-a-python-terminal-shell)
     * [Complete DB reset](#Complete-DB-reset)
     * [Repopulating the DB](#Re-populating-the-DB)
     * [Admin panel](#admin-panel)
     * [Create a custom management command](#Create-a-custom-management-command)  
     * [Add new predefined flatfiles](#Add-new-predefined-flatfiles)
     * [Add new regionalization](#Add-new-regionalization)
     

DISCLAIMER: **This document does not cover the server installation of 
the web app**, which is publicly available at the URL above. 
**Here you can find instructions on**:

 - How to install  eGSIM as local Python library 
   (`import egsim.smtk` in your code)
 - (For developers and contributors) How to install the Django app locally for testing,
   features addition, maintenance


# Installation


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
check `python_requires=`. As of January 2022, it's `>=3.11`) *which you must 
install* in addition to the Python version required by your system, and use
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

Assuming you are in the egsim directory with a virtualenv <VENVNAME>:

```console
source .env/<ENVNAME>/bin/activate
pip install -r ./requirements.txt
```

### eGSIM as local library

If you want to use eGSIM locally using the 
strong motion toolkit package only (`from egsim.smtk import ...`
in your code):

```console
source .env/<ENVNAME>/bin/activate
pip install -r ./requirements.lib.txt
```

#### Run tests 

(remember to `pip install pytest` first)
```bash
pytest -vvv ./tests/smtk
```

## Run Test

(web app tests. For testing the library only, see above)

> Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below 
> must be changed in production

Move in the `egsim directory` and type:

```bash
export DJANGO_SETTINGS_MODULE=egsim.settings_debug; pytest -xvvv ./tests/
```
(x=stop at first error, v*=increase verbosity). 

with coverage report:

```bash
export DJANGO_SETTINGS_MODULE=egsim.settings_debug; pytest --cov=egsim --cov-report=html -xvvv ./tests/
```

<details>
<summary>Configure PyCharm</summary>
For **PyCharm users**, you need to configure the environment variable
for all tests. Go to:

- Run
  - Edit Configurations
    - Python tests
    
And then under **Environment variables:** add:

`DJANGO_SETTINGS_MODULE=egsim.settings_debug`

(type several env vars separated by ;)

</details>


# Usage

> Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below 
> must be changed in production

If you didn't do already, perform 
a [Complete DB reset](#Complete-DB-reset)
(**one-time only operation**)

If you want to access the admin panel, see [the admin panel](#admin-panel).

**To run the program in your local browser**, type:

```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py runserver 
```

<details>
<summary>Configure PyCharm</summary>
For **PyCharm users**, you can implement a service, which can be run as any
PyCharm configuration in debug mode, allowing to open the browser 
and stop at specific point in the code (the PyCharm window will popup 
automatically in case). 
To implement a service, go to:

- Run
  - Edit Configurations
    - Add new configuration

then under **Run**:
 - between `script` and `module` (should be a combo box) choose `script`,
   and in the next text field put `manage.py`
 - script parameters: `runserver`
 - And then under **Environment variables:** add:
   `DJANGO_SETTINGS_MODULE=egsim.settings_debug`
   (type several env vars separated by ;)

You should see in the `Services` tab appearing the script name, so you can
run / debug it normally

</details>


## Packages upgrade


```console
source .env/<ENVNAME>/bin/activate
pip install --upgrade pip setuptools
```

Upgrade OpenQuake (**optional**). The operation below should be performed in
very specific cases only (important bugfixes or features) because
**being OpenQuake often backward incompatible** it might require additional 
code fixes and feedbacks from scientific experts or OpenQuake developers.
First, **open `setup.py` and comment the line of `install_requires` where OpenQuake
is installed** (should be starting with `openquake.engine`). Then 
(note that `pip install openquake` works but is not the recommended way):
```console
pip install -r "https://raw.githubusercontent.com/gem/oq-engine/master/requirements-py311-macos_x86_64.txt"
# pip install -r "https://raw.githubusercontent.com/gem/oq-engine/master/requirements-py311-linux64.txt"
```


Install eGSIM Python library, upgrading its dependencies:
```console
pip install -Ue . && pip freeze >./requirements.lib.txt && pip install pytest
```

Run tests:
```console
pytest -vvv ./tests/smtk
```

Install eGSIM web app, upgrading its dependencies:
```console
pip install -U --upgrade-strategy eager ".[web]"
pip freeze > ./requirements.txt
```

Run tests:
```console
export DJANGO_SETTINGS_MODULE=egsim.settings_debug; pytest -xvvv ./tests/
```

Change `setup.py` and set the current OpenQuake version in 
`install_requires` (uncomment it if commented). Optionally,
remove egsim from requirements.txt (it might interfere with Django web?*).

Eventually, **commit and push**


# Django

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
   Django `admin` app, visible through the [Admin panel](#admin-panel).

</details>

## Starting a Python terminal shell

> Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below 
> must be changed in production

Typing `python` on the terminal does not work as one needs to
initialize Django settings. The Django `shell` command does this:

```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py shell 
```

## Complete DB reset

> Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below 
> must be changed in production

We perform a complete DB reset every time we change something 
in the Database schema (see `egsim.api.models.py`), e.g. a table, 
a column, a constraint.

<details>
<summary>(if you wonder why we do not use DB migrations, click here)</summary>

The usual way to change a DB in a web app is to create and run
migrations 
([full details here](https://docs.djangoproject.com/en/stable/topics/migrations/)),
which allow to keep track of all changes (moving back and forth if necessary) 
whilst preserving the data stored in the DB. 
However, none of those features is required in eGSIM: DB data is predefined
and would be regenerated from scratch in any case after any new migration.
Consequently, **upon changes in the DB, a complete DB reset is an easier 
procedure**.

In any case (**just for reference**), the steps to create and run migrations 
in eGSIM are the following:

```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py makemigrations egsim --name <migration_name>
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py migrate egsim
```
And then repopulate the db:
```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py egsim_init
```

Notes: 
  - The `make_migration` command just generates a migration file, it doesn't 
    change the db. The `migrate` command does that, by means of the migration 
    files generated. For details on Django migrations, see:
    - https://realpython.com/django-migrations-a-primer/#changing-models
    - https://docs.djangoproject.com/en/stable/topics/migrations/#workflow 
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

 - delete or rename the database of the settings file used and *all* migration 
   files. In dev mode they are:
   - `egsim/db.sqlite3`
   - `egsim/api/migrations/0001_initial.py` (there should be only one. If there 
     are others, delete all of them)
 - Execute:
   ```bash
   export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py makemigrations && python manage.py migrate && python manage.py egsim_init
   ```
 - `git add` the newly created migration file (in dev mode it's 
   `egsim/api/migrations/0001_initial.py`)
 - [**Optional**] re-add the Django admin superuser(s) as explained in the
   [admin panel](#admin-panel)

Notes:
 - Commands explanation:
   - `makemigrations` creates the necessary migration file(s) from Python 
     code and existing migration file(s)
   - `migrate` re-create the DB via the generated migration file(s)
   - `egsim_init` repopulates the db with eGSIM data


## Re-populating the DB
 
We repopulate the DB when  **its schema has not changed** but its data 
needs to, e.g., OpenQuake is upgraded, or new data is implemented 
(new regionalization or flatfile), or a bug in the code has been 
fixed. The operations are similar but simpler than a complete Db Rest:

- delete or rename the database of the settings file used:
   - `egsim/db.sqlite3`
- Execute: 
  ```bash
  export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py migrate && python manage.py egsim_init
  ```
- [**Optional**] most likely (not tested, please check) you need to re-add 
  the Django admin superuser(s) as explained in the [admin panel](#admin-panel)
   

## Admin panel

> Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below 
> must be changed in production

This command allows the user to check database data from the 
web browser. For further details, check the 
[Django doc](https://docs.djangoproject.com/en/stable/ref/django-admin/)

The database must have been created and populated (see [Usage](#usage)). 

Create a superuser (to be done **once only** ):
```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py createsuperuser
```
and follow the instructions.

Start the program (see [Usage](#Usage)) and then navigate in the browser to 
`[SITE_URL]/admin` (in development mode, `http://127.0.0.1:8000/admin/`)

*Note: Theoretically, you can modify db data from the browser, e.g., hide some 
model, regionalization or predefined flatfile. Persistent changes should be
implemented in Python code and then run a [Complete DB reset](#Complete-DB-reset)*


## Create a custom management command

See `egsim/api/management/commands/README.md`.

The next two sections will describe how to store
new data (regionalizations and flatfiles) that will be
made available in eGSIM with the `egsim_init` command
(see [Complete DB reset](#Complete-DB-reset) for details)


## Add new predefined flatfiles

- Add the file (CSV or zipped CSV) in
  `managements/commands/data/flatfiles`. 
  If the file is too big try to zip it. 
  **If it is more than few tens of Mb, then do not commit it** (explain in 
  the section `details` - see below - how to get the source file). 
  When zipping in macOS you will probably need to
  [exclude or remove (after zipping) the MACOSX folder](https://stackoverflow.com/q/10924236)~~
- 
- Implement a new `FlatfileParser` class in 
  `management/commands/flatfile_parsers`. Take another parser, copy it 
  and follow instructions.
  The parser goal is to read the file and convert it into a harmonized HDF 
  table

- Add binding file -> parser in the Python `dict`:
  `management.commands._egsim_flatfiles.Command.PARSER`

- (Optional) Add the file refs 
  in `management/commands/data/references.yaml`, e.g. reference, url, the 
  file name that will be used in the API (if missing, defaults to the file 
  name without extension)

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

- Add two files *with the same basename* and extensions in 
  `managements/commands/data/regionalization_files`:

  - <name>.geojson (regionalization, aka regions collection) and
  - <name>.json (region -> gsim mapping)
  
  See already implemented files for an example

- (Optional) Add the file refs 
  in `management/commands/data/references.yaml`, e.g. reference, url, the 
  file name that will be used in the API (if missing, defaults to the file 
  name without extension)

- Repopulate all eGSIM tables (command `egsim_init`)

