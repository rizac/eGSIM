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

The web portal (and API documentation) is available at:

# https://egsim.gfz.de

## Citation

### Software

> Zaccarelli, Riccardo; Weatherill, Graeme (2020): eGSIM - a Python library and web application to select and test Ground Motion models. GFZ Data Services. https://doi.org/10.5880/GFZ.2.6.2023.007

### Research paper

> Riccardo Zaccarelli, Graeme Weatherill, Dino Bindi, Fabrice Cotton; Ground‐Motion Models at Your Fingertips: Easy, Rapid, and Flexible Analysis with eGSIM. Seismological Research Letters 2026; doi: https://doi.org/10.1785/0220250228

## Installation

**DISCLAIMER** Because the web application is already installed and managed on a 
server (https://egsim.gfz.de), this README focuses **exclusively on the Python library 
called strong motion modeler toolkit (`smtk`)**.

If you need access to, or information about, the web application 
installation, please contact the project authors.

<!--
## Clone repository

Select a `root directory` (e.g. `/root/path/to/egsim`), and clone egsim into the
so-called egsim directory:

```bash
git clone https://github.com/rizac/eGSIM.git egsim
```
-->

### Create and activate Python virtual env

Move to whatever directory you want (usually the egsim directory above) and then:

```bash
python3 -m venv .venv/egsim  # replace .venv/egsim with your preferred path
```

Activate virtualenv:
```bash
source .venv/egsim/bin/activate  # activate venv
```

Deactivate virtualeanv:

```
deactivate
```

### Install

**IMPORTANT: From now on, all following operations must have the virtualenv 
activated FIRST**


Choose your requirements file and then run installation 
(`-e` is optional. If you do not know what it is, simply remove it)

- Old macOS (before 2023. Check by typing `uname -m` on terminal, 
  you should **not** get `arm64`):
  
  `pip install -r requirements-py311-macos_x86_64.txt && pip install [-e] .`

- New macOS (`uname -m` on terminal gives `arm64`)
  
  `pip install -r requirements-py311-macos_arm64.txt && pip install [-e] .`

- Linux (To be done)


```zsh
# activate virtualenv first!
pip install -r ./requirements-py311-macos_arm64.txt  # remember: you might need to change the file name
pip install .
```

From now on, you can use eGSIM 
strong motion toolkit package (`from egsim.smtk import ...`)
in your code

### Run tests (optional) 

(remember to `pip install pytest` first)
```bash
pytest -vvv ./tests/smtk
```

<!-- END OF FIXED TEXT -->
