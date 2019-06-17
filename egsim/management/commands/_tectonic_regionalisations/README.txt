This directory contains sub-directories each representing 
a Tectonic regionalisation (TR) for gsim selection.
To implement a new TR with name $MODEL, create a $model directory
($model is usually equal to $MODEL but it needs not to: e.g., when
$MODEL contains invalid Python characters) and put in the directory all needed
data and an __init__.py module. In the module, create a function:
```
def create(trts)
```
which must return a list of `egsim.models.TectonicRegion` objects.
The argument, trts, is a list of Tectonic region type objects
(`egsim.models.Trt`) currently saved on the database

Once done, register the function to be called in the TECREG_FUNCTIONS global
dict of `initdb.py` :
```
from ._tectonic_regionalisations import share, $model
TECREG_FUNCTIONS = {
	'SHARE': SHARE.create
	# YOUR NEW MAPPING HERE:
	$MODEL: $model.create
}
```
The initdb command, when run from the terminal (python manage.py initdb)
will call the function and populate the database

Final note: this document's folder needs to start with an underscore to let
Django recognize it as non-command inside 'management/commands'
(https://docs.djangoproject.com/en/2.1/howto/custom-management-commands/)
