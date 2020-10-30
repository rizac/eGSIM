# eGSIM
A web service for selecting and testing  ground shaking models in Europe (eGSIM), developed
in the framework of the  Thematic Core Services for Seismology of EPOS-IP
(European Plate Observing  System-Implementation Phase)


## Installation (development)

This is a tutorial tested with MacOS (El Capitan and Catalina)
and Ubuntu 18.04. 


### Requirements

```bash
sudo apt-get update # pre-requisite
sudo apt-get install gcc  # optional
sudo apt-get install git python3-venv python3-pip python3-dev
```

(The command above are Ubuntu specific, in macOS install brew and type
`brew install` instead of `apt-get install`. *Remove python3-dev as it does not
exist on macOS*).


Please use Python 3.7+. Check with ```python --version```:
if it's Python2, then use ```python3 --version```.
If it's not 3.7+, then you need to install Python3.7 **along with**
(i.e., not replacing) the current default python3 installed on your computer.
From now on, each `python` command refers to the path of the Python3.7 distribution you have
(i.e., you might need to type e.g. `/opt/lib/python3.7` or something similar,
instead of `python` or `python3`)


### Clone repository

Select a `root directory` (e.g. `/path/to/egsim`), and clone egsim and gmpe-smtk
into two subdirectories (we call them `egsim directory` and `smtk directory`).


```bash
git clone https://github.com/rizac/eGSIM.git egsim
git clone https://github.com/rizac/gmpe-smtk.git gmpe-smtk
```

<!-- In production mode could we simply clone `eGSIM`? yes. But in many cases
we follow the procedure above also in production, to allow the same procedure also
from the server.

Also note that this is a client program but a server web app,
there is no need to install this program:
what happens under the hoods when doing `pip install .`
is probably harmless, but was not tested.  -->

### Create and activate Python virtual env
```bash
python3 -m venv .env/<ENVNAME>  # create python virtual environment (venv)
source .env/<ENVNAME>/bin/activate  # activate venv
pip install --upgrade pip setuptools
```

**NOTE: From now on, all following operations must have the virtualenv activated FIRST**

### Install

*(note: you can replace `requirements.dev.txt` with `requirements.txt`
in the commands below to skip installing packages used for testing,
but we don't see how this should be useful in dev mode)*

```bash
pip install -r requirements.dev.txt
cd ../gmpe-smtk # (or whatever you cloned the forked branch)
pip install -e . # (also installs openquake and django)
cd ../egsim. # (or wherever egsim is)
```

<details> 
  <summary>Why creating a `root directory` and cloning therein `eGSIM` and `gmpe-smtk`?</summary>

1. Because by installing `gmpe-smtk` in editable mode (`-e`)
   we can fix bugs immediately and also issue pull requests (PR) to the upstream branch

2. Because as of end 2020, pip installing from git repositories does not seems to
   work. E.g. both these option work:
   `pip install git+https://github.com/rizac/gmpe-smtk#egg=smtk` or 
   `pip install smtk@git+https://github.com/rizac/gmpe-smtk`
   but, instead of to the recommended installation procedure, they store `smtk` in
   `pip` with a format (something like `smtk<version>#<commit_hash>`)
   that will not work with `pip install -r requirements.txt`
</details>

For the maintenance (e.g., upgrading dependencies to newer versions) see
[upgrading the dependencies](#dependencies-upgrade).

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

Create and activate a new virtualenv:

```bash
python3 -m venv .env/<ENVNAME>  # create python virtual environment (venv)
source .env/<ENVNAME>/bin/activate  # activate venv
pip install --upgrade pip setuptools
```

```bash
cd ../gmpe-smtk # (or whatever you cloned the forked branch)
git pull && git checkout master
pip install -e . # (also installs openquake and django)
cd ../egsim. # (or wherever egsim is)
pip freeze > requirements.txt
```

Open `requirements.txt` and comment the line with "-e ... gmpe-smtk"

```
pip install pylint pytest-django pytest-cov
pip freeze > requirements.dev.txt
```

Open `requirements.dev.txt` and comment the line with "-e ... gmpe-smtk"

(then, proceed with the normal workflow:
run tests, fix new bugs and then `git push`, an so on)
