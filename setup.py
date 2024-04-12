from setuptools import setup, find_packages

_README = """
Python and OpenQuake-based web service for selecting, comparing and testing
Ground Shaking Intensity Models.
"""

setup(
    name='egsim',
    version='2.1.0',
    description=_README,
    url='https://github.com/rizac/eGSIM',
    packages=find_packages(exclude=['tests', 'tests.*']),
    python_requires='>=3.11',
    # Minimal requirements for the library (egsim.smtk package).
    # FOR DEV/TESTS, add: `pip install pytest`
    install_requires=[
        'openquake.engine>3.5.0,<=3.15.0',
        'pyyaml>=6.0',
        'tables>=3.8.0',
    ],
    # List additional groups of dependencies here (e.g. development
    # dependencies). You can install these using the following syntax,
    # for example:
    # $ pip install -e ".[web]"
    extras_require={
        'web': [
            'Django>=4.1.2',
            'plotly>=5.10.0',
            'kaleido>=0.2.1',  # required by plotly to save images
            # test packages:
            'pytest',
            'pylint>=2.3.1',
            'pytest-django>=3.4.8',
            'pytest-cov>=2.6.1'
        ]
    },
    author='r. zaccarelli',
    author_email='',
    maintainer='r. zaccarelli',
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
    platforms=["any"],
    # package_data={"smtk": [
    #    "README.md", "LICENSE"]},
    # include_package_data=True,
    zip_safe=False,
)
