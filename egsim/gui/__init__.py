from enum import Enum

# import here once all api modules (also those used in other modules of this package)
from ..api.views import ResidualsView, TestingView, TrellisView


class URLS:  # noqa
    """Define URLs to be used in :module:`urls.py` and in GUI views (injected in
    web pages via dicts or templates). NO URL MUST END WITH THE SLASH CHARACTER "/"
    """
    # url(s) for downloading the requests (configuration params) in json or
    # yaml. Example of a complete url:
    # DOWNLOAD_CFG/trellis/filename.json
    # (see function 'main' below and module 'urls')
    DOWNLOAD_CFG = 'data/downloadcfg'

    # urls for downloading text. Example of a complete url:
    # DOWNLOAD_ASTEXT/trellis/filename.csv
    # DOWNLOAD_ASTEXT_EU/trellis/filename.csv
    # (see function 'main' below and module 'urls')
    DOWNLOAD_ASTEXT = 'data/downloadascsv'
    DOWNLOAD_ASTEXT_EU = 'data/downloadaseucsv'

    # url for downloading as image. Note that the request body (POST data) is
    # the frontend data, in turn previously generated from one of the REST APIs
    # above: this is a bit convoluted and prevents the url to be used outside
    # the web page (all other endpoints can in principle be used as REST
    # endpoints without the web page), but we want to generate figures based on
    # what the user chooses, and also it is not always possible to convert
    # a REST API response to image (e.g., 3D grid of plots)
    DOWNLOAD_ASIMG = 'data/downloadasimage'

    # url for the frontend pages to be rendered as HTML by means of the
    # typical Django templating system: these pages are usually inside
    # <iframe>s of the web SPA (single page application)
    HOME_PAGE = 'pages/home'
    DOC_PAGE = 'pages/apidoc'


class TABS(Enum):
    """Define web page tabs as Enum with custom attributes:
    (title:str, icon:str, formclass:`forms.APIForm | None`)
    Use Enum name (e.g. TABS.home) as Tab string ID. Conversely,
    given a name (e.g. 'home') you can get the TABS element via TABS[name]
    """
    # icons (2nd element) are fontawesome bootsrap icons FIXME REF
    home = 'Home', 'fa-home'
    trellis = 'Model-to-Model Comparison', 'fa-area-chart', TrellisView
    residuals = 'Model-to-Data Comparison', 'fa-bar-chart', ResidualsView
    testing = 'Model-to-Data Testing', 'fa-list', TestingView
    apidoc = 'API Doc / Legal Info', 'fa-info-circle'

    # GMDBPLOT = 'gmbdplot', 'Ground Motion Database', 'fa-database'
    # GSIMS = 'Model Selection', 'fa-map-marker'

    def __init__(self, *args):
        # args is the unpacked tuple passed above (2-elements), set attributes:
        self.title: str = args[0]
        self.icon: str = args[1]
        _viewclass = args[2] if len(args) > 2 else None
        self.urls = _viewclass.urls if _viewclass else []
        self.formclass = _viewclass.formclass if _viewclass else None

    def __str__(self):
        return self.name
