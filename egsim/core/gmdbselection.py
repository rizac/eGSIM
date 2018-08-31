'''
Ground motion database selection utilities

Created on 25 Jul 2018

@author: riccardo
'''
from datetime import datetime

from smtk.strong_motion_selector import SMRecordSelector
from smtk.database_visualiser import db_magnitude_distance, DISTANCE_LABEL, get_magnitude_distances
from egsim.core.utils import EGSIM, strptime

GMDB = 'gmdb'
SEL = 'selection'
MIN = 'selection_min'
MAX = 'selection_max'
DIST_TYPE = 'distance_type'


def magdistdata(params):
    gmdb = compute_selection(params)
    dist_type = params[DIST_TYPE]
    mags, dists = get_magnitude_distances(gmdb, dist_type)
    return {'x': dists, 'y': mags, 'labels': [r.id for r in gmdb.records],
            'xlabel': DISTANCE_LABEL[dist_type], 'ylabel': 'Magnitude'}


def compute_selection(params):
    '''Computes the selection from the given already validated params and returns a filtered
    GroundMotionDatabase object'''
    # Instantiate the selection object with a database as argument:
    gmdb = params[GMDB]
    if params[MIN] is None and params[MAX] is None:
        return gmdb

    selector = SMRecordSelector(gmdb)
    selection = params[SEL]
    if selection == 'distance':
        def ret(params):
            return selector.select_within_distance_range(params[DIST_TYPE], params[MIN],
                                                         params[MAX], as_db=True)
    elif selection == 'magnitude':
        def ret(params):
            return selector.select_within_magnitude(params[MIN], params[MAX], as_db=True)
    elif selection == 'vs30':
        def ret(params):
            return selector.select_within_vs30_range(params[MIN], params[MAX], as_db=True)
    elif selection == 'time':
        def ret(params):
            return selector.select_within_time(params[MIN], params[MAX], as_db=True)
    elif selection == 'depth':
        def ret(params):
            return selector.select_within_depths(params[MIN], params[MAX], as_db=True)
    else:
        raise ValueError('invalid selection type')

    return ret(params)
