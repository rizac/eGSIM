"""Module for rendering the main page of the site (single page application)"""

from typing import Any, Type, Callable, Union
from enum import Enum

from django.db.models import Prefetch
from django.forms import (Field, IntegerField, ModelChoiceField)
from django.forms.widgets import ChoiceWidget, Input

from ...api import models
from ...api.forms import EgsimBaseForm, APIForm
from ...api.forms.flatfile import FlatfileForm, FlatfileRequiredColumnsForm, MOF
from ...api.forms.flatfile.inspection import FlatfilePlotForm
from ...api.views import (ResidualsView, TestingView, TrellisView, RESTAPIView)


class URLS:  # noqa
    """Define global URLs"""
    # we should put this class in `urls.py` but it is used here and in `views.py`
    # NOTE NO URL HERE (unless external, i.e., http://) MUST END WITH  "/"

    # JSON data requested by the main page at startup:
    MAIN_PAGE_INIT_DATA = "init_data"
    # Url for getting the gsim list from a given geographic location:
    GET_GSIMS_FROM_REGION = 'data/getgsimfromlatlon'
    # inspecting a flatfile:
    FLATFILE_INSPECTION = 'data/flatfile_inspection'
    FLATFILE_REQUIRED_COLUMNS = 'data/flatfile_required_columns'
    FLATFILE_PLOT = 'data/flatfile_plot'
    DOWNLOAD_REQUEST = 'data/downloadrequest'
    DOWNLOAD_RESPONSE = 'data/downloadresponse'
    # info pages:
    HOME_NO_MENU = 'home_no_menu'
    API = 'api'
    DATA_PROTECTION = 'https://www.gfz-potsdam.de/en/data-protection/'
    IMPRINT = "imprint"
    REF_AND_LICENSE = "ref_and_license"


class TAB(Enum):
    """Define Tabs/Menus of the Single page Application. A TAB T is an Enum with attr:
    ```
    title: str
    icon: str
    viewclass: Union[Type[RESTAPIView], None]
    ```
    Enum names should be kept constant as they are used as ID also in frontend code.
    Remember that a Tab element can be obtained from its name via square notation
    e.g. tab = TAB["trellis"] (and conversely, `tab.name` returns "trellis")
    """
    # icons (2nd element) are currently given as font-awesome bootsrap icons
    home = '', 'fa-home'
    trellis = 'Model-to-Model Comparison', 'fa-area-chart', TrellisView
    flatfile = 'Flatfiles', 'fa-database'
    residuals = 'Model-to-Data Comparison', 'fa-bar-chart', ResidualsView
    testing = 'Model-to-Data Testing', 'fa-list', TestingView

    def __init__(self, *args):
        # args is the unpacked tuple passed above (2-elements), set attributes:
        self.title: str = args[0]
        self.icon: str = args[1]
        self.viewclass: Type[RESTAPIView] = args[2] if len(args) > 2 else None

    @property
    def urls(self) -> list[str]:
        return self.viewclass.urls if self.viewclass else []

    @property
    def formclass(self) -> Type[APIForm]:
        return self.viewclass.formclass if self.viewclass else None

    @property
    def download_request_filename(self) -> str:
        return f"egsim-{self.name}-config"

    @property
    def download_response_filename(self) -> str:
        return f"egsim-{self.name}-result"

    def __str__(self):
        return self.name


