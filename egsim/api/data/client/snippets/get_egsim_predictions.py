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
    
    Each row denotes a scenario (i.e., a combination of a given Rupture and Site)
    labelled by a unique integer id, incremental and starting from 0 (*), and each column
    denotes:

    - a computed prediction if the first chunk of the column name is an intensity
      measure type (e.g. "PGA median BindiEtAl2014Rjb"): in this case, the second chunk
      is the metric type (e.g. "median") and the third the predicting model
      ("BindiEtAl2014Rjb")
    
    - a scenario input property if the first chunk of the column name is the text "input"
      (e.g., "input distance_measure rrup"): in this case, the second
      chunk is the configuration data type ("distance_measure", "intensity_measure",
      "rupture_parameter", "site_parameter" or "uncategorized") and the third is the
      configuration data name ("rrup")
    """
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
