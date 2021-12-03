from typing import Any
from . import TABS, URLS


def get_components_properties(debugging=False) -> dict[str, dict[str, Any]]:
    """Return a dict with all the properties to be passed
    as VueJS components in the frontend

    :param debugging: if True, the components input elements will be setup
        with default values so that the frontend FORMS will be ready to
        test click buttons
    """
    # properties to be passed to vuejs components.
    # If you change THE KEYS of the dict here you should change also the
    # javascript:
    components_props = {
        TABS.home.name: {
            'src': URLS.HOME_PAGE
        },
        # KEY.GSIMS: {  # FIXME REMOVE
        #     'form': GsimsView.formclass().to_rendering_dict(),
        #     'url': URLS.GSIMS_RESTAPI,
        #     'urls': {
        #         'getTectonicRegionalisations': URLS.GSIMS_TR
        #     }
        # },
        TABS.trellis.name: {
            'form': TABS.trellis.formclass().to_rendering_dict(),
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
        #     'form': GmdbPlotView.formclass().to_rendering_dict(),
        #     'url': URLS.GMDBPLOT_RESTAPI
        # },
        TABS.residuals.name: {
            'form': TABS.residuals.formclass().to_rendering_dict(),
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
            'form': TABS.testing.formclass().to_rendering_dict(),
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
        TABS.doc.name: {
            'src': URLS.DOC_PAGE
        }
    }
    if debugging:
        _configure_values_for_testing(components_props)
    return components_props


def _configure_values_for_testing(components_props: dict[str, dict[str, Any]]):
    """Set up some dict keys and subkeys so that the frontend FORM is already
    filled with test values
    """
    gsimnames = ['AkkarEtAlRjb2014', 'BindiEtAl2014Rjb', 'BooreEtAl2014',
                 'CauzziEtAl2014']
    trellisformdict = components_props['trellis']['form']
    trellisformdict['gsim']['val'] = gsimnames
    trellisformdict['imt']['val'] = ['PGA']
    trellisformdict['magnitude']['val'] = "5:7"
    trellisformdict['distance']['val'] = "10 50 100"
    trellisformdict['aspect']['val'] = 1
    trellisformdict['dip']['val'] = 60
    trellisformdict['plot_type']['val'] = 's'

    residualsformdict = components_props['residuals']['form']
    residualsformdict['gsim']['val'] = gsimnames
    residualsformdict['imt']['val'] = ['PGA', 'SA']
    residualsformdict['sa_period']['val'] = "0.2 1.0 2.0"
    residualsformdict['selexpr']['val'] = "magnitude > 5"
    residualsformdict['plot_type']['val'] = 'res'

    testingformdict = components_props['testing']['form']
    testingformdict['gsim']['val'] = gsimnames + ['AbrahamsonSilva2008']
    testingformdict['imt']['val'] = ['PGA', 'PGV']
    testingformdict['sa_period']['val'] = "0.2 1.0 2.0"

    components_props['testing']['form']['fit_measure']['val'] = ['res',
                                                                 'lh',
                                                                 # 'llh',
                                                                 # 'mllh',
                                                                 # 'edr'
                                                                 ]
