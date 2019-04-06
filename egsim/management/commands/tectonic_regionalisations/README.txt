This folder contains sub-folder representing 
Tectonic regionalisations. Each set of tectonic regionalisation
has to be associated with a model.

To implement a new model [MODEL], create a [MODEL] sub-directory
placing in it all necessary files. There is only one mandatory file:
__init__.py

where the user has to implement a `create(trts)` function which returns
instances of the TectonicRegion model implemented in models.py
The argument,. trts, is a list of Trt instances (Tectonic region types)
from the relative Trt model defined in models.py

The initdb command, when run from the terminal (python manage.py initdb)
will call the function and populate the database
