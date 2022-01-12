from typing import Any, Type, Callable, Union
import json

from django.db.models import Prefetch, QuerySet
from . import TABS, URLS
from ..api import models
from ..api.forms import EgsimBaseForm
from ..api.forms.tools import field_to_dict, field_to_htmlelement_attrs


def get_context(selected_menu=None, debug=True) -> dict:
    """The context to be injected in the template of the main HTML page"""

    # Tab components (one per tab, one per activated vue component)
    # (key, label and icon) (the last is bootstrap fontawesome name)
    components_tabs = [[_.name, _.title, _.icon] for _ in TABS]

    # this can be changed if needed:
    sel_component = TABS.home.name if not selected_menu else selected_menu

    # setup browser detection
    allowed_browsers = [['Chrome', 49], ['Firefox', 45], ['Safari', 10]]
    allowed_browsers_msg = ', '.join('%s &ge; %d' % (brw, ver)
                                     for brw, ver in allowed_browsers)
    invalid_browser_message = ('Some functionalities might not work '
                               'correctly. In case, please use any of the '
                               'following tested browsers: %s' %
                               allowed_browsers_msg)

    gsims = [[g.name, [i.name for i in g.imtz], g.warning or ""] for g in query_gims()]

    components_props = get_components_properties(debug)

    regionalization = {
        'url': URLS.GET_GSIMS_FROM_REGION,
        'names': list(models.RegionalizationDataSource.objects.
                      values_list('name', flat=True))
    }

    return {
        'debug': debug,
        'sel_component': sel_component,
        'components': components_tabs,
        'component_props': json.dumps(components_props, separators=(',', ':')),
        'gsims': json.dumps(gsims, separators=(',', ':')),
        'flatfiles': [(f.name, str(f)) for f in query_flatfiles()],
        'regionalization': regionalization,
        'allowed_browsers': allowed_browsers,
        'invalid_browser_message': invalid_browser_message
    }


def query_gims() -> QuerySet:
    """Return a QuerySet of Gsims instances from the database, with the
    necessary information (field 'warning' and associated Imts in the `imtz`
    attribute)
    """
    # Try to perform everything in a single more efficient query. Use
    # prefetch_related for this. It Looks like we need to assign the imts to a
    # new attribute, the attribute "Gsim.imts" does not work as expected
    imts = Prefetch('imts', queryset=models.Imt.objects.only('name'),
                    to_attr='imtz')

    return models.Gsim.objects.only('name', 'warning').prefetch_related(imts)


def query_flatfiles() -> QuerySet:
    return models.Flatfile.get_flatfiles(hidden=False)


def get_components_properties(debugging=False) -> dict[str, dict[str, Any]]:
    """Return a dict with all the properties to be passed
    as VueJS components in the frontend

    :param debugging: if True, the components input elements will be setup
        with default values so that the frontend FORMS will be ready to
        test click buttons
    """
    def ignore_choices(field_att_name):
        return field_att_name in ('gsim', 'imt', 'flatfile')

    # properties to be passed to vuejs components.
    # If you change THE KEYS of the dict here you should change also the
    # javascript:
    components_props = {
        TABS.home.name: {
            'src': URLS.HOME_PAGE
        },
        TABS.trellis.name: {
            'form': form_to_json(TABS.trellis.formclass, ignore_choices),
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
            'form': form_to_json(TABS.residuals.formclass, ignore_choices),
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
            'form': form_to_json(TABS.testing.formclass, ignore_choices),
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
        TABS.apidoc.name: {
            'src': URLS.DOC_PAGE
        }
    }
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
    residuals_form['imt'][val] = ['PGA', "SA(0.2)", "SA(1.0)", "SA(2.0)"]
    residuals_form['selexpr'][val] = "magnitude > 5"
    residuals_form['plot_type'][val] = 'res'

    testing_form = components_props['testing']['form']
    testing_form['gsim'][val] = gsimnames + ['AbrahamsonSilva2008']
    testing_form['imt'][val] = ['PGA', 'PGV', "0.2", "1.0", "2.0"]
    testing_form['fit_measure'][val] = ['res', 'lh']


def form_to_json(form: Union[Type[EgsimBaseForm], EgsimBaseForm],
                 ignore_choices: Callable[[str], bool] = None) -> dict[str, dict[Any]]:
    """Return a JSON-serializable dictionary of the Form Field names mapped to
    their properties, in order e.g. to be injected in HTML templates in order
    to render the Field as HTML component.

    :param form: EgsimBaseForm class or object (class instance)
    :param ignore_choices: callable accepting a string (field attribute name)
        and returning True or False. If False, the Field choices will not be
        loaded and the returned dict 'choices' key will be `[]`. Useful for
        avoiding time consuming long list loading
    """

    if ignore_choices is None:
        def ignore_choices(*a, **k):
            return False

    form_data = {}
    # keep track of Field done. Initialize the set below with the ignored fields:
    field_done = {'format', 'csv_sep', 'csv_dec'}
    # iterate over the field (public) names because we also have the attribute
    # name immediately available:
    for field_name, field_attname in form.public_field_names.items():
        if field_attname in field_done:
            continue
        field_done.add(field_attname)
        field = form.declared_fields[field_attname]
        field_dict = field_to_dict(field, ignore_choices=ignore_choices(field_attname))
        field_dict |= dict(field_to_htmlelement_attrs(field), name=field_name)
        field_dict['error'] = ''
        form_data[field_attname] = field_dict

    return form_data
