"""
Created on 16 Feb 2018

@author: riccardo
"""
import pytest

from egsim.smtk import flatfile
from egsim.smtk.flatfile import (InvalidColumn, MissingColumn, ConflictingColumns,
                                 InvalidDataInColumn, InvalidColumnName)


def test_flatfile_exceptions():
    tested_classes = []

    for cols in [['hypo_lat'], ['unknown'], ['hypo_lat', 'unknown'],
                 ['st_lon', 'hypo_lat', 'unknown']]:

        tested_classes.append(InvalidColumn)
        exc = tested_classes[-1](*cols)
        if len(cols) == 1:
            assert str(exc) == 'Invalid column ' + repr(cols[0])
        else:
            assert str(exc).startswith('Invalid columns ' + repr(cols[0]) + ', ')

        tested_classes.append(MissingColumn)
        exc = tested_classes[-1](*cols)
        c_names = exc.names
        if len(cols) == 1:
            assert str(exc).startswith('Missing column ' + c_names[0])
        else:
            assert str(exc).startswith('Missing columns ' + c_names[0])
        if cols[0] == 'hypo_lat':
            assert c_names[0] in str(exc)

        tested_classes.append(ConflictingColumns)
        if len(cols) <=1:
            with pytest.raises(TypeError):
                # conflicting cols need at least two arguments:
                exc = tested_classes[-1](*cols)
            continue
        exc = tested_classes[-1](*cols)
        assert str(exc).startswith('Conflicting columns ' + repr(cols[0]) + ' vs. ')

        tested_classes.append(InvalidDataInColumn)
        exc = tested_classes[-1](*cols)
        if len(cols) == 1:
            assert str(exc).startswith('Invalid data in column ' + repr(cols[0]))
        else:
            assert str(exc).startswith('Invalid data in columns ' + repr(cols[0]))

        tested_classes.append(InvalidColumnName)
        exc = tested_classes[-1](*cols)
        if len(cols) == 1:
            assert str(exc).startswith('Invalid column name ' + repr(cols[0]))
        else:
            assert str(exc).startswith('Invalid column names ' + repr(cols[0]))

        # check that we tested all exception types:
        excs = set(tested_classes)
        found = 0
        for exc in dir(flatfile):
            cls = getattr(flatfile, exc, None)
            try:
                is_subcls = issubclass(cls, InvalidColumn)
            except TypeError:
                is_subcls = False
            if is_subcls:
                found +=1
                if cls not in excs:
                    raise ValueError(f'Not tested: {str(cls)}')

        if found != len(excs):
            raise ValueError(f'Expected {len(excs)} InvalidColumn subclasses '
                             f'in module {str(flatfile)}, found {found}')