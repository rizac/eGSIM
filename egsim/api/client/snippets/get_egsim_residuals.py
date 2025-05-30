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
        ranking=False,
        likelihood=False,
        normalize=True,
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
    - normalize: bool (default True): normalize the random effects residuals 
      (Abrahamson & Youngs (1992), Eq. 10)
    - ranking: bool (default False). Return aggregate measures from the computed 
      residuals (e.g., median, loglikelihood, EDR). Useful in model ranking to easily 
      assess how predictions fit the data. When True, the parameters likelihood and 
      normalize are set to true by default
    - data_format: the requested data format. "hdf" (the default, recommended) or "csv".
      HDF is more performant and support more data types, but it requires pytables
      (`pip install tables`)

    Returns:

    A [pandas DataFrame](https://pandas.pydata.org/docs/user_guide/dsintro.html#dataframe)
    
    If ranking is True, then each row denotes a model (labelled by the unique model name)
    and each column a measure of fit.
    
    If ranking is False, then each row denotes a flatfile record, labelled by a unique
    integer id (the record position in the original flatfile, starting from 0), and
    each column denotes:
    
    - a computed residual or prediction if the first chunk of the column name is an
      intensity measure type (e.g. "PGA total_residual BindiEtAl2014Rjb"): in this case,
      the second chunk is the metric type ("total_residual") and the third the predicting
      model ("BindiEtAl2014Rjb")
    
    - a record input property (copied from the original flatfile) if the first chunk
      of the column name is the text "input"  (e.g., "input distance_measure rrup"): in
      this case, the second chunk is the flatfile data type ("distance_measure",
      "intensity_measure", "rupture_parameter", "site_parameter" or "uncategorized") and
      the third the data name ("rrup")
    """
    # request parameters:
    parameters = {
        'model': model,
        'imt': imt,
        'format': data_format,
        'ranking': ranking,
        'likelihood': likelihood,  # ignored if ranking is True
        'normalize': normalize,  # ignored (set to true) if ranking is True
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

    # check HTTPErrors (status_code >= 400):
    if response.status_code >= 400 and response.text:
        raise requests.exceptions.HTTPError(response.text)
    else:
        response.raise_for_status()  # raises if status >= 400 (with a default message)

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
