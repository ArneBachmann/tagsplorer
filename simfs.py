# TODO add fnmatch patching?
import logging
import os
import sys

_log = logging.getLogger(__name__); debug, info, warn, error = _log.debug, _log.info, _log.warn, _log.error; del _log
debug("Using virtual case-insensitive file system")

if sys.version_info.major >= 3: unichr = chr


# Patch existence function
_exists = os.path.exists
def exists(path, get = False):
  ''' Case-normalized exists.
      path: file system path to check for existence
      get: if True, returns actual case-corrected path instead of boolean value
      returns: boolean (existence) or string for path
  >>> _saveUnlink("_x.X")
  >>> with open("_x.X", "w"):
  ...   pass  # write using context manager
  >>> print(os.path.exists("_x.X"))
  True
  >>> with open("_x.X", "w"):
  ...   pass  # write over same file using context manager
  >>> print(os.path.exists("_x.X"))
  True
  >>> fd = open("_x.X", "w"); fd.write("123"); fd.close()  # write over same file using file handle
  >>> print(os.path.exists("_x.X"))
  True
  >>> fd = open("_X.x", "w"); fd.write("234"); fd.close()  # write over different case of file using file handle
  >>> print(os.path.exists("_X.x"))
  True
  >>> with open("_X.X", "a") as fd:
  ...   l = fd.write("567")
  >>> fd = open("_x.x", "r"); contents = fd.read(); fd.close(); print(contents)
  234567
  >>> _saveUnlink("_x.X")
  >>> print(os.path.exists("_X.x"))
  False
  >>> print(os.path.exists("_x.X"))
  False
  '''
  debug("Patched os.path.exists")
  if type(path) not in (str, bytes, unichr): return os.path.exists(path)
  if path in (None, ""): return os.path.exists(path)
  steps = path.split(os.sep)
  if steps[0] == "": steps[0] = os.sep # absolute
  else: steps.insert(0, ".")
  path = ""
  files = {steps[0].upper(): steps[0]}  # initial mapping
  for step in steps:
    try: path += (os.sep if step not in (os.sep, ".") else "") + files[step.upper()]
    except Exception as E:
      return False if not get else path + (os.sep if step not in (os.sep, ".") else "") + step  # file name not in last folder: doesn't exist (yet)
    try: files = {f.upper(): f for f in os.listdir(path)}
    except Exception as E:
      with _open(path, "r") as fd: return True if not get else path
      return False  # cannot open file
  return True if not get else path
os.path.exists = exists  # monkey-patch function

# Path file removal
_unlink = os.unlink
_remove = os.remove
def remove(path):
  return _remove(exists(path, True))
os.unlink = os.remove = remove
def _saveUnlink(path):
  try: _unlink(path)
  except: pass

_isdir = os.path.isdir
def isdir(path): return _isdir(exists(path, True))  # in Coconut: def os.path.isdir = ...
os.path.isdir = isdir

_islink = os.path.islink
def islink(path): return _islink(exists(path, True))  # in Coconut: def os.path.isdir = ...
os.path.isdir = islink


# Patch open function
class Open(object):
  def __init__(_, path, mode):
    debug("calling patched 'open' function")
    _.path = path
    _.mode = mode
    _.fd = _open(exists(path, True), mode)

  def __enter__(_):
    debug("Entering patched 'open' context manager")
    return _.fd

  def __exit__(_, *args):
    debug("Exiting patched 'open' context manager %r" % str(args))
    try: _.fd.close()
    except: pass
    finally: del _.fd

  def read(_, *args, **kwargs): return _.fd.read(*args, **kwargs)
  def write(_, *args, **kwargs): _.fd.write(*args, **kwargs)
  def close(_, *args, **kwargs):
    try: _.fd.close(*args, **kwargs)
    except: pass
    finally: del _.fd
_open, open = open, Open

# Patch chdir
_chdir = os.chdir
def chdir(path):
  return _chdir(exists(path, True))
os.chdir = chdir


def load_tests(loader, tests, ignore):
  ''' Queried by unittest. '''
  tests.addTests(doctest.DocTestSuite("simfs"))
  return tests


if __name__ == '__main__':
  import doctest, sys, unittest
#  import pdb; pdb.set_trace()
  logging.basicConfig(level = logging.DEBUG if "--debug" in sys.argv else logging.INFO, stream = sys.stderr, format = "%(asctime)-25s %(levelname)-8s %(name)-12s | %(message)s")
  if sys.platform == 'win32': print("Testing on Windows makes no sense, this is a Windows file system simulator"); exit(1)  # TODO maybe it does anyway?
  unittest.main()  # warnings = "ignore")
