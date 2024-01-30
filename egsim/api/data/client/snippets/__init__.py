from collections.abc import Callable


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
