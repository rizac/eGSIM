"""
Tests the eGSIM Django commands

Created on 6 Apr 2019

@author: riccardo
"""
import os
from stat import S_IWUSR, S_IWGRP, S_IWOTH
import pytest

from egsim.management.commands._utils import get_classes, EgsimBaseCommand

try:  # https://stackoverflow.com/questions/44441929
    from unittest.mock import patch  # noqa (ok in py3.8)
except ImportError:
    from mock import patch  # noqa (ok in py3.7)

from django.core.management.base import CommandError
from django.core.management import call_command


# def test_get_classes():
    # commands = ['oq2db', 'gsimsel2db', 'reg2db']
    # commands =  ['egsim.management.commands.' + _ for _ in commands]
    # for _ in commands:
    #     cls = get_classes(_, EgsimBaseCommand)
    # clz = get_classes('egsim.models')

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


@pytest.mark.parametrize('input_flatfile_name, sep',
                         [('egsim_flatfile_marmara_event_26092019_nobom.csv', 'comma'),
                          ('egsim_flatfile_marmara_event_26092019.csv', 'comma'),
                          ('esm_sa_flatfile_2018.csv', None)])
@patch('egsim.management.commands.gmdb.get_gmdb_path')
@patch('egsim.management.commands.gmdb.input')
def test_gmdb_esm(mock_input,
                  mock_get_gmdb_path,
                  input_flatfile_name, sep,
                  # pytest fixtures:
                  testdata, capsys):
    '''Test gmdb_esm command (and consequently, also gmbd command)'''
    ffname = input_flatfile_name
    ffpath = testdata.path(ffname)
    outdir = testdata.path('gmdb')
    outpath = os.path.join(outdir, os.path.splitext(ffname)[0] + '.hdf5')
    assert not os.path.isfile(outpath)
    mock_get_gmdb_path.return_value = outdir
    try:
        # not specifying arguments:
        with pytest.raises(CommandError) as cerr:
            _ = call_command('gmdb_esm')
        assert 'the following arguments are required: flatfile' in \
            str(cerr)

        mock_input.return_value = ''
        # we decide NOT to create the dir:
        with pytest.raises(CommandError) as cerr:
            _ = call_command('gmdb_esm',  ffpath)
        assert 'Operation aborted by user' in \
            str(cerr)
        # now we anser 'yes' to the create dir:
        mock_input.return_value = 'y'

        # specifying duplicated arguments:
        with pytest.raises(CommandError) as cerr:
            _ = call_command('gmdb_esm', ffpath, ffpath)
        assert 'flatfile is specified more than once' in \
            str(cerr)

        # ok, normal case:
        if sep is None:
            _ = call_command('gmdb_esm',  ffpath)
        else:
            _ = call_command('gmdb_esm', ffpath, sep=sep)
        assert os.path.isfile(outpath)
        captured = capsys.readouterr()
        assert not captured.err
        sout = captured.out
        # try to remove the file: not permitted:
        assert os.access(outpath, os.R_OK)
        # this is False if you are testing from root, as root has always
        # write privileges: https://stackoverflow.com/a/27747471
        # Thus this MIGHT not work:
        # assert not os.access(outpath, os.W_OK)
        # therefore
        assert not os.stat(outpath).st_mode & S_IWUSR
        assert not os.stat(outpath).st_mode & S_IWGRP
        assert not os.stat(outpath).st_mode & S_IWOTH

        # now that the file exists, test that overwriting on the same
        # db raises:
        with pytest.raises(CommandError) as cerr:
            _ = call_command('gmdb_esm',  ffpath)
        assert 'No flatfile to parse' in str(cerr)

    finally:
        if os.path.isfile(outpath):
            os.remove(outpath)
        if os.path.isdir(outdir):
            os.rmdir(outdir)
