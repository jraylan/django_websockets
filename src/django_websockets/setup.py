import os
import pathlib
import re

import setuptools


root_dir = pathlib.Path(__file__).parent

long_description = ''''''
version = "0.0.0"
with open(root_dir / 'pyproject.toml', 'rt') as pyproject_file:
    pyproject_file_content = pyproject_file.read()
    try:
        version = re.search(r'version\s*=\s*"(\d*.\d*.\d*)"',
                            pyproject_file_content).groups(0)[0]
    except:
        pass
    try:
        long_description = re.search(r'description\s*=\s*"(.*)?"',
                            pyproject_file_content).groups(0)[0]
    except:
        pass

# Static values are declared in pyproject.toml.
setuptools.setup(
    version=version,
    long_description=long_description,
    ext_modules=[],
)
