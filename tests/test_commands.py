'''
Tests the eGSIM Django commands

Created on 6 Apr 2019

@author: riccardo
'''
import os
import pytest

from mock import patch
from django.core.management.base import CommandError
from django.core.management import call_command


@pytest.mark.django_db
def test_initdb(capsys):
    " Test initdb command."
    call_command('initdb')
    captured = capsys.readouterr()
    assert not captured.err
    # sout = captured.out


@pytest.mark.django_db
def test_initdb_gsim_required_attrs_not_defined(capsys):
    """Test initdb command, with new Gsims and required attributes not
    managed by egsim"""
    # why is it @patch not working if provided as decorator?
    # It has conflicts with capsys fixture, but only here ....
    # Anyway:
    with patch('egsim.management.commands.initdb.'
               'get_gsim_required_attrs_dict',
               return_value={'rjb': 'rjb'}) as _:
        call_command('initdb')
        captured = capsys.readouterr()
        capout = captured.out
        assert 'WARNING: ' in capout

    for key in ['vs30measured', 'ztor', 'dip']:
        assert "%s (defined for " % key in capout
    assert "rjb" not in capout


@patch('egsim.management.commands.gmdb.get_gmdb_path')
def test_gmdb_esm(mock_get_gmdb_path, testdata, capsys):
    '''Test gmdb_esm command (and consequently, also gmbd command)'''
    ffname = 'esm_sa_flatfile_2018.csv'
    ffpath = testdata.path(ffname)
    outpath = ffpath + '.tmp.hd5'
    assert not os.path.isfile(outpath)
    mock_get_gmdb_path.return_value = outpath
    try:
        ret = call_command('gmdb_esm',  ffpath)
        captured = capsys.readouterr()
        assert not captured.err
        sout = captured.out
        # now that the file exists, test that overwriting on the same
        # db raises:    
        with pytest.raises(CommandError):
            ret = call_command('gmdb_esm')
    finally:
        if os.path.isfile(outpath):
            os.remove(outpath)
