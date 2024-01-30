import io
from typing import Union
# required external packages (pip install ...):
import requests
import pandas as pd  # https://pandas.pydata.org/docs/user_guide/dsintro.html#dataframe
# recommended external packages:
import tables  # enables reading HDF data. If not installed, use CSV (see "format" parameter below)


def get_egsim_residuals(
        model: list[str],
        imt: list[str],
        flatfile: Union[io.IOBase, str],
        query_string=None,
        likelihood=False,
        format="hdf"
) -> pd.DataFrame:
    """Retrieve the residuals for the flatfile and the selected
    set of ground motion models and intensity measure types. Examples:
    ```
        dataframe = get_residuals_from_egsim(... flatfile=<predefined_flatfile_name>...)
    ```
    or, by uploading a user-defined flatfile:
    ```
        with open(<user_defined_flatfile_path>, "rb") as ff:
            dataframe = get_residuals_from_egsim(... flatfile=ff...)
    ```

    Args:
    - flatfile: A string denoting a predefined flatfile (e.g. "esm2018"), or a
      [file object](https://docs.python.org/3/glossary.html#term-file-object),
      e.g., the object returned by the `open` function
    - model: ground motion model(s) (OpenQuake class names)
    - imt: intensity measure type(s) (e.g. "PGA", "PGV", "SA(0.1)")
    - query_string: selection query to apply to the data (e.g. "mag>6")
    - likelihood: bool (default False): compute the residuals likelihood
      according to [Scherbaum et al. (2004)](https://doi.org/10.1785/0120030147)
    - format: the requested data format. "hdf" (the default, recommended) or "csv".
      HDF is more performant and support more data types, but it requires pytables
      (`pip install tables`)

    Returns:

    a tabular structure (pandas DataFrame) where each row contains the
    input data and the computed residuals for a given flatfile record.
    The table has a multi-level column header composed of 3 rows indicating:

    | Header row | Each 'residuals' cell indicates:                                  | Each 'input data' cell indicates:                                        |
    |------------|-------------------------------------------------------------------|--------------------------------------------------------------------------|
    | 1          | the requested intensity measure, e.g. "PGA", "SA(1.0)"            | the string "input_data"                                                  |
    | 2          | the residual type (e.g. "total_residual", "intra_event_residual") | the flatfile field type (e.g. "distance", "rupture" "intensity", "site") |
    | 3          | the requested model name                                          | the flatfile field name (e.g. "mag", "rrup")                             |
    |            | data ...                                                          | data ...                                                                 |

    *Note: the table 1st column (called Index in pandas) reports the row position (starting from 0)
    in the original flatfile*
    """

    # request parameters:
    parameters = {
        'model': model,
        'imt': imt,
        'format': format,
        'likelihood': likelihood
    }
    if query_string:
        parameters['data-query'] = query_string

    # Set up the arguments to be passed to `requests.post`, which vary depending on
    # the request type (with or without uploaded file):
    if isinstance(flatfile, str):
        # preloaded flatfile:
        parameters['flatfile'] = flatfile
        args = { 'json': parameters }
    else:
        # uploaded flatfile:
        args = {'data': parameters, 'files': {'flatfile': flatfile}}

    # POST request for eGSIM. Return a response object (the server/eGSIM response)
    response = requests.post(
        "https://egsim.gfz-potsdam.de/query/residuals",  # the base request URL
        **args
    )
    # eGSIM might return response denoting an error. Treat these response as
    # Python exceptions outputting the original eGSIM message (more meaningful)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        msg = exc.response.json()['message']  # eGSIM detailed error message
        raise ValueError(f"eGSIM error: {msg} ({exc.response.url}) ") from None

    # `response.content` is the computation result, as bytes sequence in CSV or HDF
    # format. Read it into a pandas.DataFrame:
    if parameters['format'] == 'hdf':
        # `pd.read_hdf` works for HDF files on disk. Workaround:
        with pd.HDFStore(
                "data.h5",  # apparently unused for in-memory data
                mode="r",
                driver="H5FD_CORE",  # create in-memory file
                driver_core_backing_store=0,  # for safety, just in case
                driver_core_image=response.content) as store:
            dframe = store[list(store.keys())[0]]
    else:
        # use `pd.read_csv` with a BytesIO (file-like object) as input:
        dframe = pd.read_csv(io.BytesIO(response.content), header=[0, 1, 2], index_col=0)

    return dframe
