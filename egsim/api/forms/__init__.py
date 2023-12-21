"""Base eGSIM forms"""
from __future__ import annotations

import re
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.imt import IMT
from typing import Union, Any
import json
from io import StringIO
from enum import StrEnum

import yaml
from shapely.geometry import Point, shape
from django.forms import Form, ModelMultipleChoiceField
from django.forms.renderers import BaseRenderer
from django.forms.forms import DeclarativeFieldsMetaclass  # noqa
from django.forms.fields import Field, FloatField

from egsim.api import models
from egsim.smtk import (validate_inputs, InvalidInput, harmonize_input_gsims,
                        harmonize_input_imts, gsim)
from egsim.smtk.validators import IncompatibleInput


_base_singleton_renderer = BaseRenderer()  # singleton no-op renderer, see below


def get_base_singleton_renderer(*a, **kw) -> BaseRenderer:
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
        been cleaned, return if the field resulted in an internal initialization error)

        :param field: a Form field name (not an input parameter name)
        :param code: an optional error code (e.g. 'invalid')
        """
        if self.init_errors and (code is None or field in self.init_errors):
            return True
        if not self._errors:
            return False
        return super().has_error(field, code)

    class ErrCode(StrEnum):
        """Custom error code and msg replacing Django defaults and simplifying
        how to raise field errors. Usage:
            raise ValidationError(self.ErrCode.invalid)
            self.add_error(field, self.ErrCode.invalid)
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
                try:
                    msg = self.ErrCode[err['code']]
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

    def as_json(self, compact=True) -> str:
        """Return the `data` argument passed in the constructor in a JSON formatted
        string that can be used in POST requests (if `self.is_valid()` is True)

        @param compact: skip optional parameters (see `compact` in `self._get_data`)
        """
        stream = StringIO()
        ret = {}
        for field, value in self.data.items():
            if compact and \
                    self._is_default_value_for_field(field, value):  # class level attr
                continue
            ret[self.param_name_of(field)] = value
        json.dump(ret, stream, indent=2, separators=(',', ': '), sort_keys=True)
        return stream.getvalue()

    def as_yaml(self, compact=True) -> str:
        """Return the `data` argument passed in the constructor as YAML formatted
        string (with parameters docstrings when available) that can be used in POST
        requests (if `self.is_valid()` is True)

        @param compact: skip optional parameters (see `compact` in `self._get_data`)
        """
        class Dumper(yaml.SafeDumper):
            """Force indentation of lists ( https://stackoverflow.com/a/39681672)"""

            def increase_indent(self, flow=False, indentless=False):
                return super(Dumper, self).increase_indent(flow, False)

        stream = StringIO()
        for field, value in self.data.items():
            if compact and \
                    self._is_default_value_for_field(field, value):  # class level attr
                continue
            docstr = self.get_field_docstring(field)
            if docstr:
                stream.write(f'# {docstr}')
                stream.write('\n')
            yaml.dump({self.param_name_of(field): value},
                      stream=stream, Dumper=Dumper, default_flow_style=False)
            stream.write('\n')

        return stream.getvalue()

    @classmethod
    def _is_default_value_for_field(cls, field: Union[str, Field], value):
        """Return True if the given value is the default value for the given
        field and can be omitted in `self.data`"""
        if isinstance(field, str):
            field = cls.declared_fields.get(field, None)
        if field:
            field_optional = not field.required or field.initial is not None
            if field_optional and value == field.initial:
                return True
        return False

    @classmethod
    def get_field_docstring(cls, field: Union[str, Field], remove_html_tags=False):
        """Return a docstring from the given Form field `label` and `help_text`
        attributes. The returned string will be a one-line (new newlines) string
        FIXME: remove? remove HTML in Fields help_text so that this method is simpler?
        """
        if isinstance(field, str):
            field = cls.declared_fields.get(field, None)
        if not field:
            return ""
        field_label = getattr(field, 'label')
        field_help_text = getattr(field, 'help_text')
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


