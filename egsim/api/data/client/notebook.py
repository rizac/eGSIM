import sys
from collections.abc import Iterable, Callable
from typing import Optional, Union
import uuid
import json

from snippets import (get_doc, create_write_hdf_snippet, create_read_hdf_snippet,
                      create_write_csv_snippet, create_read_csv_snippet, pd_tutorial,
                      egsim_base_url, local_server_base_url)

def nb_code_cell(src_code: Optional[Union[str, Iterable[str]]]=None):
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": str(uuid.uuid4()),
        "metadata": {},
        "outputs": [],
        "source": _split_lines(src_code)
    }

def nb_markdown_cell(src_code: Optional[Union[str, Iterable[str]]]=None):
    return  {
        "cell_type": "markdown",
        "id":  str(uuid.uuid4()),
        "metadata": {},
        "source": _split_lines(src_code)
    }


def _split_lines(src_code: Optional[Union[str, Iterable[str]]]=None) -> list[str]:
    if src_code is None:
        return []
    if isinstance(src_code, str):
        return src_code.strip().splitlines(keepends=True)
    ret = []
    for chunk in src_code:
        ret.extend(_split_lines(chunk))
    return ret


def nb_create(*cells: dict) -> dict:
    return {
        "cells": list(cells),
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3 (ipykernel)",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.9.7"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 5
    }



nb_setup_cell = """
# IPython/Jupyter setup (Optional: edit or remove at your wish)
%reload_ext autoreload
%autoreload 2
from IPython.display import display, HTML, Markdown
# make wide HTML cells (e.g., as created by `display(dataframe)`) display a scrollbar:
display(HTML("<style>div.jp-OutputArea-output.jp-RenderedHTML{display:block;overflow:auto;}</style>"))
from IPython.core.display import HTML
# make tables cells with a border:
display(HTML("<style>th, td{border: 1px solid #DDE !important;}</style>"))
"""


# # python file
# return "\n\n".join([
#     title,
#     setup_code,
#     'if __name__ == "__main__":\n',
#     '# This code is executed when this file is run as script\n',
#     '# (python <this_file>):',
#     f'{textwrap.indent(example_code, "    ")}',
#     f'{textwrap.indent(pd_tutorial, "#")}'
# ])


def egsim_predictions_dataframe_tutorial(
        doc_prefix = 'The downloaded data'
    ) -> dict:
    from snippets.get_egsim_predictions import get_egsim_predictions
    # Create a doc with the var_name + le last 'Returns:' section of the func docstring:
    doc = f'**{doc_prefix}** is {get_doc(get_egsim_predictions)[-1]}'
    return nb_markdown_cell(f"\n{doc}\n\n{pd_tutorial}")

def egsim_residuals_dataframe_tutorial(
        doc_prefix = 'The downloaded data'
    ) -> dict:
    from snippets.get_egsim_residuals import get_egsim_residuals
    # Create a doc with the var_name + le last 'Returns:' section of the func docstring:
    doc = f'**{doc_prefix}** is {get_doc(get_egsim_residuals)[-1]}'
    return nb_markdown_cell(f"\n{doc}\n\n{pd_tutorial}")


def egsim_get_predictions_nb(
        model: list[str],
        imt: list[str],
        magnitudes: list[float],
        distances: list[float],
        rupture_params: Optional[dict] = None,
        site_params: Optional[dict] = None,
        format="hdf",
        debug=False,  # for debugging, write code performing I/O to file
) -> dict:
    """"""
    from snippets.get_egsim_predictions import get_egsim_predictions
    request_func_name = get_egsim_predictions.__name__
    request_var_name = 'predictions'
    request_code = (
        f'model = [{", ".join(repr(m) for m in model)}]\n'
        f'imt = [{", ".join(repr(i) for i in imt)}]\n'
        f'magnitudes = [{ ", ".join(repr(m) for m in magnitudes) }]\n'
        f'distances = [{ ", ".join(repr(d) for d in distances)}]\n'
    )
    args = ['model', 'imt', 'magnitudes', 'distances']
    if rupture_params:
        request_code += f'rupture_params = {json.dumps(rupture_params)}\n'
        args += [f'rupture_params=rupture_params']
    if site_params:
        request_code += f'site_params = {json.dumps(site_params)}\n'
        args += ['site_params=site_params']
    if format != 'hdf':
        request_code += f'format = {repr(format)}\n'
        args += ['format=format']
    request_code += f'{request_var_name} = {request_func_name}({", ".join(args)})'

    # setup function (source code imported function):
    with open(sys.modules[get_egsim_predictions.__module__].__file__,
              'rt', encoding='utf8') as file_obj:
        setup_code = file_obj.read()
    if debug:
        setup_code = setup_code.replace(egsim_base_url, local_server_base_url)
    debug_cells = []
    if debug:
        debug_cells = _egsim_debug_cell_nb(request_var_name)

    return nb_create(
        nb_markdown_cell(f'# Computing and fetching {request_var_name} '
                         f'with the eGSIM web API'),
        nb_markdown_cell('## Setup'),
        nb_code_cell(nb_setup_cell),
        nb_code_cell(setup_code),  # default functions from snippet
        nb_markdown_cell('## Requesting data'),
        nb_code_cell(request_code),  # query
        nb_markdown_cell('## Working with the data'),
        nb_code_cell(f'display({request_var_name})'),
        egsim_predictions_dataframe_tutorial(request_var_name),
        *debug_cells
    )


