# Predefined flat files

*Predefined* flat files are parametric tables, usually coming from 
established research projects, that must be available to all eGSIM users.
This directory simply collects these files in their original format with
no modifications (albeit compression, if needed). As eGSIM works with
flat files stored in the efficient HDF format, in most of the cases a 
conversion to HDF is needed.

The conversion is a one-time operation performed via the Django management 
command `egsim_init` by admins, to be called from the terminal (see global 
README). Therefore, after adding a new flat file here, open the
module `egsim/management/commands/_flatfiles.py`, which is called by 
`egsim_init`, and look at the global variable 
`FLATFILES`: therein, you can add the new flat file name mapped to its 
metadata: url, description and the name of the conversion function,
which must be eventually implemented in the module
(scroll to the bottom to see the already implemented ESM conversion function). 

Usually, flat files are quite big. We suggest 
compressing them so that `git` can better handle them. 

NOTES:

To compress a file in macOS:

- Zip with macOS adds a kind of `__MACOSX` folder
  in the zip file (https://stackoverflow.com/q/10924236). 
  Pandas expects zips with only one item,
  so in order to remove that macOS specific folder
  zip **and afterwards type**:

  ```buildoutcfg
  zip -d <filename>.zip __MACOSX/\*
  ```
  
  OR ZIP like this (-9 is optional is the compression level):

  ```buildoutcfg
  zip ZIPFILE_PATH  CSV_FILEPATH -9 -x ".*" -x "__MACOSX"
  ```

# Added flatfiles

## ESM 2018 flatfile

- Go to https://esm.mi.ingv.it//flatfile-2018/flatfile.php
(with username and password, you must be registered 
  beforehand it's relatively fast and simple)

- Download `ESM_flatfile_2018.zip`, uncompress and extract
  `ESM_flatfile_SA.csv` from there 
  
- `ESM_flatfile_SA.csv` is our raw flatfile, compress it 
  again (it's big) into this directory as 
  `ESM_flatfile_2018_SA.zip`
 
- If on macOS, type the command above to remove the
  macOS folder from the zip