def get_init_json_data(browser: dict = None,
                       selected_menu: str = None,
                       debug=True) -> dict:
    """Return the JSON data to be passed to the browser at startup to initialize
    the page content

    :param browser: a dict with 'name':str and 'version': float keys
    """
    # check browser:
    allowed_browsers = {'chrome': 49, 'firefox': 45, 'safari': 10}
    allowed_browsers_msg = ', '.join(f'{b.title()}≥{v}'
                                     for b, v in allowed_browsers.items())
    invalid_browser_message = (f'eGSIM could not determine if your browser '
                               f'matches {allowed_browsers_msg}. '
                               f'This portal might not work as expected')
    browser_name = (browser or {}).get('name', None)
    browser_ver = (browser or {}).get('version', None)
    if browser_ver is not None:
        a_browser_ver = allowed_browsers.get(browser_name.lower(), None)
        if a_browser_ver is not None and browser_ver >= a_browser_ver:
            invalid_browser_message = ''

    # Get gsims and all related data (imts and warnings). Try to perform everything
    # in a single more efficient query. Use prefetch_related for this:
    gsims = []
    imt_groups = []
    # imts = Prefetch('imts', queryset=models.Imt.objects.only('name'))
    # for gsim in models.Gsim.objects.only('name', 'warning').prefetch_related(imts):
    for gsim in _get_gsim_for_init_data():
        imt_names = sorted(i for i in gsim.imts.values_list('name', flat=True))
        try:
            imt_group_index = imt_groups.index(imt_names)
        except ValueError:
            imt_group_index = len(imt_groups)
            imt_groups.append(imt_names)
        if gsim.warning:
            gsims.append([gsim.name, imt_group_index, str(gsim.warning)])
        else:
            gsims.append([gsim.name, imt_group_index])

    # get regionalization data (for selecting models on a map):
    regionalization = {
        'url': URLS.GET_GSIMS_FROM_REGION,
        'names': list(models.Regionalization.objects.values_list('name', flat=True))
    }

    # get predefined flatfiles info:
    flatfiles = []
    for r in models.Flatfile.get_flatfiles(hidden=False):
        flatfiles .append({
            'value': r.name,
            'innerHTML': f'{r.name} ({r.display_name})',
            'url': r.url,
            'columns': FlatfileForm.get_flatfile_dtypes(
                FlatfileForm.read_flatfile_from_db(r), compact=True)
        })

    # Get component props (core data needed for Vue rendering):
    components_props = get_components_properties(debug)

    return {
        'components': {
            'names': [_.name for _ in TAB],
            'tabs': {_.name: {'title': _.title, 'icon': _.icon} for _ in TAB},
            'props': components_props
        },
        'sel_component': TAB.home.name if not selected_menu else selected_menu,
        'gsims': gsims,
        'imt_groups': imt_groups,
        'flatfile': {
            'choices': flatfiles,
            'upload_url': URLS.FLATFILE_INSPECTION,
        },
        'regionalization': regionalization,
        'invalid_browser_message': invalid_browser_message,
        'newpage_urls': {
            'api': URLS.API,
            'imprint': URLS.IMPRINT,
            'data_protection': URLS.DATA_PROTECTION,
            'ref_and_license': URLS.REF_AND_LICENSE
        }
    }


def _get_gsim_for_init_data():
    """Get gsim DB model instances and all related data (imts and warnings)"""
    # Try to perform everything in a single more efficient query. Use prefetch_related
    # for this:
    imts = Prefetch('imts', queryset=models.Imt.objects.only('name'))
    return models.Gsim.objects.only('name', 'warning').prefetch_related(imts)


def get_components_properties(debugging=False) -> dict[str, dict[str, Any]]:
    """Return a dict with all the properties to be passed
    as VueJS components in the frontend

    :param debugging: if True, the components input elements will be setup
        with default values so that the frontend FORMS will be ready to
        test click buttons
    """
    def ignore_choices(field_att_name):
        return field_att_name in {'gsim', 'imt', 'flatfile'}

    def ignore_field(field_att_name):
        return field_att_name in {'format', 'csv_sep', 'csv_dec',
                                  'latitude', 'longitude', 'regionalization'}

    # properties to be passed to vuejs components.
    # If you change THE KEYS of the dict here you should change also the
    # javascript:
    components_props = {
        TAB.home.name: {
            'src': URLS.HOME_NO_MENU
        },
        TAB.trellis.name: {
            'form': form_to_json(TAB.trellis.formclass, ignore_field, ignore_choices),
            'url': TAB.trellis.urls[0],
            'urls': {
                'downloadRequest': f"{URLS.DOWNLOAD_REQUEST}/{TAB.trellis.name}/"
                                   f"{TAB.trellis.download_request_filename}",
                'downloadResponse': f"{URLS.DOWNLOAD_RESPONSE}/{TAB.trellis.name}/"
                                    f"{TAB.trellis.download_response_filename}"
            }
        },
        TAB.flatfile.name: {  # FIXME REMOVE
            'forms': [form_to_json(FlatfileRequiredColumnsForm, ignore_field,
                                   ignore_choices),
                      form_to_json(FlatfilePlotForm, ignore_field, ignore_choices)],
            'urls': [URLS.FLATFILE_REQUIRED_COLUMNS,
                     URLS.FLATFILE_PLOT]
        },
        TAB.residuals.name: {
            'form': form_to_json(TAB.residuals.formclass, ignore_field, ignore_choices),
            'url': TAB.residuals.urls[0],
            'urls': {
                'downloadRequest': f"{URLS.DOWNLOAD_REQUEST}/{TAB.residuals.name}/"
                                   f"{TAB.residuals.download_request_filename}",
                'downloadResponse': f"{URLS.DOWNLOAD_RESPONSE}/{TAB.residuals.name}/"
                                    f"{TAB.residuals.download_response_filename}"
            }
        },
        TAB.testing.name: {
            'form': form_to_json(TAB.testing.formclass, ignore_field, ignore_choices),
            'url': TAB.testing.urls[0],
            'urls': {
                'downloadRequest': f"{URLS.DOWNLOAD_REQUEST}/{TAB.testing.name}/"
                                   f"{TAB.testing.download_request_filename}",
                'downloadResponse': f"{URLS.DOWNLOAD_RESPONSE}/{TAB.testing.name}/"
                                    f"{TAB.testing.download_response_filename}"
            }
        }
    }

    # FlatfilePlotForm has x and y that must be represented as <select> but cannot
    # be implemented as ChoiceField, because their content is not static but
    # flatfile dependent. So
    plot_form: dict = components_props[TAB.flatfile.name]['forms'][-1]  # noqa
    plot_form['x']['type'] = 'select'
    plot_form['y']['type'] = 'select'
    # provide initial value:
    plot_form['x']['choices'] = [('', 'None: display histogram of Y values')]
    plot_form['y']['choices'] = [('', 'None: display histogram of X values')]

    if debugging:
        _setup_default_values(components_props)
    return components_props


