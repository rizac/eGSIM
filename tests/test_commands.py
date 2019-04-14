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
    ret = call_command('initdb')
    captured = capsys.readouterr()
    assert not captured.err
    sout = captured.out


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
