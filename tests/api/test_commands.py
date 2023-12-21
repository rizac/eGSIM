"""
Tests the eGSIM Django commands

Created on 6 Apr 2019

@author: riccardo
"""
import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_initdb(capsys):
    """Test the command initializing the DB with eGSIM data"""
    # NOTE: the decorator `django_db` already executes the command below, so
    # we could simply pass here, or even remove the test entirely. Just provide
    # capsys in case we want to test the generated output in more details
    call_command('egsim_init', interactive=False)
    captured = capsys.readouterr()
    capout = captured.out
    assert capout and "Unused Flatfile column(s)" not in capout


def test_areequal(areequal):
    """tests our fixture areequal used extensively in tests"""
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


    # FIXME: why if we write the code below inside a new function, e.g.:
# @pytest.mark.django_db
# def tst_initdb_gsim_required_attrs_not_defined(capsys):
#     # we have a 'ValueError: I/O operation on closed file.' which makes sense only if `capsys`
#     # (which closes the I/O TeewtWriter stream) was the same as above.
#
#     with patch('egsim.api.management.commands._egsim_oq.read_registered_flatfile_columns',
#                return_value={
#                    'azimuth' : ColumnMetadata(),
#                    # {'oq_name': 'rx',
#                    #  'category': ColumnMetadata.Category.distance_measure}
#                 }) as _:
#         call_command('egsim_init', interactive=False)
#         captured = capsys.readouterr()
#         capout = captured.out
#         assert "Unused Flatfile column(s): azimuth" in capout
