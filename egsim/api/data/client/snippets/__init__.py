import sys
from collections.abc import Iterable, Callable
from typing import Optional, Union
import uuid
import json


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


def create_notebook(*cells: dict) -> dict:
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


def get_doc(function:Callable) -> list[str, str, str]:  # intro, args, returns sections
    """Return the docstring of the given function in a list of three
    strings with the content of 'intro', 'args', and 'returns' sections
    """
    doc = function.__doc__.strip()  # noqa
    # dedent (unfortunately, textwrap.dedent needs all lines indented):
    indent = '    '
    if doc.startswith(indent):
        doc = doc[len(indent):]
    doc = doc.replace(f'\n{indent}', '\n').strip()
    sections = []
    prev_index = None
    for section_title in ['Args:', 'Returns:']:
        try:
            idx = doc.index(section_title)
        except ValueError:
            raise ValueError(f'"{function.__name__}" docstring must implement '
                             f'two sections after the intro with title "Args:" and '
                             f'"Returns:"')
        sections.append(doc[prev_index: idx].strip())
        prev_index = idx + len(section_title)
    # append the remaining text ('Returns:' section body test):
    sections.append(doc[prev_index:].strip())

    return sections


def create_read_csv_snippet(file_path:str):
    return f'pd.read_csv({repr(file_path)}, header=[0, 1, 2], index_col=0)'


def create_read_hdf_snippet(file_path:str):
    return f'pd.read_hdf({repr(file_path)})'


def create_write_hdf_snippet(dataframe_var_name:str, file_path:str, key: str):
    return f'{dataframe_var_name}.to_hdf({repr(file_path)}, key={repr(key)}, ' \
           f'format="table")'


def create_write_csv_snippet(dataframe_var_name:str, file_path:str):
    return f'{dataframe_var_name}.to_csv({repr(file_path)})'


egsim_base_url = "https://egsim.gfz-potsdam.de"
local_server_base_url = "http://127.0.0.1:8000"


# trailing section of each doc sections of the notebooks:
pd_tutorial = f'''
#### Read / write DataFrame

[HDF format](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_hdf.html) 

```python
import pandas as pd
# read:
dataframe = {create_read_hdf_snippet('/path/to/file.hdf')}
# write:
{create_write_hdf_snippet('dataframe', '/path/to/file.hdf', 'table_key')}
```

[CSV format](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html)

```python
import pandas as pd
# read
dataframe = {create_read_csv_snippet('/path/to/file.csv')}
# write
{create_write_csv_snippet('dataframe', '/path/to/file.csv')}
```

*Note: HDF is the **recommended format**: it requires `pytables` (`pip install tables`)
but is more performant and preserves data types (i.e., if you write a dataframe to 
CSV file and read it back, some data types might not be the same)


#### Useful pandas links

- [Short intro](https://pandas.pydata.org/docs/user_guide/10min.html)
- [Indexing and selecting data](https://pandas.pydata.org/docs/user_guide/indexing.html)
  - [with multi-index row or column (the case at hand)](https://pandas.pydata.org/docs/user_guide/advanced.html)
- [Plotting](https://pandas.pydata.org/docs/user_guide/visualization.html#visualization)
'''.strip()  # noqa


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


##############################
# Actual functions to be used:
##############################


def response_tutorial_md_cell(
        request_function: Callable,
        request_var_name = 'The downloaded data'
    ) -> dict:
    # Create a doc with the var_name + le last 'Returns:' section of the func docstring:
    doc = f'**{request_var_name}** is {get_doc(request_function)[-1]}'
    return nb_markdown_cell(f"\n{doc}\n\n{pd_tutorial}")


def predictions_request_nb(
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
    from .get_egsim_predictions import get_egsim_predictions
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

    return create_notebook(
        nb_markdown_cell(f'# Computing and fetching {request_var_name} '
                         f'with the eGSIM web API'),
        nb_markdown_cell('## Setup'),
        nb_code_cell(nb_setup_cell),
        nb_code_cell(setup_code),  # default functions from snippet
        nb_markdown_cell('## Requesting data'),
        nb_code_cell(request_code),  # query
        nb_markdown_cell('## Working with the data'),
        nb_code_cell(f'display({request_var_name})'),
        response_tutorial_md_cell(get_egsim_predictions, request_var_name),
        *debug_cells
    )


def residuals_request_nb(
        model: list[str],
        imt: list[str],
        flatfile: str,  # if != "esm_2018" => uploaded case
        query_string=None,
        likelihood=False,
        format="hdf",
        debug=False,   # for debugging, write code performing I/O to file
) -> dict:
    """"""
    from .get_egsim_residuals import get_egsim_residuals
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

    return create_notebook(
        nb_markdown_cell(f'# Computing and fetching {request_var_name} '
                         f'with the eGSIM web API'),
        nb_markdown_cell('## Setup'),
        nb_code_cell(nb_setup_cell),
        nb_code_cell(setup_code),  # default functions from snippet
        nb_markdown_cell('## Requesting data'),
        nb_code_cell(request_code),  # query
        nb_markdown_cell('## Working with the data'),
        nb_code_cell(f'display({request_var_name})'),
        response_tutorial_md_cell(get_egsim_residuals, request_var_name),
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
