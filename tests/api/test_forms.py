"""
Tests form validations and errors

Created on 2 Jun 2018

@author: riccardo
"""
from datetime import datetime

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openquake.hazardlib import imt

from egsim.api.forms import (GsimImtForm, GsimFromRegionForm)
from egsim.api.forms.flatfile import FlatfileForm
from egsim.api.forms.flatfile.compilation import FlatfileInspectionForm
from egsim.api.forms.trellis import TrellisForm

GSIM, IMT = 'gsim', 'imt'


@pytest.mark.django_db
class Test:

    def test_gsimimt_form_invalid(self, areequal):  # areequal: fixture in conftest.py
        """tests the gsimimt form invalid case. The form is the base class for all
        forms using imt and gsim as input"""
        # test by providing the 'model' parameter (not gsim, still valid byt 'hidden',
        # see below)
        form = GsimImtForm({'model': ['BindiEtAl2011t', 'BindiEtAl2014RJb'],
                            'imt': ['PGA']})
        # Note: both models are invalid, as the latter has the last J capitalized
        # We could provide ignore case fields but we need to think about it
        # (only for model(s)?)
        assert not form.is_valid()
        err = form.errors_json_data()
        expected_err = {
            'message': 'Invalid request. Problems found in: model',
            'errors': [
                {
                    'location': 'model',
                    'message': 'Value not found or misspelled: BindiEtAl2011t, '
                               'BindiEtAl2014RJb',
                    'reason': 'invalid_choice'
                }
            ]
        }
        assert areequal(err, expected_err)

        form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        err = form.errors_json_data()
        expected_err = {
            'message': 'Invalid request. Problems found in: imt',
            'errors': [
                {
                    'location': 'imt',
                    'message': 'This parameter is required',
                    'reason': 'required'
                }
            ]
        }
        assert areequal(err, expected_err)

        form = GsimImtForm({GSIM: ['abcde', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        err = form.errors_json_data()
        expected_err = {
            'message': 'Invalid request. Problems found in: gsim, imt',
            'errors': [
                {
                    'location': 'gsim',
                    'message': 'Value not found or misspelled: abcde',
                    'reason': 'invalid_choice'
                },
                {
                    'location': 'imt',
                    'message': 'This parameter is required',
                    'reason': 'required'
                }
            ]
        }
        assert areequal(err, expected_err)

        form = GsimImtForm({IMT: ['abcde', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        err = form.errors_json_data()
        expected_err = {
            'message': 'Invalid request. Problems found in: imt, model',
            'errors': [
                {
                    'location': 'model',
                    'message': 'This parameter is required',
                    'reason': 'required'
                },
                {
                    'location': 'imt',
                    'message': "Value not found or misspelled: abcde, BindiEtAl2014Rjb",
                    'reason': 'invalid_choice'
                }
            ]
        }
        # fix the case of inverted params:
        expected_err2 = dict(expected_err, message='Invalid parameters: imt, model')
        assert areequal(err, expected_err) or areequal(err, expected_err2)

        form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['SA', '0.t', 'MMI']})
        assert not form.is_valid()
        err = form.errors_json_data()
        expected_err = {
            'message': 'Invalid request. Problems found in: imt',
            'errors': [
                # {
                #     'location': 'imt',
                #     'message': 'Value not found or misspelled: MMI',
                #     'reason': 'invalid_choice'
                # },
                {
                    'location': 'imt',
                    'message': 'Value not found or misspelled: SA, 0.t',
                    'reason': 'invalid_choice'
                }
            ]
        }
        assert areequal(err, expected_err)

        form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['MMI', '_T_']})
        assert not form.is_valid()
        err = form.errors_json_data()
        expected_err = {
            'message': 'Invalid request. Problems found in: imt',
            'errors': [
                {
                    'location': 'imt',
                    'message': 'Value not found or misspelled: _T_',
                    'reason': 'invalid_choice'
                }
            ]
        }
        assert areequal(err, expected_err)

    def test_flatifle_form(self, areequal):
        # with pytest.raises(ValidationError) as verr:
        csv = SimpleUploadedFile("file.csv", b"a,b,c,d", content_type="text/csv")
        form = FlatfileForm({'flatfile': 'esm2018'}, {'flatfile': csv})
        assert not form.is_valid()
        err = form.errors_json_data()
        expected_err = {
            'message': 'Invalid request. Problems found in: flatfile',
            'errors': [
                {
                    'location': 'flatfile',
                    'message': 'Please either select a flatfile, or upload one',
                    'reason': 'conflict'}
            ]
        }
        assert areequal(err, expected_err)
        # assert verr.value.message == 'Please either select a flatfile, or upload one'

    def test_provide_unknown_params(self):
        """Test that unknown and conflicting parameters"""

        form = GsimImtForm({
            'unknown_param': 5,
            GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
            IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']
        })
        assert not form.is_valid()
        verr = form.errors_json_data()
        assert 'unknown_param' in verr['message']

        # test another unknown parameter, but this time provide a name of an existing
        # Form Field ('plot_type'):
        data = {
            GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
            IMT: ['PGA'],
            'mag': '9', 'distance': '0', 'aspect': '1', 'dip': '60', 'plot_type': 'm'
        }
        form = TrellisForm(data)
        assert not form.is_valid()
        verr = form.errors_json_data()
        assert 'plot_type' in verr['message']

        form = GsimImtForm({
            'model': ['BindiEtAl2011'],
            'gmm': ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
            IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']
        })
        assert not form.is_valid()
        verr = form.errors_json_data()
        assert 'model' in verr['message'] and 'gmm' in verr['message']

        # assert verr.value.message == 'Conflicting parameters: model, gmm'

    @pytest.mark.parametrize('data',
                             [({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                                IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']}),
                              ({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                                IMT: ['0.1', '0.2', 'PGA', 'PGV']}),
                              # Do not support anymore wilcards in models:
                              # ({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                              #   IMT: ['0.1', '0.2', 'PG[AV]']})
                              ])
    def test_gsimimt_form_valid(self, data,
                                areequal):  # areequal: fixture in conftest.py
        form = GsimImtForm(data)
        assert form.is_valid()
        dic = form.cleaned_data
        # This does not work:
        # assert dic == data
        # because we processed the imts
        assert areequal(list(dic['gsim']), data['gsim'])
        imts = dic['imt']
        assert 'PGA' in imts
        assert 'PGV' in imts
        # to test SA's it's complicated, they should be 'SA(0.1)', 'SA(0.2)'
        # IN PRINCIPLE but due to rounding errors they might be slighlty different.
        # So do not test for string equality but create imts and test for
        # 'period' equality:
        imts = sorted([imt.from_string(i) for i in imts if i not in
                       ('PGA', 'PGV')], key=lambda imt: imt.period)
        assert imts[0].period == 0.1
        assert imts[1].period == 0.2

    def test_imt_invalid(self, areequal):
        data = {
            GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
            IMT: ['SA(r)', 'SA(0.2)', 'PGA', 'PGV']
        }
        form = GsimImtForm(data)
        assert not form.is_valid()
        err_json = form.errors_json_data()
        expected_json = {
            'message': 'Invalid request. Problems found in: imt',
            'errors': [
                {
                    'location': 'imt',
                    'message': 'Value not found or misspelled: SA(r)',
                    'reason': 'invalid_choice'
                }
            ]
        }
        assert areequal(err_json, expected_json)

    @pytest.mark.skip('MMI is implemented in egsim3.0')
    def test_gsim_not_available(self, areequal):
        data = {
            'gmm': ['AllenEtAl2012'],  # defined for MMI (not an available IMT in egsim2.0)
            IMT: ['SA(0.1)', 'SA(0.2)', 'PG*']
        }
        form = GsimImtForm(data)
        assert not form.is_valid()
        expected_err = {
            'message': 'Invalid request. Problems found in: gmm',
            'errors': [
                {
                    'location': 'gmm',
                    'message': 'Value not found or misspelled: AllenEtAl2012',
                    'reason': 'invalid_choice'
                }
            ]
        }
        assert areequal(form.errors_json_data(), expected_err)

    def test_gsimimt_form_notdefinedfor_skip_invalid_periods(self, areequal):
        """tests that mismatching gsim <-> imt has the priority over bad
        SA periods"""
        data = {
            GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],  # not defined for PGD
            IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV', 'PGD']
        }
        form = GsimImtForm(data)
        assert not form.is_valid()
        expected_err = {
            'message': 'Invalid request. Problems found in: gsim, imt',
            'errors': [
                {
                    'location': 'gsim',
                    'message': '2 model(s) not defined for all supplied imt(s)',
                    'reason': 'invalid_model_imt_combination'
                },
                {
                    'location': 'imt',
                    'message': '1 imt(s) not defined for all supplied model(s)',
                    'reason': 'invalid_model_imt_combination'
                }
            ]
        }
        assert areequal(form.errors_json_data(), expected_err)

    def test_arrayfields_all_valid_input_types(self):
        """Tests some valid inputs in the egsim Fields accepting array of values
        (MultipleChoiceWildcardField and NArrayField) using the trellis form
        because it's the most heterogeneous. What we want to check is:
        1. a MultipleChoiceWildcardField can be input as string S and will be
            returned as the 1-element list [S] (param GSIM)
        2. NArrayField can be input as string with space- or comma-separated
            string chunks (or matlab range notation), but also:
            2a. As python number (param magnitude)
            2b. As string parsable to float (param distance)
            2c. As list of any of the above types (param vs30)
        3. A MultipleChoiceWildcardField expands wildcards not only if
            the input is a string, but also, if the input is a list of strings,
            for all list sub-elements (param imt)
        """
        data = {
            'model': 'BindiEtAl2011',
            IMT: ['PGA', 'PGV'],  # ['SA(0.1)', 'PGA', 'PGV'],
            'mag': 0.5,
            'dist': '0.1',
            'dip': 60,
            'vs30': 60,
            # 'plot': 'm',
            'aspect': 1
        }
        form = TrellisForm(data)
        assert form.is_valid()
        assert list(form.cleaned_data[GSIM]) == ['BindiEtAl2011']  # testing 1)
        assert form.cleaned_data['magnitude'] == [0.5]  # testing 2a)
        assert form.cleaned_data['distance'] == [0.1]  # testing 2b)
        assert form.cleaned_data['vs30'] == 60  # testing 2c)
        assert sorted(form.cleaned_data['imt']) == ['PGA', 'PGV']  # testing 3)

    def test_trellisform_invalid(self, areequal):
        """Tests trellis form invalid"""
        data = {GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                IMT: ['SA', 'PGA', 'PGV'],
                'mag': 'a'}

        form = TrellisForm(data)
        assert not form.is_valid()
        expected_json = {
            'message': 'Invalid request. Problems found in: aspect, dip, '
                       'distance, imt, mag',
            'errors': [
                {
                    'location': 'imt',
                    'message': 'Value not found or misspelled: SA',
                    'reason': 'invalid_choice'
                },
                # {
                #     'location': 'plot',
                #     'message': 'This parameter is required',
                #     'reason': 'required'
                # },
                {
                    'location': 'mag',
                    'message': "Invalid value(s): a",
                    'reason': 'invalid'
                },
                {
                    'location': 'distance',
                    'message': 'This parameter is required',
                    'reason': 'required'
                },
                {
                    'location': 'aspect',
                    'message': 'This parameter is required',
                    'reason': 'required'
                },
                {
                    'location': 'dip',
                    'message': 'This parameter is required',
                    'reason': 'required'
                }
            ]
        }
        err = form.errors_json_data()
        assert areequal(err, expected_json)

    def test_flatfile_inspect(self, testdata):

        # file_content = testdata.read('esm2018.hdf.small.csv')
        # files = {'esm2019': SimpleUploadedFile('cover', file_content)}
        # # mvd = MultiValueDict({'flatfile': fp})
        # form = FlatfileInspectionForm({}, files=files)
        # is_valid = form.is_valid()
        # assert is_valid

        # now let's test some errors:
        flatfile_df = FlatfileForm.read_flatfilefrom_csv_bytes(testdata.open('tk_20230206_flatfile_geometric_mean.csv'))

        # Normal case (form valid)
        flatfile = flatfile_df[['rake', 'station_id',
                                'magnitude', 'rrup', 'vs30', 'event_id', 'PGA']].copy()
        bio = BytesIO()
        flatfile.to_csv(bio, sep=',')
        files = {'esm2019': SimpleUploadedFile('cover', bio.getvalue())}
        # mvd = MultiValueDict({'flatfile': fp})
        form = FlatfileInspectionForm({}, files=files)
        is_valid = form.is_valid()
        assert is_valid
        # data = form.response_data
        assert 'CauzziEtAl2014' in form.cleaned_data['gsim']

        # Test removing event_id (form still valid. Previously, had event_id
        # was required and the form was invalid. Now we removed the mandatory
        # property for columns because hard to maintain with inference rules):
        flatfile = flatfile_df[
            ['rake', 'magnitude', 'rrup', 'vs30', 'PGA']].copy()
        bio = BytesIO()
        flatfile.to_csv(bio, sep=',')
        files = {'esm2019': SimpleUploadedFile('cover', bio.getvalue())}
        # mvd = MultiValueDict({'flatfile': fp})
        form = FlatfileInspectionForm({}, files=files)
        is_valid = form.is_valid()
        assert is_valid

        # Test PGA lower case
        flatfile = flatfile_df[['rake', 'station_id',
                                'magnitude', 'rrup', 'vs30', 'event_id', 'PGA']].copy()
        flatfile = flatfile.rename(columns={'PGA': 'pga'})
        bio = BytesIO()
        flatfile.to_csv(bio, sep=',')
        files = {'esm2019': SimpleUploadedFile('cover', bio.getvalue())}
        # mvd = MultiValueDict({'flatfile': fp})
        form = FlatfileInspectionForm({}, files=files)
        is_valid = form.is_valid()
        assert not is_valid
        assert form.errors.as_json()

        # Test removing all IMTs
        flatfile = flatfile_df[
            ['rake', 'magnitude', 'rrup', 'vs30', 'event_id']].copy()
        bio = BytesIO()
        flatfile.to_csv(bio, sep=',')
        files = {'esm2019': SimpleUploadedFile('cover', bio.getvalue())}
        # mvd = MultiValueDict({'flatfile': fp})
        form = FlatfileInspectionForm({}, files=files)
        is_valid = form.is_valid()
        assert not is_valid

        # Test changing a column data type (magnitude becomes string):
        flatfile = flatfile_df[[c for c in flatfile_df.columns if c != 'magnitude']].copy()
        flatfile['magnitude'] = 'A'
        bio = BytesIO()
        flatfile.to_csv(bio, sep=',')
        files = {'esm2019': SimpleUploadedFile('cover', bio.getvalue())}
        # mvd = MultiValueDict({'flatfile': fp})
        form = FlatfileInspectionForm({}, files=files)
        is_valid = form.is_valid()
        assert not is_valid


    def test_get_gsim_from_region(self, areequal):
        form = GsimFromRegionForm({'lat': 50, 'lon': 7})
        assert form.is_valid()
        models = form.get_region_selected_model_names()
        assert len(models) == 12

def test_get_flatfile_columns():
    import pandas as pd
    d = pd.DataFrame({
        'a': ['', None],
        'b': [datetime.utcnow(), None],
        'e': [1, 0],
        'f': [1.1, None],
    })
    for c in d.columns:
        d[c+'_categ'] = d[c].astype('category')

    res = FlatfileForm.get_flatfile_dtypes(d)
