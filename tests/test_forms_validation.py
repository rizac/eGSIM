"""
Tests form validations and errors

Created on 2 Jun 2018

@author: riccardo
"""
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openquake.hazardlib import imt

from egsim.api.forms import GsimImtForm
from egsim.api.forms.model_to_data import FlatfileForm
from egsim.api.forms.model_to_model.trellis import TrellisForm


GSIM, IMT = 'gsim', 'imt'


@pytest.mark.django_db
class Test:

    def test_gsimimt_form_invalid(self, areequal):  # areequal: fixture in conftest.py
        """tests the gsimimt form invalid case. The form is the base class for all
        forms using imt and gsim as input"""

        form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        err = form.validation_errors()
        expected_err = {
            'message': 'Invalid parameter: imt',
            'errors': [
                {
                    'location': 'imt',
                    'message': 'This field is required.',
                    'reason': 'required'
                }
            ]
        }
        assert areequal(err, expected_err)

        form = GsimImtForm({GSIM: ['abcde', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        err = form.validation_errors()
        expected_err = {
            'message': 'Invalid parameters: gsim, imt',
            'errors': [
                {
                    'location': 'gsim',
                    'message': 'Select a valid choice. abcde is not one of '
                               'the available choices.',
                    'reason': 'invalid_choice'
                },
                {
                    'location': 'imt',
                    'message': 'This field is required.',
                    'reason': 'required'
                }
            ]
        }
        assert areequal(err, expected_err)

        form = GsimImtForm({IMT: ['abcde', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        err = form.validation_errors()
        expected_err = {
            'message': 'Invalid parameters: gsim, imt',
            'errors': [
                {
                    'location': 'gsim',
                    'message': 'This field is required.',
                    'reason': 'required'
                },
                {
                    'location': 'imt',
                    'message': "invalid 'abcde'",
                    'reason': ''
                }
            ]
        }
        assert areequal(err, expected_err)

        form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['SA', 'MMI']})
        assert not form.is_valid()
        err = form.validation_errors()
        expected_err = {
            'message': 'Invalid parameter: imt',
            'errors': [
                {
                    'location': 'imt',
                    'message': 'Missing period in SA',
                    'reason': ''
                }
            ]
        }
        assert areequal(err, expected_err)

        form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['MMI']})
        assert not form.is_valid()
        err = form.validation_errors()
        expected_err = {
            'message': 'Invalid parameter: imt',
            'errors': [
                {
                    'location': 'imt',
                    'message': 'Select a valid choice. MMI is not one of the '
                               'available choices.',
                    'reason': 'invalid_choice'
                }
            ]
        }
        assert areequal(err, expected_err)

    def test_flatifle_form(self):
        csv = SimpleUploadedFile("file.csv", b"a,b,c,d", content_type="text/csv")
        form = FlatfileForm({'flatfile': 'esm2018'}, {'flatfile': csv})
        form.is_valid()
        asd = 9

    def test_provide_unknown_params(self):
        """Test that unknown parameters are ignored"""
        form = GsimImtForm({
            'unknown_param': 5,
            GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
            IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']
        })
        assert form.is_valid()
        assert not form.validation_errors()

    @pytest.mark.parametrize('data',
                             [({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                                IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']}),
                              ({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                                IMT: ['0.1', '0.2', 'PGA', 'PGV']}),
                              ({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                                IMT: ['0.1', '0.2', 'PG[AV]']})
                              ])
    def test_gsimimt_form_valid(self, data,
                                areequal):  # areequal: fixture in conftest.py
        form = GsimImtForm(data)
        assert form.is_valid()
        dic = form.cleaned_data
        # This does not work:
        # assert dic == data
        # because we processed the imts
        assert areequal(dic['gsim'], data['gsim'])
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
        err_json = form.validation_errors()
        expected_json = {
            'message': 'Invalid parameter: imt',
            'errors': [
                {
                    'location': 'imt',
                    'message': "could not convert string to float: 'r'",
                    'reason': ''
                }
            ]
        }
        assert areequal(err_json, expected_json)

    def test_gsim_not_available(self, areequal):
        data = {
            GSIM: ['AllenEtAl2012'],  # defined for MMI (not an available IMT in egsim2.0)
            IMT: ['SA(0.1)', 'SA(0.2)', 'PG*']
        }
        form = GsimImtForm(data)
        assert not form.is_valid()
        expected_err = {
            'message': 'Invalid parameter: gsim',
            'errors': [
                {
                    'location': 'gsim',
                    'message': 'Select a valid choice. AllenEtAl2012 is not '
                               'one of the available choices.',
                    'reason': 'invalid_choice'
                }
            ]
        }
        assert areequal(form.validation_errors(), expected_err)

    def test_gsimimt_form_notdefinedfor_skip_invalid_periods(self, areequal):
        """tests that mismatching gsim <-> imt has the priority over bad
        SA periods"""
        data = {
            GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],  # not defined for PGD
            IMT: ['SA(0.1)', 'SA(0.2)', 'PG*']
        }
        form = GsimImtForm(data)
        assert not form.is_valid()
        expected_err = {
            'message': 'Invalid parameters: gsim, imt',
            'errors': [
                {
                    'location': 'gsim',
                    'message': '2 gsim(s) not defined for all supplied imt(s)',
                    'reason': 'invalid'
                },
                {
                    'location': 'imt',
                    'message': '1 imt(s) not defined for all supplied gsim(s)',
                    'reason': 'invalid'
                }
            ]
        }
        assert areequal(form.validation_errors(), expected_err)

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
            GSIM: 'BindiEtAl2011',
            IMT: ['PG[AV]'],  # ['SA(0.1)', 'PGA', 'PGV'],
            'magnitude': 0.5,
            'distance': '0.1',
            'dip': 60,
            'vs30': [60, '76'],
            'plot_type': 'm',
            'aspect': 1
        }
        form = TrellisForm(data)
        assert form.is_valid()
        assert form.cleaned_data[GSIM] == ['BindiEtAl2011']  # testing 1)
        assert form.cleaned_data['mag'] == 0.5  # testing 2a)
        assert form.cleaned_data['dist'] == 0.1  # testing 2b)
        assert form.cleaned_data['vs30'] == [60, 76]  # testing 2c)
        assert sorted(form.cleaned_data['imt']) == ['PGA', 'PGV']  # testing 3)

    def test_trellisform_invalid(self, areequal):
        """Tests trellis form invalid"""
        data = {GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                IMT: ['SA', 'PGA', 'PGV'],
                'magnitude': 'a'}

        form = TrellisForm(data)
        assert not form.is_valid()
        expected_json = {
            'message': 'Invalid parameters: imt, plottype, magnitude, dist, aspect, dip',
            'errors': [
                {
                    'location': 'imt',
                    'message': 'Missing period in SA',
                    'reason': ''
                },
                {
                    'location': 'plottype',
                    'message': 'This field is required.',
                    'reason': 'required'
                },
                {
                    'location': 'magnitude',
                    'message': "Unable to parse 'a'",
                    'reason': ''
                },
                {
                    'location': 'dist',
                    'message': 'This field is required.',
                    'reason': 'required'
                },
                {
                    'location': 'aspect',
                    'message': 'This field is required.',
                    'reason': 'required'
                },
                {
                    'location': 'dip',
                    'message': 'This field is required.',
                    'reason': 'required'
                }
            ]
        }
        assert areequal(form.validation_errors(), expected_json)
