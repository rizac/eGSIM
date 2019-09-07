'''
Created on 16 Feb 2018

@author: riccardo
'''
from datetime import datetime, date

import pytest

from egsim.core.utils import vectorize, querystring, get_gmdb_column_desc,\
    GSIM_REQUIRED_ATTRS, OQ
from egsim.forms.fields import NArrayField
from egsim.core.smtk import _relabel_sa, gmdb_records, get_selexpr
from smtk.sm_table import GMTableDescription, GroundMotionTable
from egsim.models import aval_gsims
from smtk.residuals.gmpe_residuals import Residuals


def test_gmdb_columns():
    '''test the gmdb column descriptions'''
    ret = get_gmdb_column_desc()
    assert not any(_ == '? (unkwnown type)' for _ in ret.values())
    assert 'string. Possible values are:' in ret['style_of_faulting'][0]
    assert 'date-time (ISO formatted) string' in ret['event_time'][0]


def test_vectorize():
    '''tests the vectorize function'''
    for arg in (None, '', 'abc', 1, 1.4005, True):
        expected = [arg]
        assert vectorize(arg) == expected
        assert vectorize(expected) is expected
    args = ([1, 2, 3], range(5), (1 for _ in [1, 2, 3]))
    for arg in args:
        assert vectorize(arg) is arg


def test_querystring():
    value = 'abc'
    with pytest.raises(AttributeError):  # @UndefinedVariable
        querystring(value)
    value = {'abc': {'a': 9}}
    with pytest.raises(ValueError):  # @UndefinedVariable
        querystring(value)
    ddd = datetime(2016, 1, 3, 4, 5, 6, 345)
    value = {'abc': ddd}
    patt = querystring(value)
    assert patt == "abc=2016-01-03T04%3A05%3A06.000345"
    for ddd in [date(2011, 4, 5), datetime(2011, 4, 5)]:
        assert querystring({'abc': ddd}) == "abc=2011-04-05"
    value = {'abc': [1, 'a', 1.1, '&invalid']}
    patt = querystring(value)
    assert patt == 'abc=1,a,1.1,%26invalid'


@pytest.mark.django_db
def test_narrayfield_get_decimals():
    '''tests ndarrayfield get_decimals'''
    d_0 = NArrayField.get_decimals('1.3e45')
    assert d_0 == 0
    d_0 = NArrayField.get_decimals('1.3e1')
    assert d_0 == 0
    d_0 = NArrayField.get_decimals('1.3e0')
    assert d_0 == 1
    d_1 = NArrayField.get_decimals('1e-45')
    assert d_1 == 45
    d_2 = NArrayField.get_decimals('-5.005601')
    assert d_2 == 6
    d_2 = NArrayField.get_decimals('-5.0')
    assert d_2 == 1
    d_3 = NArrayField.get_decimals('-6')
    assert d_3 == 0
    d_4 = NArrayField.get_decimals('1.3E-6')
    assert d_4 == 7
    d_5 = NArrayField.get_decimals('1.3e45', '1.3E-6', '-6', '-5.005601',
                                   '1e-45')
    assert d_5 == 45


def test_relabel_sa():
    '''tests _relabel_sa, which removes redundant trailing zeroes'''
    inputs = ['SA(1)', 'SA(1.133)', 'SA(10000)',
              ' SA(1)', ' SA(1.133)', ' SA(10000)',
              'SA(1) ', 'SA(1.133) ', 'SA(10000) ',
              '-SA(.100)', 'aSA(.100)', 'SA(1.1030)r', 'SA(1.1030)-']
    for string in inputs:
        assert _relabel_sa(string) == string

    assert _relabel_sa('SA(.100)') == 'SA(.1)'
    assert _relabel_sa('SA(.100) ') == 'SA(.1) '
    assert _relabel_sa(' SA(.100)') == ' SA(.1)'
    assert _relabel_sa('SA(1.1030)') == 'SA(1.103)'
    assert _relabel_sa(' SA(1.1030)') == ' SA(1.103)'
    assert _relabel_sa('SA(1.1030) ') == 'SA(1.103) '
    assert _relabel_sa('SA(1.1030)') == 'SA(1.103)'
    assert _relabel_sa(' SA(1.1030)') == ' SA(1.103)'
    assert _relabel_sa('SA(1.1030) ') == 'SA(1.103) '
    assert _relabel_sa('SA(1.000)') == 'SA(1.0)'
    assert _relabel_sa(' SA(1.000)') == ' SA(1.0)'
    assert _relabel_sa('SA(1.000) ') == 'SA(1.0) '
    assert _relabel_sa('(SA(1.000))') == '(SA(1.0))'
    assert _relabel_sa(' (SA(1.000))') == ' (SA(1.0))'
    assert _relabel_sa('(SA(1.000)) ') == '(SA(1.0)) '
    # test some "real" case:
    assert _relabel_sa('Median SA(0.200000) (g)') == \
        'Median SA(0.2) (g)'
    assert _relabel_sa('Median SA(2.00000) (g)') == \
        'Median SA(2.0) (g)'
    assert _relabel_sa('Z (SA(2.00000))') == \
        'Z (SA(2.0))'


