This folder contains sub-folder representing 
Tectonic regionalisations. Each set of tectonic regionalisation
has to be associated with a model.

To implement a new model [MODEL], create a [MODEL] sub-directory, put therein
data and code, and create somewhere a function:

def func(trts)

which must returns instances of the TectonicRegion model.
The argument, trts, is a list of Trt instances (Tectonic region types).
See models.py for info.

Once done, import `func` from within `initdb` and put the function in the
global variable TECREG_FUNCTIONS

The initdb command, when run from the terminal (python manage.py initdb)
will call the function and populate the database

Remember that Django skips all stuff inside 'management/commands' if it starts
with underscore (https://docs.djangoproject.com/en/2.1/howto/custom-management-commands/)
so for safety use the underscore to anything not a command