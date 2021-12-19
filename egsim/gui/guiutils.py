from typing import Any, Type, Callable, Union
from collections import defaultdict
import json
import yaml
import re
from io import StringIO

from django.forms import (MultipleChoiceField, Field, CharField,
                          ChoiceField, BooleanField, FloatField, IntegerField,
                          DecimalField, ModelChoiceField)
from django.forms.widgets import ChoiceWidget, Input

from egsim.api.forms.fields import MultipleChoiceWildcardField, NArrayField

from . import TABS, URLS
from ..api.forms import APIForm, EgsimBaseForm


def get_components_properties(debugging=False) -> dict[str, dict[str, Any]]:
    """Return a dict with all the properties to be passed
    as VueJS components in the frontend

    :param debugging: if True, the components input elements will be setup
        with default values so that the frontend FORMS will be ready to
        test click buttons
    """
    def ignore_choices(field_att_name):
        return field_att_name in ('gsim', 'imt')

    # properties to be passed to vuejs components.
    # If you change THE KEYS of the dict here you should change also the
    # javascript:
    components_props = {
        TABS.home.name: {
            'src': URLS.HOME_PAGE
        },
        TABS.trellis.name: {
            'form': to_vuejs(TABS.trellis.formclass, ignore_choices),
            'url': TABS.trellis.urls[0],
            'urls': {
                # the lists below must be made of elements of
                # the form [key, url]. For each element the JS library (VueJS)
                # will then create a POST data and issue a POST request
                # at the given url (see JS code for details).
                # Convention: If url is a JSON-serialized string representing
                # the dict: '{"file": <str>, "mimetype": <str>}'
                # then we will simply donwload the POST data without calling
                # the server.
                # Otherwise, when url denotes a Django view, remember
                # that the function should build a response with
                # response['Content-Disposition'] = 'attachment; filename=%s'
                # to tell the browser to download the content.
                # (it is just for safety, remember that we do not care because
                # we will download data in AJAX calls which do not care about
                # content disposition
                'downloadRequest': [
                    [
                        'json',
                        "{0}/{1}/{1}.config.json".format(URLS.DOWNLOAD_CFG,
                                                         TABS.trellis.name)
                    ],
                    [
                        'yaml',
                        "{0}/{1}/{1}.config.yaml".format(URLS.DOWNLOAD_CFG,
                                                         TABS.trellis.name)
                    ]
                ],
                'downloadResponse': [
                    [
                        'json',
                        '{"file": "%s.json", "mimetype": "application/json"}' %
                        TABS.trellis.name
                    ],
                    [
                        'text/csv',
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT,
                                                 TABS.trellis.name)
                    ],
                    [
                        "text/csv, decimal comma",
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT_EU,
                                                 TABS.trellis.name)
                    ],
                ],
                'downloadImage': [
                    [
                        'png (visible plots only)',
                        "%s/%s.png" % (URLS.DOWNLOAD_ASIMG, TABS.trellis.name)
                    ],
                    [
                        'pdf (visible plots only)',
                        "%s/%s.pdf" % (URLS.DOWNLOAD_ASIMG, TABS.trellis.name)
                    ],
                    [
                        'eps (visible plots only)',
                        "%s/%s.eps" % (URLS.DOWNLOAD_ASIMG, TABS.trellis.name)
                    ],
                    [
                        'svg (visible plots only)',
                        "%s/%s.svg" % (URLS.DOWNLOAD_ASIMG, TABS.trellis.name)
                    ]
                ]
            }
        },
        # KEY.GMDBPLOT: {  # FIXME REMOVE
        #     'form': to_vuejs_dict(GmdbPlotView.formclass()),
        #     'url': URLS.GMDBPLOT_RESTAPI
        # },
        TABS.residuals.name: {
            'form': to_vuejs(TABS.residuals.formclass, ignore_choices),
            'url': TABS.residuals.urls[0],
            'urls': {
                # download* below must be pairs of [key, url]. Each url
                # must return a
                # response['Content-Disposition'] = 'attachment; filename=%s'
                # url can also start with 'file:///' telling the frontend
                # to simply download the data
                'downloadRequest': [
                    [
                        'json',
                        "{0}/{1}/{1}.config.json".format(URLS.DOWNLOAD_CFG,
                                                         TABS.residuals.name)],
                    [
                        'yaml',
                        "{0}/{1}/{1}.config.yaml".format(URLS.DOWNLOAD_CFG,
                                                         TABS.residuals.name)
                    ],
                ],
                'downloadResponse': [
                    [
                        'json',
                        '{"file": "%s.json", "mimetype": "application/json"}' %
                        TABS.residuals.name
                    ],
                    [
                        'text/csv',
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT,
                                                 TABS.residuals.name)
                    ],
                    [
                        "text/csv, decimal comma",
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT_EU,
                                                 TABS.residuals.name)
                    ]
                ],
                'downloadImage': [
                    [
                        'png (visible plots only)',
                        "%s/%s.png" % (URLS.DOWNLOAD_ASIMG, TABS.residuals.name)
                    ],
                    [
                        'pdf (visible plots only)',
                        "%s/%s.pdf" % (URLS.DOWNLOAD_ASIMG, TABS.residuals.name)
                    ],
                    [
                        'eps (visible plots only)',
                        "%s/%s.eps" % (URLS.DOWNLOAD_ASIMG, TABS.residuals.name)
                    ],
                    [
                        'svg (visible plots only)',
                        "%s/%s.svg" % (URLS.DOWNLOAD_ASIMG, TABS.residuals.name)
                    ]
                ]
            }
        },
        TABS.testing.name: {
            'form': to_vuejs(TABS.testing.formclass, ignore_choices),
            'url': TABS.testing.urls[0],
            'urls': {
                # download* below must be pairs of [key, url]. Each url
                # must return a
                # response['Content-Disposition'] = 'attachment; filename=%s'
                # url can also start with 'file:///' telling the frontend
                # to simply download the data
                'downloadRequest': [
                    [
                        'json',
                        "{0}/{1}/{1}.config.json".format(URLS.DOWNLOAD_CFG,
                                                         TABS.testing.name)
                    ],
                    [
                        'yaml',
                        "{0}/{1}/{1}.config.yaml".format(URLS.DOWNLOAD_CFG,
                                                         TABS.testing.name)
                    ]
                ],
                'downloadResponse': [
                    [
                        'json',
                        '{"file": "%s.json", "mimetype": "application/json"}' %
                        TABS.testing.name
                    ],
                    [
                        'text/csv',
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT,
                                                 TABS.testing.name)
                    ],
                    [
                        "text/csv, decimal comma",
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT_EU,
                                                 TABS.testing.name)
                    ]
                ]
            }
        },
        TABS.doc.name: {
            'src': URLS.DOC_PAGE
        }
    }
    if debugging:
        _configure_values_for_testing(components_props)
    return components_props


