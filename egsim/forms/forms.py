'''
Django Forms for eGSIM

Created on 29 Jan 2018

@author: riccardo
'''

import re
# import sys
import json
from datetime import datetime
from collections import defaultdict
from io import StringIO

import yaml
import numpy as np

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.forms import Form
from django.utils.safestring import mark_safe
from django.forms.fields import (BooleanField, CharField, FloatField,
                                 ChoiceField, CallableChoiceIterator,
                                 MultipleChoiceField)
# from django.forms.widgets import HiddenInput
from smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14

from egsim.core.utils import (vectorize, isscalar, yaml_load, querystring,
                              tostr, DISTANCE_LABEL)
from egsim.forms.fields import (NArrayField, ImtclassField, ImtField,
                                TrellisplottypeField, MsrField, PointField,
                                TrtField, GmdbField, ResidualplottypeField,
                                GsimField, TrModelField, MeasureOfFitField,
                                SelExprField, TextDecField, TextSepField)
from egsim.models import sharing_gsims, shared_imts


class BaseForm(Form):
    '''Base eGSIM form'''

    # Subclass this attribute to write optional field names mapped to any of
    # the form field names. You can also merge two parent classes additional
    # field names with the py3 notation:
    # __additional_fieldnames__ = {**ParentForm1.__additional_fieldnames__,
    #                              **ParentForm2.__additional_fieldnames__}
    __additional_fieldnames__ = {}

    # this is a list of fields that should be hidden from the doc
    # and not used in the API. Also, the 'dump' method does not returns them.
    # By specifying widget=HiddenInput in the field
    # you achieve the same result BUT also the <input> will be of type hidden
    # in the GUI
    __hidden_fieldnames__ = []

    def __init__(self, *args, **kwargs):
        '''Overrides init to set custom attributes on field widgets and to set
        the initial value for fields of this class with no match in the keys
        of self.data'''
        # remove colon in labels by default in templates:
        kwargs.setdefault('label_suffix', '')
        # call super:
        super(BaseForm, self).__init__(*args, **kwargs)
        # now we want to re-name potential parameter names (e.g., 'mag' into
        # 'magnitude'). To do this, define a dict __additional_fieldnames__ as
        # class attribute (see sub-classes) of name (string) mapped to its
        # possible alternative name
        repl_dict = self.__additional_fieldnames__ or {}
        if repl_dict:
            for key in list(self.data.keys()):
                repl_key = repl_dict.get(key, None)
                if repl_key is not None:
                    self.data[repl_key] = self.data.pop(key)

        # Make fields initial value the default when missing.
        # From https://stackoverflow.com/a/20309754 and other posts therein:
        # initial isn't really meant to be used to set default values for form
        # fields. Instead, it's really more a placeholder utility when
        # displaying forms to the user, and won't work well if the field isn't
        # required (see also the class method is_optional):
        for name in self.fields:
            if not self[name].html_name in self.data and \
                    self.fields[name].initial is not None:
                self.data[name] = self.fields[name].initial

        # Custom attributes for js libraries (e.,g. bootstrap, angular...)?
        # All solutions (widget_tweaks, django-angular) are too much overhead
        # in our simple scenario. This is the best solution but not that
        # after refactoring it is no-op:
        self.customize_widget_attrs()

    def clean(self):
        '''Checks that if longitude is provided, also latitude is provided,
        and vice versa (the same for longitude2 and latitude2)
        '''
        cleaned_data = super().clean()
        # django sets all values provided in self.declared_fields with a
        # default if the field is not provided, usually falsy (e.g. []
        # for MultipleChoiceField. See django.forms.Form._clean_fields)
        # This behaviour should not be changed as it allows to raise the
        # 'missing' ValidationError (see e.g. MultipleChoiceField.validate)
        # if the field is required, but prevents subclasses to know if the
        # field was explicitly provided or not. To achieve the latter, remove
        # fields not in self.data:
        for key in list(_ for _ in cleaned_data if _ not in self.data):
            cleaned_data.pop(key)

        return cleaned_data

    def customize_widget_attrs(self):  # pylint: disable=no-self-use
        '''customizes the widget attributes. This method is no-op and might be
        overwritten in subclasses. Check however `self.to_rendering_dict`
        which is currently the method to be used in order to inject data in
        the frontend'''
        # this method is no-op, as we delegate the view (frontend)
        # to set the custom attributes. Example in case subclassed:
        #
        # atts = {'class': 'form-control'}  # for bootstrap
        # for name, field in self.fields.items():  # @UnusedVariable
        #     if not isinstance(field.widget,
        #                       (CheckboxInput, CheckboxSelectMultiple,
        #                        RadioSelect)) and not field.widget.is_hidden:
        #         field.widget.attrs.update(atts)
        return

    @classmethod
    def is_optional(cls, field):
        '''Returns True if the given field is optional.
        A field is optional if either field.required=False OR
        the field inital value is specified (not None). Remeber that
        a field initial value acts as default value when missing

        :param field: a Field object or a string denoting the name of one of
            this Form's fields
        '''
        if isinstance(field, str):
            field = cls.declared_fields[field]
        return not field.required or field.initial is not None

    def dump(self, stream=None, syntax='yaml'):
        """Serialize this Form instance into a YAML or JSON stream.
        **The form needs to be already validated via e.g. `form.is_valid()`**.
        Hidden fields in `self.__hidden_fieldnames__` are not returned.

        The result collects the fields of `self.data`, i.e., the unprocessed
        input, with one exception: if this form subclasses
        :class:`GsimImtForm`, as 'sa_period' is hidden,
        the value mapped to 'imt' will be `self.cleaned_data['imt']` and not
        `self.data['imt']`.

        :param stream: A file-like object **for text I/O** (e.g. `StringIO`),
           or None.
        :param syntax: string either json or yaml. Deault: yaml

        :return: if the passed `stream` argument is None, returns the produced
            string. If the passed `stream` argument is a file-like object,
            this method writes to `stream` and returns None
        """
        if syntax not in ('yaml', 'json'):
            raise ValueError("invalid `syntax` argument in `dump`: '%s' "
                             "not in ('json', 'yam')" % syntax)

        hidden_fn = set(self.__hidden_fieldnames__)
        cleaned_data = {}
        for key, val in self.data.items():
            if key in hidden_fn:
                continue
            # Omit unchanged optional parameters. This is not only to make
            # the dumped string more readable and light size, but to avoid
            # parameters which defaults to None (e.g. z1pt0 in
            # TrellisForm): if they were written here (e.g. `z1pt0: None`) then
            # a routine converting the returned JSON/YAML to a query string
            # would wrtie "...z1pt0=null...", which might be interpreted as
            # the string "null"
            if self.is_optional(key) and val == self.fields[key].initial:
                continue
            cleaned_data[key] = self.cleaned_data[key] \
                if key == 'imt' and isinstance(self, GsimImtForm) else val

        if syntax == 'json':
            if stream is None:
                return json.dumps(cleaned_data, indent=4,
                                  separators=(',', ': '), sort_keys=True)
            json.dump(cleaned_data, stream, indent=4, separators=(',', ': '),
                      sort_keys=True)
            return None

        class MyDumper(yaml.SafeDumper):  # pylint: disable=too-many-ancestors
            '''forces indentation of lists.
            See https://stackoverflow.com/a/39681672'''
            def increase_indent(self, flow=False, indentless=False):
                return super(MyDumper, self).increase_indent(flow, False)

        # regexp to replace html entities with their content, i.e.:
        # <a href='#'>bla</a> -> bla
        # V<sub>s30</sub> -> Vs30
        # ... and so on ...
        html_tags_re = re.compile('<(\\w+)(?: [^>]+|)>(.*?)<\\/\\1>')

        # inject comments in yaml by using the field label and its help:
        stringio = StringIO() if stream is None else stream
        fields = self.to_rendering_dict(ignore_callable_choices=False)
        for name, value in cleaned_data.items():
            field = fields[name]
            label = (field['label'] or '') + \
                ('' if not field['help'] else ' (%s)' % field['help'])
            if label:
                # replace html characters with their content
                # (or empty str if no content):
                label = html_tags_re.sub(r'\2', label)
                # replace newlines for safety:
                label = '# %s\n' % (label.replace('\n', ' ').
                                    replace('\r', ' '))
                stringio.write(label)
            yaml.dump({name: value}, stream=stringio, Dumper=MyDumper,
                      default_flow_style=False)
            stringio.write('\n')
        # compatibility with yaml dump if stream is None:
        if stream is None:
            ret = stringio.getvalue()
            stringio.close()
            return ret
        return None

    def to_rendering_dict(self, ignore_callable_choices=True):
        '''Converts this form to a python dict for rendering the field as input
        in the frontend, allowing it to be injected into frontend libraries
        like VueJS (the currently used library) or AngularJS: each
        Field name is mapped to a dict of keys such as 'val' (the value),
        'help' (the help text), 'label' (the label text), 'err':
        (the error text), 'attrs' (a dict of HTML element attributes),
        'choices' (the list of available choices, see argument
        `ignore_callable_choices`).

        :param ignore_callable_choices: handles the 'choices' for fields
            defining it as CallableChoiceIterator: if True (the default) the
            function is not evluated and the choices are simply set to [].
            If False, the choices function will be evaluated.
            Use True when the choices list is too big or too expensive and
            there is a faster way to provide them to the frontend (e.g., later
            via HTTP requests).
        '''
        hidden_fn = set(self.__hidden_fieldnames__)
        formdata = {}
        optional_names = defaultdict(list)
        for k, v in self.__additional_fieldnames__.items():
            optional_names[v].append(k)
        for name, field in self.declared_fields.items():  # pylint: disable=no-member
            # little spec: self.declared_fields and self.base_fields are the
            # same thing (see django.forms.forms.DeclarativeFieldsMetaclass)
            # and are declared AT CLASS level: modifying them applies changes
            # to all instances, thus avoid. On the other hand,
            # self.fields[name] returns the fields on the instance level and
            # it's where specific instance-level changes have to be made
            # https://docs.djangoproject.com/en/2.2/ref/forms/api/#accessing-the-fields-from-the-form
            # Finally, self[name] creates a BoundField from self.fields[name]:
            # A BoundField deals with displaying the field and populating it
            # with any values. So for returning *all* field data (also that
            # set automatically by django on our init parameter, as in this
            # case) it should be used.
            boundfield = self[name]
            val = boundfield.value()
            widget = boundfield.field.widget
            attrs = boundfield.build_widget_attrs({}, widget)
            fielddata = widget.get_context(name, val, attrs)
            widgetdata = fielddata['widget']
            attrs = dict(widgetdata.pop('attrs', {}))
            if 'type' in widgetdata:
                attrs['type'] = widgetdata.pop('type')
            if 'required' in widgetdata:
                attrs['required'] = widgetdata.pop('required')
            if 'id' not in attrs:
                attrs['id'] = boundfield.auto_id
            attrs['name'] = widgetdata.pop('name')
            is_hidden = widgetdata.pop('is_hidden', False) or \
                name in hidden_fn
            # coerce val to [] in case val falsy and multichoice:
            if isinstance(field, MultipleChoiceField) and not val:
                val = []
            fielddata = {
                'name': attrs['name'],
                'opt_names': optional_names.get(name, []),
                'is_optional': self.is_optional(name),
                'help': boundfield.help_text,
                'label': boundfield.label,
                'attrs': attrs,
                'err': '',
                'is_hidden': is_hidden,
                'val': val,
                'initial': field.initial
            }
            fielddata['choices'] = getattr(field, 'choices', [])
            if isinstance(fielddata['choices'], CallableChoiceIterator):
                if ignore_callable_choices:
                    fielddata['choices'] = []
                else:
                    fielddata['choices'] = list(fielddata['choices'])
            formdata[name] = fielddata
        return formdata


