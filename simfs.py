import doctest
import logging
import os
import sys
import unittest

_log = logging.getLogger(__name__)
_log.debug("Using virtual case-insensitive file system")

if sys.version_info.major >= 3:
  import io
  file = io.IOBase
  _types = (str, bytes)
  _RIGHTS = 0o777
else:  # Python 2
  import dircache  # in addition to os.listdir
  _types = (str, bytes, unicode)
  RIGHTS = 0755


# Patch existence function
_exists = os.path.exists
def exists(path, get = False):  # TODO move path determination to own function and base exists on that
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
  _log.debug("Patched os.path.exists %r" % path)
  if type(path) is file: return _exists(path)  # file handle
  if not isinstance(path, _types):
    if not get: return _exists(path)  # delegate or force original Exception
    raise ValueError("Unknown argument type %r" % type(path))
  if path is None or path == "": return _exists(path) if not get else path
  steps = path.split(os.sep)
  if steps[0] == "": steps[0] = os.sep # absolute
  elif steps[0] != os.curdir: steps.insert(0, os.curdir)
  i = 1
  while "" in steps[i:]: i = steps.index("", i); steps.pop(i)
  path2 = ""
  files = {steps[0].upper(): steps[0]}  # initial mapping
  for step in steps:
    if step == os.pardir:
      if os.sep in path2: path2 = path2[:path2.rindex(os.sep)]; continue  # remove intermediate "..""
      else: path2 = os.pardir  # if ".."" is first entry
    try: path2 += (os.sep if step not in (os.sep, os.curdir) and path2 != os.sep else "") + files[step.upper()]
    except KeyError as E:  # file entry not found
      return False if not get else path2 + (os.sep if step not in (os.sep, os.curdir) and path2 != os.sep else "") + step  # file name not in last folder: doesn't exist (yet)
    try: files = {f.upper(): f for f in _listdir(path2)}; continue
    except IOError as E:
      try:
        with _open(path2, "rb") as fd: return True if not get else path2  # cannot stat
      except: return False if not get else path2
    except OSError as E:
      try:
        with _open(path2, "rb") as fd: return True if not get else path2
      except: return False if not get else path2
  return True if not get else path2
os.path.exists = exists  # monkey-patch function

# Path file removal
_unlink, _remove = os.unlink, os.remove  # could be the same, but just in case
def __unlink(path): return _unlink(exists(path, True))
def __remove(path): return _remove(exists(path, True))
os.unlink, os.remove = __unlink, __remove

def _saveUnlink(path):
  try: _unlink(path)
  except: pass

_isdir = os.path.isdir
def __isdir(path): return _isdir(exists(path, True))  # in Coconut: def os.path.isdir = ...
os.path.isdir = __isdir

_isfile = os.path.isfile
def __isfile(path): return _isfile(exists(path, True))
os.path.isfile = __isfile

_islink = os.path.islink
def __islink(path): return _islink(exists(path, True))
os.path.islink = __islink

_stat, _lstat = os.stat, os.lstat
def __stat(path): return _stat(exists(path, True))
def __lstat(path): return _lstat(exists(path, True))
os.stat, os.lstat = __stat, __lstat

_listdir = os.listdir
def __listdir(path): return _listdir(exists(path, True))
os.listdir = __listdir
if sys.version_info.major < 3:
  _dircache = dircache.listdir
  def __dircache(path): return _dircache(exists(path, True))
  dircache.listdir = __dircache



# Patch open function
class Open(object):
  def __init__(_, path, mode):
    _log.debug("calling patched 'open' function")
    _.path = path
    _.mode = mode
    _.fd = _open(exists(path, True), mode)

  def __enter__(_):
    _log.debug("Entering patched 'open' context manager")
    return _.fd

  def __exit__(_, *args):
    _log.debug("Exiting patched 'open' context manager %r" % str(args))
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

_chdir = os.chdir
def __chdir(path): return _chdir(exists(path, True))
os.chdir = __chdir

_mkdir = os.mkdir
def __mkdir(path, mode = _RIGHTS): return _mkdir(exists(path, True), mode)
os.mkdir = __mkdir

_rmdir = os.rmdir
def __rmdir(path): return _rmdir(exists(path, True))
os.rmdir = __rmdir

_makedirs = os.makedirs
def __makedirs(path, mode = _RIGHTS, exist_ok = False): return _makedirs(exists(path, True), **({"mode": mode} if sys.version_info.major < 3 else {"mode": mode, "exist_ok": exist_ok}))
os.makedirs = __makedirs


class TestRepoTestCase(unittest.TestCase):
  def testStuff(_):
    _.assertIsNot(_exists, os.path.exists)
    _.assertTrue(os.path.exists("./_test-data"))  # directory check
    _.assertTrue(_exists("_test-data/d/a.b"))
    _.assertTrue(_exists("./_test-data/d/a.b"))
    _.assertTrue(os.path.exists("./_test-data/d/a.b"))  # file check
    _.assertTrue(os.path.exists("./_test-data/D/a.b"))
    _.assertFalse(os.path.exists("./_test-data/D/a.c"))
    _.assertEqual(0, os.stat("_test-data/D/A.B")[6])
    _.assertEqual(0, os.lstat("_test-datA/d/A.B")[6])
    _.assertTrue(os.path.isdir("_test-data"))
    _.assertFalse(os.path.isdir("_test-data/d/A.B"))
    _.assertFalse(os.path.isdir("_test-data/d/A.c"))  # even if file doesn't exist
    _.assertTrue(os.path.isfile("_test-data/d/A.b"))
    _.assertFalse(os.path.isfile("_test-data/d/A.c"))  # even if file doesn't exist
    _.assertFalse(os.path.islink("_test-data/d"))
    _.assertFalse(os.path.islink("_test-data/d/a.b"))
    with open("_test-data/d/tmp", "w") as fd: pass  # touch
    os.unlink("_test-data/d/tmp")
    _.assertFalse(os.path.exists("_test-data/d/tmp"))
    try: os.makedirs("_test-data/tmp/2")
    except Exception as E: _.fail(str(E))
    _.assertTrue(os.path.exists("_test-data/tmp/2"))
    try: os.makedirs("_test-data/tmp/2"); _.fail("Should have thrown OSError")
    except OSError as E: pass
    _.assertTrue(os.path.exists("_test-data/tmp/2"))
    os.rmdir("_test-data/tmp/2")
    os.rmdir("_test-data/tmp")
    _.assertFalse(os.path.exists("_test-data/tmp"))
    os.mkdir("_test-data/tmp2")
    _.assertTrue(os.path.exists("_test-data/tmp2"))
    os.rmdir("_test-data/tmp2")
    _.assertFalse(os.path.exists("./_test-data/tmp2"))



def load_tests(loader, tests, ignore):
  ''' Queried by unittest. '''
  tests.addTests(doctest.DocTestSuite("simfs"))
  return tests


if __name__ == '__main__':
#  import pdb; pdb.set_trace()
  logging.basicConfig(level = logging.DEBUG if os.environ.get("DEBUG", "False").lower() == "true" else logging.INFO, stream = sys.stderr, format = "%(asctime)-23s %(levelname)-8s %(name)s:%(lineno)d | %(message)s")
  if sys.platform == 'win32': print("Testing on Windows makes no sense, this is a Windows file system simulator"); exit(1)  # TODO maybe it does anyway?
  unittest.main()  # warnings = "ignore")
