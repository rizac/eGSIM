from types import FunctionType

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


egsim_base_url = "https://egsim.gfz-potsdam.de"
local_server_base_url = "http://127.0.0.1:8000"
egsim_predictions_url = egsim_base_url + '/query/predictions'
egsim_residuals_url = egsim_base_url + '/query/residuals'


pd_useful_links = '''
### Useful links to work with your dataframe
- [Short intro](https://pandas.pydata.org/docs/user_guide/10min.html)
- [Indexing and selecting data](https://pandas.pydata.org/docs/user_guide/indexing.html)
  - [with multi-index row or column (the case at hand)](https://pandas.pydata.org/docs/user_guide/advanced.html)
- [Read from / write to disk](https://pandas.pydata.org/docs/user_guide/io.html)
- [Plotting](https://pandas.pydata.org/docs/user_guide/visualization.html#visualization)
'''.strip()  # noqa


def create_request_code(
        request_function: Callable,
        request_code: str,
        request_var_name:str,
        as_notebook=True,
        local_server=False) -> str:
    """"""
    # assure the request code ends with <request_var_name> = :
    assert request_code.strip().split("\n")[-1].strip().startswith(request_var_name)

    header = f'# Computing and fetching {request_var_name} with the eGSIM web API'
    main_function = open_snippet(sys.modules[request_function.__module__].__file__)
    if local_server:
        main_function = main_function.replace(egsim_base_url, local_server_base_url)

    if as_notebook:
        jupyter_setup = open_snippet(join(dirname(__file__), 'notebook_setup.py'))
        doc = request_function.__doc__
        doc = doc[doc.rindex('Returns:')+len('Returns:'):].strip()
        # remove indentation (textwrap.dedent does not work in this case):
        doc = doc.replace('\n    ', '\n')
        doc = f'**{request_var_name}** is ' + doc + "\n\nas you can see by running:"
        return json.dumps(create_notebook([
            create_notebook_markdown_cell(header),
            create_notebook_code_cell(jupyter_setup),
            create_notebook_code_cell(main_function),  # default functions from snippet
            create_notebook_code_cell(request_code),  # query
            create_notebook_markdown_cell(doc),
            create_notebook_code_cell([f'display({request_var_name})']),  # query
            create_notebook_markdown_cell(pd_useful_links)
        ]))
    else:
        request_code = (
            'if __name__ == "__main__":\n'
            '# The code below is executed when this file is '
            'invoked as script (python <this_file>):\n\n'
            f'{textwrap.indent(request_code, "    ")}'
        )
        return f'{header}\n\n{main_function}\n\n{request_code}\n\n' \
               f'{textwrap.indent(pd_useful_links, "#")}'


def create_predictions_request_code(
        model: list[str],
        imt: list[str],
        magnitudes: list[float],
        distances: list[float],
        rupture_params: Optional[dict] = None,
        site_params: Optional[dict] = None,
        format="hdf",
        as_notebook=True,
        local_server=False) -> str:
    """"""
    from .get_egsim_predictions import get_egsim_predictions
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
    request_code += f'{request_var_name} = get_egsim_predictions({", ".join(args)})'

    return create_request_code(get_egsim_predictions, request_code, request_var_name,
                               as_notebook, local_server)


def create_residuals_request_code(
        model: list[str],
        imt: list[str],
        flatfile: str,  # if != "esm_2018" => uploaded case
        query_string=None,
        likelihood=False,
        format="hdf",
        as_notebook=True,
        local_server=False) -> str:
    """"""
    from .get_egsim_residuals import get_egsim_residuals
    request_var_name = 'residuals'
    request_code = (
        f'model = [{", ".join(repr(m) for m in model)}]\n'
        f'imt = [{", ".join(repr(i) for i in imt)}]\n'
        f'flatfile = {repr(flatfile)}\n'
        f'likelihood = {str(likelihood)}\n'
    )
    upload = flatfile != 'esm_2018'
    args = ['model', 'imt', "file_obj" if upload else 'flatfile']
    if query_string:
        request_code += f'query_string = {repr(query_string)}\n'
        args += ['query_string=query_string']
    args+= ['likelihood=likelihood']
    if format != 'hdf':
        request_code += f'format = {repr(format)}\n'
        args += ['format=format']

    request_line = f'{request_var_name} = get_egsim_residuals({", ".join(args)})'
    if upload:
        request_code += f'with open(flatfile, "rb") as file_obj:\n    {request_line}'
    else:
        request_code += request_line

    return create_request_code(get_egsim_residuals, request_code, request_var_name,
                               as_notebook, local_server)
