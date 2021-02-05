''' tagsPlorer setup script  (C) 2017-2021  Arne Bachmann  https://github.com/ArneBachmann/tagsplorer '''

import os, shutil, subprocess, sys, time
from setuptools import setup

from tagsplorer.constants import MAJOR_VERSION

if os.path.exists(".git"):
  so, se = subprocess.Popen("git describe --always", shell = True, stdout = subprocess.PIPE).communicate()
  micro = "-" + so.strip().decode(sys.stdout.encoding).strip()
else: micro = ""
lt = time.localtime()
versionString = "%d.%d.%d" % (MAJOR_VERSION, lt.tm_year * 100 + lt.tm_mon, lt.tm_mday * 10000 + lt.tm_hour * 100 + lt.tm_min) if any(_ in sys.argv for _ in ('clean', 'build')) else open(os.path.join(os.path.dirname(os.path.join(__file__)), "tagsplorer", "VERSION"), "r", encoding = "utf-8").read()
if 'clean' not in sys.argv:
  with open(os.path.join(os.path.dirname(os.path.join(__file__)), "tagsplorer", "VERSION"), "w", encoding = "utf-8") as fd: fd.write(versionString)


setup(
  name = 'tagsPlorer',
  version = versionString,
  description = "tagsPlorer V" + versionString + micro,
  long_description = "",
  classifiers = [c.strip() for c in """
        Development Status :: 5 - Production/Stable
        Intended Audience :: Other Audience
        Intended Audience :: System Administrators
        License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)
        Operating System :: OS Independent
        Programming Language :: Python :: 3
        Programming Language :: Python :: 3.6
        Programming Language :: Python :: 3.7
        Programming Language :: Python :: 3.8
        Programming Language :: Python :: 3.9
        """.split('\n') if c.strip()],  # https://pypi.python.org/pypi?:action=list_classifiers
  keywords = '',
  author = 'Arne Bachmann',
  author_email = 'ArneBachmann@users.noreply.github.com',
  maintainer = 'Arne Bachmann',
  maintainer_email = 'ArneBachmann@users.noreply.github.com',
  url = 'http://github.com/ArneBachmann/corrupdetect',
  license = 'MPL-2.0',
  packages = ["tagsplorer"],
  #package_dir = {"tagsplorer": ""},
  package_data = {"tagsplorer": ["VERSION"]},
  zip_safe = False,
  entry_points = {
    'console_scripts': [
      'tp=tagsplorer.tp:main'
    ]
  },
)

if "clean" in sys.argv:
  try: shutil.rmtree("tagsplorer.egg-info")  # if keeping this folder, built files will remain no matter what exclude options are configured above (MANIFEST.in or exclude_...)
  except: pass  # noqa: E722
  try: shutil.rmtree("build")
  except: pass  # noqa: E722
  try: shutil.rmtree("dist")
  except: pass  # noqa: E722
