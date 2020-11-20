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


Please use Python versions>=3.7, referred here for simplicity as
Python3.7+ (as of start 2021, the last tested version is 3.9).
Check with ```python --version```: if it's Python2, then use ```python3 --version```.
If it's not 3.7+, then you need to install Python3.7+ **along with**
(i.e., not replacing) the current default python3 installed on your computer.
From now on, each `python` command refers to the path of the Python3.7+ distribution you have
(i.e., you might need to type e.g. `/opt/lib/python3.7` or something similar,
instead of `python` or `python3`)


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
pip install --upgrade pip setuptools
```

**NOTE: From now on, all following operations must have the virtualenv activated FIRST**

### Install

#### Quick

Note: in this case you can not modify `smtk`, if needed, and you must
**not** update or push `requirement`s file (e.g., you can **not** perform any
[dependency upgrade](#dependencies-upgrade))

Open `requirements.txt` and check the line where smtk is installed
(it should be commented). Avoid the initial comment '#' (and the following "-e",
if any) and copy the rest of the line. Then:

```bash
pip install <smtk_line>
```

Then, if you want to run tests (the usual case in dev mode):

```bash
pip install pylint pytest-django pytest-cov
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

**move back into the the `egsim directory`** and then:

```bash
pip install -r requirements.dev.txt
cd ../gmpe-smtk # (or whatever you cloned the forked branch)
```

<details>
	<summary>What is requirements.txt?</summary>
	It is the list of dependencies without those required for running
	tests. It is to be used optionally only in production
</details>

**Note** that the current commit hash (`git log -1`) **should be the same** as
in `requirements.txt` [^].
If not, please report this to the eGSIM maintainers (e.g. open an issue on the githiub page).
If you can not wait the reply, `git checkout <commit_hash>` [**§**].

<details>
	<summary>[**§**]</summary>
	The commit hash in any `requirements.*.txt` file is the string portion of `smtk`
	between '@' and '#'
</details>

```
pip install -e .
cd ../egsim. # (or wherever egsim is)
```

<details> 
  <summary>Is this longer installation needed in production?</summary>

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

### Fixing / Adding features to gmpe-smtk

We will refer to smtk as the [forked branch](https://github.com/rizac/gmpe-smtk)
used by eGSIM. As we have seen during installation, it is a forked repository from the
[upstream branch](https://github.com/GEMScienceTools/gmpe-smtk.git).

By convention **the branch `master` of smtk must always point to the latest
tested commit used in production**. Therefore, when fixing an smtk issue or implementing
a new feature, switch to a dev branch (we usually use the branch called ... "dev").

Then simply implement your changes, tests and issue a PR, as usual.
Once done, you now can get back to eGSIM by simply staying in the "dev" branch (or whatever):
because in dev mode smtk is usually installed as editable ('-e' flag),
you immediately have the new features/fixes available in eGSIM locally.

Then, **once the PR is merged in the upstream branch**, you can switch to
"master" in smtk, and merge from the upstream branch.

<details>
	<summary>First make sure you added the upstream branch (once-only operation)</summary>

Type:

```bash
git remote -v
```

if you see these lines

```bash
upstream	https://github.com/GEMScienceTools/gmpe-smtk.git (fetch)
upstream	https://github.com/GEMScienceTools/gmpe-smtk.git (push)
```

Then you are done (skip the line below), otherwise, add the upstream branch by typing:

```bash
git remote add upstream https://github.com/GEMScienceTools/gmpe-smtk.git
```
</details>

Then:

```bash
# Fetch all the branches of that remote into remote-tracking branches, such as upstream/master:
git fetch upstream

# Make sure that you're on your master branch, and then:
git merge upstream/master
```

Finally, update the requirements file: issue a `git log -1` and copy the commit
hash into `requirements.*.txt` in the line of `gmpe-smtk` between '@' and '#'
(the whole line should be commented, see below), and issue a `git push` 



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
git checkout master && git pull
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
