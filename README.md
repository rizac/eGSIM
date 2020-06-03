# eGSIM
A web service for selecting and testing  ground shaking models in Europe (eGSIM), developed
in the framework of the  Thematic Core Services for Seismology of EPOS-IP
(European Plate Observing  System-Implementation Phase)

## Installation (development)

Disclaimer: this is a temporary tutorial tested with MacOS (El Capitan) and Ubuntu 16.04. 

### Requirements (Ubuntu specific, in Mac should not be an issue, otherwise `brew install` instead of `apt-get install`):
```bash
brew doctor  # pre-requisite
brew update # pre-requisite
brew install gcc
sudo apt-get install git python3-venv python3-pip python3-dev
```

Please use Python 3.7+. Check with ```python --version```: If it's Python2, then use ```python3 --version```. If it's not 3.7+, then you need to install Python3.7 **along with** (i.e., not replacing) the current default python3 installed on your computer.
From now on, each `python` command refers to the path of the Python3.7 distribution you have (i.e., you might need to type e.g. `/opt/lib/python3.7` or something similar, instead of `python` or `python3`)


### Activate virtualenv (links TBD).
[Pending: doc TBD] Three options:
  1. python-venv (for python>=3.5): Please use this option as it does not issues the 'matplotlib installed as a framework ...' problem
  2. python-virtualenv
  3. virtualenvwrapper (our choice)

*FROM NOW ON virtualenv MUST be activated! EVERYTHING WILL BE INSTALLED ON YOUR "copy" of pyhton with no conflicts with the OS python distribution*


### Clone and install this repository

`git clone` and so on (see Github). From now on we assume you are inside the git repo (the local folder you clone the project into).
Then, to install:

```bash
./installme
```

*IMPORTANT* for details on `installme`, just open the file and read the comments.
Also, please refer to [Package Maintenance](#package-maintenance) for updating package versions


### Test

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
Download ESM flatfile from https://esm.mi.ingv.it//flatfile-2018/flatfile.php  (ESM_flatfile_2018)
Unzip it and from within the same directory, copy the file:
```bash
cp ESM_flatfile_2018/ESM_flatfile_SA.csv ./ESM_flatfile_2018_SA.csv
```
Called $FLATFILE_PATH the full path of the CSV file just copied, now parse it into the ESM database, the database will be a HDF5 file inside the /media/ directory of the egsim repository (git ignores that directory):
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

## Package Maintenance

[The script `installme`](#clone-and-install-this-repository) installs `requirements.txt` first
and then `requirements.pipfreeze.txt`.

- `requirements.txt` is the file with the only necessary packages (with the exception of `gmpe-smtk` which is
  moved to `requirements.pipfreeze.txt` because it has to be installed **after** OpenQuake), whereas

- `requirements.pipfreeze.txt` is the file with *all* necessary packages after running `requirements.txt`
  
`requirements.pipfreeze.txt` **is intended to contain an updated list of all packages and relative dependencies.**.

`requirements.pipfreeze.txt` will also be used by Github to warn us for potential security alerts.

### Github packages security issues / dependencies alert:

Either ignore security alerts as in 99% of the cases a package is a OpenQuake dependency, so live with that
and upgrade OpenQuake when necessary (see below)

or, if really necessary:

Open `requirements.pipfreeze.txt` and change the version of the package to be upgraded.
Run `installme`
Run [tests](#test)

Note: because in most of the cases an installed package is an OpenQuake dependency, errors like this might be issued during pip install:
```ERROR: openquake-engine 3.5.0 has requirement django<2.1,>=1.10, but you'll have django 2.2.10 which is incompatible.```
If you spot them, they might not necessarily be critical. As always, run tests and see.


### OpenQuake (smtk) upgrade

An OpenQuake upgrade should be done when really necessary, as it usually requires several fixes in both smtk and egsim.
In case:

Open `requirements.txt`and change OpenQuake version (commit hash)
Open `requirements.pipfreeze.txt`and change gmpe-smtk version (commit hash)
run `installme`
Run [tests](#test)
Good luck

