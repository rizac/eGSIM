'''
Test the core.shapes module

Created on 2 Jul 2018

@author: riccardo
'''
from openquake.hazardlib.const import TRT


from egsim.core.utils import EGSIM

from egsim.core.shapes import get_features_containing, find_shp, to_geojson,\
    get_features_intersecting, get_feature_properties


def test_share_geojson():
    '''tests the shapes module by mocking the creation of the share geojson from its
    shape files'''
    files = find_shp('/Users/riccardo/work/gfz/projects/sources/python/egsim/tmp/data/share')
    assert len(files) == 3
    geojson = to_geojson(*files)
    assert len(geojson['features']) == 432
    trts2 = EGSIM.aval_trts
    # define the mappings between share trt and openquake trt
    mappings = {
                'active shallow crust':  TRT.ACTIVE_SHALLOW_CRUST,  # 'Active Shallow Crust',
                'stable shallow crust': TRT.STABLE_CONTINENTAL,  # 'Stable Shallow Crust',
                'subduction interface': TRT.SUBDUCTION_INTERFACE,  # 'Subduction Interface',
                'subduction intraslab': TRT.SUBDUCTION_INTRASLAB,  # 'Subduction IntraSlab',
                "upper mantle": TRT. UPPER_MANTLE,  # "Upper Mantle",
                'volcanic': TRT.VOLCANIC,  # 'Volcanic',
                'geothermal': TRT.GEOTHERMAL,  # 'Geothermal',
                'induced': TRT.INDUCED,  # 'Induced',
                "subduction inslab": TRT.SUBDUCTION_INTRASLAB,  # "Subduction IntraSlab",
                "stable continental crust": TRT.STABLE_CONTINENTAL,  # 'Stable Shallow Crust',
                "inslab": TRT.SUBDUCTION_INTRASLAB,  # "Subduction IntraSlab"
        }

    for feat in geojson['features']:
        props = feat['properties']
        trt = mappings[(props.get('TECTONICS', '') or props['TECREG']).lower()]
        assert trt in trts2.values()
        props['OQ_TRT'] = trt

    # do a test with random coordinates:
    berlin_coordinates = (13.40, 52.52)
    fts = get_features_containing(geojson, *berlin_coordinates)
    assert len(fts) == 1 and fts[0]['properties']['OQ_TRT'] == TRT.STABLE_CONTINENTAL

    berlin_coordinates_rect = (13.40, 52.52, 13.41, 52.53)
    fts = get_features_intersecting(geojson, *berlin_coordinates_rect)
    assert len(fts) == 1 and fts[0]['properties']['OQ_TRT'] == TRT.STABLE_CONTINENTAL

    wrong_coords = (berlin_coordinates[1], berlin_coordinates[0])
    fts = get_features_containing(geojson, *wrong_coords)
    assert not fts

    props1 = get_feature_properties(geojson, *berlin_coordinates)
    props2 = get_feature_properties(geojson, *berlin_coordinates_rect[:2], None,
                                    *berlin_coordinates_rect[2:])
    assert props1 == props2 == {'Stable Shallow Crust'}

