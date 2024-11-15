"""
Tests form validations and errors

Created on 2 Jun 2018
"""
from django.forms import Field
from typing import Type
from io import BytesIO
from os.path import dirname, join, abspath

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from openquake.hazardlib import imt

from egsim.api.forms import (GsimImtForm, GsimFromRegionForm, EgsimBaseForm)
from egsim.api.forms.flatfile import FlatfileForm, FlatfileValidationForm
from egsim.api.forms.scenarios import PredictionsForm
from egsim.smtk import read_flatfile
from egsim.smtk.scenarios import RuptureProperties, SiteProperties

GSIM, IMT = 'gsim', 'imt'

flatfile_tk_path = abspath(join(dirname(dirname(__file__)), 'data',
                                'test_flatfile.csv'))

@pytest.mark.django_db
class Test:

    def test_gsimimt_form_invalid(self):
        """tests the gsimimt form invalid case. The form is the base class for all
        forms using imt and gsim as input"""
        # test by providing the 'model' parameter (not gsim, still valid byt 'hidden',
        # see below)
        form = GsimImtForm({'model': ['BindiEtAl2011t', 'BindiEtAl2014RJb'],
                            'imt': ['PGA']})
        # Note: both models are invalid, as the latter has the last J capitalized
        # We could provide ignore case fields, but we need to think about it
        # (only for model(s)?)
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == \
               'model: invalid model(s) BindiEtAl2011t, BindiEtAl2014RJb'

        form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == \
               'imt: missing parameter is required'

        form = GsimImtForm({GSIM: ['abcde', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == \
               'gsim: invalid model(s) abcde; ' \
               'imt: missing parameter is required'

        form = GsimImtForm({IMT: ['abcde', 'BindiEtAl2014Rjb']})
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == \
               'imt: invalid intensity measure(s) BindiEtAl2014Rjb, abcde; ' \
               'model: missing parameter is required'

    def test_imt_invalid(self):
        data = {
            GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
            IMT: ['SA(r)', 'SA(0.2)', 'PGA', 'PGV']
        }
        form = GsimImtForm(data)
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == \
               'imt: invalid intensity measure(s) SA(r)'

        form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['SA', '0.t', 'MMI']})
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == \
               'imt: invalid intensity measure(s) 0.t, SA'

        form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['MMI', '_T_', 'SA(r)']})
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == \
               'imt: invalid intensity measure(s) SA(r), _T_'

    def test_flatifle_form(self):
        # double flatfile provided (this should NOT be poossible from the API
        # but we test the correct message anyway):
        csv = SimpleUploadedFile("file.csv", b"a,b,c,d", content_type="text/csv")
        form = FlatfileForm({'flatfile': 'esm2018'}, {'flatfile': csv})
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == \
               'flatfile: select a flatfile by name or upload one, not both'

        # malformed uploaded flatfile:
        csv = SimpleUploadedFile("file.csv", b"", content_type="text/csv")
        form = FlatfileForm({}, {'flatfile': csv})
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == \
               'flatfile: the submitted file is empty'

        # no imt:
        csv = SimpleUploadedFile("file.csv", b"a,b,c,d", content_type="text/csv")
        form = FlatfileForm({}, {'flatfile': csv})
        assert not form.is_valid()

        # PGA provided but empty works as the cast to float succeeds:
        csv = SimpleUploadedFile("file.csv", b"PGA,b,c,d", content_type="text/csv")
        form = FlatfileForm({}, {'flatfile': csv})
        assert form.is_valid()

        # ok?:
        csv = SimpleUploadedFile("file.csv", b"PGA,b,c,d\n1.1,,,", content_type="text/csv")
        form = FlatfileForm({}, {'flatfile': csv})
        assert form.is_valid()

    def test_provide_unknown_params(self):
        """Test that unknown and conflicting parameters"""
        form = GsimImtForm({
            '_r567_': 5,
            GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
            IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']
        })
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == '_r567_: unknown parameter'

        # test another unknown parameter, but this time provide a name of an existing
        # Form Field ('plot_type'):

        data = {
            GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
            IMT: ['PGA'],
            'mag': '9', 'distance': '0', 'aspect': '1', 'dip': '60', 'plot_type': 'm'
        }
        form = PredictionsForm(data)
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == 'plot_type: unknown parameter'

        # conflicting names:
        form = GsimImtForm({
            'model': ['BindiEtAl2011'],
            'gmm': ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
            IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']
        })
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == \
               'gmm: this parameter conflicts with model; ' \
               'model: this parameter conflicts with gmm'

    @pytest.mark.parametrize('data',
                             [({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                                IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']}),
                              ({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                                IMT: ['0.1', '0.2', 'PGA', 'PGV']}),
                              # Do not support anymore wilcards in models:
                              # ({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                              #   IMT: ['0.1', '0.2', 'PG[AV]']})
                              ])
    def test_gsimimt_form_valid(self, data):
        form = GsimImtForm(data)
        assert form.is_valid()
        dic = form.cleaned_data
        assert sorted(dic['gsim']) == sorted(data['gsim'])
        imts = dic['imt']
        assert 'PGA' in imts
        assert 'PGV' in imts
        # to test SA's it's complicated, they should be 'SA(0.1)', 'SA(0.2)'
        # IN PRINCIPLE but due to rounding errors they might be slightly different.
        # So do not test for string equality but create imts and test for
        # 'period' equality:
        imts = sorted([imt.from_string(i) for i in imts if i not in
                       ('PGA', 'PGV')], key=lambda imt: imt.period)
        assert imts[0].period == 0.1
        assert imts[1].period == 0.2

    @pytest.mark.skip('MMI is implemented in egsim3.0')
    def test_gsim_not_available(self):
        data = {
            'gmm': ['AllenEtAl2012'],  # defined for MMI (not an available IMT in egsim2.0)
            IMT: ['SA(0.1)', 'SA(0.2)', 'PG*']
        }
        form = GsimImtForm(data)
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == \
               'Invalid request. Problems found in: gmm'

    def test_gsimimt_form_notdefinedfor_skip_invalid_periods(self):
        """tests that mismatching gsim <-> imt has the priority over bad
        SA periods"""
        data = {
            GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],  # not defined for PGD
            IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV', 'PGD']
        }
        form = GsimImtForm(data)
        assert not form.is_valid()
        msg = form.errors_json_data()['message']
        assert msg == (
            'gsim, imt: incompatible model(s) and intensity measure(s) '
            'BindiEtAl2011+PGD, BindiEtAl2014Rjb+PGD'
        )

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
        form = PredictionsForm(data)
        assert form.is_valid()
        assert list(form.cleaned_data[GSIM]) == ['BindiEtAl2011']  # testing 1)
        assert form.cleaned_data['magnitude'] == [0.5]  # testing 2a)
        assert form.cleaned_data['distance'] == [0.1]  # testing 2b)
        assert form.cleaned_data['vs30'] == 60  # testing 2c)
        assert sorted(form.cleaned_data['imt']) == ['PGA', 'PGV']  # testing 3)

    def test_trellisform_invalid(self):
        """Tests trellis form invalid"""
        data = {GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                IMT: ['SA', 'PGA', 'PGV'],
                'distance' : [1, 'x', ''],
                'msr': 'x',
                'mag': 'a'}

        form = PredictionsForm(data)
        assert not form.is_valid()
        assert form.errors_json_data()['message'] == (
            'distance: 2 values are invalid; '
            'imt: invalid intensity measure(s) SA; '
            'mag: 1 value is invalid; '
            'msr: value not found or misspelled'
        )

    def test_flatfile_validation(self):
        flatfile_df = read_flatfile(flatfile_tk_path)

        # Normal case (form valid)
        flatfile = flatfile_df[['rake', 'station_id',
                                'magnitude', 'rrup', 'vs30', 'event_id', 'PGA']].copy()
        bio = BytesIO()
        flatfile.to_csv(bio, sep=',', index=False)
        files = {'esm2019': SimpleUploadedFile('cover', bio.getvalue())}
        # mvd = MultiValueDict({'flatfile': fp})
        form = FlatfileValidationForm({}, files=files)
        is_valid = form.is_valid()
        assert is_valid
        data = form.output()
        assert isinstance(data['columns'], list) and data['columns']

        # Test removing event_id (form still valid. Previously, had event_id
        # was required and the form was invalid. Now we removed the mandatory
        # property for columns because hard to maintain with inference rules):
        flatfile = flatfile_df[
            ['rake', 'magnitude', 'rrup', 'vs30', 'PGA']].copy()
        bio = BytesIO()
        flatfile.to_csv(bio, sep=',')
        files = {'esm2019': SimpleUploadedFile('cover', bio.getvalue())}
        # mvd = MultiValueDict({'flatfile': fp})
        form = FlatfileValidationForm({}, files=files)
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
        form = FlatfileValidationForm({}, files=files)
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
        form = FlatfileValidationForm({}, files=files)
        is_valid = form.is_valid()
        assert not is_valid

        # Test changing a column data type (magnitude becomes string):
        flatfile = flatfile_df[[c for c in flatfile_df.columns if c != 'magnitude']].copy()
        flatfile['magnitude'] = 'A'
        bio = BytesIO()
        flatfile.to_csv(bio, sep=',')
        files = {'esm2019': SimpleUploadedFile('cover', bio.getvalue())}
        # mvd = MultiValueDict({'flatfile': fp})
        form = FlatfileValidationForm({}, files=files)
        is_valid = form.is_valid()
        assert not is_valid

    def test_get_gsim_from_region(self):
        form = GsimFromRegionForm({'lat': 50, 'lon': 7})
        assert form.is_valid()
        models = form.get_region_selected_model_names()
        assert len(models) == 12

        form = GsimFromRegionForm({'lat': 50, 'lon': 7, 'regionalization': 'share'})
        assert form.is_valid()
        models = form.get_region_selected_model_names()
        assert len(models) == 5
        form = GsimFromRegionForm({'lat': 50, 'lon': 7, 'regionalization': ['share']})
        assert form.is_valid()
        _models = form.get_region_selected_model_names()
        assert sorted(models) == sorted(_models)


def test_field2params_in_forms():
    clz = list(EgsimBaseForm.__subclasses__())
    while len(clz):
        cls = clz.pop()
        check_egsim_form(cls)
        for c in cls.__subclasses__():
            if c not in clz:
                clz.append(c)

    # mock a Form with errors and check it
    class Test(PredictionsForm):
        _field2params = {'gsim': ['model']}  # already defined

    with pytest.raises(ValueError):
        check_egsim_form(Test)

    class Test(PredictionsForm):
        _field2params = {'gsim_45673': ['model']}  # not a form field defined

    with pytest.raises(ValueError):
        check_egsim_form(Test)

    class Test(PredictionsForm):
        _field2params = {'test': ['gsim']}  # 'gsim' already a field name
        test = Field()

    with pytest.raises(ValueError):
        check_egsim_form(Test)

    class Test(PredictionsForm):
        _field2params = {'test': ['model']}  # 'model' already mapped
        test = Field()

    with pytest.raises(ValueError):
        check_egsim_form(Test)

    class Test(PredictionsForm):
        _field2params = {'test': 'model'}  # 'model' neither tuple or list
        test = Field()

    with pytest.raises(ValueError):
        check_egsim_form(Test)


def test_trellis_rupture_site_fields():

    form_rupture_fields = set(PredictionsForm().rupture_fields)
    rup_fields = RuptureProperties.__annotations__
    missing = set(rup_fields) -form_rupture_fields
    assert sorted(missing) == ['tectonic_region']

    form_site_fields = set(PredictionsForm().site_fields)
    site_fields = SiteProperties.__annotations__
    missing = set(site_fields) - form_site_fields
    assert sorted(missing) == ['distance_type', 'origin_point', 'xvf']

    # check that we did not misspell any TrellisField. To do this, let's
    # remove the site and rupture fields, and all fields defined in superclasses.
    # We should be left with 2 fields only: magnitude and distance

    rem_fields = set(PredictionsForm.base_fields) - \
                 form_rupture_fields - form_site_fields

    for super_cls in PredictionsForm.__mro__:
        if super_cls is not PredictionsForm:
            try:
                rem_fields -= set(super_cls.base_fields)  # noqa
            except AttributeError:
                pass
    assert sorted(rem_fields) == ['distance', 'magnitude', 'multi_header']


def check_egsim_form(new_class:Type[EgsimBaseForm]):
    # Dict denoting the field -> API params mappings:
    field2params = {}
    form_fields = set(new_class.base_fields)
    # Attribute denoting field -> API params mappings:
    attname = '_field2params'
    # Merge this class `field2params` data into `field2params`, and do some check
    # (Note: use `__dict__.get` because `getattr` also returns superclass attrs):
    for field, params in new_class.__dict__.get(attname, {}).items():
        err_msg = f"Error in {new_class.__name__}.{attname}:"
        # no key already implemented in `field2params`:
        if field in field2params:
            raise ValueError(f"{err_msg} '{field}' is already a key of "
                             f"`{attname}` in some superclass")
        # no key that does not denote a Django Form Field name
        if field not in form_fields:
            raise ValueError(f"{err_msg}: '{field}' must be a Form Field name")
        for param in params:
            # no param equal to another field name:
            if param != field and param in field2params:
                raise ValueError(f"{err_msg} '{field}' cannot be mapped to the "
                                 f"Field name '{param}'")
            # no param keyed by multiple field names:
            dupes = [f for f, p in field2params.items() if param in p]
            if dupes:
                raise ValueError(f"{err_msg} '{field}' cannot be mapped to "
                                 f"'{param}', as the latter is already keyed by "
                                 f"the field(s) "
                                 f"{', '.join(dupes)}")
        if not isinstance(params, tuple):
            raise ValueError(f"{err_msg} dict values must be lists or tuples")
        # all good. Merge into `field2params`:
        field2params[field] = params
    return field2params
