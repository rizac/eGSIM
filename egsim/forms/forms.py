'''
Django Forms for eGSIM

Created on 29 Jan 2018

@author: riccardo
'''

import re
import sys
import json
from datetime import datetime
from collections import OrderedDict
from io import StringIO

import yaml
import numpy as np

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.forms import Form
from django.utils.safestring import mark_safe
from django.forms.fields import BooleanField, CharField, FloatField, \
    ChoiceField, CallableChoiceIterator

from openquake.hazardlib.imt import from_string as imt_from_string
from smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14
# from smtk.database_visualiser import DISTANCES

from egsim.core.utils import vectorize, isscalar, yaml_load, querystring, \
    tostr, DISTANCE_LABEL
from egsim.forms.fields import NArrayField, IMTField, TrellisplottypeField, \
    MsrField, PointField, TrtField, GmdbField, ResidualplottypeField, \
    GsimField, TrModelField
from egsim.models import sharing_gsims, shared_imts


class BaseForm(Form):
    '''Base eGSIM form'''

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
        repl_dict = getattr(self, '__additional_fieldnames__', None)
        if repl_dict:
            for key in list(self.data.keys()):
                repl_key = repl_dict.get(key, None)
                if repl_key is not None:
                    self.data[repl_key] = self.data.pop(key)

        # https://stackoverflow.com/a/20309754:
        # Defaults are set accoridng to the initial value in the field
        # This must be set here cause in clean() required fields are processed
        # before and their error set in the error form
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
        # If the field is required, this behaviour allows to set the 'missing'
        # error (see e.g. MultipleChoiceField.validate), but if the field
        # is not required, we want simply the field to be missing, not having
        # a value set. Hence:
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
    def load(cls, obj):
        '''Safely loads the YAML-formatted object `obj` into a Form instance'''
        return cls(data=yaml_load(obj))

    def dump(self, stream=None, syntax='yaml'):
        """Serialize this Form instance into a YAML, JSON or URL query stream.
           If stream is None, return the produced string instead.

           :param stream: A stream **for text I/O** like a file-like object
               (in general any object with a write method, e.g. StringIO) or
               None.
           :param syntax: string, either 'json', 'yaml' or 'GET'. If not
               either string, this method raises ValueError
        """
        syntax = syntax.lower()
        if syntax not in ('json', 'yaml'):
            raise ValueError("Argument 'syntax' must be 'json' or 'yaml'")

        obj = self.to_dict()

        if syntax == 'GET':  # GET
            querystr = querystring(obj)
            if stream is None:
                return querystr
            else:
                stream.write(querystr)
        elif syntax == 'json':  # JSON
            if stream is None:
                return json.dumps(obj, indent=2, separators=(',', ': '),
                                  sort_keys=True)
            else:
                json.dump(obj, stream, indent=2, separators=(',', ': '),
                          sort_keys=True)
        else:  # YAML

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
            for name, value in obj.items():
                field = self.fields[name]
                label = field.label + \
                    ('' if not field.help_text else ' (%s)' % field.help_text)
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

    def to_dict(self):
        '''Converts this form to python dict. Each value is the `to_python`
        method of the corresponding django Field. Note that for lists, the
        original value is checked and, if string and contains the colon ':',
        it indicates a range and thus is returned as it was. Also, datetimes
        are quoted in ISO format as json might not support them.

        raise: ValidationError if the form is not valid
        '''
        if not self.is_valid():
            raise ValidationError(self.errors, code='invalid')

        ret = {}
        for name, val in self.data.items():
            parsedval = self.fields[name].to_python(val)
            is_scalar = isscalar(parsedval)
            if is_scalar and isinstance(parsedval, datetime):
                parsedval = tostr(parsedval)
            elif not is_scalar and isinstance(val, str) and ':' in val:
                parsedval = val
            ret[name] = parsedval

        return ret

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
        formdata = {}
        for name, _ in self.declared_fields.items():  # pylint: disable=no-member
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
            fielddata = {'help': boundfield.help_text,
                         'label': boundfield.label,
                         'attrs': attrs,
                         'err': '',
                         'is_hidden': widgetdata.pop('is_hidden', False),
                         'val': val}
            fielddata['choices'] = getattr(_, 'choices', [])
            if isinstance(fielddata['choices'], CallableChoiceIterator):
                if ignore_callable_choices:
                    fielddata['choices'] = []
                else:
                    fielddata['choices'] = list(fielddata['choices'])
            formdata[name] = fielddata
        return formdata

    @classmethod
    def parnames(cls):  # FIXME: Is this method necessary?
        '''returns an object where attributes are ALL parameters found on any
        Form of this module'''
        ret = OrderedDict()
        thismodule = sys.modules[__name__]
        for name in dir(thismodule):
            obj = thismodule.__dict__[name]
            try:
                if issubclass(obj, cls):
                    ret[obj.__name__.lower()] = \
                        {key: {"name": key, "label": field.label,
                               "help": field.help_text,
                               'choices': [{'name': n, 'label': l}
                                           for n, l in getattr(field,
                                                               'choices', [])]}
                         for key, field in obj.declared_fields.items()}
            except:
                pass
        return ret


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
    imt = IMTField(required=False, sa_periods_required=False)

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

