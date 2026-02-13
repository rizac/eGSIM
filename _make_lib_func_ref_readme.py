import textwrap
import inspect
from egsim import smtk


def list_function_docstrings():
    module = smtk

    for name, obj in module.__dict__.items():
        if name.startswith("__") and name.endswith("__"):
            continue
        obj_mod = getattr(obj, "__module__", "")
        if obj_mod != module.__name__ and not obj_mod.startswith(f"{module.__name__}."):
            continue
        sig = pretty_print_signature(obj)
        doc = textwrap.indent(inspect.getdoc(obj), "    ")
        yield name, sig, doc


def pretty_print_signature(obj, indent=4):
    obj_name = obj.__name__
    prefix = "class "
    sig_params = []
    if inspect.isfunction(obj) or inspect.ismethod(obj):
        prefix = "def "
    elif not inspect.isclass(obj):
        raise ValueError(f"{obj} must be a function or a class")
    try:
        sig = inspect.signature(obj)
        sig_params = sig.parameters.values()
    except ValueError:
        if not inspect.isclass(obj):
            raise

    params = []
    for p in sig_params:
        if p.default is inspect._empty:
            params.append(p.name)
        else:
            params.append(f"{p.name}={p.default!r}")

    if len(params) == 1:
        obj_name = f"{obj_name}({params[0]})"
    elif len(params):
        pad = "    "
        params_str = ",\n".join(pad + p for p in params)
        obj_name = f"{obj_name}(\n{params_str}\n)"
    elif inspect.isfunction(obj) or inspect.ismethod(obj):
        obj_name += "()"

    ret = ":"
    if inspect.isfunction(obj) or inspect.ismethod(obj):
        if sig.return_annotation is not inspect._empty:
            ret = " -> " + str(sig.return_annotation) + ":"

    return prefix + obj_name + ret


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

        for n, s, d in list_function_docstrings():
            print('', file=f)  # append newline
            print('', file=f)
            print(f'### {n}', file=f)
            print("```python", file=f)
            print(f'from egsim.smtk import {n}', file=f)
            print('', file=f)
            print('# Signature and docstring:', file=f)
            print(s, file=f)
            print('    """', file=f)
            print(d, file=f)
            print('    """', file=f)
            print('```', file=f)
            print('', file=f)