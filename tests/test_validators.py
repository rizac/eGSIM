import pytest
from openquake.hazardlib import imt

from egsim.smtk import validate_inputs, harmonize_input_gsims, harmonize_input_imts, gsim
from egsim.smtk.validators import ModelUndefinedForImtError, validate_imt_sa_limits


def test_invalid_imts():
    gsims = ['BindiEtAl2014Rjb']
    imts = ['CAV']
    with pytest.raises(ModelUndefinedForImtError) as err:
        validate_inputs(
            harmonize_input_gsims(gsims),
            harmonize_input_imts(imts)
        )

    # period outside the gsim SA limits:
    validate_inputs(
        harmonize_input_gsims(gsims),
        harmonize_input_imts(['SA(50)'])
    )

    valid_imts = validate_imt_sa_limits(gsim(gsims[0]),
                                        {'SA(50)': imt.from_string('SA(50)')})

    assert not valid_imts

    valid_imts = validate_imt_sa_limits(gsim(gsims[0]),
                                        {'SA(1.1)': imt.from_string('SA(1.1)'),
                                         'SA(50)': imt.from_string('SA(50)')})
    assert list(valid_imts) == ['SA(1.1)']