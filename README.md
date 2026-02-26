eGSIM is a web service and Python library for selecting and testing ground shaking intensity models (GSIM), developed by the [GFZ](https://www.gfz.de/) 
in the framework of the Thematic Core Services for Seismology of 
[EPOS](https://www.epos-eu.org/) under the umbrella of 
[EFEHR](http://www.efehr.org/en/home/)

<p align="middle">
    <a title='EFEHR' href='https://www.efehr.org'><img height='50' alt='efehr' src='https://www.efehr.org/export/system/modules/ch.ethz.sed.bootstrap.efehr2021/resources/img/logos/efehr.png'></a>
    &nbsp;
    <a title='GFZ' href='https://www.gfz.de/'><img height='50' alt='gfz' src='https://media.gfz-potsdam.de/gfz/wv/media/pic/logo/2025_GFZ-Wortbildmarke-EN-Helmholtzdunkelblau-RGB.jpg'></a>
    &nbsp;
    <a title='EPOS' href='https://www.epos-eu.org/'><img height='50' alt="eops" src='https://www.epos-eu.org/themes/epos/logo.svg'></a>
    <br>
</p>

[![License](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)
![Build](https://github.com/rizac/eGSIM/actions/workflows/pytest.yml/badge.svg)
![Build](https://github.com/rizac/eGSIM/actions/workflows/pytest-web.yml/badge.svg)

<!-- [![Coverage](https://codecov.io/gh/rizac/eGSIM/main/main/graph/badge.svg)](https://codecov.io) -->

### The web portal and API documentation is available at:

# https://egsim.gfz.de


## Citation

### Software

> Zaccarelli, Riccardo; Weatherill, Graeme (2020): eGSIM - a Python library and web application to select and test Ground Motion models. GFZ Data Services. https://doi.org/10.5880/GFZ.2.6.2023.007

### Research paper

> Riccardo Zaccarelli, Graeme Weatherill, Dino Bindi, Fabrice Cotton; Ground‐Motion Models at Your Fingertips: Easy, Rapid, and Flexible Analysis with eGSIM. Seismological Research Letters 2026; doi: https://doi.org/10.1785/0220250228

## Web Service

- Web portal: https://egsim.gfz.de
- API Documentation: https://egsim.gfz.de/api_doc
- API Usage (Python): https://github.com/rizac/egsim-client.
  - Jupyter notebook examples (Python): https://github.com/rizac/egsim-client/tree/main/notebook

## Python library

![Python](https://img.shields.io/badge/python-3.11-blue) 
![Python](https://img.shields.io/badge/python-3.12-blue)

eGSIM can also be installed and used as a Python package under specific Python versions
and OSs (see below) according to OpenQuake compatibilities.

This approach bypasses the web API and, 
while requiring a steeper learning curve to directly call core functions, 
allows local execution on the CPU with greater control over optimization.


**For usage in your code after installation, 
see the [Library functions reference](docs/LIBRARY_FUNCTIONS_REFERENCE.md)**


### Installation

#### Clone repository

Select a `root directory` and clone eGSIM into it:

```bash
git clone https://github.com/rizac/eGSIM.git
```

this will create the eGSIM directory. Move into it
(`cd eGSIM`)


### Create and activate a Python virtual environment (virtualenv)

Move to whatever directory you want (you can use the eGSIM repo directory, 
as long as you create your virtualenv inside `.env` or `.venv` directories, 
which are ignored by git), and then:

```bash
python3 -m venv .venv/egsim  # replace ".venv/egsim" with your path
```

Activate virtualenv:
```bash
source .venv/egsim/bin/activate  # replace ".venv/egsim" with your path
```

Deactivate virtualeanv:

```bash
deactivate
```

### Install eGSIM

> **IMPORTANT**: From now on, all following operations must have the virtualenv activated **FIRST**
> and assume you `cd` into eGSIM repository (If not the case, adjust paths accordingly)


#### Linux

- Python 3.11

  ```bash
  python -m pip install --upgrade pip setuptools wheel && pip install -r ./requirements/requirements-py311-linux64.txt && pip install .
  ```

- Python 3.12

  ```bash
  python -m pip install --upgrade pip setuptools wheel && pip install -r ./requirements/requirements-py312-linux64.txt && pip install .
  ```

#### MacOs

- Python 3.11
  ```bash
  python -m pip install --upgrade pip setuptools wheel && pip install -r ./requirements/requirements-py311-macos_arm64.txt && pip install .
  ```

- Python 3.12
  ```bash
  python -m pip install --upgrade pip setuptools wheel && pip install -r ./requirements/requirements-py312-macos_arm64.txt && pip install .
  ```

<details>

<summary>Older MacOs (discontinued)</summary>

- Python 3.11
  ```bash
  python -m pip install --upgrade pip setuptools wheel && pip install -r ./requirements/requirements-py311-macos_x86_64.txt && pip install .
  ```

- Python 3.12
  ```bash
  python -m pip install --upgrade pip setuptools wheel && pip install -r ./requirements/requirements-py312-macos_x86_64.txt && pip install .
  ```

</details>

#### Windows

- Python 3.11
  ```bash
  python -m pip install --upgrade pip setuptools wheel && pip install -r ./requirements/requirements-py311-win64.txt && pip install .
  ```

- Python 3.12
  ```bash
  python -m pip install --upgrade pip setuptools wheel && pip install -r ./requirements/requirements-py312-win64.txt && pip install .
  ```



### Run tests (optional) 

(remember to `pip install pytest` first)

```bash
pytest -vvv ./tests/smtk
```
