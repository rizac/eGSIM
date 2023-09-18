"""
Created on 16 Feb 2018

@author: riccardo
"""
import pytest

from egsim.smtk.flatfile import columns
# from egsim.smtk.flatfile.columns import (InvalidColumn, MissingColumn,
#                                          ConflictingColumns,
#                                          get_all_names_of, InvalidDataInColumn,
#                                          InvalidColumnName)InvalidColumnName


def test_flatfile_exceptions():
    tested_classes = []

    for cols in [['hypo_lat'], ['unknown'], ['hypo_lat', 'unknown'],
                 ['st_lon', 'hypo_lat', 'unknown']]:

        tested_classes.append(columns.InvalidColumn)
        exc = tested_classes[-1](*cols)
        if len(cols) == 1:
            assert str(exc) == 'Invalid column ' + repr(cols[0])
        else:
            assert str(exc).startswith('Invalid columns ' + repr(cols[0]) + ', ')

        tested_classes.append(columns.MissingColumn)
        exc = tested_classes[-1](*cols)
        c_names = exc.get_all_names_of(cols[0])
        if len(cols) == 1:
            assert str(exc).startswith('Missing column ' + repr(c_names[0]))
        else:
            assert str(exc).startswith('Missing columns ' + repr(c_names[0]))
        if cols[0] == 'hypo_lat':
            assert f"{repr(c_names[0])} (or " in str(exc)
            assert all (repr(_) in str(exc) for _ in c_names)

        tested_classes.append(columns.ConflictingColumns)
        if len(cols) <=1:
            with pytest.raises(TypeError):
                # conflicting cols need at least two arguments:
                exc = tested_classes[-1](*cols)
            continue
        exc = tested_classes[-1](*cols)
        assert str(exc).startswith('Conflicting columns ' + repr(cols[0]) + ' vs. ')

        tested_classes.append(columns.InvalidDataInColumn)
        exc = tested_classes[-1](*cols)
        if len(cols) == 1:
            assert str(exc).startswith('Invalid data in column ' + repr(cols[0]))
        else:
            assert str(exc).startswith('Invalid data in columns ' + repr(cols[0]))

        tested_classes.append(columns.InvalidColumnName)
        exc = tested_classes[-1](*cols)
        if len(cols) == 1:
            assert str(exc).startswith('Invalid column name ' + repr(cols[0]))
        else:
            assert str(exc).startswith('Invalid column names ' + repr(cols[0]))

        # check that we tested all exception types:
        excs = set(tested_classes)
        found = 0
        for exc in dir(columns):
            cls = getattr(columns, exc, None)
            try:
                is_subcls = issubclass(cls, columns.InvalidColumn)
            except TypeError:
                is_subcls = False
            if is_subcls:
                found +=1
                if cls not in excs:
                    raise ValueError(f'Not tested: {str(cls)}')

        if found != len(excs):
            raise ValueError(f'Expected {len(excs)} InvalidColumn subclasses '
                             f'in module {str(columns)}, found {found}')