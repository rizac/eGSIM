"""
tests that execution of prediction and residuals is consistent with pre-executed
output. Useful after an OpenQuake upgrade

IMPORTANT NOTE. These tests rely on older dataframes saved on disk - in case of
OpenQuake upgrade, you might need to regenerate them. Ij case of eGSIM upgrade
(e.g., column naming change) you might need to open them, rename the columns and
save them again
"""

from os.path import dirname, abspath, join, isdir, isfile
import pandas as pd
from egsim.smtk import get_ground_motion_from_scenarios, get_residuals, read_flatfile
from egsim.smtk.flatfile import ColumnType
from egsim.smtk.registry import Clabel

test_data_dir = join(dirname(dirname(abspath(__file__))), 'data')

assert isdir(test_data_dir)

models = ['CauzziEtAl2014', 'BindiEtAl2014Rjb']
imts = ['PGA', 'SA(0.032)', 'SA(0.034)']


def test_create_predictions_is_consistent_with_preexecuted_output():
    """
    test that executions of predictions is consistent by comparing it with pre-executed
    output of the same test. Useful after an OpenQuake upgrade
    """
    dfr = get_ground_motion_from_scenarios(models, imts, [4, 5], [1, 10, 100])
    file = join(test_data_dir, 'predictions.hdf')
    dfr2: pd.DataFrame = pd.read_hdf(file)  # noqa
    # we have all columns that were present in legacy code:
    assert not set(dfr2.columns) - set(dfr.columns)
    # code modifications of sept 2025 add more metadata columns. Check this:
    assert all(
        c.startswith(f'{Clabel.input} ') for c in dfr.columns if c not in dfr2.columns
    )
    pd.testing.assert_frame_equal(dfr[dfr2.columns], dfr2, rtol=1e-4, atol=0)


def test_create_residuals_is_consistent_with_preexecuted_output():
    """
    test that executions of residuals is consistent by comparing it with pre-executed
    output of the same test. Useful after an OpenQuake upgrade
    """
    ffile = read_flatfile(join(test_data_dir,
                          'test_flatfile.csv'))
    # take only the relevant columns, otherwise the file is too big:
    columnz = {'event_id', 'rjb', 'rrup', 'rake', 'magnitude', 'vs30',
               'SA(0.032)', 'SA(0.035)', 'PGA'}
    ffile = ffile[[c for c in ffile.columns if c in columnz]]

    dfr = get_residuals(models, imts, ffile, likelihood=False)
    file = join(test_data_dir, 'residuals.hdf')
    dfr2 = pd.read_hdf(file)
    # HERE YOU MIGHT WANT TO RELAX SOME CONDITIONS (see assert_frame_equal options):
    pd.testing.assert_frame_equal(dfr, dfr2)  # noqa
    # Some outdated checks when we had multi-level columns. First restore multi-level:
    dfr.columns = pd.MultiIndex.from_tuples(c.split(Clabel.sep) for c in dfr.columns)
    # now run tests:
    assert not dfr.loc[:, ('SA(0.032)', slice(None), slice(None))].empty
    assert not dfr.loc[:, ('SA(0.034)', slice(None), slice(None))].empty
    assert not dfr.loc[:, ('PGA', slice(None), slice(None))].empty
    assert not dfr.loc[:, (Clabel.input, ColumnType.intensity.value,
                           'PGA')].empty
    assert not dfr.loc[:, (Clabel.input, ColumnType.intensity.value,
                           'SA(0.034)')].empty
    assert not dfr.loc[:, (Clabel.input, ColumnType.intensity.value,
                           'PGA')].empty
