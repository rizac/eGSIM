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

    :param data: the form input data to be serialized. The dict keys are the
        Field attribute names, which might not be the API parameter names
    :param form_class: a EgsimMBaseForm class that should process the input data
    :param syntax: string either json or yaml. Default: yaml

    :return: a StringIO with the Form input data, None if the form is not valid
    """
    if syntax not in ('yaml', 'json'):
        raise ValueError("invalid `syntax` argument in `dump`: '%s' "
                         "not in ('json', 'yam')" % syntax)

    docstrings = {}
    serializable_data = {}
    for param_names, field_name, field in form_class.apifields():
        data_keys = set(chain(param_names, [field_name])) & set(data)
        # this should never happen if the form is successfully validated, however:
        if len(data_keys) > 1:
            raise ValueError(f'Conflicting parameters: {", " .join(data_keys)}')
        elif not data_keys:
            continue
        data_key = next(iter(data_keys))  # 1st (and only) element
        param_value = data[data_key]
        # Omit unchanged optional parameters. This is not only to make
        # the dumped string more readable and light size, but to avoid
        # parameters which default to None (e.g. z1pt0 in
        # TrellisForm): if they were written here (e.g. `z1pt0: None`) then
        # a routine converting the returned JSON/YAML to a query string
        # would write "...z1pt0=null...", which might be interpreted as
        # the string "null"
        is_optional = not field.required or field.initial is not None
        if is_optional and param_value == field.initial:
            continue
        param_name = param_names[0]
        serializable_data[param_name] = param_value
        if syntax == 'yaml':
            docstrings[param_name] = get_field_docstring(field, True)

    if syntax == 'json':
        stream = _dump_json(serializable_data)
    else:
        stream = _dump_yaml(serializable_data, docstrings)
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
