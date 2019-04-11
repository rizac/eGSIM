'''
Django Forms for eGSIM

Created on 29 Jan 2018

@author: riccardo
'''

import re
import sys
import os
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
from django.forms.widgets import RadioSelect, CheckboxSelectMultiple, CheckboxInput
from django.forms.fields import BooleanField, CharField, FloatField, \
    ChoiceField, MultipleChoiceField

from openquake.hazardlib.imt import from_string as imt_from_string
from smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14
from smtk.database_visualiser import DISTANCES

from egsim.core.utils import vectorize, EGSIM, isscalar, yaml_load, querystring, tostr
from egsim.forms.fields import NArrayField, IMTField, TrellisplottypeField, MsrField, \
    PointField, TrtField, GmdbField, ResidualplottypeField, GmdbSelectionField, GsimField, \
    TrModelField, MultipleChoiceWildcardField
from egsim.models import aval_imts, aval_gsims, sharing_gsims, shared_imts


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

    def clean(self):
        '''Checks that if longitude is provided, also latitude is provided, and vice versa
            (the same for longitude2 and latitude2)'''
        cleaned_data = super().clean()
        # django sets all values provided in self.declared_fields with a
        # default if the field is not provided, usually falsy
        # (e.g. [] for MultipleChoiceField. See django.forms.Form._clean_fields)
        # If the field is required, this behaviour allows to set the 'missing'
        # error (see e.g. MultipleChoiceField.validate), but if the field
        # is not required, we want simply the field to be missing, not having
        # a value set. Hence:
        for key in list(_ for _ in cleaned_data if _ not in self.data):
            cleaned_data.pop(key)

        return cleaned_data

    def customize_widget_attrs(self):
        '''customizes the widget attributes'''
        # this method is no-op, as we delegate the view (frontend)
        # to set the custom attributes
        return
        # Old colde:
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
        """Serialize this Form instance into a YAML, JSON or URL query stream.
           If stream is None, return the produced string instead.

           :param stream: A stream **for text I/O** like a file-like object (in general any
               object with a write method, e.g. StringIO) or None.
           :param syntax: string, either 'json', 'yaml' or 'GET'. If not either string, this
                method raises ValueError
        """
        syntax = syntax.lower()
        if syntax not in ('json', 'yaml'):
            raise ValueError("Form serialization syntax must be 'json' or 'yaml'")

        obj = self.to_dict()

        if syntax == 'GET':  # GET
            querystr = querystring(obj)
            if stream is None:
                return querystr
            else:
                stream.write(querystr)
        elif syntax == 'json':  # JSON
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
        corresponding django Field. Note that for lists, the original value is checked and,
        if string and contains the colon ':', it indicates a range and thus is returned
        as it was. Also, datetimes are quoted in ISO format as json might not support them.

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

    def to_rendering_dict(self):
        '''Converts this form to a python dict for rendering the field as input
        in the frontend, free from django limiitation and allowing it to use wuth custom
        frontend libraries such as Vuejs or AngularJS: each Field name is mapped to
        a dict of keys such as 'val' (the value), 'help' (the help text),
        'label' (the label text), 'err': (the error text), 'attrs' (a dict
        of attributes), 'choices' (empty list if not ChoiceField, otherwise
        the list of available choices). 'gsim' and 'imt' will have choices set
        to the empty list to avoid injecting too much data redundantly
        (in case of several components) in the HTML template: it is the client library
        responsible to set the vailable choices (See Javascript code)
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
            formdata[name] = fielddata
        return formdata

    @classmethod
    def toHTML(cls):
        '''Converts this form to an HTML table with all necessary documentation on each field.
        The table will have a css class set to "egsim-form-parameters. Notes will have
        class 'param-notes', and alternative names the css class 'param-alternative-name'"
        '''
        altnameclass = 'param-alternative-name'
        thead = ["Name<br><span class='%s'>%s</span>" % (altnameclass, 'Alternative name'),
                 "Description", "Optional"]
        tbody = []
        # reverse key value pairs in additional fieldnames and use the reversed dict afn:
        afn = {val: key for key, val in getattr(cls, '__additional_fieldnames__', {}).items()}

        notes = []

        for name, field in cls.declared_fields.items():  # pylint: disable=no-member

            line = []
            optname = afn.get(name, '')
            line.append("%s%s" % (name, "" if not optname else
                                  '<br><span class="%s">%s</span>' % (altnameclass, optname)))

            defval = field.initial

            desc = "%s%s" % (field.label or '',
                             "" if not field.help_text else " (%s)" % field.help_text)

            if isinstance(field, FloatField):
                desc += "<br>Type: number. " + cls._bounds2html(field)
            elif isinstance(field, BooleanField):
                desc += "<br>Type: boolean (true or false)"
            elif isinstance(field, NArrayField):
                desc += ("<br>Type: %s. " % cls._numtype2str(field)) + cls._bounds2html(field)
            elif isinstance(field, ChoiceField):
                choicesdoc, defaults2all = cls._choices2str(field)
                if defaults2all:
                    defval = 'All choosable values'
                desc = choicesdoc if not desc else "%s. %s" % (desc, choicesdoc)
                if isinstance(field, MultipleChoiceWildcardField):
                    desc += " " + \
                        cls._addnote('The value can be supplied (not from the GUI) '
                                     'as string with special characters e.g.:'
                                     '* (matches zero or more characters) or '
                                     '? (matches any single character). See '
                                     '<a href="https://docs.python.org/3/library/fnmatch.html" '
                                     'target="_blank">here</a> for details', notes)

            optional = ''
            if defval is not None or not field.required:
                # &#10004; is the checkmark. Works in FF and Chrome.
                # In case of problems, type: 'Yes':
                optional = '&#10004;'
                if defval is not None:
                    optional += "<br><span style='white-space:nowrap'>Default: %s</span>" % \
                        (str(defval).lower() if isinstance(defval, bool) else str(defval))

            line.extend([desc, optional])

            tbody.append("<td>%s</td>" % "</td><td>".join(line))

        return ("<table class='egsim-form-parameters egsim-form-%s'>"
                "\n\t<thead>\n\t\t<tr>\n\t\t\t<td>%s</td>\n\t\t</tr>\n\t</thead>"
                "\n\t<tbody>\n\t\t<tr>%s</tr>\n\t</tbody>"
                "\n\t<tfoot>%s</tfoot>"
                "\n</table>\n") % \
            (cls.__name__,
             "</td>\n\t\t\t<td>".join(thead),
             "</tr>\n\t\t<tr>".join(tbody),
             "".join('<tr><td colspan="%d">%s</td></tr>' % (len(thead), note['html'])
                     for note in notes))

    @classmethod
    def parnames(cls):
        '''returns an object where attributes are ALL parameters found on any Form of this
        module'''
        ret = OrderedDict()
        thismodule = sys.modules[__name__]
        for name in dir(thismodule):
            obj = thismodule.__dict__[name]
            try:
                if issubclass(obj, cls):
                    ret[obj.__name__.lower()] = \
                        {key: {"name": key, "label": field.label, "help": field.help_text,
                               'choices': [{'name': n, 'label': l}
                                           for n, l in getattr(field, 'choices', [])]}
                         for key, field in obj.declared_fields.items()}
            except:
                pass
        return ret
    ################################################################################
    # Below private methods used in tohtml above to break it into multiple functions
    ################################################################################

    @staticmethod
    def _bounds2html(field):
        '''returns a field bounds to html text'''
        ret = ''
        minval, maxval = getattr(field, 'min_value', None), getattr(field, 'max_value', None)
        if minval is not None:
            ret += '%s: ' % ('Min' if isscalar(minval) else 'Minima')
            ret += str(minval)
        if maxval is not None:
            ret += '%s%s: ' % ('' if minval is None else '. ',
                               'Max' if isscalar(maxval) else 'Maxima')
            ret += str(maxval)
        return ret

    @classmethod
    def _addnote(cls, text, notes):
        '''Adds a note and returns the anchor to it. `notes` is an array populated with added
        notes'''
        for note in notes:
            if note['text'] == text:
                return note['anchor']
        num = len(notes) + 1
        notesclass = 'param-notes'
        note = {'text': text,
                'html': '<div class="%s">note %d: %s</div>' %
                (notesclass, num, text),
                'anchor': '<sup class="%s">see note %d</sup>' % (notesclass, num)}
        notes.append(note)
        return notes[-1]['anchor']

    @staticmethod
    def _numtype2str(narrayfield):
        '''NArrayField type to string'''
        min_count, max_count = getattr(narrayfield, 'min_count', None),\
            getattr(narrayfield, 'max_count', None)
        if min_count == max_count == 1:
            numtype = 'number'
        elif min_count is not None and min_count == max_count:
            numtype = 'numeric array of %d values' % min_count
        elif min_count is not None and max_count is not None:
            numtype = 'numeric array of %d to %d values' % (min_count, max_count)
        else:
            numtype = 'number, numeric array or range'
        return numtype

    @classmethod
    def _choices2str(cls, choicefield):
        '''Returns a choicefield description of all choices, and a boolean indicating if its
        default value is: take possible choices'''
        multi = isinstance(choicefield, MultipleChoiceField)
        choices = OrderedDict(choicefield.choices)
        choicesdoc = '%s choosable from' % ('One or more values' if multi else 'A value')

        if len(choices) > 30:
            choicesdoc += ' a list of %d possible values (too long to show)' % \
                len(choices)
        else:
            choicesdoc += ': '
            # choices is a list of django ChoiceField values and in brackets
            # the label used, but if the label is the same avoid printing twice the same
            # value. Actually, relax the conditions, the equality is if the two strings
            # are the same by replacing spaces with undeerscores and the case,
            # so that 'A b' == 'a_b'. So call cls._equals which does this:
            printedchoices = ['%s%s' % (k, '' if cls._equals(v, k) else " (%s)" % v)
                              for k, v in choices.items()]

            if len(printedchoices) == 1:
                choicesdoc = 'Currently, only one choice is implemented: %s' % \
                    printedchoices[0]
            else:
                # this might raise if printedchoices has no element, which is what we
                # want as a ChoiceField needs choices
                choicesdoc += ", ".join(printedchoices[:-1]) + \
                    ' or %s' % printedchoices[-1]

        defval = choicefield.initial
        return choicesdoc, \
            multi and not isscalar(defval) and sorted(defval) == sorted(choices.keys())

    @staticmethod
    def _equals(str1, str2):
        '''Tests equality of strings (ignoring the case). Underscore and spaces are
        considered the same character''' 
        return str1.lower().replace(' ', '_') == str2.lower().replace(' ', '_')


class GsimSelectionForm(BaseForm):
    '''Form for (t)ectonic (r)egion gsim selection from a point or rectangle.
    This form is currently only used as validator as the HTML page renderes a map.
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


    def __init__(self, *args, **kwargs):
        '''Overrides init to set default values for gsim and imt'''
        super(GsimSelectionForm, self).__init__(*args, **kwargs)
        # Set gsim and imt default.
        # This could be accomplished by simply setting the 'initial' argument
        # in the class-level attributes `gsim` and `imt` (see above), but it would
        # force by design the injection of large amount of data into the html template.
        # Note also that we need to provide the defaults HERE and not in clean() because we
        # have to force GsimField to convert its selected values to string-like
        # classes (see fields.py)
