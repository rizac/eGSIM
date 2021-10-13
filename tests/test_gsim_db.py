"""
Created on 5 Apr 2019

@author: riccardo
"""
from itertools import product
import uuid

import pytest
from openquake.hazardlib.gsim import registry
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned

from egsim.models import (Gsim, Imt, gsim_names, aval_gsims, aval_imts,
                          aval_trts, shared_imts, sharing_gsims, TrSelector)
from egsim.core.utils import OQ


# @pytest.mark.django_db
# def test_clear_db(django_db_setup):
#     test1 = list(aval_gsims())
#     assert len(test1)
#     empty_all()
#     test1 = list(aval_gsims())
#     assert not len(test1)


@pytest.mark.django_db
def test_db_0(django_db_setup):
    """Tests the egsim db"""
    with pytest.raises(MultipleObjectsReturned):  # @UndefinedVariable
        Gsim.objects.get()  # pylint: disable=no-member

    # from oq-engine
    # (https://github.com/gem/oq-engine/tree/master/openquake/hazardlib/gsim)
    #
    # AbrahamsonEtAl2014: 'PGA', 'SA', 'PGV'
    # const.TRT.ACTIVE_SHALLOW_CRUST
    #
    # AbrahamsonEtAl2015SInter: 'PGA' 'SA'
    # const.TRT.SUBDUCTION_INTERFACE
    #
    # BommerEtAl2009RSD: 'RSD595', 'RSD575'
    # const.TRT.ACTIVE_SHALLOW_CRUST
    #
    # CauzziEtAl2014: 'PGA', 'SA', 'PGV'
    # const.TRT.ACTIVE_SHALLOW_CRUST

    # there are:
    # 4 gsims with trt1
    # 4 gsims with trt2
    # 4 gsims with imt1 and imt2
    # 2 gsims with imt1
    # 2 gims with no imt

    test1 = list(aval_gsims())
    assert len(test1) <= len(OQ.gsims())

    test2 = list(aval_gsims())
    assert len(test2) <= len(OQ.gsims())
    assert len(test1) == len(test2)

    test1 = list(aval_imts())
    assert len(test1) <= len(OQ.imts())

    test1 = list(aval_trts())
    assert len(test1) <= len(OQ.trts())

    test1 = list(gsim_names())
    assert len(test1) <= len(OQ.gsims())

    # Note that below we can supply each instance key (string, e.g.
    # 'PGA') or the entity itself. Same for trt

    test1 = set(gsim_names(imts=['PGA', 'SA']))
    expected = set(['AbrahamsonEtAl2014', 'AbrahamsonEtAl2015SInter',
                    'CauzziEtAl2014'])
    assert expected & test1 == expected
    assert 'BommerEtAl2009RSD' not in test1

    imtobjs = Imt.objects  # pylint: disable=no-member
    PGA, SA = list(imtobjs.filter(key='PGA')), list(imtobjs.filter(key='SA'))
    assert len(PGA) == len(SA) == 1
    PGA, SA = PGA[0], SA[0]
    # try by querying via objects (same result as above):
    test2 = set(gsim_names(imts=[PGA, SA]))
    assert test1 == test2
    # try to get by id (same result as above):
    test2 = set(gsim_names(imts=[PGA.id, SA.id]))
    assert test1 == test2

    test1 = set(gsim_names(imts=['PGA', 'SA'], trts=['SUBDUCTION_INTERFACE']))
    assert 'AbrahamsonEtAl2015SInter' in test1
    not_expected = set(['AbrahamsonEtAl2014', 'BommerEtAl2009RSD',
                        'CauzziEtAl2014'])
    assert not (not_expected & test1)

    test1 = set(gsim_names(gsims=[_ for _ in aval_gsims() if _[0] == 'C'],
                           imts=['PGA', 'SA'], trts=['ACTIVE_SHALLOW_CRUST']))
    assert 'CauzziEtAl2014' in test1
    not_expected = set(['AbrahamsonEtAl2014', 'AbrahamsonEtAl2015SInter',
                        'BommerEtAl2009RSD'])
    assert not (not_expected & test1)

    test1 = set(gsim_names(imts=['PGA', 'SA', 'PGV']))
    expected = set(['AbrahamsonEtAl2014', 'AbrahamsonEtAl2015SInter',
                    'CauzziEtAl2014'])
    assert expected & test1 == expected
    assert 'BommerEtAl2009RSD' not in test1

    # BUT now provide strict match for imts:
    test1 = set(gsim_names(imts=['PGA', 'SA', 'PGV'],
                           imts_match_all=True))
    expected = set(['AbrahamsonEtAl2014', 'CauzziEtAl2014'])
    assert expected & test1 == expected
    assert 'BommerEtAl2009RSD' not in test1
    assert 'AbrahamsonEtAl2015SInter' not in test1

    # AbrahamsonEtAl2014: 'PGA', 'SA', 'PGV'
    # const.TRT.ACTIVE_SHALLOW_CRUST
    #
    # AbrahamsonEtAl2015SInter: 'PGA' 'SA'
    # const.TRT.SUBDUCTION_INTERFACE
    #
    # BommerEtAl2009RSD: 'RSD595', 'RSD575'
    # const.TRT.ACTIVE_SHALLOW_CRUST
    #
    # CauzziEtAl2014: 'PGA', 'SA', 'PGV'
    # const.TRT.ACTIVE_SHALLOW_CRUST

    expected_imts = ['PGA', 'SA']
    assert sorted(shared_imts(['AbrahamsonEtAl2014',
                               'AbrahamsonEtAl2015SInter',
                               'CauzziEtAl2014'])) == expected_imts

    expected_gsims = set(['AbrahamsonEtAl2014', 'AbrahamsonEtAl2015SInter',
                          'CauzziEtAl2014'])
    sharing_gsims_set = set(sharing_gsims(['PGA','SA']))
    assert sharing_gsims_set & expected_gsims == expected_gsims
    assert 'BommerEtAl2009RSD' not in sharing_gsims_set

    # type a point on italy (active shallow crust), and see
    trsel = TrSelector('SHARE', lon0=11, lat0=44)
    test1 = set(gsim_names(tr_selector=trsel))
    expected_gsims = set(['AbrahamsonEtAl2014', 'BommerEtAl2009RSD',
                          'CauzziEtAl2014'])
    assert expected_gsims & test1 == expected_gsims
    assert 'AbrahamsonEtAl2015SInter' not in test1
