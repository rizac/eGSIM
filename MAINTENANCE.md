# eGSIM - Maintenance & Operations (web app)

## Run tests (smtk lib only)
```bash
pytest -vvv ./tests/smtk
```

## Run tests (web app)

> Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below 
> must be changed in production

Move in the `egsim directory` and type:

```bash
export DJANGO_SETTINGS_MODULE=egsim.settings.test; pytest -xvvv ./tests/
```
(x=stop at first error, v*=increase verbosity). 

with coverage report:

```bash
export DJANGO_SETTINGS_MODULE=egsim.settings.test; pytest --cov=egsim --cov-report=html -xvvv ./tests/
```

<details>
<summary>Configure PyCharm</summary>
For PyCharm developers, you need to configure the environment variable
for all tests. Go to:

- Run
  - Edit Configurations Templates ...
    - Python tests
      - pytest
    
And then under **Environment variables:** add:

`DJANGO_SETTINGS_MODULE=egsim.settings.test`

(type several env vars separated by ;)

</details>

## Test GUI in local browser

> Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below 
> must be changed in production

> Note: the DB should have been created beforehand (see dedicated section below)

Type:

```bash
export DJANGO_SETTINGS_MODULE="egsim.settings.dev";python manage.py runserver 
```

<details>
<summary>Configure PyCharm</summary>
For PyCharm developers, you can implement a service, which can be run as any
PyCharm configuration in debug mode, allowing to open the browser 
and stop at specific point in the code (the PyCharm window will popup 
automatically in case). To implement a service, go to:

- Run
  - Edit Configurations
    - Add new configuration

then under **Run**:
 - between `script` and `module` (should be a combo box) choose `script`,
   and in the next text field put `manage.py`
 - script parameters: `runserver`
 - And then under **Environment variables:** add:
   `DJANGO_SETTINGS_MODULE=egsim.settings.dev`
   (type several env vars separated by ;)

You should see in the `Services` tab appearing the script name, so you can
run / debug it normally

</details>


## Packages upgrade

**WHEN:** OpenQuake upgrade (e.g., new models to be made available)

Set variables (change it in your case!!):
```
export PY_VERSION="3.11.14"; export OQ_VERSION="3.24.1";
```

Create a new virtual env, decide which Python version you want 
to use for the server, and install it if needed.

```
python -m venv .venv .venv/py${PY_VERSION}-oq${OQ_VERSION}
source .venv/py${PY_VERSION}-oq${OQ_VERSION}/bin/activate
```

Clone a specific openquake version, usually on the same level of eGSIM:
```
(cd .. && git clone --branch v${OQ_VERSION} https://github.com/gem/oq-engine.git ./oq-engine${OQ_VERSION})
```

Look at the openquake directory and search your installation file ${REQUIREMENTS_FILE}. E.g.:
```
export REQUIREMENTS_FILE=../oq-engine${OQ_VERSION}/requirements-py311-linux64.txt
```
```
pip install --upgrade pip && pip install -r "$REQUIREMENTS_FILE" && pip install openquake.engine==${OQ_VERSION} && pip freeze > "$(basename "$REQUIREMENTS_FILE")"
```

Go to eGSIM setup.py and set:
`__VERSION_=${OQ_VERSION}` (e.g., `__VERSION__="3.24.1"`. We keep eGSIM version 
in synchro with OpenQuake):
```
pip install -U -e . && pip freeze > "$(basename "$REQUIREMENTS_FILE")"
```
Open requirements file and **remove** egsim line.

Run tests (smtk only):
```
pip install -U pytest
```
```
pytest -xvvv ./tests/smtk
```
Fix if needed

Install web app (force upgrade :
```
pip install -U --ignore-installed django && pip install -U -e ".[web]"
```

(you might still see old django version in requirements file. To check Django version, run:)
`python -c 'import django;print(django.__version__)'`
Run tests:
```
export DJANGO_SETTINGS_MODULE="egsim.settings.test" && pytest -xvvv ./tests/django
```
Fix code as needed, commit push and so on



## New data

**WHEN:** New selectable flatfile or regionalization to be added 
to the platform.

- Consult `README.md` in the `egsim-data` Nextcloud directory 

- Copy the newly created file(s) and the `media_files.yml` file in the project
  media directory (`MEDIA_ROOT` in the used Django settings file)


## Django Database (sqlite DB)

> Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below 
> must be changed in production

**WHEN**: 

 - **The DB needs to be emptied and repopulated**  
   (e.g., OpenQuake is upgraded, or new regionalization or 
   flatfile was added)
 
 - **The DB schema (columns, tables, constraints) 
   has changed** (see `egsim.api.models.py`)

To do so:

- Delete or rename the database of the settings file

  (path is in the settings file variable `DATABASES['default']['NAME']`)

- **If the DB Schema HAS CHANGED** (otherwise skip):
  
  - Delete the (only) migration file

    (should be `egsim/api/migrations/0001_initial.py`, if more than
    one migration file in the directory, delete all of them)

  - Recreate migration file (file to autopopulate the DB):
    ```bash
    export DJANGO_SETTINGS_MODULE="egsim.settings.dev";python manage.py makemigrations && python manage.py migrate && python manage.py egsim-init
    ```

  - `git add` the newly created migration file 
     
    (should be `egsim/api/migrations/0001_initial.py`)

- Migrate (populate DB): 
  ```bash
  export DJANGO_SETTINGS_MODULE="egsim.settings.dev";python manage.py migrate && python manage.py egsim-init
  ```

> Note:
> eGSIM DB is extremely simple and rarely modified, recreating DB file all the time is cheaper than
> managing migration files

## Modify eGSIM DB data from the command line

> Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below 
> must be changed in production

**WHEN**: mostly when you want to hide a flatfile, model or 
regionalization from the program usually temporarily (more complex 
modifications are possible but do it at your own risk)

Execute the interactive command:
   ```bash
   export DJANGO_SETTINGS_MODULE="egsim.settings.dev";python manage.py egsim-db
   ```

> NOTE:
> this Django command replaces the very expensive admin panel
> (again, our DB is very simple)


## Django utilities

### Starting a Python terminal shell

> Note: the value of `DJANGO_SETTINGS_MODULE` in the examples below 
> must be changed in production

Typing `python` on the terminal does not work as one needs to
initialize Django settings. The Django `shell` command does this:

```bash
export DJANGO_SETTINGS_MODULE="egsim.settings.dev";python manage.py shell 
```

### Get Django uploaded files directory

If you did not set it explicitly in `settings.FILE_UPLOAD_TEMP_DIR` 
(by default is missing), then Django will put uploaded files 
in the standard temporary directory which you can get easily by 
typing:

```bash
python -c "import tempfile;print(tempfile.gettempdir())"
```