import io
from typing import Optional
# required external packages (pip install ...):
import requests
import pandas as pd  # https://pandas.pydata.org/docs/user_guide/dsintro.html#dataframe
# import tables  # recommended to read HDF. Uncomment to check it's installed


def get_egsim_predictions(
        model: list[str],
        imt: list[str],
        magnitudes: list[float],
        distances: list[float],
        rupture_params: Optional[dict] = None,
        site_params: Optional[dict] = None,
        data_format="hdf",
        base_url="https://egsim.gfz-potsdam.de/api/query/predictions"
) -> pd.DataFrame:
    """Retrieve the ground motion predictions for the selected set of ground motion
    models and intensity measure types. Each prediction will be the result of a given
    model, imt, and scenario, which is a configurable set of Rupture parameters and
    Site parameters.

    Args:
    - model: ground motion model(s) (OpenQuake class names)
    - imt: intensity measure type(s) (e.g. PGA, PGV, SA(0.1) etc.)
    - magnitudes: list of magnitudes configuring each Rupture
    - distances: list of distances configuring each Site
    - rupture_params: dict of shared Rupture parameters (magnitude excluded)
    - site_params: dict of shared Site parameters (distance excluded)
    - data_format: the requested data format. "hdf" (the default, recommended) or "csv".
      HDF is more performant and support more data types, but it requires pytables
      (`pip install tables`)

    Returns:

    A [pandas DataFrame](https://pandas.pydata.org/docs/user_guide/dsintro.html#dataframe)
    where each row contains the input data and
    the computed predictions for a given scenario (i.e., a combination
    of a configured Rupture and Site properties).

    The DataFrame column labels are composed of 3 hierarchical rows indicating:

    | Header row |  Each 'predictions' cell indicates:                    | Each 'input data' cell indicates:                                    |
    |------------|--------------------------------------------------------|----------------------------------------------------------------------|
    | 1          | the requested intensity measure, e.g. "PGA", "SA(1.0)" | the string "input_data"                                              |
    | 2          | the metric type (e.g. "median", "stddev")              | the input data type (e.g. "distance", "rupture" "intensity", "site") |
    | 3          | the requested model name                               | the input data name (e.g. "mag", "rrup")                             |
    |            | data ...                                               | data ...                                                             |

    The DataFrame row labels report a unique row identifier (incremental and starting from 0)
    """  # noqa
    # request parameters (concatenate with site_config and rupture_config):
    parameters = {}
    if site_params:
        parameters |= site_params
    if rupture_params:
        parameters |= rupture_params

    # add remaining parameters:
    parameters |= {
        'model': model,
        'imt': imt,
        'format': data_format,
        'mag': magnitudes,
        'dist': distances
    }

    # POST request to eGSIM
    response = requests.post(base_url, json=parameters)

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
