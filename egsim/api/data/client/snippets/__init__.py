import textwrap

import sys
from collections.abc import Iterable, Callable
from typing import Optional, Union
import uuid
import json
from os.path import join, dirname


def create_notebook_code_cell(src_code: Optional[Union[str, Iterable[str]]]=None):
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": str(uuid.uuid4()),
        "metadata": {},
        "outputs": [],
        "source": _split_lines(src_code)
    }

def create_notebook_markdown_cell(src_code: Optional[Union[str, Iterable[str]]]=None):
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


def create_notebook(cells: Optional[list[dict]]=None):
    return {
        "cells": [] if cells is None else cells,
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


def open_snippet(file_path) -> str:
    with open(file_path, 'rt', encoding='utf8') as file_obj:
        return file_obj.read()


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


egsim_base_url = "https://egsim.gfz-potsdam.de"
local_server_base_url = "http://127.0.0.1:8000"
egsim_predictions_url = egsim_base_url + '/query/predictions'
egsim_residuals_url = egsim_base_url + '/query/residuals'


# trailing section of each doc sections of the notebooks:
pd_useful_links = '''
**Useful links to work with your dataframe**:
- [Short intro](https://pandas.pydata.org/docs/user_guide/10min.html)
- [Indexing and selecting data](https://pandas.pydata.org/docs/user_guide/indexing.html)
  - [with multi-index row or column (the case at hand)](https://pandas.pydata.org/docs/user_guide/advanced.html)
- [Read from / write to disk](https://pandas.pydata.org/docs/user_guide/io.html)
- [Plotting](https://pandas.pydata.org/docs/user_guide/visualization.html#visualization)
'''.strip()  # noqa


def create_example_code(
        title:str,
        setup_module_path: str,
        example_code: str,
        doc:str,
        as_notebook=True,
        local_server=False) -> str:
    """"""
    # assure the request code ends with <request_var_name> = :

    setup_code = open_snippet(setup_module_path)
    if local_server:
        setup_code = setup_code.replace(egsim_base_url, local_server_base_url)

    if as_notebook:
        jupyter_setup = open_snippet(join(dirname(__file__), 'notebook_setup.py'))
        doc += f"\n\n{pd_useful_links}"
        return json.dumps(create_notebook([
            create_notebook_markdown_cell(title),
            create_notebook_markdown_cell('## Setup'),
            create_notebook_code_cell(jupyter_setup),
            create_notebook_code_cell(setup_code),  # default functions from snippet
            create_notebook_markdown_cell('## Working example with short tutorial'),
            create_notebook_code_cell(example_code),  # query
            create_notebook_markdown_cell(doc)
        ]))
    else:
        request_code = (
            'if __name__ == "__main__":\n'
            '# The code below is executed when this file is '
            'invoked as script (python <this_file>):\n\n'
            f'{textwrap.indent(example_code, "    ")}'
        )
        return f'{title}' \
               f'\n\n' \
               f'{setup_code}' \
               f'\n\n' \
               f'{request_code}' \
               f'\n\n' \
               f'{textwrap.indent(pd_useful_links, "#")}'


##############################
# Actual functions to be used:
##############################

def create_predictions_request_code(
        model: list[str],
        imt: list[str],
        magnitudes: list[float],
        distances: list[float],
        rupture_params: Optional[dict] = None,
        site_params: Optional[dict] = None,
        format="hdf",
        save_files=False,
        as_notebook=True,
        local_server=False) -> str:
    """"""
    from .get_egsim_predictions import get_egsim_predictions
    request_func_name = get_egsim_predictions.__name__
    request_module_path = sys.modules[get_egsim_predictions.__module__].__file__
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
    request_code += (
        '\n\n'
        '# show result (optional, here for illustrative purposes only):'
        '\n' 
        f'display({request_var_name})'
    )
    if save_files:
        request_code += (
            '\n\n'
            '# save files to disk WARNING: check the file path\n'
            f'{request_var_name}.to_hdf("./{request_var_name}.hdf", '
            f'key="{request_var_name}")\n'
            f'{request_var_name}.to_csv("./{request_var_name}.csv")'
        )

    title = f'# Computing and fetching {request_var_name} with the eGSIM web API'
    # Create a doc with the var_name + le last 'Returns:' section of the func docstring:
    doc = f'**{request_var_name}** is {get_doc(get_egsim_predictions)[-1] }'
    return create_example_code(title, request_module_path, request_code, doc,
                               as_notebook, local_server)


def create_residuals_request_code(
        model: list[str],
        imt: list[str],
        flatfile: str,  # if != "esm_2018" => uploaded case
        query_string=None,
        likelihood=False,
        format="hdf",
        save_files=False,
        as_notebook=True,
        local_server=False) -> str:
    """"""
    from .get_egsim_residuals import get_egsim_residuals
    request_func_name = get_egsim_residuals.__name__
    request_module_path = sys.modules[get_egsim_residuals.__module__].__file__
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
    request_code += (
        '\n\n'
        '# show result (optional, here for illustrative purposes only):'
        '\n' 
        f'display({request_var_name})'
    )
    if save_files:
        fname = request_var_name
        if upload:
            fname += '.upload'
        if likelihood:
            fname+= '.likelihood'
        request_code += (
            '\n\n'
            '# save files to disk WARNING: check the file path\n'
            f'{request_var_name}.to_hdf("./{fname}.hdf", '
            f'key="{request_var_name}")\n'
            f'{request_var_name}.to_csv("./{fname}.csv")'
        )

    title = f'# Computing and fetching {request_var_name} with the eGSIM web API'
    # Create a doc with the var_name + le last 'Returns:' section of the func docstring:
    doc = f'**{request_var_name}** is {get_doc(get_egsim_residuals)[-1]}'
    return create_example_code(title, request_module_path, request_code, doc,
                               as_notebook, local_server)


def create_predictions_response_openfile_code(filepath:str, as_notebook=True) -> str:
    """"""
    from .open_egsim_downloaded_file import open_egsim_downloaded_file
    func_name = open_egsim_downloaded_file.__name__
    module_path = sys.modules[open_egsim_downloaded_file.__module__].__file__
    from .get_egsim_predictions import get_egsim_predictions
    request_var_name = 'predictions'

    # Create a doc with the var_name + le last 'Returns:' section of the func docstring:
    doc = f'**{request_var_name}** is {get_doc(get_egsim_predictions)[-1]}'
    title = f'# Working with {request_var_name} downloaded from eGSIM'
    request_code = (
        f"flatfile = {repr(filepath)}  # PLEASE CHECK and provide an existing file path"
        f"{request_var_name} = {func_name}(flatfile)\n"
        "\n\n"
        '# show result (optional, here for illustrative purposes only):\n'
        f'display({request_var_name})'
    )
    return create_example_code(title, module_path, request_code, doc, as_notebook)


def create_residuals_response_openfile_code(filepath:str, as_notebook=True) -> str:
    """"""
    from .open_egsim_downloaded_file import open_egsim_downloaded_file
    func_name = open_egsim_downloaded_file.__name__
    module_path = sys.modules[open_egsim_downloaded_file.__module__].__file__
    from .get_egsim_residuals import get_egsim_residuals
    request_var_name = 'residuals'

    # Create a doc with the var_name + le last 'Returns:' section of the func docstring:
    doc = f'**{request_var_name}** is {get_doc(get_egsim_residuals)[-1]}'
    title = f'# Working with {request_var_name} downloaded from eGSIM'
    request_code = (
        f"flatfile = {repr(filepath)}  # PLEASE CHECK and provide an existing file path"
        f"{request_var_name} = {func_name}(flatfile)\n"
        "\n\n"
        '# show result (optional, here for illustrative purposes only):\n'
        f'display({request_var_name})'
    )
    return create_example_code(title, module_path, request_code, doc, as_notebook)
