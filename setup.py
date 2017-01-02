import sys
import os
import time
from setuptools import setup

# Upload to PyPI by running setup.py clean build_py sdist bdist upload with a correctly set up ~/.pypirc (need HOME variable set correctly on Windows)

with open("version.py", "w") as fd:  # create version string at build time
  fd.write(time.strftime("__version_info__ = tuple(int(_) for _ in ('%Y', '%m%d', '%H%M'))\n__version__ = '.'.join(map(str, __version_info__))\n"))
