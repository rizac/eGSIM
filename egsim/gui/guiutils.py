from typing import Any, Iterable, Callable
from collections import defaultdict
import json
import yaml
import re
from io import StringIO

from django.forms import (MultipleChoiceField, Form, Field, CharField,
                          ChoiceField, BooleanField, FloatField, IntegerField)

from egsim.api.forms import MultipleChoiceWildcardField, NArrayField

from . import TABS, URLS


def get_components_properties(debugging=False) -> dict[str, dict[str, Any]]:
    """Return a dict with all the properties to be passed
    as VueJS components in the frontend

    :param debugging: if True, the components input elements will be setup
        with default values so that the frontend FORMS will be ready to
        test click buttons
    """
    # properties to be passed to vuejs components.
    # If you change THE KEYS of the dict here you should change also the
    # javascript:
    components_props = {
        TABS.home.name: {
            'src': URLS.HOME_PAGE
        },
        TABS.trellis.name: {
            'form': to_vuejs_dict(TABS.trellis.formclass()),
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
            'form': to_vuejs_dict(TABS.residuals.formclass()),
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
            'form': to_vuejs_dict(TABS.testing.formclass()),
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
    trellisformdict['plot_type']['val'] = 's'

    residualsformdict = components_props['residuals']['form']
    residualsformdict['gsim']['val'] = gsimnames
    residualsformdict['imt']['val'] = ['PGA', 'SA']
    residualsformdict['sa_period']['val'] = "0.2 1.0 2.0"
    residualsformdict['selexpr']['val'] = "magnitude > 5"
    residualsformdict['plot_type']['val'] = 'res'

    testingformdict = components_props['testing']['form']
    testingformdict['gsim']['val'] = gsimnames + ['AbrahamsonSilva2008']
    testingformdict['imt']['val'] = ['PGA', 'PGV']
    testingformdict['sa_period']['val'] = "0.2 1.0 2.0"

    components_props['testing']['form']['fit_measure']['val'] = ['res',
                                                                 'lh',
                                                                 # 'llh',
                                                                 # 'mllh',
                                                                 # 'edr'
                                                                 ]


def get_widgetdata(form: Form) -> Iterable[tuple[str, Field, dict]]:  # FIXME DOCSTRING
    for name in form.declared_fields:
        # little spec needed before proceeding:
        # `self.declared_fields` and `self.base_fields` are the same thing
        # (see django.forms.forms.DeclarativeFieldsMetaclass) and are
        # declared at CLASS level: modifying them applies changes to all
        # instances, thus avoid. Conversely, `self.fields[name]` is where
        # specific instance-level changes have to be made:
        # https://docs.djangoproject.com/en/2.2/ref/forms/api/#accessing-the-fields-from-the-form
        # Finally, `self[name]` creates a `BoundField` from
        # `self.fields[name]` i.e. "a Field plus data" (e.g., its initial
        # value, if given. See `__init__`). `BoundField`s is what we want
        # to use here
        boundfield = form[name]
        val = boundfield.value()
        widget = boundfield.field.widget
        attrs = boundfield.build_widget_attrs({}, widget)
        widgetdata = widget.get_context(name, val, attrs)['widget']
        yield name, widgetdata


def dump_request_data(form: Form, stream=None, syntax='yaml'):
    """Serialize this Form instance into a YAML or JSON stream.
    **The form needs to be already validated via e.g. `form.is_valid()`**.

    The result collects the fields of `self.data`, i.e., the unprocessed
    input, with one exception: if this form subclasses
    :class:`GsimImtForm`, as 'sa_period' is hidden,
    the value mapped to 'imt' will be `self.cleaned_data['imt']` and not
    `self.data['imt']`.

    :param stream: A file-like object **for text I/O** (e.g. `StringIO`),
       or None.
    :param syntax: string either json or yaml. Default: yaml

    :return: if the passed `stream` argument is None, returns the produced
        string. If the passed `stream` argument is a file-like object,
        this method writes to `stream` and returns None
    """
    if syntax not in ('yaml', 'json'):
        raise ValueError("invalid `syntax` argument in `dump`: '%s' "
                         "not in ('json', 'yam')" % syntax)

    cleaned_data = {}
    for key, val in form.data.items():
        # Omit unchanged optional parameters. This is not only to make
        # the dumped string more readable and light size, but to avoid
        # parameters which defaults to None (e.g. z1pt0 in
        # TrellisForm): if they were written here (e.g. `z1pt0: None`) then
        # a routine converting the returned JSON/YAML to a query string
        # would wrtie "...z1pt0=null...", which might be interpreted as
        # the string "null"
        field = form.fields[key]
        is_optional = not field.required or field.initial is not None
        if is_optional and val == field.initial:
            continue
        # FIXME REMOVE THIS COMMENT BELOW
        # # provide tha value given as input, not the value processed
        # # by `self.clean`, which might be not JSON or YAML serializable,
        # # with one exception: imt in GsimImtForm, becasue we might have
        # # provided the parameter `sa_periods` and thus the processed
        # # imt in `cleaned_data` is the value to return:
        # cleaned_data[key] = form.cleaned_data[key] \
        #     if key == 'imt' and isinstance(form, GsimImtForm) else val

    if syntax == 'json':
        return _dump_json(form, stream, cleaned_data)

    return _dump_yaml(form, stream, cleaned_data)


def _dump_json(form: Form, stream, cleaned_data: dict):  # pylint: disable=no-self-use
    """Serialize to JSON. See `self.dump`"""
    # compatibility with yaml dump if stream is None:
    if stream is None:
        return json.dumps(cleaned_data, indent=4,
                          separators=(',', ': '), sort_keys=True)
    json.dump(cleaned_data, stream, indent=4, separators=(',', ': '),
              sort_keys=True)
    return None


def _dump_yaml(form: Form, stream, cleaned_data: dict):
    """Serialize to YAML. See `self.dump`"""

    class MyDumper(yaml.SafeDumper):  # noqa
        """Force indentation of lists"""

        # For info see: https://stackoverflow.com/a/39681672
        def increase_indent(self, flow=False, indentless=False):
            return super(MyDumper, self).increase_indent(flow, False)

    # regexp to replace html entities with their content, i.e.:
    # <a href='#'>bla</a> -> bla
    # V<sub>s30</sub> -> Vs30
    # ... and so on ...
    html_tags_re = re.compile('<(\\w+)(?: [^>]+|)>(.*?)<\\/\\1>')

    # inject comments in yaml by using the field label and its help:
    stringio = StringIO() if stream is None else stream
    for name, value in cleaned_data.items():
        field = form.declared_fields[name]
        label = (field.label or '') + \
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


def to_vuejs_dict(form) -> dict:
    return to_json_dict(form, ignore_choices=lambda _: _ in ('gsim', 'imt'))


def to_json_dict(form: Form,
                 skip: Callable[[str], bool] = None,
                 ignore_choices: Callable[[str], bool] = None) -> dict:
    """Convert this form to a Python dict which can be injected in the HTML and
    processed via JavaScript: each Field name is mapped to a dict of keys such
    as 'val' (the value), 'help' (the help text), 'label' (the label text),
    'err': (the error text), 'attrs' (a dict of HTML element attributes),
    'choices' (the list of available choices, see argument
    `ignore_callable_choices`).

    :param skip: iterable of strings denoting the field names to be skipped
    :param aliases: dict of field name aliases mapped to a form field name

    :param ignore_callable_choices: handles the 'choices' for fields
        defining it as CallableChoiceIterator: if True (the default) the
        function is not evaluated and the choices are simply set to [].
        If False, the choices function will be evaluated.
        Use True when the choices list is too big and you do not need
        this additional overhead
    """

    if skip is None:
        skip = lambda _: False
    if ignore_choices is None:
        ignore_choices = lambda _: False

    formdata = {}
    for name, widgetdata in get_widgetdata(form):
        if skip(name):
            continue
        field = form[name]

        val = field.value()
        if isinstance(field, MultipleChoiceField) and not val:
            val = []

        if ignore_choices(name):
            choices = []
        else:
            choices = getattr(field, 'choices', [])
            if not isinstance(choices, (list, tuple)):
                choices = list(choices)

        formdata[name] = {
            'name': name,
            'val': val,
            'err': '',
            'help': field.help_text,
            'label': field.label,
            'initial': field.initial,
            'is_hidden': widgetdata.get('is_hidden', False),
            'attrs': {
                'type': widgetdata.get('type', field.widget_type),
                'id': field.auto_id,
                'required': widgetdata.get('required', False),
                'disabled': False,
                **widgetdata.get('attrs', {}),
                'name': name,  # at last: it must override widgetdata's
            },
            'choices': choices
        }

    return formdata


def to_help_dict(form: Form,
                 skip: Callable[[str], bool] = None,
                 aliases: dict[str, str] = None) -> dict:
    """Convert this form to a Python dict which can be injected in the HTML and
    processed via JavaScript: each Field name is mapped to a dict of keys such
    as 'val' (the value), 'help' (the help text), 'label' (the label text),
    'err': (the error text), 'attrs' (a dict of HTML element attributes),
    'choices' (the list of available choices, see argument
    `ignore_callable_choices`).

    :param skip: iterable of strings denoting the field names to be skipped
    :param aliases: dict of field name aliases mapped to a form field name

    :param ignore_callable_choices: handles the 'choices' for fields
        defining it as CallableChoiceIterator: if True (the default) the
        function is not evaluated and the choices are simply set to [].
        If False, the choices function will be evaluated.
        Use True when the choices list is too big and you do not need
        this additional overhead
    """
    aliases = aliases or {}
    optional_names = defaultdict(list)
    for key, val in aliases.items():
        optional_names[val].append(key)
    formdata = to_json_dict(form, skip)
    for name, data in formdata.items():
        data['opt_names'] = optional_names.get(name, [])
        field = form.declared_fields[name]
        data['typedesc'] = _type_description(field)
        data['is_optional'] = not field.required or field.initial is not None
    return formdata


def _type_description(field):
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
    elif isinstance(field, (CharField, ChoiceField)):
        typedesc = 'String'
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
        raise ValueError(f'Specify the Field data type in module {__name__} '
                         f'(Field: {field})')
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


# def to_vuejs_dict(form: Form, ignore_callable_choices=True,
#                   skip: Iterable[str] = None, aliases: dict[str, str] = None) -> dict:
#     """Convert this form to a Python dict which can be injected in the HTML and
#     processed via JavaScript: each Field name is mapped to a dict of keys such
#     as 'val' (the value), 'help' (the help text), 'label' (the label text),
#     'err': (the error text), 'attrs' (a dict of HTML element attributes),
#     'choices' (the list of available choices, see argument
#     `ignore_callable_choices`).
#
#     :param skip: iterable of strings denoting the field names to be skipped
#     :param aliases: dict of field name aliases mapped to a form field name
#
#     :param ignore_callable_choices: handles the 'choices' for fields
#         defining it as CallableChoiceIterator: if True (the default) the
#         function is not evaluated and the choices are simply set to [].
#         If False, the choices function will be evaluated.
#         Use True when the choices list is too big and you do not need
#         this additional overhead
#     """
#     # import here stuff used only in this method:
#     from collections import defaultdict
#
#     hidden_fn = set(skip or [])
#     aliases = aliases or {}
#     formdata = {}
#     # aliases = {}
#     # self.fieldname_aliases(aliases)
#     optional_names = defaultdict(list)
#     for key, val in aliases.items():
#         optional_names[val].append(key)
#     for name, field in form.declared_fields.items():  # pylint: disable=no-member
#         # little spec needed before proceeding:
#         # `self.declared_fields` and `self.base_fields` are the same thing
#         # (see django.forms.forms.DeclarativeFieldsMetaclass) and are
#         # declared at CLASS level: modifying them applies changes to all
#         # instances, thus avoid. Conversely, `self.fields[name]` is where
#         # specific instance-level changes have to be made:
#         # https://docs.djangoproject.com/en/2.2/ref/forms/api/#accessing-the-fields-from-the-form
#         # Finally, `self[name]` creates a `BoundField` from
#         # `self.fields[name]` i.e. "a Field plus data" (e.g., its initial
#         # value, if given. See `__init__`). `BoundField`s is what we want
#         # to use here
#         boundfield = form[name]
#         val = boundfield.value()
#         widget = boundfield.field.widget
#         attrs = boundfield.build_widget_attrs({}, widget)
#         widgetdata = widget.get_context(name, val, attrs)['widget']
#         attrs = dict(widgetdata.pop('attrs', {}))
#         if 'type' in widgetdata:
#             attrs['type'] = widgetdata.pop('type')
#         if 'required' in widgetdata:
#             attrs['required'] = widgetdata.pop('required')
#         if 'id' not in attrs:
#             attrs['id'] = boundfield.auto_id
#         attrs['name'] = widgetdata.pop('name')
#         # coerce val to [] in case val falsy and multichoice:
#         if isinstance(field, MultipleChoiceField) and not val:
#             val = []
#         # type description:
#         fielddata = {  # noqa
#             'name': attrs['name'],
#             'opt_names': optional_names.get(name, []),
#             # 'is_optional': self.is_optional(name),
#             'help': boundfield.help_text,
#             'label': boundfield.label,
#             'attrs': attrs,
#             'err': '',
#             'is_hidden': widgetdata.pop('is_hidden',
#                                         False) or name in hidden_fn,
#             'val': val,
#             'initial': field.initial,
#             'typedesc': EgsimBaseForm._type_description(field,
#                                                         attrs.get('min', None),
#                                                         attrs.get('max', None))
#         }
#         fielddata['choices'] = getattr(field, 'choices', [])
#         if isinstance(fielddata['choices'], CallableChoiceIterator):
#             if ignore_callable_choices:
#                 fielddata['choices'] = []
#             else:
#                 fielddata['choices'] = list(fielddata['choices'])
#         formdata[name] = fielddata
#     return formdata
