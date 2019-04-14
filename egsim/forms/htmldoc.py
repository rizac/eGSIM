'''
Handles the form to html conversion, where the HTML is not the dynamic
Django HTML representation, but a sttic one documenting the form fields and
types

Created on 14 Apr 2019

@author: riccardo
'''
from collections import OrderedDict

from django.forms.fields import FloatField, BooleanField, ChoiceField, \
    MultipleChoiceField
from egsim.forms.fields import NArrayField, MultipleChoiceWildcardField
from egsim.core.utils import isscalar


def to_html_table(form_class):
    '''Converts `form_class` to a HTML-formatted string of a table with all
    necessary documentation on each field.
    The table will have a css class set to "egsim-form-parameters.
    Notes will have class 'param-notes', and alternative names the css class
    'param-alternative-name'
    '''
    altnameclass = 'param-alternative-name'
    thead = ["Name<br><span class='%s'>%s</span>" % (altnameclass,
                                                     'Alternative name'),
             "Description", "Optional"]
    tbody = []
    # reverse key value pairs in additional fieldnames and use the reversed
    # dict afn:
    afn = {val: key for key, val in getattr(form_class,
                                            '__additional_fieldnames__',
                                            {}).items()}

    notes = []

    for name, field in form_class.declared_fields.items():

        line = []
        optname = afn.get(name, '')
        line.append("%s%s" % (name, "" if not optname else
                              '<br><span class="%s">%s</span>' %
                              (altnameclass, optname)))

        defval = field.initial

        desc = "%s%s" % (field.label or '',
                         "" if not field.help_text else " (%s)" %
                         field.help_text)

        if isinstance(field, FloatField):
            desc += "<br>Type: number. " + _bounds2html(field)
        elif isinstance(field, BooleanField):
            desc += "<br>Type: boolean (true or false)"
        elif isinstance(field, NArrayField):
            desc += ("<br>Type: %s. " %
                     _numtype2str(field)) + _bounds2html(field)
        elif isinstance(field, ChoiceField):
            choicesdoc, defaults2all = _choices2str(field)
            if defaults2all:
                defval = 'All choosable values'
            desc = choicesdoc if not desc else "%s. %s" % (desc, choicesdoc)
            if isinstance(field, MultipleChoiceWildcardField):
                desc += " " + \
                    _addnote('The value can be supplied (not from the GUI) '
                             'as string with special characters e.g.:'
                             '* (matches zero or more characters) or '
                             '? (matches any single character). See <a href='
                             '"https://docs.python.org/3/library/fnmatch.html"'
                             ' target="_blank">here</a> for details', notes)

        optional = ''
        if defval is not None or not field.required:
            # &#10004; is the checkmark. Works in FF and Chrome.
            # In case of problems, replace with: 'Yes':
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
        (form_class.__name__,
         "</td>\n\t\t\t<td>".join(thead),
         "</tr>\n\t\t<tr>".join(tbody),
         "".join('<tr><td colspan="%d">%s</td></tr>' %
                 (len(thead), note['html']) for note in notes))


######################
# Private-like methods
######################


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


def _addnote(text, notes):
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


def _choices2str(choicefield):
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
        printedchoices = ['%s%s' % (k, '' if _equals(v, k) else " (%s)" % v)
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


def _equals(str1, str2):
    '''Tests equality of strings (ignoring the case). Underscore and spaces are
    considered the same character'''
    return str1.lower().replace(' ', '_') == str2.lower().replace(' ', '_')