class GsimSelectionForm(BaseForm):
    '''Form for (t)ectonic (r)egion gsim selection from a point or rectangle.
    This form is currently only used as validator as the HTML page renderes
    a custom map.
    '''

    __additional_fieldnames__ = {'lat': 'latitude', 'lon': 'longitude',
                                 'lat2': 'latitude2', 'lon2': 'longitude2',
                                 'gmpe': 'gsim'}

    # NOTE: DO NOT set initial
    gsim = GsimField(required=False)
    imt = ImtclassField(required=False)

    model = TrModelField(label='Tectonic region model', required=False)
    longitude = FloatField(label='Longitude', min_value=-180, max_value=180,
                           required=False)
    latitude = FloatField(label='Latitude', min_value=-90, max_value=90,
                          required=False)
    longitude2 = FloatField(label='Longitude 2nd point', min_value=-180,
                            max_value=180, required=False)
    latitude2 = FloatField(label='Latitude 2nd point', min_value=-90,
                           max_value=90, required=False)
    trt = TrtField(label='Tectonic region type(s)', required=False)

    def clean(self):
        '''Checks that if longitude is provided, also latitude is provided,
        and vice versa (the same for longitude2 and latitude2)'''
        cleaned_data = super().clean()

        # check that params combinations are ok:
        couplings = (('latitude', 'longitude'), ('longitude2', 'latitude2'))
        for (key1, key2) in couplings:
            val1, val2 = \
                cleaned_data.get(key1, None), cleaned_data.get(key2, None)
            if val1 is None and val2 is not None:
                # instead of raising ValidationError, which is keyed with
                # '__all__' we add the error keyed to the given field name
                # `name` via `self.add_error`:
                # https://docs.djangoproject.com/en/2.0/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
                error = ValidationError(_("missing value"), code='missing')
                self.add_error(key1, error)
            elif val1 is not None and val2 is None:
                error = ValidationError(_("missing value"), code='missing')
                self.add_error(key2, error)

        return cleaned_data