def _configure_values_for_testing(components_props: dict[str, dict[str, Any]]):
    """Set up some dict keys and subkeys so that the frontend FORM is already
    filled with test values
    """
    gsimnames = ['AkkarEtAlRjb2014', 'BindiEtAl2014Rjb', 'BooreEtAl2014',
                 'CauzziEtAl2014']
    trellisformdict = components_props['trellis']['form']
    trellisformdict['gsim']['val'] = gsimnames
    trellisformdict['imt']['val'] = ['PGA']
    trellisformdict['magnitude']['val'] = "5:7"
    trellisformdict['distance']['val'] = "10 50 100"
    trellisformdict['aspect']['val'] = 1
    trellisformdict['dip']['val'] = 60
    trellisformdict['plot']['val'] = 's'

    residualsformdict = components_props['residuals']['form']
    residualsformdict['gsim']['val'] = gsimnames
    residualsformdict['imt']['val'] = ['PGA', "SA(0.2)", "SA(1.0)", "SA(2.0)"]
    # residualsformdict['sa_period']['val'] = "0.2 1.0 2.0"
    residualsformdict['selexpr']['val'] = "magnitude > 5"
    residualsformdict['plot']['val'] = 'res'

    testingformdict = components_props['testing']['form']
    testingformdict['gsim']['val'] = gsimnames + ['AbrahamsonSilva2008']
    testingformdict['imt']['val'] = ['PGA', 'PGV', "0.2", "1.0","2.0"]
    # testingformdict['sa_period']['val'] = "0.2 1.0 2.0"

    components_props['testing']['form']['mof']['val'] = ['res', 'lh',
                                                                 # 'llh',
                                                                 # 'mllh',
                                                                 # 'edr'
                                                                 ]


