a pandas DataFrame where each row represents a given  
record and the columns represent the flatfile input data and the relative
computed residuals:

| Residuals | Input-data |
|-----------|------------|
| data ...  | data ...   |

The table has a multi-level column header composed of 3 rows indicating:

| Header row | Residuals / Each cell indicates:                                  | Input-data / Each cell indicates:                                        |
|------------|-------------------------------------------------------------------|--------------------------------------------------------------------------|
| 1          | the requested intensity measure, e.g. "PGA", "SA(1.0)"            | the string "input-data"                                                  |
| 2          | the residual type (e.g. "total_residual", "intra_event_residual") | the flatfile field type (e.g. "distance", "rupture" "intensity", "site") |
| 3          | the requested model name                                          | the flatfile field name (e.g. "mag", "rrup")                             |
|            | data ...                                                          | data ...                                                                 |