#     def __init__(self, *args, **kwargs):
#         '''Overrides init to set default values for gsim and imt'''
#         super(GsimSelectionForm, self).__init__(*args, **kwargs)

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

    __additional_fieldnames__ = {'gmpe': 'gsim', 'sap': 'sa_periods'}

    # fields (not used for rendering, just for validation)
    gsim = GsimField(required=True)
    imt = IMTField(required=True)
    sa_periods = NArrayField(label="The Spectral Acceleration (SA) period(s)",
                             required=False,
                             help_text=("Required only if SA is a selected "
                                        "Intensity Measure Type. "
                                        "Alternatively, you can ignore this "
                                        "parameter but each SA must be "
                                        "supplied with its period in "
                                        "parentheses, e.g: SA(0.1) SA(0.2)"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # put 'sa_periods in the IMTField:
        self.fields['imt'].sa_periods = self.data.pop('sa_periods', [])

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

        cleaned_data = super().clean()

        gsims = cleaned_data.get("gsim", [])
        # We need to reduce all IMT strings in cleaned_data['imt'] to a set
        # where all 'SA(#)' strings are counted as 'SA' once..
        # Use imt.from_string and get the class name: quite cumbersome, but it works
        imt_classnames = set(imt_from_string(imtname).__class__.__name__
                             for imtname in cleaned_data.get("imt", []))

        if gsims and imt_classnames:
            invalid_gsims = set(gsims) - set(sharing_gsims(imt_classnames))

            if invalid_gsims:
                # instead of raising ValidationError, which is keyed with
                # '__all__' we add the error keyed to the given field name
                # `name` via `self.add_error`:
                # https://docs.djangoproject.com/en/2.0/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
                # note: pass only invalid_gsims as the result would be equal
                # than passing all gsims but the loop is faster:
                invalid_imts = set(imt_classnames) - set(shared_imts(gsims))
                err_gsim = ValidationError(_("%(num)d gsim(s) not defined "
                                             "for all supplied imt(s)"),
                                           params={'num': len(invalid_gsims)},
                                           code='invalid')
                err_imt = ValidationError(_("%(num)d imt(s) not defined for "
                                            "all supplied gsim(s)"),
                                          params={'num': len(invalid_imts)},
                                          code='invalid')
                self.add_error('gsim', err_gsim)
                self.add_error('imt', err_imt)

        return cleaned_data

    @classmethod
    def invalid_imts(cls, gsims, imts):
        '''returns a *set* of all invalid imt(s) from the given selected
        gsims and imts

        :param gsims: iterable of Egsim objects denoting the selected gsims
        :param gsims: iterable of strings denoting the selected imts. Strings
            should represent the imt class name only, so e.g. 'SA', not
            'SA(2.0)'
        :return: a set of invalid imts
        '''
        imts = set(imts)
        invalid_imts = set()
        for gsim in gsims:
            invalid_imts |= imts - gsim.imts

        return invalid_imts


class TrellisForm(GsimImtForm):
    '''Form for Trellis plot generation'''

    # py3 dict merge (see https://stackoverflow.com/a/26853961/3526777):
    __additional_fieldnames__ = {'mag': 'magnitude', 'dist': 'distance',
                                 'tr': 'tectonic_region',
                                 'msr': 'magnitude_scalerel',
                                 'lineazi': 'line_azimuth',
                                 'vs30m': 'vs30_measured',
                                 'hyploc': 'hypocentre_location',
                                 **GsimImtForm.__additional_fieldnames__}

    plot_type = TrellisplottypeField(label='Plot type')
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

    def clean(self):
        cleaned_data = super(TrellisForm, self).clean()
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
            elif not isscalar(cleaned_data[name]) and not isscalar(vs30) \
                    and len(vs30) != len(cleaned_data[name]):
                # instead of raising ValidationError, which is keyed with
                # '__all__' we add the error keyed to the given field name
                # `name` via `self.add_error`:
                # https://docs.djangoproject.com/en/2.0/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
                error = ValidationError(_("value must be scalar, empty or "
                                          "a %(num)d-elements vector"),
                                        params={'num': len(vs30)},
                                        code='invalid')
                self.add_error(name, error)

        return cleaned_data


class GmdbForm(BaseForm):
    '''Abstract-like class for handling gmdb (GroundMotionDatabase)'''

    __additional_fieldnames__ = {'sel': 'selexpr', 'dist': 'distance_type'}

    gmdb = GmdbField(label='Ground Motion database', required=True)
    selexpr = CharField(label='Selection expression', required=False)


class GmdbPlot(GmdbForm):
    '''Abstract-like class for handling gmdb (GroundMotionDatabase)'''

    __additional_fieldnames__ = {**GmdbForm.__additional_fieldnames__,
                                 'dist': 'distance_type'}

    distance_type = ChoiceField(label='Distance type',
                                choices=list(DISTANCE_LABEL.items()),
                                initial='rrup')


class ResidualsForm(GsimImtForm, GmdbPlot):
    '''Form for residual analysis'''

    # py3 dict merge (see https://stackoverflow.com/a/26853961/3526777):
    __additional_fieldnames__ = {**GsimImtForm.__additional_fieldnames__,
                                 **GmdbPlot.__additional_fieldnames__}

    plot_type = ResidualplottypeField(required=True)

    def clean(self):
        # Note: the call below calls GmdbForm.clean(self) BUT we should
        # check why and how:
        GsimImtForm.clean(self)
