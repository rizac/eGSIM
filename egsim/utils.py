'''
Created on 29 Jan 2018

@author: riccardo
'''
from collections import OrderedDict

def get_menus():
    return OrderedDict([('home', 'Home'), ('trellis', 'Trellis plots'),
                        ('residuals', 'Residuals'), ('loglikelihood', 'Log-likelihood analysis')])
