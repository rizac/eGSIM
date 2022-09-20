from enum import Enum
from typing import Any, Type, Callable, Union

from ..api.forms import APIForm

from ..api.views import (ResidualsView, TestingView, TrellisView, RESTAPIView)


class URLS:  # noqa
    """Define URLs to be used in :module:`urls.py` and in GUI views (injected in
    web pages via dicts or templates). NO URL MUST END WITH THE SLASH CHARACTER "/"
    """

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
    """Define web page tabs properties as Enum. A TAB T has  attributes:
    `T.title:str, T.icon:str, and optionally `T.viewclass`

    **Each Enum NAME is assumed to be constant**: if you change them, be prepared to
     fix a lot of stuff (also frontend side)

    as they are used as ID (also in JavaScript).
    Note: given a name as string variable, you can get the
    TAB element via square brackets notation, e.g. TAB["trellis"]
    """
    # icons (2nd element) are fontawesome bootsrap icons FIXME REF
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

