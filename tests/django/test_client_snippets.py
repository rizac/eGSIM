from os.path import dirname, abspath, join, isdir, isfile
import pandas as pd
from requests import HTTPError
import pytest

from egsim.smtk.registry import Clabel
from egsim.api.data.client.snippets.get_egsim_predictions import get_egsim_predictions
from egsim.api.data.client.snippets.get_egsim_residuals import get_egsim_residuals
from egsim.api.urls import PREDICTIONS_URL_PATH, RESIDUALS_URL_PATH

test_data_dir = join(dirname(dirname(abspath(__file__))), 'data')

assert isdir(test_data_dir)

# these must be equal to the values provided in tests.smtk.test_create_data:
models = ['CauzziEtAl2014', 'BindiEtAl2014Rjb']
imts = ['PGA', 'SA(0.032)', 'SA(0.034)']


def test_client_get_residuals(live_server):
    ffile_path = abspath(join(test_data_dir,
                         'test_flatfile.csv'))
    with open(ffile_path) as fpt:
        dfr = get_egsim_residuals(
            models, imts, fpt, likelihood=False,
            base_url=f"{live_server.url}/{RESIDUALS_URL_PATH}"
        )
    file = join(test_data_dir, 'residuals.hdf')
    if isfile(file):
        dfr2:pd.DataFrame = pd.read_hdf(file) # noqa
        # legacy code: series now returns flatten header, so reformat input
        if isinstance(dfr2.columns, pd.MultiIndex):
            dfr2.columns = [Clabel.sep.join(c) for c in dfr2.columns]  # noqa
        # dfr2 has only required columns for performance reasons,
        # so check those are the same:
        dfr = dfr[[c for c in dfr.columns if c in dfr2.columns]]
        # now test equality:
        pd.testing.assert_frame_equal(
            dfr, dfr2, check_exact=False, atol=0, rtol=1e-8
        )


def test_client_get_predictions(live_server):
    dfr = get_egsim_predictions(
        models, imts, [4, 5], [1, 10, 100],
        base_url=f"{live_server.url}/{PREDICTIONS_URL_PATH}"
    )
    file = join(test_data_dir, 'predictions.hdf')
    if isfile(file):
        dfr2 = pd.read_hdf(file)
        # legacy code: series now returns flatten header, so reformat input
        if isinstance(dfr2.columns, pd.MultiIndex):
            dfr2.columns = [Clabel.sep.join(c) for c in dfr2.columns]  # noqa
        pd.testing.assert_frame_equal(
            dfr, dfr2, check_exact=False, atol=0, rtol=1e-3
        )


def test_predictions_400(live_server):
    with pytest.raises(HTTPError) as exc:
        dfr = get_egsim_predictions(
            ['asd'], imts, [4, 5], [1, 10, 100],
            base_url=f"{live_server.url}/{PREDICTIONS_URL_PATH}"
        )
    assert "model:" in str(exc.value)


def test_residuals_400(live_server):
    with pytest.raises(HTTPError) as exc:
        ffile_path = abspath(join(test_data_dir,
                             'test_flatfile.csv'))
        with open(ffile_path) as fpt:
            dfr = get_egsim_residuals(
                models, ['x'], fpt, likelihood=False,
                base_url=f"{live_server.url}/{RESIDUALS_URL_PATH}"
            )
    assert "imt:" in str(exc.value)


def test_not_found(live_server):
    with pytest.raises(HTTPError) as exc:
        dfr = get_egsim_predictions(
            ['asd'], imts, [4, 5], [1, 10, 100],
            base_url=f"{live_server.url}/{PREDICTIONS_URL_PATH}x"
        )
    assert "404" in str(exc.value)