def test_areequal(areequal):
    '''tests our fixture areequal used extensively in tests'''
    obj1 = [{'a': 9, 'b': 120}, 'abc', [1.00000001, 2, 2.000000005]]
    obj2 = ['abc', [1, 2, 2], {'b': 120, 'a': 9}]
    assert areequal(obj1, obj2)
    # make a small perturbation in 'a':
    obj2 = ['abc', [1, 2, 2], {'b': 120, 'a': 9.00000001}]
    assert areequal(obj1, obj2)  # still equal
    assert not areequal([], {})
    assert not areequal({}, [])
    assert areequal([1.0000000000001], [1])
    assert areequal({'a': 1.0000000000001, 'b': [1, 2, 3], 'c': 'abc'},
                    {'c': 'abc', 'b': [1, 1.99999999998, 3], 'a': 1})
    # 'b' is now 1.9, retol says: not equal:
    assert not areequal({'a': 1.0000000000001, 'b': [1, 2, 3], 'c': 'abc'},
                        {'c': 'abc', 'b': [1, 1.9, 3], 'a': 1})
    assert areequal(1.0000000000001, 1)


def test_gsim_required_attrs_mappings_are_in_gmtable():
    '''self explanatory'''
    columns = set(GMTableDescription.keys())
    for (column, nanval) in GSIM_REQUIRED_ATTRS.values():
        if column:
            assert column in columns


@pytest.mark.django_db
def test_gsim_required_attrs_mappings_are_in_gsims():
    # now test that all keys are in Gsims required attrs:
    gsims_attrs = set()
    for gsim in aval_gsims():
        gsims_attrs |= set(OQ.required_attrs(gsim))
    # exlude some attributes not currently in any gsim but that we
    # be included in future OpenQuake releases:
    exclude = set(['strike'])
    for att in GSIM_REQUIRED_ATTRS:
        if att not in exclude:
            assert att in gsims_attrs


def check_gsim_defined_for_current_db(testdata):
    '''no test function, it is used to inspect in debug mode in order to get
    gsims with records in the current gmdb used for tests'''
    for gsim in OQ.gsims():
        try:
            residuals = Residuals([gsim], ['PGA', 'PGV', 'SA(0.1)'])
            gmdbpath = testdata.path('esm_sa_flatfile_2018.csv.hd5')
            gm_table = GroundMotionTable(gmdbpath, 'esm_sa_flatfile_2018',
                                         mode='r')
            selexpr = get_selexpr(gsim)
            num = gmdb_records(residuals, gm_table.filter(selexpr))
        except:
            pass


def test_dict_is_ordered():
    '''Stupid test to assert that dicts keys are sorted according to insertion
    order (from py3.6 on, standard from py3.7 on)'''
    assert list(dict([[1, 2], [3, 4], [6, 5], [3, 5], [1, 1]]).keys()) \
        == [1, 3, 6]
    assert list(dict({1: 2, 3: 4, 6: 5, 3: 5, 1: 1}).keys()) == [1, 3, 6]
    assert list({11: 5, 'g': 67}) == [11, 'g']
    assert list({'11': 5, 6.05: 67}) == ['11', 6.05]


def test_oq_dicts_are_copies():
    '''tests that OQ entities (gsims and imts) are newly created'''
    dic1 = OQ.gsims()
    dic2 = OQ.gsims()
    assert dic1 == dic2
    assert dic1 is not dic2
    dic1 = OQ.imts()
    dic2 = OQ.imts()
    assert dic1 == dic2
    assert dic1 is not dic2
