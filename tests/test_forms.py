'''
Created on 2 Jun 2018

@author: riccardo
'''
import unittest
from egsim.forms import BaseForm, TrellisForm
import django


class Test(unittest.TestCase):

    GSIM, IMT = 'gsim', 'imt'

    def setUp(self):
        django.setup()
        pass


    def tearDown(self):
        pass


    def testName(self):
        pass

    def test_BaseForm(self):
        GSIM, IMT = self.GSIM, self.IMT
        form = BaseForm()
        assert not form.is_valid()
        # https://docs.djangoproject.com/en/2.0/ref/forms/api/#django.forms.Form.is_bound:
        assert not form.is_bound
        # Note (from url link above):
        #  There is no way to change data in a Form instance.
        # Once a Form instance has been created, you should consider its data immutable,
        # whether it has data or not.
        err = form.errors.as_json()
        assert err == '{}'

        form = BaseForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        err = form.errors.as_json()
        assert err == '{"imt": [{"message": "This field is required.", "code": "required"}]}'

        form = BaseForm({GSIM: ['abcde', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        err = form.errors.as_json()
        assert err == ('{"gsim": [{"message": "Select a valid choice. abcde is not one of '
                       'the available choices.", '
                       '"code": "invalid_choice"}], "imt": [{"message": "This field is required.",'
                       ' "code": "required"}]}')

        form = BaseForm({IMT: ['abcde', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        err = form.errors.as_json()
        assert err == ('{"gsim": [{"message": "This field is required.", "code": "required"}], '
                       '"imt": [{"message": "Select a valid choice. abcde is not one of the '
                       'available choices.", "code": "invalid_choice"}]}')

        form = BaseForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'], IMT: ['SA', 'MMI']})
        assert not form.is_valid()
        err = form.errors.as_json()

        data = {GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'], IMT: ['SA', 'PGA', 'PGV']}
        form = BaseForm(data)
        assert form.is_valid()
        dic = form.clean()
        assert dic == data

    def test_TrellisForm(self):
        GSIM, IMT = self.GSIM, self.IMT
        data = {GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'], IMT: ['SA', 'PGA', 'PGV']}

        form = TrellisForm(data)
        assert not form.is_valid()
        err = form.errors.as_json()
        assert err == ('{"magnitude": [{"message": "This field is required.", "code": "required"}],'
                       ' "distance": [{"message": "This field is required.", "code": "required"}],'
                       ' "dip": [{"message": "This field is required.", "code": "required"}],'
                       ' "aspect": [{"message": "This field is required.", "code": "required"}]}')

        form = TrellisForm(dict(data, magnitude='0:1:5', distance=6, dip=56, aspect='ert'))
        assert not form.is_valid()
        # form.clean()
        err = form.errors.as_json()
        assert err == '{"aspect": [{"message": "Enter a number.", "code": "invalid"}]}'

        form = TrellisForm(dict(data, magnitude='0:1:5', distance=6, dip=56, aspect=67))
        if form.is_valid():
            data = form.clean()
        err = form.errors.as_json()

        form = BaseForm({GSIM: ['abcde', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        err = form.errors.as_json()
        assert err == ('{"gsim": [{"message": "Select a valid choice. abcde is not one of '
                       'the available choices.", '
                       '"code": "invalid_choice"}], "imt": [{"message": "This field is required.",'
                       ' "code": "required"}]}')

        form = BaseForm({IMT: ['abcde', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        err = form.errors.as_json()
        assert err == ('{"gsim": [{"message": "This field is required.", "code": "required"}], '
                       '"imt": [{"message": "Select a valid choice. abcde is not one of the '
                       'available choices.", "code": "invalid_choice"}]}')

        form = BaseForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'], IMT: ['SA', 'MMI']})
        assert not form.is_valid()
        err = form.errors.as_json()

        data = {GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'], IMT: ['SA', 'PGA', 'PGV']}
        form = BaseForm(data)
        assert form.is_valid()
        dic = form.clean()
        assert dic == data


if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()