'''
Django Forms for eGSIM

Created on 29 Jan 2018

@author: riccardo
'''

import re
import os
import json
from collections import OrderedDict
from io import StringIO

import yaml
import numpy as np

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.forms import Form
from django.utils.safestring import mark_safe
from django.forms.widgets import RadioSelect, CheckboxSelectMultiple, CheckboxInput,\
    HiddenInput
from django.forms.fields import BooleanField, CharField, FloatField, \
    ChoiceField, MultipleChoiceField
# from django.core import validators

from openquake.hazardlib import imt
from smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14
from smtk.database_visualiser import DISTANCES

from egsim.core import yaml_load
from egsim.core.utils import vectorize, EGSIM, isscalar
from egsim.forms.fields import NArrayField, IMTField, TrellisplottypeField, MsrField, \
    PointField, TrtField, GmdbField, ResidualplottypeField, GmdbSelectionField, GsimField, \
    TrModelField, MultipleChoiceWildcardField
import time
import uuid



class BaseForm(Form):
    '''Base eGSIM form'''

    def __init__(self, *args, **kwargs):
        '''Overrides init to set custom attributes on field widgets and to set the initial
        value for fields of this class with no match in the keys of self.data'''
        kwargs.setdefault('label_suffix', '')  # remove colon in labels by default in templates
        # How do we implement custom attributes for js libraries (e.,g. bootstrap, angular...)?
        # All solutions (widget_tweaks, django-angular) are, as always, for big projects and they
        # are huge overheads for the goal we want to achieve.
        # So, after all we just need to overwrite few attributes on a form:
        super(BaseForm, self).__init__(*args, **kwargs)
        # now we want to re-name potential parameter names (e.g., 'mag' into 'magnitude')
        # To do this, define a __additional_fieldnames__ as class attribute, where
        # is a dict of name (string) mapped to its possible
        repl_dict = getattr(self, '__additional_fieldnames__', None)
        if repl_dict:
            for key in list(self.data.keys()):
                repl_key = repl_dict.get(key, None)
                if repl_key is not None:
                    self.data[repl_key] = self.data.pop(key)

        # https://stackoverflow.com/a/20309754:
        # Defaults are set accoridng to the initial value in the field
        # This must be set here cause in clean() required fields are processed before and their
        # error set in the error form
        for name in self.fields:
            if not self[name].html_name in self.data and self.fields[name].initial is not None:
                self.data[name] = self.fields[name].initial

        self.customize_widget_attrs()

    def customize_widget_attrs(self):
        '''customizes the widget attributes (currently sets a bootstrap class on almost all
        of them'''
        atts = {'class': 'form-control'}  # for bootstrap
        for name, field in self.fields.items():  # @UnusedVariable
            # add class only for specific html elements, some other might have weird layout
            # if class 'form-control' is added on them:
            if not isinstance(field.widget,
                              (CheckboxInput, CheckboxSelectMultiple, RadioSelect))\
                    and not field.widget.is_hidden:
                field.widget.attrs.update(atts)

    @classmethod
    def load(cls, obj):
        '''Safely loads the YAML-formatted object `obj` into a Form instance'''
        return cls(data=yaml_load(obj))

    def dump(self, stream=None, syntax='yaml'):
        """Serialize this Form instance into a YAML or JSON stream.
           If stream is None, return the produced string instead.

           :param stream: A stream like a file-like object (in general any
               object with a write method) or None
           :param syntax: string, either 'json' or 'yaml'. If not either string, this
                method raises ValueError
        """
        syntax = syntax.lower()
        if syntax not in ('json', 'yaml'):
            raise ValueError("Form serialization syntax must be 'json' or 'yaml'")

        obj = self.to_dict()
        if syntax == 'json':  # JSON
            if stream is None:
                return json.dumps(obj, indent=2, separators=(',', ': '), sort_keys=True)
            else:
                json.dump(obj, stream, indent=2, separators=(',', ': '), sort_keys=True)
        else:  # YAML

            class MyDumper(yaml.SafeDumper):  # pylint: disable=too-many-ancestors
                '''forces indentation of lists. See https://stackoverflow.com/a/39681672'''
                def increase_indent(self, flow=False, indentless=False):
                    return super(MyDumper, self).increase_indent(flow, False)

            # regexp to replace html entities with their content, i.e.:
            # <a href='#'>bla</a> -> bla
            # V<sub>s30</sub> -> Vs30
            # ... and so on ...
            html_tags_re = re.compile('<(\\w+)(?: [^>]+|)>(.*?)<\\/\\1>')

            # inject comments in yaml by using the field label and the label help:
            stringio = StringIO() if stream is None else stream
            for name, value in obj.items():
                field = self.fields[name]
                label = field.label + ('' if not field.help_text else ' (%s)' % field.help_text)
                if label:
                    # replace html characters with their content (or empty str if no content):
                    label = html_tags_re.sub(r'\2', label)
                    # replace newlines for safety:
                    label = '# %s\n' % (label.replace('\n', ' ').replace('\r', ' '))
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
        '''Converts this form to python dict. Each value is the `to_python` method of the
        corresponding django Field. Note that for :class:`NArrayField`s, the resulting array
        might be extremely long (in case of semicolon notation, e.g. '1:1:10000')..

        raises ValidationError if the form is not valid
        '''
        if not self.is_valid():
            raise ValidationError(self.errors, code='invalid')

        # we might keep the value as-it-is for NArrayFields, but we might have non-JSON/YAML
        # parsable elements, if the dict has to be serialized in any of those syntaxes.
        # Moreover, remember that '1:1:30' is interpreted by pyyaml as hour, which results
        # in an int (number of seconds?)
        return {name: self.fields[name].to_python(val) for name, val in self.data.items()}

    @classmethod
    def toHTML(cls):
        def small(text):
            return "<span style='color:gray;font-size=smaller'>%s</span>" % text

        thead = ["Name<br>%s" % small('Alternative name'), "Description", "Min", "Max",
                 "Optional"]
        tbody = []
        # reverse key value paris in additional fieldnames and use the reversed dict afn:
        afn = {val: key for key, val in getattr(cls, '__additional_fieldnames__', {}).items()}

        notes = []

        def addnote(text):
            '''Adds a note and returns the anchor to it'''
            for note in notes:
                if note['text'] == text:
                    return note['anchor']
            id_ = cls.__name__ + "note" + str(uuid.uuid4())
            num = len(notes) + 1
            note = {'text': text,
                    'html': '<tr><td colspan="%d" id="%s"><small>note %d: %s</small></td></tr>' %
                    (len(thead), id_, num, text),
                    'anchor': '<a href="#%s">see note %d</a>' % (id_, num)}
            notes.append(note)
            return notes[-1]['anchor']

        for name, field in cls.declared_fields.items():  # pylint: disable=no-member

            line = []
            optname = afn.get(name, '')
            line.append("%s%s" % (name, "" if not optname else '<br>%s' % small(optname)))

            typ, defval, minval, maxval = '', field.initial, \
                getattr(field, 'min_value', ''), \
                getattr(field, 'max_value', '')

            desc = "%s%s" % (field.label or '',
                             "" if not field.help_text else " (%s)" % field.help_text)

            if isinstance(field, ChoiceField):
                multi = isinstance(field, MultipleChoiceField)
                choices = OrderedDict(field.choices)
                if multi:  # if multi, asn default is 'a;;', do not print all choices
                    # in the default column:
                    if not isscalar(defval) and sorted(defval) == sorted(choices.keys()):
                        defval = 'All choosable values'

                typ = '%s choosable from' % ('One or more values' if multi else 'A value')

                if len(choices) > 30:
                    typ += ' a list of %d possible values (too long to show)' % len(choices)
                else:
                    typ += ':<br>'
                    # choices is a list of django ChoiceField values and in brackets
                    # the label used, but if the label is the same avoid printing twice the same
                    # value. Actually, relax the conditions, the equality is if the two strings
                    # are the same by replacing spaces with undeerscores and the case,
                    # so that 'A b' == 'a_b'
                    def equals(a, b):
                        return a.lower().replace(' ', '_') == b.lower().replace(' ', '_')

                    printedchoices = ['%s%s' % (k, '' if equals(v, k) else " (%s)" % v)
                                      for k, v in choices.items()]

                    if len(printedchoices) == 1:
                        typ = 'Currently, only one choice is implemented: %s' % printedchoices[0]
                    else:
                        # this might raise if printedchoices has no element, which is what we
                        # want as a ChoiceField needs choices
                        typ += ", ".join(printedchoices[:-1]) + ' or %s' % printedchoices[-1]

                desc = typ if not desc else "%s. %s" % (desc, typ)

                if isinstance(field, MultipleChoiceWildcardField):
                    desc += "<br>" + \
                        addnote('In URLs (GET request) or YAML/JSON data (POST requests), '
                                'the value can be supplied as string with special '
                                'characters e.g.:'
                                '* (meaning: zero or more characters) or '
                                '? (meaning: any single character). See '
                                '<a href="https://docs.python.org/3/library/fnmatch.html" '
                                'target="_blank">here</a> for details')

            optional = ''
            if defval is not None or not field.required:
                # &#10004; is the checkmark. Works in FF and Chrome.
                # In case of problems, type: 'Yes':
                optional = '&#10004;'
                if defval is not None:
                    optional += "<br>Default: %s" % str(defval)

            line.extend([desc,
                         '' if minval is None else str(minval),
                         '' if maxval is None else str(maxval),
                         optional])

            tbody.append("<td>%s</td>" % "</td><td>".join(line))

        return ("<table class='form-%s'><thead><tr><td>%s</td></tr></thead>"
                "<tbody><tr>%s</tr></tbody><tfoot>%s</tfoot></table>") % \
            (cls.__name__,
             "</td><td>".join(thead),
             "</tr><tr>".join(tbody),
             "".join(note['html'] for note in notes))


