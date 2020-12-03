# eGSIM
A web service for selecting and testing  ground shaking models in Europe (eGSIM), developed
in the framework of the  Thematic Core Services for Seismology of EPOS-IP
(European Plate Observing  System-Implementation Phase)


## Installation (development)

This is a tutorial tested with MacOS (El Capitan, Catalina, Big Sur)
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
Python3.7+ (as of end 2020, we are testing with 3.8.6).
Check with ```python --version```: if it's Python2, then use ```python3 --version```.
If it's not 3.7+, then you need to install Python3.7+ **along with**
(i.e., not replacing) the current default python3 installed on your computer.
From now on, each `python` command refers to the path of the Python3.7+ distribution you have
(i.e., you might need to type e.g. `/opt/lib/python3.7` or similar,
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
```

**NOTE: From now on, all following operations must have the virtualenv activated FIRST**

### Install

*Note: if the installation is done for upgrading all dependencies and `pip freeze` into new requirements files,
please go to [dependency upgrade](#dependencies-upgrade)* 


On the terminal, execute:
```bash
pip install --upgrade pip setuptools && pip install -r requirements.dev.txt
```

If you want also to be able to modify `gmpe-smtk` (fix bug, implement new features
and issue Pull Requests to the master branch), then clone gmpe-smtk, usually on the same level
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

and have a look at [Fixing/adding features to gmpe-smtk](#fixing--adding-features-to-gmpe-smtk)
for the suggested workflow.


<details> 
  <summary>Notes</summary>

1. There is also a `requirements.txt` file available, which is the same as `requirements.dev.txt` but
   without the dependencies required for running tests. In general, `requirements.txt` is supposed to be used
   in production only. In our case, we suggest to use `requirements.dev.txt` in any case
   and be able to run tests also on the server.

3. This is not a client program but a web app in Django, there is no need to install this
   program via `pip install .`, but only its dependencies. Also note that this way we have to list dependencies
   in `setup.py`, which is not straightforward with github packages. As of end 2020, both these options work:
   `pip install git+https://github.com/rizac/gmpe-smtk#egg=smtk` or 
   `pip install smtk@git+https://github.com/rizac/gmpe-smtk`
   but they store `smtk` in `pip` with a format (something like `smtk<version>#<commit_hash>`)
   that will not work with `pip install -r requirements.txt`

</details>


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

<details> 
  <summary>Implementation note (for future planning)</summary>
	
In the current implementation, each parsed flatfile is stored as HDF file using pytables (see `smtk`
package). These HDF files (which are *not* readable through `pandas.read_hdf` by the way)
are stored in the "media" directory (see [installation for production](#Installation-(production))
for details).

This method, which is due to several legacy reasons, has also some drawbacks:

1. It makes the data handling more complex with several management
   commands and storages (flatfile vs. database, as you can see here)
   
2. It has to be re-done if new flatfile columns (GSIM "required" attributes) are added
   in OpenQuake

Therefore, it might be probably safer to store all eGSIM data in the database, using a single storage
point, exploit Django migration features (e.g., make the addition of new
columns easier). Note however that storing a flatfile in the database has some caveats:

1. Implement array types for IMT components (or better, orientations. See e.g.
   https://ds.iris.edu/ds/nodes/dmc/data/formats/seed-channel-naming/).
   Currently, we have IMT which can be stored
   with components or as scalars. A database should store all IMT as 3x1
   float arrays, the frist two elements being the horizontal components. For scalars,
   only the first element shoiuld be given (the other two being Null or NaN). For SA,
   the float arrays would be 3xN, where N is the number of periods, and the periods
   should be stored probably in a separate table 'sa_periods' to avoid redundant data)

2. Implement the selection expression. Currently, HDF are stored using the pytables
   package, which allows selection expressions such as '(PGA != nan) & ... ()".
   A database storage has not natively such a feature unless we implement it.
   Note that this would not be hard to implement - at last in a very naive way -
   currently we already parse the selection expression to cast some types
   so some work is already in place (see package `smtk` package)

If we go for this solution in the future, we could implement in the command `initdb`
all operations needed to have the required eGSIM input data (SAHRE, ESM + other tectonic regionalisations + other flatfiles).
The idea would be to keep a 'input_data' directory (maybe separated from the
project if too big) and then for any new data in 'input_data' directory, add code
to the 'initdb' command to populate the db, and eventually on the server pull the
new 'input_data' and re-execute 'initdb' on the server.

Final note: the user-defined flatfile should not be considered here, as it turned out to be
more easily menageable by simply reading a CSV via `pandas.read_csv`, which is
extremely fast (providing a limited amount of rows - maybe up to 5000, only required columns,
and no selection possible).

</details>

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

Please note before proceeding that Django projects have two fundamental
organization structures:
	
1. the Django project itself in the base
   working directory (created with the command
   `django-admin startproject egsim`)
	
2. the app(s), usually organized in sub-directories, which are used to break
   a project's functionality down into logical units (For details, see
   https://ultimatedjango.com/learn-django/lessons/understanding-apps/)

**In eGSIM we have a project (root directory) named "egsim" with a single
user-defined app (sub-directory) called also "egsim"**. Hence, the
directory structure might look redundant (but as we saw, it isn't).
Also note (see `INSTALLED_APPS` in
the settings file) that egsim is not the only used app, as we installed several
other builtin apps for our project (e.g. the "admin" app in order to visualize and
easily edit on the browser the database content).


### Starting a `python` terminal shell

Tyiping `python` on the terminal does not work if you need to import django stuff, as
there are things to be initialized beforehand. The Django `shell` command does this:

```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py shell 
```

### Check database data on the web browser

(for further admin relateed stuff information,
see https://docs.djangoproject.com/en/3.1/ref/django-admin/)

Run the program, open the browser and go to:

<details>
	<summary>Create a super user (to be done **once only**)</summary>

```bash
export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py createsuperuser
```
and follow the instructions.
</details>

Then navigate in the browser to: http://127.0.0.1:8000/admin/

### Modify database models (make migrations)

See here: https://realpython.com/django-migrations-a-primer/#changing-models
or here:
https://docs.djangoproject.com/en/2.2/topics/migrations/#workflow

In a nutshell (DJANGO_SETTINGS_MODULE below must be changed in production):

1. modify the code
2. ```export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py makemigrations egsim --name <migration_name>```
3. ```export DJANGO_SETTINGS_MODULE="egsim.settings_debug";python manage.py migrate egsim```

("egsim" above is the app name. If you omit the app, all apps will be migrated.
The command `migrate` does nothing if it detects that there is nothing to migrate)

### Fixing / Adding features to gmpe-smtk

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
upstream	https://github.com/GEMScienceTools/gmpe-smtk.git (fetch)
upstream	https://github.com/GEMScienceTools/gmpe-smtk.git (push)
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

```
pip install pylint pytest-django pytest-cov
pip freeze > requirements.dev.txt
```

(then, proceed with the normal workflow:
run tests, fix new bugs and then `git push`, an so on).
