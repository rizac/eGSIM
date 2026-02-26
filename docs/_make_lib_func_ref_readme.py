import textwrap
import inspect

from numpy.core.defchararray import startswith

from egsim import smtk


def list_function_docstrings():
    module = smtk

    for name, obj in module.__dict__.items():
        if name.startswith("__") and name.endswith("__"):
            continue
        obj_mod = getattr(obj, "__module__", "")
        if obj_mod != module.__name__ and not obj_mod.startswith(f"{module.__name__}."):
            continue
        obj_header = get_obj_header(obj)
        yield name, obj_header


def get_obj_header(py_obj):
    """Return an obj header. If py_obj is a Python function or method, return the
    function signature and its docstring. If class/ dataclass, the class name
    and the class body up to the first occurrence of "def ".

    Note: obj must have a docstring!
    """
    source_lines, _ = inspect.getsourcelines(py_obj)
    result = []
    quote = None
    is_class = None
    for line in source_lines:
        result.append(line.rstrip("\n"))
        line = line.strip()
        if is_class is None:
            is_class = line.startswith("class ") or line == "@dataclass"
            continue
        if quote is None and (
            line.startswith("'''") or line.startswith('"""')
        ):
            quote = line[:3]
            line = line[3:] # avoid jumping in if below if it's just """ or '''
        if quote is not None and line.endswith(quote):
            if not is_class:
                break
            quote = None
            continue
        if is_class and quote is None and line.startswith("def "):
            result.pop()
            break

    return "\n".join(result)


if __name__ == "__main__":

    import os
    root = os.path.dirname(__file__)
    output_path = os.path.join(root, "LIBRARY_FUNCTIONS_REFERENCE.md")

    with open(output_path, "w", encoding="utf-8") as f:
        print("# eGSIM Library Functions Reference", file=f)
        print("> Note: `smtk` stands for Strong Motion Toolkit, ", file=f)
        print("> a legacy project now integrated as the core package of eGSIM. ",
              file=f)
        print("", file=f)

        for n, s_d in list_function_docstrings():
            print('', file=f)  # append newline
            print('', file=f)
            print(f'### {n}', file=f)
            print("```python", file=f)
            print(f'from egsim.smtk import {n}', file=f)
            print('', file=f)
            print('# Signature and docstring:', file=f)
            print(s_d, file=f)
            # print('    """', file=f)
            # print(d, file=f)
            # print('    """', file=f)
            print('```', file=f)
            print('', file=f)