def to_request_data(form: APIForm, syntax='yaml') -> StringIO:
    """Serialize this Form input (uncleaned) data into a YAML or JSON stream to
    be used as custom Request data.

    :param syntax: string either json or yaml. Default: yaml

    :return: a StringIO with the Form input data
    """
    if syntax not in ('yaml', 'json'):
        raise ValueError("invalid `syntax` argument in `dump`: '%s' "
                         "not in ('json', 'yam')" % syntax)

    data, docstrings = {}, {}
    for key, val in form.data.items():
        # Omit unchanged optional parameters. This is not only to make
        # the dumped string more readable and light size, but to avoid
        # parameters which defaults to None (e.g. z1pt0 in
        # TrellisForm): if they were written here (e.g. `z1pt0: None`) then
        # a routine converting the returned JSON/YAML to a query string
        # would write "...z1pt0=null...", which might be interpreted as
        # the string "null"
        field = form.fields[key]
        is_optional = not field.required or field.initial is not None
        if is_optional and val == field.initial:
            continue
        param_name = field.names[0]
        data[param_name] = val
        if syntax == 'yaml':
            docstrings[param_name] = get_docstring(field)

    if syntax == 'json':
        stream = _dump_json(data)
    else:
        stream = _dump_yaml(data, docstrings)
    stream.seek(0)
    return stream


# replace html tags, e.g.: "<a href='#'>X</a>" -> "X", "V<sub>s30</sub>" -> "Vs30"
_html_tags_re = re.compile('<(\\w+)(?: [^>]+|)>(.*?)</\\1>')


def get_docstring(field: Field):
    """Return a docstring from the given Form field by parsing its attributes
    `label` and `help_text`. The returned string will have no newlines
    """
    label = (field.label or '') + \
            ('' if not field.help_text else ' (%s)' % field.help_text)
    if label:
        # replace html characters with their content
        # (or empty str if no content):
        label = _html_tags_re.sub(r'\2', label)
        # replace newlines for safety:
        label = label.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')

    return label


def _dump_json(data: dict) -> StringIO:
    """Serialize to JSON. See `self.dump` or return the produced string"""
    stream = StringIO()
    json.dump(data, stream, indent=4, separators=(',', ': '), sort_keys=True)
    return stream


def _dump_yaml(data: dict, docs: dict = None) -> StringIO:
    """Serialize to YAML. See `self.dump` or return the produced string"""

    class MyDumper(yaml.SafeDumper):  # noqa
        """Force indentation of lists"""

        # For info see: https://stackoverflow.com/a/39681672
        def increase_indent(self, flow=False, indentless=False):
            return super(MyDumper, self).increase_indent(flow, False)

    stream = StringIO()

    docstrings = docs or {}
    for name, value in data.items():
        docstring = docstrings.get(name, None)
        if docstring:
            stream.write(f'# {docstring}')
            stream.write('\n')

        yaml.dump({name: value}, stream=stream, Dumper=MyDumper,
                  default_flow_style=False)
        stream.write('\n')

    return stream


# def to_vuejs_dict(form) -> dict:
#     return to_json_dict(form, ignore_choices=lambda _: _ in ('gsim', 'imt'))


def to_vuejs(form: Union[Type[EgsimBaseForm], EgsimBaseForm],
             ignore_choices: Callable[[str], bool] = None) -> dict:
    """Return a dictionary of field names mapped to their widget context.
     A widget context is in turn a dict with key and value pairs used to render
     the Field as HTML component.

    :param form: EgsimBaseForm class or object (class instance)
    :param ignore_choices: callable accepting a string (field attribute name)
        and returning True or False. If False, the Field choices will not be
        loaded and the returned dict 'choices' key will be `[]`. Useful for
        avoiding time consuming long list loading
    """

    if ignore_choices is None:
        ignore_choices = lambda _: False

    fieldattname2fieldname = defaultdict(list)
    for field_name, field_attname in form.public_field_names.items():
        fieldattname2fieldname[field_attname].append(field_name)

    formdata = {}
    field_done = set()  # keep track of Field done using their attribute name
    for field_name, field_attname in form.public_field_names.items():
        if field_attname in field_done:
            continue
        field_done.add(field_attname)

        field = form.declared_fields[field_attname]
        ret = {
            'attrs': dict(get_html_element_attrs(field), name=field_name),
            'val': None,
            'err': '',
            'initial': field.initial,
            'help': (field.help_text or "").strip(),
            'label': (field.label or "").strip(),
            'is_hidden': False,
            'choices': []
        }

        if not ignore_choices(field_attname):
            choices = getattr(field, 'choices', [])
            if isinstance(field, ModelChoiceField):
                # choices are ModeChoiceIteratorValue instances and are not
                # JSON serializable. Let's take their `value` attribute:
                choices = [(val.value, label) for (val, label) in choices]
            elif not isinstance(choices, (list, tuple)):
                # if generator or other Django element, then expand it to list:
                choices = list(choices)
            ret['choices'] = choices

        formdata[field_name] = ret

    return formdata


