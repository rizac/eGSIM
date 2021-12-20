"""Form Fields tools"""

import re

from django.forms import (Field, IntegerField, ModelChoiceField)
from django.forms.widgets import ChoiceWidget, Input


def get_docstring(field_label: str, field_help_text: str, remove_html_tags=False):
    """Return a docstring from the given Form field by parsing its attributes
    `label` and `help_text`. The returned string will have no newlines
    """
    label = (field_label or '') + \
            ('' if not field_help_text else f' ({field_help_text})')
    if label and remove_html_tags:
        # replace html tags, e.g.: "<a href='#'>X</a>" -> "X",
        # "V<sub>s30</sub>" -> "Vs30"
        _html_tags_re = re.compile('<(\\w+)(?: [^>]+|)>(.*?)</\\1>')
        # replace html characters with their content
        # (or empty str if no content):
        label = _html_tags_re.sub(r'\2', label)

    # replace newlines for safety:
    label = label.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')

    return label


def field_to_dict(field: Field, ignore_choices: bool = False) -> dict:
    """Convert a Field to a JSON serializable dict with keys:
    {
        'initial': field.initial,
        'help': (field.help_text or "").strip(),
        'label': (field.label or "").strip(),
        'is_hidden': False,
        'choices': field.choices
    }

    :param field: a Django Field
    :param ignore_choices: boolean. If True, 'chocies' will be not evaluated
        and set to `[]`. Useful with long lists for saving time and space
    """

    choices = []

    if not ignore_choices:
        choices = list(get_choices(field))

    return {
        'initial': field.initial,
        'help': (field.help_text or "").strip(),
        'label': (field.label or "").strip(),
        'is_hidden': False,
        'choices': choices
    }


def get_choices(field: Field):
    """Yields tuples (value, label) corresponding to the field choices"""
    if isinstance(field, ModelChoiceField):
        # choices are ModeChoiceIteratorValue instances and are not
        # JSON serializable. Let's take their `value` attribute:
        for (val, label) in field.choices:
            yield val.value, label
    else:
        yield from getattr(field, 'choices', [])


def field_to_htmlelement_attrs(field: Field) -> dict:
    """Convert a Field to a JSON serializable dict with keys denoting the
    attributes of the associated HTML Element, e.g.:
    {'type', 'required', 'disabled', 'min' 'max', 'multiple'}
    and values inferred from the Field

    :param field: a Django Field
    """
    # Note: we could return the dict `field.widget.get_context` but we build our
    # own for several reaaons, e.g.:
    # 1. Avoid loading all <option>s for Gsim and Imt (we could subclass
    #    `optgroups` in `widgets.SelectMultiple` and return [], but it's clumsy)
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
        # The step attribute seems to be needed by some browsers:
        if field.__class__.__name__ == IntegerField.__name__:
            attrs['step'] = '1'  # IntegerField
        else:  # FloatField or DecimalField.
            attrs['step'] = 'any'

    if isinstance(widget, ChoiceWidget):
        if widget.allow_multiple_selected:
            attrs['multiple'] = True
    elif isinstance(widget, Input):
        attrs['type'] = widget.input_type

    return attrs
