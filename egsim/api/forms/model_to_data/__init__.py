"""Common utilities for forms related to model-to-data operations, i.e.
involving flatfiles
"""
from io import BytesIO

# from django.core.exceptions import ValidationError
from django.forms import CharField, ModelChoiceField, FileField

from ...flatfile import (PredefinedFlatfile, Flatfile, UserFlatfile)
from .. import EgsimBaseForm
from ... import models

##########
# Fields #
##########


class PredefinedFlatfileField(ModelChoiceField):
    """ModelChoiceField returning `PredefinedFlatfile`s"""

    def __init__(self, **kwargs):
        kwargs.setdefault('queryset', models.PredefinedFlatfile.objects.all())
        kwargs.setdefault('empty_label', None)
        kwargs.setdefault('label', 'Predefined Flatfile')
        kwargs.setdefault('to_field_name', "name")
        # note: the <select> name will be set as the instance __str__ value
        super(PredefinedFlatfileField, self).__init__(**kwargs)

    def clean(self, value):
        """Converts the given value (string) into the tuple
        hf5 path, database name (both strings)"""
        value = super(PredefinedFlatfileField, self).clean(value)
        return PredefinedFlatfile(value.path)


#########
# Forms #
#########


class FlatfileForm(EgsimBaseForm):
    """Abstract-like class for handling gmdb (GroundMotionDatabase)"""

    def fieldname_aliases(self, mapping):
        """Set field name aliases (exposed to the user as API parameter aliases):
        call `super()` and then for any field alias: `mapping[new_name]=name`
        See `EgsimBaseForm.__init__` for details
        """
        super().fieldname_aliases(mapping)
        mapping['sel'] = 'selexpr'
        mapping['dist'] = 'distance_type'

    predefined_flatfile = PredefinedFlatfileField(required=False)
    selexpr = CharField(required=False, label='Selection expression')
    user_flatfile = FileField(required=False)

    def clean(self):
        """Call `super.clean()` and handles the flatfile
        """
        cleaned_data = super().clean()
        flatfile_obj: Flatfile = None

        key_u, key_p = 'user_flatfile', 'predefined_flatfile'
        if cleaned_data[key_u]:
            dtype, defaults = models.FlatfileField.get_dtype_and_defaults()
            flatfile_obj = UserFlatfile(BytesIO(cleaned_data[key_u]),
                                        dtype=dtype, defaults=defaults)
        else:
            flatfile_obj = PredefinedFlatfile(cleaned_data[key_p].path)

        selexpr = cleaned_data['sleexpr']
        if selexpr:
            flatfile_obj = flatfile_obj.query(selexpr)

        cleaned_data['flatfile'] = flatfile_obj


#############
# Utilities #
#############


class MOF:  # noqa
    # simple class emulating an Enum
    RES = 'res'
    LH = 'lh'
    LLH = "llh"
    MLLH = "mllh"
    EDR = "edr"
