"""
Django Forms for eGSIM model-to-data comparison (residuals computation)

@author: riccardo
"""
from collections import defaultdict
from itertools import chain, repeat
from typing import Iterable, Any

from smtk.residuals.residual_plots import (residuals_density_distribution,
                                           residuals_with_depth,
                                           residuals_with_distance,
                                           residuals_with_magnitude,
                                           residuals_with_vs30,
                                           likelihood)
from smtk.database_visualiser import DISTANCE_LABEL

from . import MOF, get_residuals, GsimImtFlatfileForm
from .. import APIForm, relabel_sa
from ..fields import ChoiceField


# For residuals with distance, use labels coded in smtk DISTANCE_LABEL dict:
from ...flatfile import EgsimContextDB

_DIST_LABEL = dict(DISTANCE_LABEL)
# But replace 'r_x' with 'rx' (residuals with distance expects the latter as arg):
_DIST_LABEL['rx'] = _DIST_LABEL.pop('r_x')


PLOT_TYPE = {
    # key: display name, residuals function, function kwargs
    MOF.RES: ('Residuals (density distribution)',
              residuals_density_distribution, {}),
    MOF.LH: ('Likelihood', likelihood, {}),
    'mag': ('Residuals vs. Magnitude', residuals_with_magnitude, {}),
    'vs30': ('Residuals vs. Vs30', residuals_with_vs30, {}),
    'depth': ('Residuals vs. Depth', residuals_with_depth, {}),
    # insert distances related residuals:
    **{'dist_%s' % n: ("Residuals vs. %s" % l, residuals_with_distance,
                       {'distance_type': n}) for n, l in _DIST_LABEL.items()}
}


class ResidualsForm(GsimImtFlatfileForm, APIForm):
    """Form for residual analysis"""

    # Fields of this class are exposed as API parameters via their attribute name. This
    # default behaviour can be changed here by manually mapping a Field attribute name to
    # its API param name(s). `_field2params` allows to easily change API params whilst
    # keeping the Field attribute names immutable, which is needed to avoid breaking the
    # code. See `egsim.forms.EgsimFormMeta` for details
    field2params = {'plot_type': ['plot']}

    plot_type = ChoiceField(required=True, label='Plot type',
                            choices=[(k, f'{v[0]} [{k}] ')
                                     for k, v in PLOT_TYPE.items()])

    RESIDUALS_STATS = ('mean', 'stddev', 'median', 'slope', 'intercept',
                       'pvalue')

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        params = cleaned_data  # FIXME: legacy code remove?
        _, func, kwargs = PLOT_TYPE[params["plot_type"]]

        # Compute residuals.
        residuals = get_residuals(params['flatfile'], params["gsim"], params["imt"])

        # statistics = residuals.get_residual_statistics()
        ret = defaultdict(lambda: defaultdict(lambda: {}))

        # extend keyword arguments:
        kwargs = dict(kwargs, residuals=residuals, as_json=True)
        # linestep = binwidth/10
        for gsim in residuals.residuals:
            for imt in residuals.residuals[gsim]:
                kwargs['gmpe'] = gsim
                kwargs['imt'] = imt
                imt2 = relabel_sa(imt)
                res_plots = func(**kwargs)
                for res_type, res_plot in res_plots.items():
                    for stat in cls.RESIDUALS_STATS:
                        res_plot.setdefault(stat, None)
                    if imt2 != imt:
                        res_plot['xlabel'] = relabel_sa(res_plot['xlabel'])
                        res_plot['ylabel'] = relabel_sa(res_plot['ylabel'])
                    # make also x and y keys consistent with trellis response:
                    res_plot['xvalues'] = res_plot.pop('x')
                    res_plot['yvalues'] = res_plot.pop('y')
                    ret[imt2][res_type][gsim] = res_plot

        return ret

    @classmethod
    def csv_rows(cls, processed_data: dict) -> Iterable[Iterable[Any]]:
        """Yield CSV rows, where each row is an iterables of Python objects
        representing a cell value. Each row doesn't need to contain the same
        number of elements, the caller function `self.to_csv_buffer` will pad
        columns with Nones, in case (note that None is rendered as "", any other
        value using its string representation).

        :param processed_data: dict resulting from `self.process_data`
        """
        stats = cls.RESIDUALS_STATS
        yield chain(['imt', 'type', 'gsim'], stats)
        for imt, imts in processed_data.items():
            for type_, types in imts.items():
                for gsim, res_plot in types.items():
                    yield chain([imt, type_, gsim],
                                (res_plot[stat] for stat in stats),
                                [res_plot['xlabel']], res_plot['xvalues'])
                    yield chain(repeat('', 9), [res_plot['ylabel']],
                                res_plot['yvalues'])
