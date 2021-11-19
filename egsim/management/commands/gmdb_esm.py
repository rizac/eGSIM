'''
Created on 11 Apr 2019

@author: riccardo
'''
from smtk.sm_table_parsers import EsmParser
from .gmdb import Command as BaseC


class Command(BaseC):
    """Command to create a standard Ground Motion Database
    """
    help = ('Creates a Ground Motion Database from a provided ESM flatfile(s). '
            'as arguments')

    parserclass = EsmParser
