from os.path import dirname, abspath, join, isdir, isfile
import numpy as np
import pandas as pd
from requests import HTTPError
import pytest

from egsim.api.client.snippets.get_egsim_predictions import get_egsim_predictions
from egsim.api.client.snippets.get_egsim_residuals import get_egsim_residuals
from egsim.api.urls import PREDICTIONS_URL_PATH, RESIDUALS_URL_PATH
from egsim.smtk.registry import Clabel

test_data_dir = join(dirname(dirname(abspath(__file__))), 'data')

assert isdir(test_data_dir)

# these must be equal to the values provided in tests.smtk.test_create_data:
models = ['CauzziEtAl2014', 'BindiEtAl2014Rjb']
imts = ['PGA', 'SA(0.032)', 'SA(0.034)']
ffile_path = abspath(join(test_data_dir, 'test_flatfile.csv'))


def test_client_get_residuals(live_server):
    with open(ffile_path) as fpt:
        dfr = get_egsim_residuals(
            models, imts, fpt, likelihood=False,
            base_url=f"{live_server.url}/{RESIDUALS_URL_PATH}"
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


def test_client_get_predictions(live_server):
    dfr = get_egsim_predictions(
        models, imts, [4, 5], [1, 10, 100],
        base_url=f"{live_server.url}/{PREDICTIONS_URL_PATH}"
    )
    file = join(test_data_dir, 'predictions.hdf')
    if isfile(file):
        dfr2: pd.DataFrame = pd.read_hdf(file)  # noqa
        # new code (sept 2025) puts more metadata in dfr. so check common columns first:
        pd.testing.assert_frame_equal(
            dfr[dfr2.columns], dfr2, check_exact=False, atol=0, rtol=1e-3
        )
        # and now check that what we wrote in addition is just metadata:
        for c in dfr.columns:
            if c not in dfr2.columns:
                if isinstance(c, str):
                    assert c.startswith(f'{Clabel.input} ')
                else:
                    assert c[0] == Clabel.input


def test_client_get_predictions_nga_east(live_server):
    models = [
        "NGAEastUSGSSammons1",
        # "NGAEastUSGSSammons10",
        # "NGAEastUSGSSammons11",
        # "NGAEastUSGSSammons12",
        # "NGAEastUSGSSammons13",
        # "NGAEastUSGSSammons14",
        # "NGAEastUSGSSammons15",
        # "NGAEastUSGSSammons16",
        # "NGAEastUSGSSammons17",
        # "NGAEastUSGSSammons2",
        # "NGAEastUSGSSammons3",
        # "NGAEastUSGSSammons4",
        # "NGAEastUSGSSammons5",
        # "NGAEastUSGSSammons6",
        # "NGAEastUSGSSammons7",
        # "NGAEastUSGSSammons8",
        # "NGAEastUSGSSammons9",
        # "NGAEastUSGSSeed1CCSP",
        # "NGAEastUSGSSeed1CVSP",
        # "NGAEastUSGSSeed2CCSP",
        # "NGAEastUSGSSeed2CVSP",
        # "NGAEastUSGSSeedB_a04",
        # "NGAEastUSGSSeedB_ab14",
        # "NGAEastUSGSSeedB_ab95",
        # "NGAEastUSGSSeedB_bca10d",
        # "NGAEastUSGSSeedB_bs11",
        # "NGAEastUSGSSeedB_sgd02",
        "NGAEastUSGSSeedFrankel",
        "NGAEastUSGSSeedGraizer",
        # "NGAEastUSGSSeedGraizer16",
        # "NGAEastUSGSSeedGraizer17",
        # "NGAEastUSGSSeedHA15",
        # "NGAEastUSGSSeedPEER_EX",
        # "NGAEastUSGSSeedPEER_GP",
        # "NGAEastUSGSSeedPZCT15_M1SS",
        # "NGAEastUSGSSeedPZCT15_M2ES",
        # "NGAEastUSGSSeedSP15",
        # "NGAEastUSGSSeedYA15"
    ]
    imts = ["PGA", "SA(0.2)", "SA(1.0)", "SA(2.0)"]

    # Magnitudes between 4.0 and 7.5 spaced every 0.25 M units
    # magnitudes = ["{:.2f}".format(mag) for mag in np.arange(4.0, 7.75, 0.25)]
    magnitudes: list = np.arange(4.0, 7.75, 0.25).tolist()  # noqa
    # magnitudes = ["{:.2f}".format(mag) for mag in magnitudes]

    # Distances
    distances = [1.0, 2.0, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0, 40.0, 50.0,
                 60.0, 80.0, 100.0, 125.0, 150.0, 175.0, 200.0, 225.0, 250.0]

    # Other rupture parameters
    rupture_params = {"aspect": 1.5, "dip": 90.0, "ztor": 2.0, "rake": 0.0}
    # Other site parameters
    site_params = {"region": 0, "vs30": 760.0, "z1pt0": 25.0, "z2pt5": 1.2,
                   "vs30measured": True}

    # simple test (should not raise anymore):
    dfr = get_egsim_predictions(
        models, imts, magnitudes=magnitudes, distances=distances,
        base_url=f"{live_server.url}/{PREDICTIONS_URL_PATH}",
        rupture_params=rupture_params, site_params=site_params
    )

    with open(ffile_path) as fpt:
        dfr = get_egsim_residuals(
            models, imts, fpt, likelihood=False,
            base_url=f"{live_server.url}/{RESIDUALS_URL_PATH}"
        )

    # dfr = get_egsim_residuals(
    #     models, imts, flatfile="esm-2018", query_string='(mag > 4) & (mag < 5)',
    #     base_url=f"{live_server.url}/{RESIDUALS_URL_PATH}"
    # )

    # ffile_path = abspath(join(test_data_dir,
    #                           'test_flatfile.csv'))
    # with open(ffile_path) as fpt:
    #     dfr = get_egsim_residuals(
    #         models, imts, fpt, likelihood=False,
    #         base_url=f"{live_server.url}/{RESIDUALS_URL_PATH}"
    #     )
    # asd = 9


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
