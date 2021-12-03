"""
Django Forms for eGSIM model-to-data comparison (residuals computation)

@author: riccardo
"""
from collections import defaultdict
from itertools import chain, repeat
from typing import Iterable

from django.forms import ChoiceField
from smtk.residuals.residual_plots import (residuals_density_distribution,
                                           residuals_with_depth,
                                           residuals_with_distance,
                                           residuals_with_magnitude,
                                           residuals_with_vs30,
                                           likelihood)
from smtk.residuals.gmpe_residuals import Residuals
from smtk.database_visualiser import DISTANCE_LABEL as SMTK_DISTANCE_LABEL

from . import FlatfileForm, MOF
from .. import GsimImtForm, relabel_sa, APIForm


##########
# Fields #
##########


# Copy SMTK_DISTANCE_LABELS replacing the key 'r_x' with 'rx':
DISTANCE_LABEL = dict(
    **{k: v for k, v in SMTK_DISTANCE_LABEL.items() if k != 'r_x'},
    rx=SMTK_DISTANCE_LABEL['r_x']
)


class PlotTypeField(ChoiceField):
    """An EgsimChoiceField which returns the selected function to compute
    residual plots"""
    # _base_choices maps the REST key to the tuple:
    # (GUI label, [function, dict_of_functon_kwargs])
    _base_choices = {
        MOF.RES: ('Residuals (density distribution)',
                  residuals_density_distribution, {}),
        MOF.LH: ('Likelihood', likelihood, {}),
        'mag': ('Residuals vs. Magnitude', residuals_with_magnitude, {}),
        'vs30': ('Residuals vs. Vs30', residuals_with_vs30, {}),
        'depth': ('Residuals vs. Depth', residuals_with_depth, {}),
        # insert distances related residuals:
        **{'dist_%s' % n: ("Residuals vs. %s" % l, residuals_with_distance,
                           {'distance_type': n})
           for n, l in DISTANCE_LABEL.items()}
        # 'site': ('Residuals vs. Site', None),
        # 'intra': ('Intra Event Residuals vs. Site', None),
    }

    def __init__(self, **kwargs):
        kwargs.setdefault('choices',
                          [(k, v[0]) for k, v in self._base_choices.items()])
        super(PlotTypeField, self).__init__(**kwargs)

    def clean(self, value):
        """Take the given value (string) and returns the tuple
        (smtk_function, function_kwargs)
        """
        value = super(PlotTypeField, self).clean(value)
        return self._base_choices[value][1:]


#########
# Forms #
#########


class ResidualsForm(GsimImtForm, FlatfileForm, APIForm):
    """Form for residual analysis"""

    plot_type = PlotTypeField(required=True)

    def clean(self):
        cleaned_data = super(ResidualsForm, self).clean()
        return cleaned_data
        # # Note: the call below calls GmdbForm.clean(self) BUT we should
        # # check why and how:
        # return GsimImtForm.clean(self)

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        params = cleaned_data  # FIXME: legacy code remove?
        func, kwargs = params["plot_type"]
        residuals = Residuals(params["gsim"], params["imt"])

        # Compute residuals.
        flatfile = params['flatfile']  # it's already filtered, in case)
        residuals.get_residuals(flatfile)

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
                    for stat in self.RESIDUALS_STATS:
                        res_plot.setdefault(stat, None)
                    if imt2 != imt:
                        res_plot['xlabel'] = relabel_sa(res_plot['xlabel'])
                        res_plot['ylabel'] = relabel_sa(res_plot['ylabel'])
                    # make also x and y keys consistent with trellis response:
                    res_plot['xvalues'] = res_plot.pop('x')
                    res_plot['yvalues'] = res_plot.pop('y')
                    ret[imt2][res_type][gsim] = res_plot

        return ret

    RESIDUALS_STATS = ('mean', 'stddev', 'median', 'slope', 'intercept',
                       'pvalue')

    @classmethod
    def csv_rows(cls, processed_data: dict) -> Iterable[list[str]]:
        """Yield lists of strings representing a csv row from the given
        process_result. the number of columns can be arbitrary and will be
        padded by `self.to_csv_buffer`

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