class GsimImtForm(BaseForm):
    '''Base abstract-like form for any form requiring Gsim+Imt selection'''

    __additional_fieldnames__ = {'gmpe': 'gsim', 'gmm': 'gsim'}
    __hidden_fieldnames__ = ['sa_period']

    gsim = GsimField(required=True)
    imt = ImtField(required=True)
    # sa_periods should not be exposed through the API, it is only used
    # from the frontend GUI. Thus required=False is necessary.
    # We use a CharField because in principle it should never raise: If SA
    # periods are malformed, the IMT field will hold the error in the response
    sa_period = CharField(label="SA period(s)", required=False)

    def __init__(self, *args, **kwargs):
        super(GsimImtForm, self).__init__(*args, **kwargs)
        # remove sa_periods and put them in imt field:
        self.fields['imt'].sa_periods_str = self.data.pop('sa_period', '')

    def clean(self):
        '''runs validation where we must validate selected gsim(s) based on
        selected intensity measure type. For info see:
        https://docs.djangoproject.com/en/1.11/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
        '''
        # UNCOMMENT THE BLOCK BELOW IF YOU WHISH TO BE STRICT with unkwnown params
        # # check that we did not provide unknown parameters. This might not be necessary
        # # but it might help warning the user for typos in case
        # unknown_params = set(self.data) - set(self.fields)
        # if unknown_params:
        #     raise ValidationError([
        #         ValidationError(_("unknown parameter '%(param)s'"),
        #                         params={'param': p}, code='unknown')
        #         for p in unknown_params])

        super().clean()
        self.validate_gsim_and_imt()
        return self.cleaned_data

    def validate_gsim_and_imt(self):
        '''Validates gsim and imt assuring that all gsims are defined for all
        supplied imts, and all imts are defined for all supplied gsim.
        This method calls self.add_error and works on self.cleaned_data, thus
        it should be called after super().clean()'''
        # the check here is to replace potential imt errors with
        # the more relevant mismatch with the supplied gsim.
        # E.g., if the user supplied imt = 'SA(abc)' (error) and
        # a gsim='SomeGsimNotDefinedForSA', the error dict should replace
        # the SA error with 'Imt not defined for supplied Gsim':
        gsims = self.cleaned_data.get("gsim", [])
        # return the class names of the supplied Imts. Thus 'Sa(...), Sa(...)'
        # is counted once as 'SA':
        imts = self.fields['imt'].get_imt_classnames(self.data.get('imt', ''))

        if gsims and imts:
            invalid_gsims = set(gsims) - set(sharing_gsims(imts))

            if invalid_gsims:
                # instead of raising ValidationError, which is keyed with
                # '__all__' we add the error keyed to the given field name
                # `name` via `self.add_error`:
                # https://docs.djangoproject.com/en/2.0/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
                # note: pass only invalid_gsims as the result would be equal
                # than passing all gsims but the loop is faster:
                invalid_imts = imts - set(shared_imts(gsims))
                err_gsim = ValidationError(_("%(num)d gsim(s) not defined "
                                             "for all supplied imt(s)"),
                                           params={'num': len(invalid_gsims)},
                                           code='invalid')
                err_imt = ValidationError(_("%(num)d imt(s) not defined for "
                                            "all supplied gsim(s)"),
                                          params={'num': len(invalid_imts)},
                                          code='invalid')
                # add_error removes also the field from self.cleaned_data:
                self.add_error('gsim', err_gsim)
                if 'imt' in self.errors:
                    self.errors.pop('imt', None)
                self.add_error('imt', err_imt)


