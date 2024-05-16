from os.path import dirname, abspath, join, isdir, isfile
import pandas as pd
from egsim.smtk import get_scenarios_predictions, get_residuals, read_flatfile
from egsim.smtk.flatfile import ColumnType
from egsim.smtk.registry import Clabel

test_data_dir = join(dirname(dirname(abspath(__file__))), 'data')

assert isdir(test_data_dir)

models = ['CauzziEtAl2014', 'BindiEtAl2014Rjb']
imts = ['PGA', 'SA(0.032)', 'SA(0.034)']


def test_create_predictions():
    dfr = get_scenarios_predictions(models, imts, [4, 5], [1, 10, 100])
    file = join(test_data_dir, 'predictions.hdf')
    if not isfile(file):
        dfr.to_hdf(file, key='data')
    else:
        dfr2 = pd.read_hdf(file)
        pd.testing.assert_frame_equal(dfr, dfr2)


def test_create_residuals():
    ffile = read_flatfile(join(test_data_dir,
                          'test_flatfile.csv'))
    # take only the relevant columns, otherwise the file is too big:
    columnz = {'event_id', 'rjb', 'rrup', 'rake', 'magnitude', 'vs30',
               'SA(0.032)', 'SA(0.035)', 'PGA'}
    ffile = ffile[[c for c in ffile.columns if c in columnz]]

    dfr = get_residuals(models, imts, ffile, likelihood=False)
    file = join(test_data_dir, 'residuals.hdf')
    if not isfile(file):
        dfr.to_hdf(file, key='data')
    else:
        dfr2 = pd.read_hdf(file)
        pd.testing.assert_frame_equal(dfr, dfr2)
        # this raises KeyError if not found:
        assert not dfr.loc[:, ('SA(0.032)', slice(None), slice(None))].empty
        assert not dfr.loc[:, ('SA(0.034)', slice(None), slice(None))].empty
        assert not dfr.loc[:, ('PGA', slice(None), slice(None))].empty
        assert not dfr.loc[:, (Clabel.input_data, ColumnType.intensity.value, 'PGA')].empty
        assert not dfr.loc[:, (Clabel.input_data, ColumnType.intensity.value, 'SA(0.034)')].empty
        assert not dfr.loc[:, (Clabel.input_data, ColumnType.intensity.value, 'PGA')].empty