class GsimSelectionForm(BaseForm):
    '''Form for (t)ectonic (r)egion gsim selection from a point or rectangle.
    This form is currently only used as validator as the HTML page renderes a map.
    '''

    __additional_fieldnames__ = {'lat': 'latitude', 'lon': 'longitude', 'lat2': 'latitude2',
                                 'lon2': 'longitude2', 'gmpe': 'gsim'}

    gsim = GsimField(required=False, initial=list(EGSIM.aval_gsims.keys()))
    imt = IMTField(required=False, initial=EGSIM.aval_imts,
                   sa_periods_required=False)

    model = TrModelField(label='Tectonic region model', required=False)
    longitude = FloatField(label='Longitude', min_value=-180, max_value=180, required=False)
    latitude = FloatField(label='Latitude', min_value=-90, max_value=90, required=False)
    longitude2 = FloatField(label='Longitude 2nd point', min_value=-180, max_value=180,
                            required=False)
    latitude2 = FloatField(label='Latitude 2nd point', min_value=-90, max_value=90,
                           required=False)
    trt = TrtField(label='Tectonic region type(s)', required=False, initial=EGSIM.aval_trts)

    def clean(self):
        '''Checks that if longitude is provided, also latitude is provided, and vice versa
            (the same for longitude2 and latitude2)'''
        cleaned_data = super().clean()

        # check that params combinations are ok:
        couplings = (('latitude', 'longitude'), ('longitude2', 'latitude2'))
        for (key1, key2) in couplings:
            val1, val2 = cleaned_data.get(key1, None), cleaned_data.get(key2, None)
            if val1 is None and val2 is not None:
                # instead of raising ValidationError, which is keyed with '__all__'
                # we add the error keyed to the given field name `name` via `self.add_error`:
                # https://docs.djangoproject.com/en/2.0/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
                error = ValidationError(_("missing value"), code='missing')
                self.add_error(key1, error)
            elif val1 is not None and val2 is None:
                error = ValidationError(_("missing value"), code='missing')
                self.add_error(key2, error)

        return cleaned_data


