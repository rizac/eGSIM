"""Base eGSIM forms"""
from __future__ import annotations

from django.db.models import QuerySet
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.imt import IMT
from typing import Any
from enum import StrEnum

from shapely.geometry import Point, shape
from django.forms import Form
from django.forms.renderers import BaseRenderer
from django.forms.forms import DeclarativeFieldsMetaclass  # noqa
from django.forms.fields import Field, FloatField

from egsim.api import models
from egsim.smtk import (validate_inputs, harmonize_input_gsims, harmonize_input_imts)
from egsim.smtk.flatfile import FlatfileMetadata
from egsim.smtk.registry import gsim_info
from egsim.smtk.validation import IncompatibleModelImtError, ImtError, ModelError

_base_singleton_renderer = BaseRenderer()  # singleton no-op renderer, see below


def get_base_singleton_renderer(*a, **kw) -> BaseRenderer:  # noqa
    """Default renderer instance (see "FORM_RENDERER" in the settings file and
    `django.forms.forms.Form` or `django.forms.utils.ErrorDict` for usage).

    :return: a singleton, no-op dummy Renderer implemented for performance reasons
        only, as this app is intended to be a REST API without Django rendering
    """
    return _base_singleton_renderer


class EgsimBaseForm(Form):
    """Base eGSIM form"""

    # make code linters happy (attr created in Django DeclarativeFieldsMetaclass):
    base_fields: dict[str, Field]

    # Mapping Field names of this class to the associated request parameter name. Dict
    # values are tuples where the 1st element is the primary parameter name, and the
    # rest aliases (the Field name can be in the tuple, but if it's the only element
    # the whole mapping can be omitted). This class attribute should be private,
    # use `param_names_of` or `param_name_of` instead.
    # Rationale: by default, a Field name is also a request parameter. With this mapping,
    # we can change the latter only and keep the former immutable: this way, we can rely
    # on field names internally during validation (e.g., keys of `self.cleaned_data`,
    # `self.data`) whilst the Form will automatically input/output data with parameter
    # names (e.g. keys of the input dicts in `__init__`, or `self.errors_json_dict`)
    _field2params: dict[str, tuple[str]]

    def __init__(self, data=None, files=None, no_unknown_params=True, **kwargs):
        """Override init: re-arrange `self.data` (renaming each key with the
        corresponding field name, if needed) and treating non None initial values
        as default values for missing fields. As such, `data` might be modified inplace.

        :param data: the Form data (dict or None)
        :param files: the Form files
        :param no_unknown_params: boolean indicating whether unknown parameters (`data`
            keys) should invalidate the Form. The default is True to prevent misspelled
            parameters to be treated as missing and thus potentially assigned a default
            "wrong" value with no warnings
        """
        # remove colon in labels by default in templates (if used):
        kwargs.setdefault('label_suffix', '')
        # Form Field names mapped to the relative param given as input:
        self._field2inputparam = {}
        # call super:
        super(EgsimBaseForm, self).__init__(data, files, **kwargs)

        unknowns = set(self.data)
        # store conflicting+unknown params and manage them later in `errors_json_data`.
        # Avoid the mess that `self.add_error(field, ...)` introduces:
        # 1. It triggers a Form validation (`full_clean`) which is unnecessary and
        #    can only be done at the end of __init__
        # 2. It raises if `field` is neither None nor a valid Field name, so unknown
        #    params should be passed as None (but this discards the param name info)
        self.init_errors = {}
        for field_name, field in self.base_fields.items():
            param_names = self.param_names_of(field_name)
            unknowns -= set(param_names)
            input_param_names = tuple(p for p in param_names if p in self.data)
            if len(input_param_names) > 1:  # names conflict, store error:
                for p in input_param_names:
                    self.init_errors[p] = \
                        f"this parameter conflicts with " \
                        f"{' and '.join(_ for _ in input_param_names if _ != p)}"
                # assure has_error(field_name) returns True ("" will not print any
                # msg related to the field in errors_json_data):
                self.init_errors.setdefault(field_name, "")
                # Do not remove all params, because if the field is required we
                # don't want a 'missing param'-ish error: keep only the 1st param:
                for p in input_param_names[1:]:
                    self.data.pop(p)
                # now let's fall in the next if below:
                input_param_names = input_param_names[:1]
            if len(input_param_names) == 1:
                input_param_name = input_param_names[0]
                self._field2inputparam[field_name] = input_param_name
                # Rename the keys of `self.data` (API params) with the mapped
                # field name (see `self.clean` and in subclasses):
                if field_name != input_param_name:
                    self.data[field_name] = self.data.pop(input_param_name)
            else:
                # Make missing fields initial value the default, if provided
                # (https://stackoverflow.com/a/20309754):
                if self.fields[field_name].initial is not None:
                    self.data[field_name] = self.fields[field_name].initial

        if no_unknown_params:
            for u in unknowns:
                self.init_errors[u] = f'unknown parameter'

        # If we have any init error, set `is_bound=False` to prevent any further
        # validation (see super `full_clean` and `is_valid`):
        if self.init_errors:
            self.is_bound = False

    def has_error(self, field, code=None):
        """Call `super.has_error` without forcing a full clean (if the form has not
        been cleaned, return whether the field resulted in an initialization error)

        :param field: a Form field name (not an input parameter name)
        :param code: an optional error code (e.g. 'invalid')
        """
        # In case of init_errors return True also if code is None, signaling
        # calling routines (e.g. self.clean) that isn't worth to proceed anyway:
        if self.init_errors and (code is None or field in self.init_errors):
            return True
        if not self._errors:
            return False
        return super().has_error(field, code)

    class ErrMsg(StrEnum):
        """Custom error message enum: maps common Django ValueError's codes
        to a standardized message string. Usage:
            raise ValidationError(self.ErrMsg.invalid)
            self.add_error(field, self.ErrMsg.required)
        """
        required = "missing parameter is required"
        invalid = "invalid value"
        invalid_choice = "value not found or misspelled"

    def errors_json_data(self) -> dict:
        """Return a JSON serializable dict with the key `message` specifying
        all invalid parameters grouped by error type. Typically, users call
        this method if `self.is_valid()` returns False.
        Note: API users should retrieve JSON formatted errors via this method only
        (e.g., do not call `self.errors.get_json_data()` or other Django utilities)
        """
        errors = {}
        # add init errors
        for param, msg in self.init_errors.items():
            if msg:
                errors.setdefault(msg, set()).add(param)

        # add Django validation errors:
        for field_name, errs in self.errors.get_json_data().items():
            param = self.param_name_of(field_name)
            for err in errs:
                # Use as error message:
                # 1. err['code'], and convert it to the relative message, if found
                # 2. if the above failed, use err['message']
                # 3. if the above failed, use the string "unknown error"
                try:
                    msg = self.ErrMsg[err['code']].value
                except KeyError:
                    msg = err.get('message', 'unknown error')
                errors.setdefault(msg, set()).add(param)

        # build message. Sort params to make tests deterministic
        return {
            'message': '; '.join(sorted(f'{", ".join(sorted(ps))}: {err}'
                                        for err, ps in errors.items()))
        }

    def param_name_of(self, field: str) -> str:
        """Return the input parameter name of `field`. If no parameter name mapped to
        `field` has been provided as input `data`, return the 1st (=primary) parameter
        name of `field` or, in case of no mapping, `field` itself
        """
        if field in self._field2inputparam:  # param is given in this form `data`:
            return self._field2inputparam[field]
        return self.param_names_of(field)[0]  # class-level method

    @classmethod
    def param_names_of(cls, field: str) -> tuple[str]:
        """Return the parameter names of `field` registered at a class-level. The
        returned tuple has nonzero length and might contain the passed field argument.
        In case of length > 1, the first item is the primary parameter name
        """
        for clz in cls.__mro__:
            params = getattr(clz, '_field2params', {})
            if field in params:
                return params[field]
        return field,  # <- tuple!