#         for key, val in (('gsim', aval_gsims), ('imt', aval_imts)):
#             if self.data.get(key, self.fields[key].initial) == self.fields[key].initial:
#                 self.data[key] = list(val())  # Django MultiChoiceField accepts lists or tuples

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
    gsim = GsimField(required=True)
    imt = IMTField(required=True)
    sa_periods = NArrayField(label="The Spectral Acceleration (SA) period(s)",
                             required=False,
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
        imt_classnames = set(imt_from_string(imtname).__class__.__name__
                             for imtname in cleaned_data.get("imt", []))

        if gsims and imt_classnames:
            invalid_gsims = set(gsims) - set(sharing_gsims(imt_classnames))

            if invalid_gsims:
                # instead of raising ValidationError, which is keyed with '__all__'
                # we add the error keyed to the given field name `name` via `self.add_error`:
                # https://docs.djangoproject.com/en/2.0/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
                # note: pass only invalid_gsims as the result would be equal than passing all gsims
                # but the loop is faster:
                invalid_imts = set(imt_classnames) - set(shared_imts(gsims))
                err_gsim = ValidationError(_("%(num)d gsim(s) not defined for all supplied "
                                             "imt(s)"),
                                           params={'num': len(invalid_gsims)}, code='invalid')
                err_imt = ValidationError(_("%(num)d imt(s) not defined for all supplied "
                                            "gsim(s)"),
                                          params={'num': len(invalid_imts)}, code='invalid')
                self.add_error('gsim', err_gsim)
                self.add_error('imt', err_imt)

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


class TrellisForm(GsimImtForm):
    '''Form for Trellis plot generation'''

    # merge additional fieldnames (see https://stackoverflow.com/a/26853961/3526777):
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
    vs30 = NArrayField(label=mark_safe('V<sub>S30</sub> (m/s)'), min_value=0., min_count=1,
                       initial=760.0)
    aspect = FloatField(label='Rupture Length / Width', min_value=0.)
    dip = FloatField(label='Dip', min_value=0., max_value=90.)
    # FIXME: removed field below, it is not used. Should we add it in clean (see below)?
#     tectonic_region = CharField(label='Tectonic Region Type',
#                                 initial='Active Shallow Crust', widget=HiddenInput)
    rake = FloatField(label='Rake', min_value=-180., max_value=180., initial=0.)
    strike = FloatField(label='Strike', min_value=0., max_value=360., initial=0.)
    ztor = FloatField(label='Top of Rupture Depth (km)', min_value=0., initial=0.)
    magnitude_scalerel = MsrField(label='Magnitude Scaling Relation', initial="WC1994")
    initial_point = PointField(label="Location on Earth", help_text='Longitude Latitude',
                               min_value=[-180, -90], max_value=[180, 90], initial="0 0")
    hypocentre_location = NArrayField(label="Location of Hypocentre", initial='0.5 0.5',
                                      help_text='Along-strike fraction, Down-dip fraction',
                                      min_count=2, max_count=2,
                                      min_value=[0, 0], max_value=[1, 1])
    # END OF RUPTURE PARAMS
    vs30_measured = BooleanField(label=mark_safe('Is V<sub>S30</sub> measured?'),
                                 help_text='Otherwise is inferred', initial=True, required=False)
    line_azimuth = FloatField(label='Azimuth of Comparison Line',
                              min_value=0., max_value=360., initial=0.)
    z1pt0 = NArrayField(label=mark_safe('Depth to 1 km/s V<sub>S</sub> layer (m)'),
                        min_value=0., required=False,
                        help_text=mark_safe("Calculated from the "
                                            "V<sub>S30</sub> if not given"))
    z2pt5 = NArrayField(label=mark_safe('Depth to 2.5 km/s V<sub>S</sub> layer (km)'),
                        min_value=0., required=False,
                        help_text=mark_safe("Calculated from the  "
                                            "V<sub>S30</sub> if not given"))
    backarc = BooleanField(label='Backarc Path', initial=False, required=False)

    def clean(self):
        cleaned_data = super(TrellisForm, self).clean()
        # cleaned_data['tectonic_region'] = 'Active Shallow Crust'  # see FIXME above
        # calculate z1pt0 and z2pt5 if needed, raise in case of errors:
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
    selection_min = CharField(label='Min', required=False,
                              help_text='The type of value depends on the selection')
    selection_max = CharField(label='Max', required=False,
                              help_text='The type of value depends on the selection')
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
        seldomain, conversion_func = cleaned_data[sel_]
        try:
            cleaned_data[min_] = conversion_func(cleaned_data.get(min_, None))
        except Exception as exc:  # pylint: disable=broad-except
            error = ValidationError(_(str(exc)), code='invalid')
            self.add_error(min_, error)
        try:
            cleaned_data[  max_] = conversion_func(cleaned_data.get(max_, None))
        except Exception as exc:  # pylint: disable=broad-except
            error = ValidationError(_(str(exc)), code='invalid')
            self.add_error(max_, error)

        cleaned_data[sel_] = seldomain  # replace the conversion function with the selection
        # domain, we will need only that one
        return cleaned_data


class ResidualsForm(GsimImtForm, GmdbForm):
    '''Form for residual analysis'''

    # merge additional fieldnames (see https://stackoverflow.com/a/26853961/3526777):
    __additional_fieldnames__ = {**GsimImtForm.__additional_fieldnames__,
                                 **GmdbForm.__additional_fieldnames__}

    plot_type = ResidualplottypeField(required=True)

    def clean(self):
        GsimImtForm.clean(self)  # <- this calls super WHICH CALLS: GmdbForm.clean(self) CHECK!!
