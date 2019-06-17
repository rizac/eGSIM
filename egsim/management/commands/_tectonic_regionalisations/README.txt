This folder contains sub-folder(s) representing 
Tectonic regionalisations. Each set of tectonic regionalisation (tr)
has to be associated with a key string identifying the tr, which we will call
MODEL.

To implement a new model MODEL, create a [MODEL] sub-directory, put therein
data and code, and create somewhere a function:

def create(trts)

which must return a list of `egsim.models.TectonicRegion` objects.
The argument, trts, is a list of Tectonic region type objects
(`egsim.models.Trt`) currently saved on the database

Once done, write the '[MODEL].create' function, keyed by the MODEL (or any other
string identifier) in the TECREG_FUNCTIONS global dict of `initdb.py` :
TECREG_FUNCTIONS = {
	'SHARE': SHARE.create
	# YOUR MAPPING HERE ...
}

The initdb command, when run from the terminal (python manage.py initdb)
will call the function and populate the database

Final note: this document's folder needs to start with an underscore to let Django
recognize it as non-command inside 'management/commands'
(https://docs.djangoproject.com/en/2.1/howto/custom-management-commands/)
