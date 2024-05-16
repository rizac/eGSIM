from os.path import dirname, abspath, join, isdir, isfile
import pandas as pd
# import pytest

from egsim.api.data.client.snippets.get_egsim_predictions import get_egsim_predictions
from egsim.api.data.client.snippets.get_egsim_residuals import get_egsim_residuals
from egsim.api.urls import PREDICTIONS_URL_PATH, RESIDUALS_URL_PATH

test_data_dir = join(dirname(dirname(abspath(__file__))), 'data')

assert isdir(test_data_dir)

# these must be equal to the values provided in tests.smtk.test_create_data:
models = ['CauzziEtAl2014', 'BindiEtAl2014Rjb']
imts = ['PGA', 'SA(0.032)', 'SA(0.034)']


def test_server_requests(live_server):
    create_predictions(live_server.url)
    create_residuals(live_server.url)


def create_residuals(base_url):
    ffile_path = abspath(join(test_data_dir,
                         'test_flatfile.csv'))
    with open(ffile_path) as fpt:
        dfr = get_egsim_residuals(
            models, imts, fpt, likelihood=False,
            base_url=f"{base_url}/{RESIDUALS_URL_PATH}"
        )
    file = join(test_data_dir, 'residuals.hdf')
    if isfile(file):
        dfr2:pd.DataFrame = pd.read_hdf(file) # noqa
        # dfr2 has only required columns for performance reasons,
        # so check those are the same:
        dfr = dfr[[c for c in dfr.columns if c in dfr2.columns]]
        # now test equality:
        pd.testing.assert_frame_equal(
            dfr, dfr2, check_exact=False, atol=0, rtol=1e-8
        )


def create_predictions(base_url):
    dfr = get_egsim_predictions(
        models, imts, [4, 5], [1, 10, 100],
        base_url=f"{base_url}/{PREDICTIONS_URL_PATH}"
    )
    file = join(test_data_dir, 'predictions.hdf')
    if isfile(file):
        dfr2 = pd.read_hdf(file)
        pd.testing.assert_frame_equal(
            dfr, dfr2, check_exact=False, atol=0, rtol=1e-3
        )
