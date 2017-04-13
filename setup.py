import os
import subprocess
import sys
import time

micro = ""
if os.path.exists(".git"):
  p = subprocess.Popen("git describe --always", shell = True, bufsize = 1, stdout = subprocess.PIPE)
  so, se = p.communicate()
  micro = so.strip() if sys.version_info.major < 3 else so.strip().decode('ascii')
with open("version.py", "w") as fd:  # create version string at build time
  md = time.localtime()
  fd.write("__version_info__ = (%d, %d, %d)\n__version__ = '.'.join(map(str, __version_info__)) + '-git-%s'\n" % (md.tm_year, (10 + md.tm_mon) * 100 + md.tm_mday, (10 + md.tm_hour) * 100 + md.tm_min, micro))
