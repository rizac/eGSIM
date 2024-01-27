import sys
from collections.abc import Iterable, Callable, FunctionType
from typing import Optional, Union
import uuid
# from os.path import join, dirname, isfile
# from datetime import datetime

import json
from os.path import join, dirname


def create_notebook_code_cell(source_code: Optional[Iterable[str]]=None):
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": str(uuid.uuid4()),
        "metadata": {},
        "outputs": [],
        "source": [] if source_code is None else list(source_code)
    }

def create_notebook_markdown_cell(source_code: Optional[Iterable[str]]=None):
    return  {
        "cell_type": "markdown",
        "id":  str(uuid.uuid4()),
        "metadata": {},
        "source": [] if source_code is None else list(source_code)
    }


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


def open_snippet(filename_or_pyfunc:Union[FunctionType, str]) -> list[str]:
    if callable(filename_or_pyfunc):
        file_path = sys.modules[filename_or_pyfunc.__module__].__file__
    else:
        file_path = join(dirname(__file__), filename_or_pyfunc)
    with open(file_path, 'rt', encoding='utf8') as file_obj:
        return [line for line in file_obj]


egsim_base_url = "https://egsim.gfz-potsdam.de"
local_server_base_url = "http://127.0.0.1:8000"
egsim_predictions_url = egsim_base_url + '/query/predictions'
egsim_residuals_url = egsim_base_url + '/query/residuals'

pd_useful_links = info_code = [
    '### Useful links to work with your dataframe\n',
    '- [Short intro](https://pandas.pydata.org/docs/user_guide/10min.html)\n',
    '- [Indexing and selecting data]'
    '(https://pandas.pydata.org/docs/user_guide/indexing.html)\n',
    '  - [with multi-index row or column (the case at hand)]'
    '(https://pandas.pydata.org/docs/user_guide/advanced.html)\n'
    '- [Read from / write to disk](https://pandas.pydata.org/docs/user_guide/io.html)\n',
    '- [Plotting]'
    '(https://pandas.pydata.org/docs/user_guide/visualization.html#visualization)'
]


def create_request_code(request_function: FunctionType,
                        request_code: list[str],
                        request_var_name:str,
                        as_notebook=True, local_server=False):
    """"""
    assert request_code[-1].strip().startswith(request_var_name)

    main_function = open_snippet(request_function)
    if local_server:
        for i, line in enumerate(main_function):
            if egsim_base_url in line:
                main_function[i] = line.replace(egsim_base_url,
                                                local_server_base_url)

    if as_notebook:
        doc = request_function.__doc__
        doc = doc[doc.rfind('Returns'):].split("\n")[1:]
        doc = "\n".join(l[4:] if l[:4] == '    ' else l for l in doc).strip()
        doc = f'**{request_var_name}** is ' + doc + "\n\nas you can see by running:"
        return json.dumps(create_notebook([
            create_notebook_markdown_cell(
                [f'# Computing {request_var_name} with the eGSIM web API']),
            create_notebook_code_cell(list(open_snippet('notebook_setup.py'))),
            create_notebook_code_cell(main_function),  # default functions from snippet
            create_notebook_code_cell(request_code),  # query
            create_notebook_markdown_cell([doc]),
            create_notebook_code_cell(['display(residuals)']),  # query
            create_notebook_markdown_cell(pd_useful_links)
        ]))
    else:
        script_code = [
            '\n',
            '\n',
            'if __name__ == "__main__":\n',
            '\n',
            '# Perform eGSIM request (this code is executed when this file is '
            'invoked as script with: python <this_file>):\n',
        ]
        request_code = [f'    {l}' for l in request_code]
        useful_links = ['\n'] + [f'#{l}' for l in pd_useful_links]
        return "".join(main_function + script_code + request_code + useful_links)


def create_predictions_request_code(model, imt, mag, dist,
                                    rup_params:dict=None, site_params:dict=None,
                                    as_notebook=True, local_server=False):
    """"""
    from .get_egsim_predictions import get_egsim_predictions
    main_function = open_snippet(sys.modules[get_egsim_predictions.__module__].__file__)
    if local_server:
        for i in range(len(main_function)):
            if egsim_base_url in main_function[i]:
                main_function[i] = main_function[i].replace(egsim_base_url,
                                                            local_server_base_url)


    request_code = [
        f'model = [{", ".join(repr(m) for m in model)}]\n',
        f'imt = [{", ".join(repr(i) for i in imt)}]\n',
        f'mag = [{ ", ".join(repr(m) for m in mag) }]\n',
        f'dist = [{ ", ".join(repr(d) for d in dist)}]\n',]
    if rup_params:
        request_code.append(f'rupture_params = {json.dumps(rup_params)}')
    if site_params:
        request_code.append(f'site_params = {json.dumps(site_params)}')
    request_code += [
        'residuals = get_egsim_predictions(model, imt, mag, dist)',
    ]


    if as_notebook:
        doc = get_egsim_predictions.__doc__
        doc = doc[doc.rfind('Returns'):].split("\n")[1:]
        doc = "\n".join(l[4:] if l[:4] == '    ' else l for l in doc).strip()
        doc  = '**residuals** is ' + doc + "\n\nas you can see by running:"
        return json.dumps(create_notebook([
            create_notebook_markdown_cell(['# Computing predictions with the eGSIM web API']),
            create_notebook_code_cell(list(open_snippet('notebook_setup.py'))),
            create_notebook_code_cell(main_function),  # default functions from snippet
            create_notebook_code_cell(request_code),  # query
            create_notebook_markdown_cell([doc]),
            create_notebook_code_cell(['display(residuals)']),  # query
            create_notebook_markdown_cell(pd_useful_links)
        ]))
    else:
       script_code = [
            '\n',
            '\n',
            'if __name__ == "__main__":\n',
            '\n',
            '# execute this file as script. Setup parameters:\n'
       ]
       request_code = [f'    {l}' for l in request_code]
       useful_links = [f'#{l}' for l in pd_useful_links]
       return "".join(main_function + script_code + request_code)
