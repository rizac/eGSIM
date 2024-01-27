Retrieve the predictions for the selected set of ground motion models
    and intensity measure types. Each prediction will be the result of a given model,
    imt, and scenario, which is a configurable set of Rupture parameters and
    Site parameters.

Args: 
- model: ground motion model(s) (OpenQuake class names)
- imt: intensity measure type(s) (e.g. PGA, PGV, SA(0.1) etc.)
- magnitudes: list of magnitudes configuring each Rupture
- distances: list of distances configuring each Site
- rupture_params: dict of shared Rupture parameters (magnitude excluded)
- site_params: dict of shared Site parameters (distance excluded)
- format: the requested data format. "hdf" (the default) or "csv". The latter is
  less performant but does not require external software and libraries

Returns:

a pandas DataFrame where each row represents a given
scenario (i.e., a configured Rupture and Site) and the columns represent the
scenario input data and the relative computed ground motion predictions:

| Predictions | Input-data |
|-------------|------------|
| data ...    | data ...   |

The table has a multi-level column header composed of 3 rows indicating:

| Header row | Predictions / Each cell indicates:                     | Input-data / Each cell indicates:                                    |
|------------|--------------------------------------------------------|----------------------------------------------------------------------|
| 1          | the requested intensity measure, e.g. "PGA", "SA(1.0)" | the string "input-data"                                              |
| 2          | the metric type (e.g. "median", "stddev")              | the input data type (e.g. "distance", "rupture" "intensity", "site") |
| 3          | the requested model name                               | the input data name (e.g. "mag", "rrup")                             |
|            | data ...                                               | data ...                                                             |