def get_html_element_attrs(field: Field) -> dict:
    """Return the HTML attributes of the HTMl element associated to the given
    Field. The returned dict can be used to render the field as HTML component
    client-side via JavaScript libraries.

    :param field: a Django Field
    """
    # Note: we could return the dict `field.widget.get_context` but  the patches
    # are so many that building our own dict is largely more convenient. For
    # instance, in our app we:
    # 1. Avoid loading all <option>s for Gsim and Imt (we could subclass
    #    `optgroups` in `widgets.SelectMultiple` and return [], but is clumsy)
    # 2. Remove some attributes (e.g. checkbox with the 'checked' attribute are
    #    not compatible with VueJS v-model or v-checked)
    # 3. Some Select with single choice set their initial value as list  (e.g.
    #    ['value'] instead of 'value') and I guess VueJs prefers strings.

    # All in all, instead of complex patching we provide our code here:
    widget = field.widget
    attrs = {
        # 'hidden': widget.is_hidden,
        'required': field.required,
        'disabled': False
    }
    if isinstance(field, IntegerField):  # note: FloatField inherits from IntegerField
        if field.min_value is not None:
            attrs['min'] = field.min_value
        if field.max_value is not None:
            attrs['max'] = field.max_value
        if isinstance(field, (FloatField, DecimalField)):
            attrs['step'] = 'any'  # this seems to be needed by some browsers?
        else:  # FloatField, DecimalField
            attrs['step'] = '1'

    if isinstance(widget, ChoiceWidget):
        if widget.allow_multiple_selected:
            attrs['multiple'] = True
    elif isinstance(widget, Input):
        attrs['type'] = widget.input_type

    return attrs


def to_help_dict(form: Union[Type[EgsimBaseForm], EgsimBaseForm],
                 skip: Callable[[str], bool] = None) -> dict:
    """Convert this form to a Python dict of information to be displayed as
    help/description. Each dict key is a field name, mapped to a sub-dict
    with several field properties:

    :param form: EgsimBaseForm class or object (class instance)
    :param skip: iterable of strings denoting the field names to be skipped
    """
    names_of = defaultdict(list)
    for f_name, a_name in form.public_field_names.items():
        names_of[a_name].append(f_name)
    formdata = to_vuejs(form, skip)
    for f_name, data in formdata.items():
        a_name = form.public_field_names[f_name]
        # remove unused keys for the help page:
        for key in ('attrs', 'val', 'err'):
            data.pop(key, None)
        data['name'] = f_name
        data['opt_names'] = [_ for _ in names_of[a_name] if _ != f_name]
        field = form.declared_fields[a_name]
        data['typedesc'] = field_type_description(field)
        data['is_optional'] = not field.required or field.initial is not None
    return formdata


def field_type_description(field: Field) -> str:
    """Return a human readable type description for the given field"""
    if isinstance(field, NArrayField):
        if field.min_count is not None and field.min_count > 1:
            typedesc = 'Numeric array'
        else:
            typedesc = 'Numeric or numeric array'
    elif isinstance(field, MultipleChoiceWildcardField):
        typedesc = 'String or string array'
    elif isinstance(field, MultipleChoiceField):
        typedesc = 'String array'
    elif isinstance(field, CharField):
        typedesc = 'String'
    elif isinstance(field, ChoiceField):
        typ = set(type(_[0] for _ in field.choices))
        if len(typ) != 1:
            raise ValueError(f'ChoiceField choices must be all of the same '
                             f'Python type, found: {typ}')
        if typ == str:
            typedesc = 'String'
        elif typ in (int, float):
            typedesc = 'Numeric'
        elif typ == bool:
            typedesc = 'Boolean'
        else:
            raise ValueError(f'ChoiceField choices type ({typ}) not supported')
    elif isinstance(field, BooleanField):
        typedesc = 'Boolean'
    elif isinstance(field, (IntegerField, FloatField)):
        typedesc = 'Numeric'
        minval = field.max_value
        maxval = field.min_value
        if minval is not None and maxval is None:
            typedesc += ' ≥ %d' % minval
        elif minval is None and maxval is not None:
            typedesc += ' ≤ %d' % maxval
        elif minval is not None and maxval is not None:
            typedesc += ' in [%d, %d]' % (minval, maxval)
    else:
        raise ValueError(f'No data type specified for Field {field}')
    return typedesc


# FIXME REMOVE
# def is_optional(cls, field):
#     """Return True if the given Field is optional, i.e. if it is not
#     required or its initial value is given (i.e., not None. A field initial
#     value acts as default value when missing)
#
#     :param field: a Field object or a string denoting the name of one of
#         this Form's fields
#     """
#     if isinstance(field, str):
#         field = cls.declared_fields[field]
#     return not field.required or field.initial is not None