class SHSRForm(EgsimBaseForm):
    """Base class for all Form accepting a list of models in form of location
    (lat lon) and optional list of seismic hazard source regionalizations (SHSR)"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params: dict[str, tuple[str]] = {
        'latitude': ('latitude', 'lat'),
        'longitude': ('longitude', 'lon'),
        'regionalization': ('regionalization', 'shsr')
    }

    latitude = FloatField(min_value=-90., max_value=90., required=False)
    longitude = FloatField(min_value=-180., max_value=180., required=False)
    regionalization = Field(required=False)  # Note: with a ModelChoiceField the
    # benefits of handling validation are outweighed by the fixes needed here and there
    # to make values JSON serializable, so we opt for a CharField + custom validation
    # in `clean_regionalization`

    def clean_regionalization(self) -> QuerySet[models.Regionalization]:
        """Custom gsim clean.
        The return value will replace self.cleaned_data['gsim']
        """
        reg_objs = models.Regionalization.queryset('name', 'media_root_path')
        value = self.cleaned_data.get('regionalization', None)
        if isinstance(value, str):
            value = [value]
        if value:
            reg_objs = reg_objs.filter(name__in=value)
        return reg_objs

    def get_region_selected_model_names(self) -> dict[str, list[str]]:
        """Get the ground motion model names from the chosen regionalization(s),
        lat and lon. This method should be invoked only if `self.is_valid()` returns
        True (form successfully validated).
        Empty / not provided `lat` ar `lon` will return an empty dict,
        empty not provided regionalizations will default to all implemented ones.
        The returned dict keys are ground motion models, mapped to the hazard source
        regionalizations they were defined for (e.g. {'CauzziEtAl2014: ['share']})
        """
        gsims = {}
        cleaned_data = self.cleaned_data
        lon = cleaned_data.get('longitude', None)
        lat = cleaned_data.get('latitude', None)
        if lat is None or lon is None:
            return gsims
        point = Point(lon, lat)
        for reg_obj in self.cleaned_data['regionalization']:  # see clean_regionalization
            reg_name = reg_obj.name
            if reg_name == 'germany':
                asd =9
            feat_collection = reg_obj.read_from_filepath()
            for feat in feat_collection['features']:
                geometry, reg_models = feat['geometry'], feat['properties']['models']
                reg_models = [r for r in reg_models if reg_name not in gsims.get(r, [])]
                # if we already have all models, skip check:
                if not reg_models:
                    continue
                if shape(geometry).contains(point):
                    for model in reg_models:
                        gsims.setdefault(model, []).append(reg_name)
        return gsims


class GsimForm(SHSRForm):
    """Base abstract-like form for any form requiring Gsim selection"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params: dict[str, list[str]] = {'gsim': ('model', 'gsim', 'gmm')}

    # Set simple Fields and perform validation in `clean_gsim` and `clean_imt`:
    gsim = Field(required=False, help_text="Ground shaking intensity Model(s)")

    def clean_gsim(self) -> dict[str, GMPE]:
        """Custom gsim clean.
        The return value will replace self.cleaned_data['gsim']
        """
        # Implementation note: as of 2024, the 1st arg to ValidationError is not
        # really used, just pass the right `code` arg (see `error_json_data`)
        key = 'gsim'
        value = self.to_list(self.cleaned_data.get(key))
        value.extend(m for m in self.get_region_selected_model_names() if m not in value)
        if not value:
            self.add_error(key, self.ErrMsg.required)
            return {}
        ret = {}
        try:
            ret = harmonize_input_gsims(value)
        except ModelError as err:
            self.add_error(key, f'invalid model(s) {str(err)}')
        return ret

    @staticmethod
    def to_list(value) -> list:
        if not value:
            return []
        if type(value) is tuple:
            value = list(value)
        if type(value) is not list:
            value = [value]
        return value


class GsimImtForm(GsimForm):
    """Base abstract-like form for any form requiring Gsim+Imt selection"""

    # Set simple Fields and perform validation in `clean_gsim` and `clean_imt`:
    imt = Field(required=False, help_text='Intensity Measure type(s)')

    def clean_imt(self) -> dict[str, IMT]:
        """Custom imt clean.
        The return value will replace self.cleaned_data['imt']
        """
        # Implementation note: as of 2024, the 1st arg to ValidationError is not
        # really used, just pass the right `code` arg (see `error_json_data`)
        key = 'imt'
        value = self.to_list(self.cleaned_data.get(key))
        if not value:
            self.add_error(key, self.ErrMsg.required)
            return {}
        ret = {}
        try:
            ret = harmonize_input_imts(value)
        except ImtError as err:
            self.add_error(key, f'invalid intensity measure(s) {str(err)}')
        return ret

    def clean(self):
        """Perform a final validation checking models and intensity measures
        compatibility
        """
        gsim_field, imt_field = 'gsim', 'imt'
        cleaned_data = super().clean()
        # If both fields were ok (no error), check that their values match:
        if not self.has_error(gsim_field) and not self.has_error(imt_field):
            try:
                validate_inputs(cleaned_data[gsim_field], cleaned_data[imt_field])
            except IncompatibleModelImtError as imi_err:
                err_msg = (f"incompatible model(s) and intensity measure(s) "
                           f"{str(imi_err)}")
                # add_error removes also the field from self.cleaned_data:
                self.add_error(gsim_field, err_msg)
                self.add_error(imt_field, err_msg)
        return cleaned_data


class APIForm(EgsimBaseForm):
    """API Form is the base Form for any eGSIM API view: in addition to handling
    input validation, it processes the given input into a Python object to be served as
    http response body / content.
    Subclasses need to implement the abstract-like `output` method
    """

    def output(self) -> Any:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        raise NotImplementedError()


class GsimFromRegionForm(SHSRForm, APIForm):
    """API Form returning a list of models from a given location and optional
    seismic hazard source regionalizations (SHSR)"""

    def output(self) -> dict:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        return {'models': sorted(self.get_region_selected_model_names())}


class GsimInfoForm(GsimForm, APIForm):
    """API Form returning a info for a list of selected of models. Info is a dict
    containing the supported imt(s), the required ground motion parameters,
    and the OpenQuake docstring
    """

    _field2params: dict[str, list[str]] = {'gsim': ('name', 'model')}

    def clean_gsim(self) -> dict[str, GMPE]:
        """Custom gsim clean. Relaxes model matching to allow partially typed,
        case-insensitive names, eventually calling the super method.
        The return value will replace self.cleaned_data['gsim']
        """
        key = 'gsim'
        gmms = self.to_list(self.cleaned_data.get(key))
        if gmms:
            registered_gmms = {m.lower(): m for m in models.Gsim.names()}
            new_gmms = []
            for gmm in gmms:
                gmm_l = gmm.lower()
                if gmm_l in registered_gmms:
                    new_gmms.append(registered_gmms[gmm_l])
                else:
                    matches = [v for k, v in registered_gmms.items() if gmm.lower() in k]
                    if matches:
                        new_gmms.extend(matches)
                    else:
                        new_gmms.append(gmm)
            self.cleaned_data[key] = new_gmms
        return super().clean_gsim()

    def output(self) -> dict:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        hazard_source_models = self.get_region_selected_model_names()
        ret = {}
        for gmm in self.cleaned_data['gsim']:
            doc, imts, gmp, sa_limits = gsim_info(gmm)
            # ground motion properties:
            gmp = {p: FlatfileMetadata.get_help(p) for p in gmp}
            # remove unnecessary flatfile-related info (everything after first ".")
            # and also jsonify the string (replace " with ''):
            gmp = {
                k: v[: (v.find('.') + 1) or None].removesuffix(".").replace('"', "''")
                for k, v in gmp.items()
            }
            # pretty print doc (removing all newlines and double quotes, see below):
            desc = []
            for line in doc.split("\n"):  # parse line by line
                line = line.strip()  # remove indentation
                if not line:
                    # if line is empty, then add a dot to the last line unless it does
                    # not already end with punctuation:
                    if desc and desc[-1][-1] not in {'.', ',', ';', ':', '?', '!'}:
                        desc[-1] += '.'
                    continue
                # avoid \" in json strings, replace with ''
                desc.append(line.replace('"', "''"))
            doc = " ".join(desc)
            # pretty print imts and add sa_)limits to it:
            imts = ['SA(PERIOD_IN_S)' if  i == 'SA' else i for i in imts]
            ret[gmm] = {
                'description': doc,
                'defined_for': imts,
                'requires': gmp,
                'sa_period_limits': sa_limits,
                'hazard_source_models': hazard_source_models.get(gmm)
            }
        return ret
