# Added flat files

NOTES:

- Zip with macOS adds a kind of `__MACOSX` folder
  in the zip file (https://stackoverflow.com/q/10924236). 
  Pandas expects zips with only one item,
  so in order to remove that macOS specific folder
  zip **and afterwards type**:

  ```buildoutcfg
  zip -d <filename>.zip __MACOSX/\*
  ```

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