"""
Tests the eGSIM Django commands

Created on 6 Apr 2019

@author: riccardo
"""
import pytest
from unittest.mock import patch
from django.core.management import call_command
import builtins
# from pytest_django.plugin import django_db_blocker

# WARNING: tests requiring db access should use the function decorator:
# @pytest.mark.django_db
# which we overwrite to auto populate the db (see django_db_setup in conftest.py).
# This however pre-execute the same custom commands that we want to test here,
# causing problems in e.g. capturing the stdout. Looking at the code, to grant access
# to the empty db in the default Django mode, we just need the django_db_blocker fixture:

@pytest.mark.django_db
def test_initdb(django_db_blocker, capsys):
    """Test initdb command, with new Gsims and required attributes not
    managed by egsim

    NOTE: these are just shallow tests to check no error is raised. Deeper tests cannot
        be easily performed. An alternative is to issue bookmarks in PyCharm and inspect §§by via a bookmark in
        PyCharm
    """
    # why is it @patch not working if provided as decorator?
    # It has conflicts with capsys fixture, but only here ....
    # Anyway:

    # with patch.object(builtins, 'input', lambda _: 'yes'):
    call_command('egsim_init', interactive=False)
    captured = capsys.readouterr()
    capout = captured.out
    assert 'dry-run' not in capout.lower()  # dummy check

    call_command('egsim_init', interactive=False, dry_run=True)
    captured = capsys.readouterr()
    capout = captured.out
    assert 'dry-run' in capout.lower()  # dummy check


@pytest.mark.django_db
def test_initdb_gsim_required_attrs_not_defined(django_db_blocker, capsys):

    with patch('egsim.api.management.commands._egsim_oq.read_gsim_params',
               return_value={'REQUIRES_DISTANCES.azimuth': {'flatfile_name': 'azimuth'}}) as _:
        call_command('egsim_init', interactive=False)
        captured = capsys.readouterr()
        capout = captured.out

