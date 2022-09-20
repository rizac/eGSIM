from os.path import join, dirname, abspath
import yaml

from .. import URLS

from .egsim import get_context as egsim_page_renderer_context
from .apidoc import get_context as apidoc_page_renderer_context


def ref_and_license_page_renderer_context():
    refs = {}
    with open(join(dirname(dirname(dirname(abspath(__file__)))), 'api',
                   'management', 'commands', 'data', 'data_sources.yaml')) as _:
        for ref in yaml.safe_load(_).values():
            name = ref.pop('display_name')
            refs[name] = ref
    return {'references': refs}


def imprint_page_renderer_context():
    return {
        'data_protection_url': URLS.DATA_PROTECTION,
        'ref_and_license_url': URLS.REF_AND_LICENSE
    }


def home_page_renderer_context():
    return {'ref_and_license_url': URLS.REF_AND_LICENSE}