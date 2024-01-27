from glob import glob
import os
import platform
import sys
try:
    from setuptools import setup, find_packages
except ImportError:
    from distutils.core import setup, find_packages

is_cpython = platform.python_implementation() == 'CPython'
is_py3 = sys.version_info >= (3,)
is_win = sys.platform.startswith('win')

if len(sys.argv) <= 1:
    print("""
Suggested setup.py parameters:

    * build
    * install
    * sdist  --formats=zip
    * sdist  # NOTE requires tar/gzip commands

    python -m pip install -e .

PyPi:

    python -m pip install setuptools twine
    twine upload dist/*
    ./setup.py  sdist ; twine upload dist/* --verbose

""")

readme_filename = 'README.md'
if os.path.exists(readme_filename):
    f = open(readme_filename)
    long_description = f.read()
    f.close()
else:
    long_description = None

# Lookup __version__
project_name = 'SQLshite'
project_name_lower = project_name.lower()
license = "GNU Affero General Public License v3 or later (AGPLv3+)"  # ensure this matches tail of http://pypi.python.org/pypi?%3Aaction=list_classifiers
exec(open(os.path.join(os.path.abspath(os.path.dirname(__file__)), project_name_lower, '_version.py')).read())  # get __version__

install_requires = ['stache @ https://github.com/clach04/stache.git#egg=package-1.0', ]  # TODO load/parse from requirements.txt


setup(
    name=project_name,
    version=__version__,
    author='clach04',
    url='https://github.com/clach04/' + project_name,
    description='Tools for dealing with SQLite3 and jsonform',
    long_description=long_description,
    long_description_content_type='text/markdown',
    license=license,

    #packages=find_packages(where=os.path.join(os.path.dirname(__file__), project_name_lower), include=['*']),  # error: package directory 'web' does not exist
    packages=[project_name_lower, project_name_lower + '.web'],
    data_files=[
        ('templates', glob(os.path.join(os.path.dirname(__file__), project_name_lower, 'web', 'www', '*'))),
        ('js', glob(os.path.join(os.path.dirname(__file__), project_name_lower, 'web', 'www', 'js', '*'))),
        ('js', glob(os.path.join(os.path.dirname(__file__), project_name_lower, 'web', 'www', 'js', '*'))),
    ],
    #py_modules=[project_name_lower, ],  # If your project contains any single-file Python modules that aren't part of a package, set py_modules to a list of the names of the modules (minus the .py extension) in order to make Setuptools aware of them.

    classifiers=[  # See http://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: ' + license,
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.12',
        'Topic :: Database',
        'Topic :: File Formats :: JSON',
        'Topic :: File Formats :: JSON :: JSON Schema',
        'Programming Language :: SQL',
        # FIXME TODO more
        ],
    platforms='any',  # or distutils.util.get_platform()
    install_requires=install_requires,
)
