'''
Ground motion database selection utilities

Created on 25 Jul 2018

@author: riccardo
'''
from datetime import datetime

from smtk.strong_motion_selector import SMRecordSelector
from smtk.database_visualiser import db_magnitude_distance, DISTANCE_LABEL, get_magnitude_distances
from egsim.core.utils import EGSIM, strptime
from egsim.core.shapes import get_feature_properties

MODEL = 'model'
LAT = 'latitude'
LON = 'longitude'
LAT2 = 'latitude2'
LON2 = 'longitude2'
TRT = 'trt'


def compute_selection(params):
    '''Computes the selection from the given already validated params and returns a filtered
    list of gsim names'''
    trts = EGSIM.aval_trts() if TRT not in params else set(params[TRT])
    model_name = params.get(MODEL, None)
    if model_name is not None:
        # Instantiate the selection object with a database as argument:
        trts = get_feature_properties(EGSIM.tr_projects()[model_name],
                                      lon0=params[LON],
                                      lat0=params[LAT],
                                      trts=params[TRT],
                                      lon1=params.get(LON2, None),
                                      lat1=params.get(LAT2, None), key='OQ_TRT')
    return [gsim for gsim in EGSIM.aval_gsims() if EGSIM.trtof(gsim) in trts]