def _setup_default_values(components_props: dict[str, dict[str, Any]]):
    """Set up some dict keys and sub-keys so that the frontend FORM is already
    filled with default values for easy testing
    """
    gsimnames = ['AkkarEtAlRjb2014', 'BindiEtAl2014Rjb', 'BooreEtAl2014',
                 'CauzziEtAl2014']
    val = 'value'
    trellis_form = components_props['trellis']['form']
    trellis_form['gsim'][val] = gsimnames
    trellis_form['imt'][val] = ['PGA']
    trellis_form['magnitude'][val] = "5:7"
    trellis_form['distance'][val] = "10 50 100"
    trellis_form['aspect'][val] = 1
    trellis_form['dip'][val] = 60
    trellis_form['plot_type'][val] = 's'

    residuals_form = components_props['residuals']['form']
    residuals_form['gsim'][val] = gsimnames
    residuals_form['imt'][val] = ["SA(0.2)", "SA(1.0)", "SA(2.0)"]
    residuals_form['flatfile'][val] = "esm2018"
    residuals_form['selexpr'][val] = "magnitude > 6"
    residuals_form['plot_type'][val] = MOF.RES

    testing_form = components_props['testing']['form']
    testing_form['gsim'][val] = ['AbrahamsonSilva2008']
    testing_form['imt'][val] = ['PGA']  # , 'PGV', "0.2", "1.0", "2.0"]
    testing_form['selexpr'][val] = "magnitude > 6"
    testing_form['fit_measure'][val] = [MOF.RES]  # , MOF.LH]


def form_to_json(form: Union[Type[EgsimBaseForm], EgsimBaseForm],
                 ignore_field: Callable[[str], bool] = None,
                 ignore_choices: Callable[[str], bool] = None) -> dict[str, dict[Any]]:
    """Return a JSON-serializable dictionary of the Form Field names mapped to
    their properties, in order e.g. to be injected in HTML templates and render the
    Form Fields as HTML component.

    :param form: EgsimBaseForm class or object (class instance)
    :param ignore_field: callable accepting a string (field attribute name)
        and returning True or False. If True, the field will be skipped and
        not included in the returned dict. Useful for Fields not visible from
        the GUI
    :param ignore_choices: callable accepting a string (field attribute name)
        and returning True or False. If False, the Field choices will not be
        loaded and the returned dict 'choices' key will be `[]`. Useful for
        avoiding time consuming long list loading
    """

    if ignore_choices is None:
        def ignore_choices(*a, **kw):
            return False

    if ignore_field is None:
        def ignore_field(*a, **kw):
            return False

    form_data = {}
    # iterate over the field (public) names because we also have the attribute
    # name immediately available:
    for field_name, field, param_names in form.field_iterator():
        if ignore_field(field_name):
            continue
        field_dict = field_to_dict(field, ignore_choices=ignore_choices(field_name))
        field_dict |= dict(field_to_htmlelement_attrs(field), name=param_names[0])
        field_dict['error'] = ''
        form_data[field_name] = field_dict

    return form_data


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
        'value': field.initial,
        'help': (field.help_text or "").strip(),
        'label': (field.label or "").strip(),
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
    # own for several reasons, e.g.:
    # 1. Avoid loading all <option>s for Gsim and Imt (we could subclass
    #    `optgroups` in `widgets.SelectMultiple` and return [], but it's clumsy)
    # 2. Remove some attributes (e.g. checkbox with the 'checked' attribute are
    #    not compatible with VueJS v-model or v-checked)
    # 3. Some Select with single choice set their initial value as list  (e.g.
    #    ['value'] instead of 'value') and I guess VueJs prefers strings

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
