This directory contains the Regionalizations input data.
A regionalization is a collection of Tectonic regions
that the command `reg2db` will save from the input data onto the eGSIM database.
A tectonic region is simply a Geographic region (polygon) with a specific
Tectonic Region Type (TRT) assigned.

To implement a new Regionalization with an assigned string identifier
"<source_id>", follow the instructions in the module `reg2db`. If the
Regionalization needs external (*not huge*) data, put that data
in a new directory named "<source_id>" here (see directory "SHARE" for
a working example).