import io
from typing import Union
# required external packages (pip install ...):
import requests
import pandas as pd  # https://pandas.pydata.org/docs/user_guide/dsintro.html#dataframe
# import tables  # recommended to read HDF. Uncomment to check it's installed


def get_egsim_residuals(
        model: list[str],
        imt: list[str],
        flatfile: Union[io.IOBase, str],
        query_string=None,
        likelihood=False,
        data_format="hdf",
        base_url="https://egsim.gfz-potsdam.de/api/query/residuals"
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
    - data_format: the requested data format. "hdf" (the default, recommended) or "csv".
      HDF is more performant and support more data types, but it requires pytables
      (`pip install tables`)

    Returns:

    A [pandas DataFrame](https://pandas.pydata.org/docs/user_guide/dsintro.html#dataframe)
    where each row contains the input data and the computed residuals for a given 
    flatfile record.

    Each DataFrame column label is composed of 3 space-separated chunks, indicating:
    
    - A computed residual or prediciton, if the first chunk is an intensity measure type 
      (e.g. "PGA total_residual BindiEtAl2014Rjb"): in this case, the second chunk is 
      the metric type (e.g. "total_residual") and the third the predicting model ("BindiEtAl2014Rjb")
    
    - The flatfile data relative to the computed prediction if the first chunk is litarally 
      "input_data" (e.g. "input_data distance_measure rrup"): in this case, the second 
      chunk is the flatfile data type (e.g. "distance_measure") and the third the data name ("rrup")

    The DataFrame row labels report the row position (starting from 0) in the original flatfile
    """  # noqa
    # request parameters:
    parameters = {
        'model': model,
        'imt': imt,
        'format': data_format,
        'likelihood': likelihood
    }
    if query_string:
        parameters['data-query'] = query_string

    # Set up the arguments to be passed to `requests.post`, which vary depending on
    # the request type (with or without uploaded file):
    if isinstance(flatfile, str):
        # preloaded flatfile:
        parameters['flatfile'] = flatfile
        args = {'json': parameters}
    else:
        # uploaded flatfile:
        args = {'data': parameters, 'files': {'flatfile': flatfile}}

    # POST request to eGSIM
    response = requests.post(base_url, **args)

    # eGSIM might return response denoting an error. Treat these response as
    # Python exceptions and output the original eGSIM message
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        msg = exc.response.json()['message']  # eGSIM detailed error message
        raise ValueError(f"eGSIM error: {msg} ({exc.response.url}) ") from None

    # `response.content` is the computed data, as in-memory file (bytes sequence)
    # in CSV or HDF format. Read it into a pandas.DataFrame:
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