def egsim_get_residuals_nb(
        model: list[str],
        imt: list[str],
        flatfile: str,  # if != "esm_2018" => uploaded case
        query_string=None,
        likelihood=False,
        format="hdf",
        debug=False,   # for debugging, write code performing I/O to file
) -> dict:
    """"""
    from snippets.get_egsim_residuals import get_egsim_residuals
    request_func_name = get_egsim_residuals.__name__
    request_var_name = 'residuals'
    request_code = (
        f'model = [{", ".join(repr(m) for m in model)}]\n'
        f'imt = [{", ".join(repr(i) for i in imt)}]\n'
        f'flatfile = {repr(flatfile)}\n'
        f'likelihood = {str(likelihood)}\n'
    )
    upload = flatfile != 'esm2018'
    args = ['model', 'imt', "file_obj" if upload else 'flatfile']
    if query_string:
        request_code += f'query_string = {repr(query_string)}\n'
        args += ['query_string=query_string']
    args+= ['likelihood=likelihood']
    if format != 'hdf':
        request_code += f'format = {repr(format)}\n'
        args += ['format=format']

    request_line = f'{request_var_name} = {request_func_name}({", ".join(args)})'
    if upload:
        request_code += f'with open(flatfile, "rb") as file_obj:\n    {request_line}'
    else:
        request_code += request_line

    # setup function (source code imported function):
    with open(sys.modules[get_egsim_residuals.__module__].__file__,
              'rt', encoding='utf8') as file_obj:
        setup_code = file_obj.read()
    if debug:
        setup_code = setup_code.replace(egsim_base_url, local_server_base_url)
    debug_cells = []
    if debug:
        debug_cells = _egsim_debug_cell_nb(request_var_name)

    return nb_create(
        nb_markdown_cell(f'# Computing and fetching {request_var_name} '
                         f'with the eGSIM web API'),
        nb_markdown_cell('## Setup'),
        nb_code_cell(nb_setup_cell),
        nb_code_cell(setup_code),  # default functions from snippet
        nb_markdown_cell('## Requesting data'),
        nb_code_cell(request_code),  # query
        nb_markdown_cell('## Working with the data'),
        nb_code_cell(f'display({request_var_name})'),
        egsim_residuals_dataframe_tutorial(request_var_name),
        *debug_cells
    )



def _egsim_debug_cell_nb(dataframe_var_name: str) -> list[dict]:
    """Creates few lines of code where the given dataframe can be visualized or
    tested on a cell notebook or py file
    """
    return [
        nb_markdown_cell('### Debug section\n'
                         'Note: the following section is for '
                         'testing/debug purposes'),
        nb_code_cell("\n".join([
            create_write_hdf_snippet(dataframe_var_name,
                                     f"./{dataframe_var_name}.hdf",
                                     dataframe_var_name),
            'tmp_df = ' + create_read_hdf_snippet(f"./{dataframe_var_name}.hdf"),
            '# test equality',
            f'pd.testing.assert_frame_equal(tmp_df, {dataframe_var_name})',
            create_write_csv_snippet(dataframe_var_name,
                                     f"./{dataframe_var_name}.csv"),
            'tmp_df = ' + create_read_csv_snippet(f"./{dataframe_var_name}.csv"),
            '# test equality',
            '# Note: CSV does not preserve all data types, so we compare dataframes ',
            '# by relaxing some conditions: here below we set arguments to fix ',
            '# categorical data type problems, but we cannot be sure that all data ',
            '# types are safe (e.g., date times?). As such, YOU MIGHT NEED TO MODIFY ',
            '# THE FUNCTION ARGUMENTS IN THE FUTURE',
            f'pd.testing.assert_frame_equal(tmp_df, {dataframe_var_name}, '
            f'check_dtype=False, check_categorical=False)'
        ]))
    ]
