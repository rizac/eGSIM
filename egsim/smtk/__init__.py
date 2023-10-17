"""Root module for the strong motion modeller toolkit (smtk) package of eGSIM"""
from .trellis import get_trellis
from .residuals import get_residuals
from .flatfile import read_flatfile
from .registry import (registered_gsim_names, registered_imt_names, gsim,
                       site_params_required_by, rupture_params_required_by,
                       distances_required_by, imts_defined_for, sa_limits,
                       gsim_name, GsimInitError)