class GsimImtForm(BaseForm):
    '''Base form for any form needing (At least) Gsim+Imt selections'''

    __additional_fieldnames__ = {'gmpe': 'gsim', 'sap': 'sa_periods'}

    # fields (not used for rendering, just for validation): required is True by default
    # FIXME: do we provide choices, as actually we are rendering the component with an
    # ajax request in vue.js?
    gsim = GsimField(widget=HiddenInput, required=True)
    imt = IMTField(widget=HiddenInput, required=True)
    sa_periods = NArrayField(label="The Spectral Acceleration (SA) period(s)",
                             required=False, widget=HiddenInput,
                             help_text=("Required only if SA is a selected "
                                        "Intensity Measure Type. Alternatively, you can "
                                        "ignore this parameter but each SA must be supplied "
                                        "with its period in parentheses, "
                                        "e.g: SA(0.1) SA(0.2)"))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # put 'sa_periods in the IMTField:
        self.fields['imt'].sa_periods = self.data.pop('sa_periods', [])

    def clean(self):
        '''runs validation where we must validate selected gsim(s) based on selected intensity
        measure type. For info see:
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
        imt_classnames = set(imt.from_string(imtname).__class__.__name__
                             for imtname in cleaned_data.get("imt", []))

        invalid_gsims = self.invalid_gsims(gsims, imt_classnames)

        if invalid_gsims:
            # instead of raising ValidationError, which is keyed with '__all__'
            # we add the error keyed to the given field name `name` via `self.add_error`:
            # https://docs.djangoproject.com/en/2.0/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
            # note: pass only invalid_gsims as the result would be equal than passing all gsims
            # but the loop is faster:
            invalid_imts = self.invalid_imts(invalid_gsims, imt_classnames)
            err_gsim = ValidationError(_("%(num)d gsim(s) not defined for all supplied "
                                         "imt(s)"),
                                       params={'num': len(invalid_gsims)}, code='invalid')
            err_imt = ValidationError(_("%(num)d imt(s) not defined for all supplied "
                                        "gsim(s)"),
                                      params={'num': len(invalid_imts)}, code='invalid')
            self.add_error('gsim', err_gsim)
            self.add_error('imt', err_imt)
        else:
            # replace Egsims objects with strings, as methods using this form/validator
            # want strings (e.g. trellis, residuals):
            cleaned_data["gsim"] = [_.name for _ in gsims]

        return cleaned_data

    @classmethod
    def invalid_imts(cls, gsims, imts):
        '''returns a *set* of all invalid imt(s) from the given selected gsims and imts

        :param gsims: iterable of Egsim objects denoting the selected gsims
        :param gsims: iterable of strings denoting the selected imts. Strings should represent
            the imt class name only, so e.g. 'SA', not 'SA(2.0)'
        :return: a set of invalid imts
        '''
        imts = set(imts)
        invalid_imts = set()
        for gsim in gsims:
            invalid_imts |= imts - gsim.imts

        return invalid_imts

    @classmethod
    def invalid_gsims(cls, gsims, imts):
        '''returns a *list* of all invalid gsim(s) from the given selected gsims and imts

        :param gsims: iterable of Egsim objects denoting the selected gsims
        :param gsims: iterable of strings denoting the selected imts
        :return: a list of invalid gsims
        '''
        if not isinstance(imts, set):
            imts = set(imts)
#         if imts == cls._aval_imts:  # as no gsim is defined for all imts, thus return the list
#             return list(gsims)
        return [gsim for gsim in gsims if imts - gsim.imts]


class TrellisForm(GsimImtForm):
    '''Form for Trellis plot generation'''

    # merge additional fieldnames (see https://stackoverflow.com/a/26853961/3526777):
    __additional_fieldnames__ = {'mag': 'magnitude', 'dist': 'distance',
                                 'tr': 'tectonic_region',
                                 'msr': 'magnitude_scalerel', 'lineazi': 'line_azimuth',
                                 'vs30m': 'vs30_measured', 'hyploc': 'hypocentre_location',
                                 **GsimImtForm.__additional_fieldnames__}

    # fields (not used for rendering, just for validation): required is True by default
#     gsim = GsimField()
#     imt = IMTField()
    plot_type = TrellisplottypeField(label='Plot type')
    # GSIM RUPTURE PARAMS:
    magnitude = NArrayField(label='Magnitude(s)', min_count=1)
    distance = NArrayField(label='Distance(s)', min_count=1)
    dip = FloatField(label='Dip', min_value=0., max_value=90.)
    aspect = FloatField(label='Rupture Length / Width', min_value=0.)
    tectonic_region = CharField(label='Tectonic Region Type',
                                initial='Active Shallow Crust', widget=HiddenInput)
    rake = FloatField(label='Rake', min_value=-180., max_value=180., initial=0.)
    ztor = FloatField(label='Top of Rupture Depth (km)', min_value=0., initial=0.)
    strike = FloatField(label='Strike', min_value=0., max_value=360., initial=0.)
    magnitude_scalerel = MsrField(label='Magnitude Scaling Relation', initial="WC1994")
    initial_point = PointField(label="Location on Earth", help_text='Longitude Latitude',
                               min_value=[-180, -90], max_value=[180, 90], initial="0 0")
    hypocentre_location = NArrayField(label="Location of Hypocentre", initial='0.5 0.5',
                                      help_text='Along-strike fraction, Down-dip fraction',
                                      min_count=2, max_count=2,
                                      min_value=[0, 0], max_value=[1, 1])
    # END OF RUPTURE PARAMS
    vs30 = NArrayField(label=mark_safe('V<sub>S30</sub> (m/s)'), min_value=0., min_count=1,
                       initial=760.0)
    vs30_measured = BooleanField(label=mark_safe('Is V<sub>S30</sub> measured?'),
                                 help_text='Otherwise is inferred', initial=True, required=False)
    line_azimuth = FloatField(label='Azimuth of Comparison Line',
                              min_value=0., max_value=360., initial=0.)
    z1pt0 = NArrayField(label=mark_safe('Depth to 1 km/s V<sub>S</sub> layer (m)'),
                        min_value=0., required=False,
                        help_text=mark_safe("If not given, it will be calculated "
                                            "from the V<sub>S30</sub>"))
    z2pt5 = NArrayField(label=mark_safe('Depth to 2.5 km/s V<sub>S</sub> layer (km)'),
                        min_value=0., required=False,
                        help_text=mark_safe("If not given, it will be calculated "
                                            "from the V<sub>S30</sub>"))
    backarc = BooleanField(label='Backarc Path', initial=False, required=False)

    def clean(self):
        cleaned_data = super(TrellisForm, self).clean()
        vs30 = cleaned_data['vs30']  # surely a list with st least one element
        vs30scalar = isscalar(vs30)
        vs30s = np.array(vectorize(vs30), dtype=float)

        # check vs30-dependent values:
        for name, func in (['z1pt0', vs30_to_z1pt0_cy14], ['z2pt5', vs30_to_z2pt5_cb14]):
            if name not in cleaned_data or cleaned_data[name] == []:
                values = func(vs30s)  # numpy-function
                cleaned_data[name] = float(values[0]) if vs30scalar else values.tolist()
            elif not isscalar(cleaned_data[name]) and not isscalar(vs30) \
                    and len(vs30) != len(cleaned_data[name]):
                # instead of raising ValidationError, which is keyed with '__all__'
                # we add the error keyed to the given field name `name` via `self.add_error`:
                # https://docs.djangoproject.com/en/2.0/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
                error = ValidationError(_("value must be scalar, empty or a %(num)d-elements "
                                          "vector"), params={'num': len(vs30)}, code='invalid')
                self.add_error(name, error)

        return cleaned_data


class GmdbForm(BaseForm):
    '''Abstract-like class for handling gmdb (GroundMotionDatabase)'''

    __additional_fieldnames__ = {'sel': 'selection', 'min': 'selection_min',
                                 'max': 'selection_max', 'dist': 'distance_type'}

    gmdb = GmdbField(label='Ground Motion database', required=True)
    selection = GmdbSelectionField(label='Filter by', required=False)
    selection_min = CharField(label='Min', required=False)
    selection_max = CharField(label='Max', required=False)
    distance_type = ChoiceField(label='Distance type', choices=zip(DISTANCES.keys(),
                                                                   DISTANCES.keys()),
                                initial='rrup')

    def clean(self):
        '''Cleans this Form checking that selection_min and selection_max parameter
        values, if provided, conform to the expected type of selection (e.g., float, datetime)'''
        cleaned_data = super().clean()
        min_, max_, sel_ = 'selection_min', 'selection_max', 'selection'
        if sel_ not in cleaned_data or not cleaned_data[sel_]:
            return cleaned_data
        conversion_func = cleaned_data[sel_]
        try:
            cleaned_data[min_] = conversion_func(cleaned_data.get(min_, None))
        except Exception as exc:  # pylint: disable=broad-except
            error = ValidationError(_(str(exc)), code='invalid')
            self.add_error(min_, error)
        try:
            cleaned_data[max_] = conversion_func(cleaned_data.get(max_, None))
        except Exception as exc:  # pylint: disable=broad-except
            error = ValidationError(_(str(exc)), code='invalid')
            self.add_error(max_, error)

        return cleaned_data


class ResidualsForm(GsimImtForm, GmdbForm):
    '''Form for residual analysis'''

    # merge additional fieldnames (see https://stackoverflow.com/a/26853961/3526777):
    __additional_fieldnames__ = {**GsimImtForm.__additional_fieldnames__,
                                 **GmdbForm.__additional_fieldnames__}

    plot_type = ResidualplottypeField(required=True)

    def clean(self):
        return GmdbForm.clean(self)
