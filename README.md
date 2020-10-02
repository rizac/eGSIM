# eGSIM
A web service for selecting and testing  ground shaking models in Europe (eGSIM), developed
in the framework of the  Thematic Core Services for Seismology of EPOS-IP
(European Plate Observing  System-Implementation Phase)


## Installation (development)

Disclaimer: this is a temporary tutorial tested with MacOS (El Capitan) and Ubuntu 16.04. 


### Requirements

```bash
sudo apt-get update # pre-requisite
sudo apt-get install gcc  # optional
sudo apt-get install git python3-venv python3-pip python3-dev
```

(The command above are Ubuntu specific, in macOS install brew and type
`brew install` instead of `apt-get install`. *Remove python3-dev as it does not
exist on macOS*).


[FIXME: CHANGE]:
Please use Python 3.7+. Check with ```python --version```:
if it's Python2, then use ```python3 --version```.
If it's not 3.7+, then you need to install Python3.7 **along with**
(i.e., not replacing) the current default python3 installed on your computer.
From now on, each `python` command refers to the path of the Python3.7 distribution you have
(i.e., you might need to type e.g. `/opt/lib/python3.7` or something similar,
instead of `python` or `python3`)


### Clone repository

Select a `root directory` (e.g. `/path/to/egsim`), and closne egsim and gmpe-smtk
into two subdirectories (we call them `egsim directory` and `smtk directory`):


```bash
git clone https://github.com/rizac/eGSIM.git egsim
git clone https://github.com/rizac/gmpe-smtk.git gmpe-smtk
```

Why creating a `root directory` and cloning therein `eGSIM` and `gmpe-smtk`?
Because by later installing `gmpe-smtk` in editable mode (see below)
we can fix bugs immediately and also issue pull requests (PR) to the upstream branch.

In production mode could we simply clone `eGSIM`? yes. But in many cases
we follow the procedure above also in production, to allow the same procedure also
from the server.


### Install

```bash
python3 -m venv .env/<ENVNAME>  # create python virtual environment (venv)
source .env/<ENVNAME>/bin/activate  # activate venv
pip install --upgrade pip setuptools
pip install openquake.engine
cd ../gmpe-smtk # (or whatever you cloned the forked branch)
pip install -e .
cd ../egsim. # (or wherever egsim is)
pip freeze > requirements.txt  # (OPTIONAL, IF YOU ARE UPGRADING)
pip install pylint pytest-django pytest-cov. # (OPTIONAL IF YOU WQNT TO RUN TESTS, which should be the case in dev mode)
pip freeze > requirements.dev.txt. # (optional if you are upgrading)
```

### Activate virtualenv

Create the virtual environment. Move into the `root directory`
(you can also move into another directory, but it does not make much sense), and type: 

```bash
python3 -m venv ./env  # create venv
source ./env/bin/activate  # activate venv
```

(to deactivate the virtual environment, type `deactivate` on the terminal)

**IMPORTANT: from now on the venv must be activated If not, type**
**`source ./env/bin/activate` as shown above. This way,**
**everything will be installed in your "copy" of**
**Pyhton with no conflicts with the OS Python distribution**


### Install

Move to `egsim directory`, open `requirements.dev.txt` and make
sure that the line starting with "gmpe-smtk" is commented (with a leading '#')
because gmpe-smtk must be installed *after* openquake (see
[Dependencies upgrade](#dependencies_upgrade))

 and type:

```bash
pip install --upgrade pip setuptools && pip install -r ./requirements.dev.txt
cd ../gmpe-smtk  # or wherever smtk is cloned to, see above
pip install -e .  # -e necessary only in dev mode
cd ../egsim  # or wherever egsim is cloned to, see above
```

<small>
(Note: you could have opened and used the file `requirements.txt`: it is the
same as `requirements.txt` but without the packages required for running tests.
Those packages are not strictly mandatory, but there is actually no reason to avoid
running tests in both dev and prod mode for a web service like this one)
</small>


### Test

Move into the `egsim directory` and type:

Normal test (x=stop at first error, v*=increase verbosity):
```bash
pytest -xvvv --ds=egsim.settings_debug ./tests/
```

Test with coverage
```bash
pytest -xvvv --ds=egsim.settings_debug --cov=./egsim/ --cov-report=html ./tests/
```

### Setup project data


#### Flatfile (ESM):
This procedure should be executed for all flatfiles to be included in the application.
For testing purposes, we will use ESM flatfile (2018) only.
Download ESM flatfile from https://esm.mi.ingv.it//flatfile-2018/flatfile.php (ESM_flatfile_2018)
Unzip it and from within the same directory, copy the file:
```bash
cp ESM_flatfile_2018/ESM_flatfile_SA.csv ./ESM_flatfile_2018_SA.csv
```
Called $FLATFILE_PATH the full path of the CSV file just copied,
now parse it into the ESM database, the database will be a HDF5 file
inside the /media/ directory of the egsim repository (git ignores that directory):
```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py gmdb_esm $FLATFILE_PATH
```


#### Migrate (setup django db)
From within the egsim folder (check that manage.py is therein):
```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py migrate
```


#### Create db  (setup egsim tables inside django db)
From within the egsim folder (check that manage.py is therein):
```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py initdb
```


## Run:
```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py runserver
```
and pen your browser (or use the API) at the URL address on the console 


## Installation (production)

Please refer to 'deploy.html' (dynamic web page, open it in your browser of choice)


## Maintenance


### Github packages security issues / dependencies alert:

Security alerts on Github should be solved by
[upgrading the dependencies](#dependencies-upgrade), as most of the required packages
are OpenQuake dependencies and thus it's safer to keep everything consistent.
Also, the new pip will be
[more strict](https://stackoverflow.com/questions/63277123/what-is-use-feature-2020-resolver-error-message-with-jupyter-installation-on)
so better be safe.

### Dependencies upgrade

Note that this operation will most likely require additional time-consuming work
to fix bugs in egsim and sometime in smtk, too.

You create a new Python venv and then:

```zsh
pip install openquake.engine
cd gmpe-smtk # (or 'cd' wherever you cloned gmpe-smtk)
pip install -e .  # install gmpe-smtk
cd ../egsim. # (or wherever egsim is)
pip freeze > requirements.txt
pip install pylint pytest-django pytest-cov
pip freeze > requirements.dev.txt
```

<!--
```bash
pip install --upgrade pip setuptools && pip install openquake-engine

# Move to the smtk directory (see section Clone-repository)
git pull && pip install -e .

# Run tests
pip freeze > ./requirements.txt
```
-->

**Important**: open the two `requirements.*` files and **comment the line with gmpe-smtk**,
because it must be installed *after* openquake (see [Install](#install))
