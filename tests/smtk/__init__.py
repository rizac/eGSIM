def test_library_functions_readme_is_updated():
    """
    LIBRARY_FUNCTIONS_README_IS_UPDATED needs to be kept in sync with changes
    with smtk code
    """
    from egsim import smtk
    from pathlib import Path
    import inspect

    paths = {Path(smtk.__file__).resolve().parent}

    for name, obj in vars(smtk).items():
        if name.startswith("__") and name.endswith("__"):
            continue
        mod_name = getattr(obj, "__module__", None)
        if mod_name is None:
            continue
        if mod_name == smtk.__name__ or mod_name.startswith(smtk.__name__ + "."):
            mod = inspect.getmodule(obj)
            if mod and hasattr(mod, "__file__"):
                paths.add(Path(mod.__file__).resolve())

    newest_mtime = -1
    for entry in paths:
        mtime = entry.stat().st_mtime
        if mtime > newest_mtime:
            newest_mtime = mtime

    lib_func_ref_readme = (
        Path(smtk.__file__).resolve().parent.parent.parent /
        'LIBRARY_FUNCTIONS_REFERENCE.md'
    )
    if Path(lib_func_ref_readme).stat().st_mtime < newest_mtime:
        raise AssertionError(
            lib_func_ref_readme.name + ' non updated. Run ' +
            'python _make_lib_func_ref_readme.py, check updated file content, '
            'commit and re-run tests'
        )