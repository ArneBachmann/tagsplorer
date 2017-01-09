import os
import subprocess
import sys
import time

micro = ""
if os.path.exists(".git"):
  p = subprocess.Popen("git describe --always", shell = True, bufsize = 1, stdout = subprocess.PIPE)
  so, se = p.communicate()
  micro = so.strip()
with open("version.py", "w") as fd:  # create version string at build time
  fd.write(time.strftime("__version_info__ = tuple(int(_) for _ in ('%Y', '%m%d', '%H%M'))\n__version__ = '.'.join(map(str, __version_info__)) + '-git-%%s'\n") % micro)
