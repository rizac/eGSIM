'''
Tests the command initdb

Created on 6 Apr 2019

@author: riccardo
'''

import pytest

from openquake.hazardlib.const import TRT
from django.core.management import call_command

from egsim.models import Trt


@pytest.mark.django_db
def test_mycommand(django_db_setup, capsys):
    " Test initdb command."

    args = []
    opts = {}
    ret = call_command('initdb', *args, **opts)
    captured = capsys.readouterr()
    assert not captured.err
    sout = captured.out