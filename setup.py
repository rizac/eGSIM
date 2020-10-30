from setuptools import setup, find_packages

_README = """
Python and OpenQuake-based web service for selecting, comparing and testing
Ground Shaking Intensity Models.
"""

setup(
    name='egsim',
    version='1.1.0',
    description=_README,
    url='https://github.com/rizac/eGSIM',
    packages=find_packages(exclude=['tests', 'tests.*']),
    python_requires='>=3.7.0',
    # Minimal requirements, for a complete list see requirements-*.txt
    install_requires=[
        # 'openquake.engine>3.5.0',
        'smtk @ git+https://github.com/rizac/gmpe-smtk.git'
    ],
    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e .[dev,test]
    extras_require={
        'test': [
            'pylint>=2.3.1',
            'pytest-django>=3.4.8',
            'pytest-cov>=2.6.1'
        ],
    },
    author='r. zaccarelli',
    author_email='',  # FIXME: what to provide?
    maintainer='Section 2.6 (Seismic Hazard and Risk Dynamics), GFZ Potsdam',  # FIXME
    maintainer_email='',
    classifiers=[
        'Development Status :: 1 - Beta',
        'Intended Audience :: Education',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering',
    ],
    keywords=[
        "seismic hazard",
        "ground shaking intensity model",
        "gsim",
        "gmpe",
        "ground motion database",
        "flatfile"
    ],
    license="AGPL3",
    platforms=["any"],  # FIXME: shouldn't be unix/macos? (shallow google search didn't help)
    # package_data={"smtk": [
    #    "README.md", "LICENSE"]},
    # include_package_data=True,
    zip_safe=False,
)