class TrellisForm(GsimImtForm):
    '''Form for Trellis plot generation'''

    # py3 dict merge (see https://stackoverflow.com/a/26853961/3526777):
    __additional_fieldnames__ = {'mag': 'magnitude', 'dist': 'distance',
                                 'stddev': 'stdev',
                                 'tr': 'tectonic_region',
                                 'msr': 'magnitude_scalerel',
                                 'lineazi': 'line_azimuth',
                                 'vs30m': 'vs30_measured',
                                 'hyploc': 'hypocentre_location',
                                 'vs30measured': 'vs30_measured',
                                 **GsimImtForm.__additional_fieldnames__}

    plot_type = TrellisplottypeField(label='Plot type')
    stdev = BooleanField(label='Compute Standard Deviation(s)', required=False,
                         initial=False)

    # GSIM RUPTURE PARAMS:
    magnitude = NArrayField(label='Magnitude(s)', min_count=1)
    distance = NArrayField(label='Distance(s)', min_count=1)
    vs30 = NArrayField(label=mark_safe('V<sub>S30</sub> (m/s)'), min_value=0.,
                       min_count=1, initial=760.0)
    aspect = FloatField(label='Rupture Length / Width', min_value=0.)
    dip = FloatField(label='Dip', min_value=0., max_value=90.)
    # FIXME: removed field below, it is not used. Should we add it
    # in clean (see below)?
    #  tectonic_region = CharField(label='Tectonic Region Type',
    #                              initial='Active Shallow Crust',
    #                              widget=HiddenInput)
    rake = FloatField(label='Rake', min_value=-180., max_value=180.,
                      initial=0.)
    strike = FloatField(label='Strike', min_value=0., max_value=360.,
                        initial=0.)
    ztor = FloatField(label='Top of Rupture Depth (km)', min_value=0.,
                      initial=0.)
    magnitude_scalerel = MsrField(label='Magnitude Scaling Relation',
                                  initial="WC1994")
    initial_point = PointField(label="Location on Earth",
                               help_text='Longitude Latitude', initial="0 0",
                               min_value=[-180, -90], max_value=[180, 90])
    hypocentre_location = NArrayField(label="Location of Hypocentre",
                                      initial='0.5 0.5',
                                      help_text=('Along-strike fraction, '
                                                 'Down-dip fraction'),
                                      min_count=2, max_count=2,
                                      min_value=[0, 0], max_value=[1, 1])
    # END OF RUPTURE PARAMS
    vs30_measured = BooleanField(label=mark_safe('Is V<sub>S30</sub> '
                                                 'measured?'),
                                 help_text='Otherwise is inferred',
                                 initial=True, required=False)
    line_azimuth = FloatField(label='Azimuth of Comparison Line',
                              min_value=0., max_value=360., initial=0.)
    z1pt0 = NArrayField(label=mark_safe('Depth to 1 km/s V<sub>S</sub> '
                                        'layer (m)'),
                        min_value=0., required=False,
                        help_text=mark_safe("Calculated from the "
                                            "V<sub>S30</sub> if not given"))
    z2pt5 = NArrayField(label=mark_safe('Depth to 2.5 km/s V<sub>S</sub> '
                                        'layer (km)'),
                        min_value=0., required=False,
                        help_text=mark_safe("Calculated from the  "
                                            "V<sub>S30</sub> if not given"))
    backarc = BooleanField(label='Backarc Path', initial=False, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If the plot_type is 's' or 'ss', remove imt and sa_period
        # and set the field (note NOT self.base_fields or self.declared_fields!
        # not to be required, so validation will be ok:
        if self.data.get('plot_type', '') in ('s', 'ss'):
            self.fields['imt'].sa_periods_str = ''  # see superclass __init__
            self.data.pop('imt', None)
            self.data.pop('sa_period', None)
            self.fields['imt'].required = False
            self.fields['sa_period'].required = False  # for safety

    def clean(self):
        cleaned_data = super(TrellisForm, self).clean()

        # this parameter is not used, comment out:
        # cleaned_data['tectonic_region'] = 'Active Shallow Crust'

        # calculate z1pt0 and z2pt5 if needed, raise in case of errors:
        vs30 = cleaned_data['vs30']  # surely a list with st least one element
        vs30scalar = isscalar(vs30)
        vs30s = np.array(vectorize(vs30), dtype=float)

        # check vs30-dependent values:
        for name, func in (['z1pt0', vs30_to_z1pt0_cy14],
                           ['z2pt5', vs30_to_z2pt5_cb14]):
            if name not in cleaned_data or cleaned_data[name] == []:
                values = func(vs30s)  # numpy-function
                cleaned_data[name] = \
                    float(values[0]) if vs30scalar else values.tolist()
            elif isscalar(cleaned_data[name]) != isscalar(vs30) or \
                    (not isscalar(vs30) and
                     len(vs30) != len(cleaned_data[name])):
                str_ = 'scalar' if isscalar(vs30) else \
                    '%d-elements vector' % len(vs30)
                # instead of raising ValidationError, which is keyed with
                # '__all__' we add the error keyed to the given field name
                # `name` via `self.add_error`:
                # https://docs.djangoproject.com/en/2.0/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
                error = ValidationError(_("value must be consistent with vs30 "
                                          "(%s)" % str_),
                                        code='invalid')
                self.add_error(name, error)

        return cleaned_data


class GmdbForm(BaseForm):
    '''Abstract-like class for handling gmdb (GroundMotionDatabase)'''

    __additional_fieldnames__ = {'sel': 'selexpr', 'dist': 'distance_type'}

    gmdb = GmdbField(required=True)
    selexpr = SelExprField(required=False)


class GmdbPlotForm(GmdbForm):
    '''Form for the Gmdb plot (currently undocumented API, frontend only)'''

    __additional_fieldnames__ = {**GmdbForm.__additional_fieldnames__,
                                 'dist': 'distance_type'}

    distance_type = ChoiceField(label='Distance type',
                                choices=list(DISTANCE_LABEL.items()),
                                initial='rrup')


class ResidualsForm(GsimImtForm, GmdbForm):
    '''Form for residual analysis'''

    # py3 dict merge (see https://stackoverflow.com/a/26853961/3526777):
    __additional_fieldnames__ = {**GsimImtForm.__additional_fieldnames__,
                                 **GmdbForm.__additional_fieldnames__}

    plot_type = ResidualplottypeField(required=True)

    def clean(self):
        # Note: the call below calls GmdbForm.clean(self) BUT we should
        # check why and how:
        return GsimImtForm.clean(self)


class TestingForm(GsimImtForm, GmdbForm):
    '''Form for testing Gsims via Measures of Fit'''

    # py3 dict merge (see https://stackoverflow.com/a/26853961/3526777):
    __additional_fieldnames__ = {**GsimImtForm.__additional_fieldnames__,
                                 **GmdbForm.__additional_fieldnames__,
                                 'fitm': 'fit_measure'}

    fit_measure = MeasureOfFitField(required=True, label="Measure(s) of fit")

    edr_bandwidth = FloatField(required=False, initial=0.01,
                               help_text=('Ignored if EDR is not a '
                                          'selected measure of fit'))
    edr_multiplier = FloatField(required=False, initial=3.0,
                                help_text=('Ignored if EDR is not a '
                                           'selected measure of fit'))

    def clean(self):
        # Note: the call below calls GmdbPlot.clean(self) BUT we should
        # check why and how:
        cleaned_data = GsimImtForm.clean(self)
        config = {}
        for parname in ['edr_bandwidth', 'edr_multiplier']:
            if parname in cleaned_data:
                config[parname] = cleaned_data[parname]
        cleaned_data['config'] = config
        return cleaned_data


class FormatForm(BaseForm):
    '''Form handling the validation of the format related argument in
    a request'''
    # py3 dict merge (see https://stackoverflow.com/a/26853961/3526777):
    __additional_fieldnames__ = {}

    format = ChoiceField(required=False, initial='json',
                         label='The format of the data returned',
                         choices=[('json', 'json'), ('text', 'text/csv')])

    text_sep = TextSepField(required=False, initial='comma',
                            label='The (column) separator character',
                            help_text=('Ignored if the requested '
                                       'format is not text'))
    text_dec = TextDecField(required=False, initial='period',
                            label='The decimal separator character',
                            help_text=('Ignored if the requested '
                                       'format is not text'))

    def clean(self):
        super().clean()
        tsep, tdec = 'text_sep', 'text_dec'
        # convert to symbols:
        if self.cleaned_data[tsep] == self.cleaned_data[tdec] and \
                self.cleaned_data['format'] == 'text':
            msg = _("'%s' must differ from '%s' in 'text' format" %
                    (tsep, tdec))
            err_ = ValidationError(msg, code='conflicting values')
            # add_error removes also the field from self.cleaned_data:
            self.add_error(tsep, err_)
            self.add_error(tdec, err_)

        return self.cleaned_data
