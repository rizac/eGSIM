"""Forms input data serialization into YAML or JSON"""
from itertools import chain
from typing import Type
import json
import yaml

from io import StringIO

from ..api.forms import EgsimBaseForm
from ..api.forms.fields import get_field_docstring


def as_text(data: dict, form_class: Type[EgsimBaseForm], syntax='json') -> StringIO:
    """Serialize `data` into a YAML or JSON stream that can be saved to file
    in order to perform POST Requests from client code.
    NOTE: This method should b executed only if `form_class(data).is_valid()`
    returns True

    :param data: the form input data to be serialized
    :param form_class: a EgsimMBaseForm class that should process the input data
    :param syntax: string either json or yaml. Default: yaml

    :return: a StringIO with the Form input data, None if the form is not valid
    """
    if syntax not in ('yaml', 'json'):
        raise ValueError("invalid `syntax` argument in `dump`: '%s' "
                         "not in ('json', 'yam')" % syntax)

    docstrings = {}
    for param_names, field_name, field in form_class.apifields():
        data_pnames = set(chain(param_names, [field_name]))
        # this should never happen if the form is successfully validated, however:
        if len(data_pnames) > 1:
            raise ValueError(f'Conflicting parameters: {", " .join(data_pnames)}')
        elif not data_pnames:
            continue
        param_name = data_pnames[0]
        # Omit unchanged optional parameters. This is not only to make
        # the dumped string more readable and light size, but to avoid
        # parameters which default to None (e.g. z1pt0 in
        # TrellisForm): if they were written here (e.g. `z1pt0: None`) then
        # a routine converting the returned JSON/YAML to a query string
        # would write "...z1pt0=null...", which might be interpreted as
        # the string "null"
        is_optional = not field.required or field.initial is not None
        if is_optional and data[param_name] == field.initial:
            data.pop(param_name)
        elif syntax == 'yaml':
            docstrings[param_name] = get_field_docstring(field, True)

    if syntax == 'json':
        stream = _dump_json(data)
    else:
        stream = _dump_yaml(data, docstrings)
    stream.seek(0)

    return stream


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