class SHSRForm(EgsimBaseForm):
    """Base class for all Form accepting a list of models in form of location
    (lat lon) and optional list of seismic hazard source regionalizations (SHSR)"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params: dict[str, tuple[str]] = {
        'latitude': ('latitude', 'lat'),
        'longitude': ('longitude', 'lon'),
        'regionalization': ('regionalization', 'shsr')
    }

    latitude = FloatField(label='Latitude', min_value=-90., max_value=90.,
                          required=False)
    longitude = FloatField(label='Longitude', min_value=-180., max_value=180.,
                           required=False)
    regionalization = ModelMultipleChoiceField(
        queryset=models.Regionalization.queryset('name', 'media_root_path'),
        initial=models.Regionalization.queryset('name', 'media_root_path'),
        to_field_name="name",
        label='Regionalization',
        required=False)

    def get_region_selected_model_names(self) -> set[str]:
        gsims = set()
        cleaned_data = self.cleaned_data
        lon = cleaned_data.get('longitude', None)
        lat = cleaned_data.get('latitude', None)
        if lat is None or lon is None:
            return gsims
        point = Point(lon, lat)
        for reg_obj in cleaned_data['regionalization']:
            feat_collection = reg_obj.read_from_filepath()
            for feat in feat_collection['features']:
                geometry, models = feat['geometry'], feat['properties']['models']
                # if we already have all models, skip check:
                if set(models) - gsims:
                    if shape(geometry).contains(point):
                        gsims.update(models)
        return gsims


class GsimImtForm(SHSRForm):
    """Base abstract-like form for any form requiring Gsim+Imt selection"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params: dict[str, list[str]] = {'gsim': ('model', 'gsim', 'gmm')}

    # Set simple Fields and perform validation in `clean_gsim` and `clean_imt`:
    gsim = Field(required=False, label="Model(s)",
                 widget=ModelMultipleChoiceField.widget)
    imt = Field(required=False, label='Intensity Measure(s)',
                widget=ModelMultipleChoiceField.widget)

    accept_empty_gsim_list = False  # override in subclasses if needed
    accept_empty_imt_list = False  # see above (for imts)

    def clean_gsim(self) -> dict[str, GMPE]:
        """Custom gsim clean.
        The return value will replace self.cleaned_data['gsim']
        """
        # Implementation note: as of 2024, the 1st arg to ValidationError is not
        # really used, just pass the right `code` arg (see `error_json_data`)
        key = 'gsim'
        value = self.cleaned_data.get(key, None)
        if not value:
            if not self.accept_empty_gsim_list:
                self.add_error(key, self.ErrCode.required)
            return {}
        if type(value) not in (list, tuple):
            value = [value]
        ret = {}
        try:
            ret = harmonize_input_gsims(value)
            for name in self.get_region_selected_model_names():
                if name not in ret:
                    ret[name] = gsim(name)
        except InvalidInput as err:
            self.add_error(key, f"{self.ErrCode.invalid} "
                                f"({', '.join(sorted(err.args))})")
        return ret

    def clean_imt(self) -> dict[str, IMT]:
        """Custom gsim clean.
        The return value will replace self.cleaned_data['imt']
        """
        # Implementation note: as of 2024, the 1st arg to ValidationError is not
        # really used, just pass the right `code` arg (see `error_json_data`)
        key = 'imt'
        value = self.cleaned_data.get(key, None)
        if not value:
            if not self.accept_empty_imt_list:
                self.add_error(key, self.ErrCode.required)
            return {}
        if type(value) not in (list, tuple):
            value = [value]
        ret = {}
        try:
            ret = harmonize_input_imts(value)
        except InvalidInput as err:
            self.add_error(key, f"{self.ErrCode.invalid} "
                                f"({', '.join(sorted(err.args))})")
        return ret

    def clean(self):
        """Perform a final validation checking models and intensity measures
        compatibility
        """
        gsim, imt = 'gsim', 'imt'
        cleaned_data = super().clean()
        # if any of the if above was true, then the parameter has been removed from
        # cleaned_data. If both are provided, check gsims and imts match:
        if not self.has_error(gsim) and not self.has_error(imt):
            try:
                validate_inputs(cleaned_data[gsim], cleaned_data[imt])
            except IncompatibleInput as err:
                # add error to form:
                msg = ", ".join(f"{m[0]} not defined for {' and '.join(m[1:])}"
                                for m in err.args)
                # add_error removes also the field from self.cleaned_data:
                self.add_error(gsim, msg)
                self.add_error(imt, msg)
        return cleaned_data


class APIForm(EgsimBaseForm):
    """API Form is the Base Form for the eGSIM API request/response. It implements
    an abstract-like `response_data` method
    """

    def response_data(self) -> Any:
        """Return the response data from this Form input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object that can be used as HTTP response data (e.g.,
            a JSON-serializable dict)
        """
        raise NotImplementedError()


class GsimFromRegionForm(SHSRForm, APIForm):
    """API Form returning a list of models from a given location and optional
    seismic hazard source regionalizations (SHSR)"""

    def response_data(self) -> dict:
        return {'models': sorted(self.get_region_selected_model_names())}
