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

Select a `root directory` (e.g. `/path/to/egsim`), and clone egsim into the
so-called egsim directory:

```bash
git clone https://github.com/rizac/eGSIM.git egsim
```

### Create and activate Python virtual env

Move to whatever directory you want (usually the egsim directory) and then:

`egsim`
```bash
python3 -m venv .env/<ENVNAME>  # create python virtual environment (venv)
source .env/<ENVNAME>/bin/activate  # activate venv
pip install --upgrade pip setuptools
```

**NOTE: From now on, all following operations must have the virtualenv activated FIRST**

### Install

#### Quick

Note: in this case you can not modify `smtk`, if needed, and you must
**not** update or push `requirement`s file (e.g., you can **not** perform any
[dependency upgrade](#dependencies-upgrade))

Open `requirements.txt` and check the line where smtk is installed
(it should be commented). Remove the comment (and the initial -e if any) and
copy the rest of the line. Then:

```bash
pip install <smtk_line>
```

Then, if you want to run tests (the usual case in dev mode):

```bash
pip install git+https://github.com/rizac/gmpe-smtk#egg=smtk
```

<details> 
  <summary>Why can't we upgrade dependencies this way?</summary>

Because as of end 2020, pip installing from git repositories does not seems to
   work with `requirements.txt` afterwards. E.g. both these options work:
   `pip install git+https://github.com/rizac/gmpe-smtk#egg=smtk` or 
   `pip install smtk@git+https://github.com/rizac/gmpe-smtk`
   but they store `smtk` in `pip` with a format (something like `smtk<version>#<commit_hash>`)
   that will not work with `pip install -r requirements.txt`

</details>

#### Longer

If on the other hand you want to have the possibility to update,
modify, and push from `smtk`, then

Clone gmpe-smtk, usually on the same level of the `egsim directory` into
the so-called `smtk directory`:

```bash
git clone https://github.com/rizac/gmpe-smtk.git gmpe-smtk
```

*(note: from now on you can replace `requirements.dev.txt` with `requirements.txt`
in the commands below to skip installing packages used for testing,
but we don't see how this should be useful in dev mode)*

```bash
pip install -r requirements.dev.txt
cd ../gmpe-smtk # (or whatever you cloned the forked branch)
```

Now check that the current commit hash is the same in `requirements.txt`.
If not, either `git checkout egsim` (the branch `egsim` *should* be kept at the
desired commit) or `git checkout <commit_hash>` (the commit hah is 
the string portion of `smtk` between '@' and '#' in any `requirements.*` file)

```
pip install -e .
cd ../egsim. # (or wherever egsim is)
```

<details> 
  <summary>Is this "double" directory needed in production?</summary>

In production mode could we simply clone `eGSIM`? yes. But we suggest to
follow the procedure above in any case, to allow the same flexibility.

Also note that this is a client program but a web app in Django,
there is no need to install this program via `pip install .`, but only its
dependencies
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
run tests, fix new bugs and then `git push`, an so on).
When done, move to `smtk` and "fix" the "egsim" branch to point to the
current commit: `git checkout egsim && git merge master`.
