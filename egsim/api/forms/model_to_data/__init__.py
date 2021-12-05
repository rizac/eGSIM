"""Common utilities for forms related to model-to-data operations, i.e.
involving flatfiles
"""
from io import BytesIO

from django.core.exceptions import ValidationError
from django.forms import CharField, ModelChoiceField, FileField
from django.utils.translation import gettext

from ...flatfile import (PredefinedFlatfile, UserFlatfile)
from .. import EgsimBaseForm
from ... import models


class FlatfileForm(EgsimBaseForm):
    """Abstract-like class for handling Flatfiles (either pre- or user-defined)"""

    def fieldname_aliases(self, mapping):
        """Set field name aliases (exposed to the user as API parameter aliases):
        call `super()` and then for any field alias: `mapping[new_name]=name`
        See `EgsimBaseForm.__init__` for details
        """
        super().fieldname_aliases(mapping)
        mapping['sel'] = 'selexpr'
        mapping['dist'] = 'distance_type'

    predefined_flatfile = ModelChoiceField(queryset=models.PredefinedFlatfile.objects.all(),
                                           empty_label=None, label='Predefined Flatfile',
                                           to_field_name="name", required=False)
    selexpr = CharField(required=False, label='Selection expression')
    user_flatfile = FileField(required=False)

    def clean(self):
        """Call `super.clean()` and handles the flatfile
        """
        cleaned_data = EgsimBaseForm.clean(self)

        key_u, key_p = 'user_flatfile', 'predefined_flatfile'
        u_ff = cleaned_data.get(key_u, None)
        p_ff = cleaned_data.get(key_p, None)
        if bool(p_ff) == bool(u_ff):
            # instead of raising ValidationError, which is keyed with
            # '__all__' we add the error keyed to the given field name
            # `name` via `self.add_error`:
            err_ff = ValidationError(gettext("%(key_u)s and %(key_p)s are both "
                                             "missing or both given, only one "
                                             "is required and allowed"),
                                             params={'key_u': key_u,
                                                     "key_p": key_p},
                                             code='invalid')
            # add_error removes also the field from self.cleaned_data:
            self.add_error(key_p, err_ff)
            self.add_error(key_u, err_ff)
            return cleaned_data

        if u_ff:
            dtype, defaults = models.FlatfileColumn.get_dtype_and_defaults()
            flatfile_obj = UserFlatfile(BytesIO(u_ff), dtype=dtype,
                                        defaults=defaults)
        else:
            flatfile_obj = PredefinedFlatfile(p_ff.path)

        selexpr = cleaned_data['selexpr']
        if selexpr:
            flatfile_obj = flatfile_obj.filter(selexpr)

        cleaned_data['flatfile'] = flatfile_obj
        return cleaned_data


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
