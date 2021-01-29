''' tagsPlorer file system emulation  (C) 2016-2021  Arne Bachmann  https://github.com/ArneBachmann/tagsplorer '''

import doctest, logging, os, sys, unittest

_log = logging.getLogger(__name__)

if '--simulate-winfs' in sys.argv or os.environ.get("SIMULATE_WINFS", "false").lower() == "true":
  _log.debug("Using case-insensitive file system emulation (for testing Windows behavior on Linux)")
  if '--simulate-winfs' in sys.argv: sys.argv.remove('--simulate-winfs')

  from tagsplorer.constants import SLASH, ST_SIZE
  from tagsplorer.utils import wrapExc

  SIMFS = True
  _RIGHTS = 0o777

  def _realPath(path):
    ''' Central function that determines the actual file name case for the given folder or file path.
        path:    file system path to analyse
        returns: string for real path as stored on the file system
    >>> with open("_x.X", "w"): pass  # create file
    >>> print(os.path.exists("_x.X"))
    True
    >>> with open("_x.X", "a"): pass  # write same
    >>> print(os.path.exists("_x.X"))
    True
    >>> fd = open("_x.X", "w"); fd.write("123"); fd.close()
    3
    >>> print(os.path.exists("_x.X"))
    True
    >>> fd = open("_X.x", "w"); fd.write("234"); fd.close()  # write over different case of same file using file handle
    3
    >>> print(os.path.exists("_X.x"))
    True
    >>> print(os.path.exists("_x.X"))
    True
    >>> with open("_X.X", "a") as fd: fd.write("567")
    3
    >>> fd = open("_x.x", "r"); contents = fd.read(); fd.close(); print(contents)
    234567
    >>> wrapExc(lambda: _unlink("_x.X"), None)
    >>> print(os.path.exists("_X.x"))
    False
    >>> print(os.path.exists("_x.X"))
    False
    '''
    _log.debug(f"_realPath '{path}'")
    assert path is not None
    if not path: return path
  #  path = _normpath(path)  # remove intermediate ".." etc. TODO leads to recursion due to use of os.stat
    steps = path.replace(os.sep, SLASH).split(SLASH)
    absolute = path[0] == SLASH
    if steps[0] not in ('', os.curdir): steps.insert(0, os.curdir)  # must be relative path like a/b, (otherwise ./a/b or /a/b, but never A:/b/c, because not on Windows)
    while os.pardir in steps:  # implement os.path.normpath
      steps.pop(steps.index(os.pardir) - 1)  # /a/b/../c = /a/c
      steps.remove(os.pardir)  # /a/b/../c = /a/c
    while os.curdir in steps: steps.remove(os.curdir)  # implement os.path.normpath
    if absolute: steps.pop(0)
    real = '' if absolute else '.'
    for step in steps:
      try: files = _listdir(real if real else '/')
      except: real += SLASH + step; continue  # cannot access: continue with path as given
      found = [f for f in files if f.lower() == step.lower()]  # match case-normalized
      if len(found) != 1:
        if len(found) > 1: debug(f"Cannot determine real path, since multiple names match {step}: {found}"); found = list(reversed(sorted(found)))[:1]
        else: found = [step]  # fallback
      real += SLASH + found[0]
    return real


  _exists = os.path.exists
  def __exists(path): return wrapExc(lambda: _exists(_realPath(path)), False)  # also for file handles
  os.path.exists = __exists  # monkey-patch function

  _unlink, _remove = os.unlink, os.remove  # could be the same, but just in case
  def __unlink(path): return _unlink(_realPath(path))
  def __remove(path): return _remove(_realPath(path))
  os.unlink, os.remove = __unlink, __remove

  _normpath = os.path.normpath
  def __normpath(path): return _normpath(_realPath(path))  # in Coconut: def os.path.isdir = ...
  os.path.normpath = __normpath

  _isdir = os.path.isdir
  def __isdir(path): return _isdir(_realPath(path))  # in Coconut: def os.path.isdir = ...
  os.path.isdir = __isdir

  _isfile = os.path.isfile
  def __isfile(path): return _isfile(_realPath(path))
  os.path.isfile = __isfile

  _islink = os.path.islink
  def __islink(path): return _islink(_realPath(path))
  os.path.islink = __islink

  _stat, _lstat = os.stat, os.lstat
  def __stat(path):  return  _stat(_realPath(path))
  def __lstat(path): return _lstat(_realPath(path))
  os.stat, os.lstat = __stat, __lstat

  _listdir = os.listdir
  def __listdir(path): return _listdir(_realPath(path))
  os.listdir = __listdir


  # Patch the open function
  class Open(object):
    def __init__(_, path, mode):
      _log.debug("calling patched 'open' function")
      _.path = path
      _.mode = mode
      _.fd = _open(_realPath(path), mode)

    def __enter__(_):
      _log.debug("Entering patched 'open' context manager")
      return _.fd

    def __exit__(_, *args):
      _log.debug(f"Exiting patched 'open' context manager {args}")
      try: _.fd.close()
      except: pass
      finally: del _.fd

    def read(_,  *args, **kwargs): return _.fd.read( *args, **kwargs)
    def write(_, *args, **kwargs): return _.fd.write(*args, **kwargs)
    def close(_, *args, **kwargs):
      try:                         return _.fd.close(*args, **kwargs)
      except: pass
      finally: del _.fd
  _open, open = open, Open

  _chdir = os.chdir
  def __chdir(path): return _chdir(_realPath(path))
  os.chdir = __chdir

  _mkdir = os.mkdir
  def __mkdir(path, mode = _RIGHTS): return _mkdir(_realPath(path), mode)
  os.mkdir = __mkdir

  _rmdir = os.rmdir
  def __rmdir(path): return _rmdir(_realPath(path))
  os.rmdir = __rmdir

  _makedirs = os.makedirs
  def __makedirs(path, mode = _RIGHTS, exist_ok = False):
    return _makedirs(_realPath(path), mode = mode, exist_ok = exist_ok)
  os.makedirs = __makedirs


  class TestRepoTestCase(unittest.TestCase):
    def testStuff(_):
      _.assertIsNot(_exists, os.path.exists)  # ensure monkey-patch worked
      _.assertTrue(os.path.exists("./_test-data"))  # directory check
      _.assertTrue(_exists("_test-data/d/a.b"))
      _.assertTrue(_exists("./_test-data/d/a.b"))
      _.assertTrue(os.path.exists("./_test-data/d/a.b"))  # file check
      _.assertTrue(os.path.exists("./_test-data/D/a.b"))
      _.assertFalse(os.path.exists("./_test-data/D/a.c"))
      _.assertEqual(0, os.stat("_test-data/D/A.B")[ST_SIZE])
      _.assertEqual(0, os.lstat("_test-DATA/d/A.B")[ST_SIZE])
      _.assertTrue(os.path.isdir("_test-data"))
      _.assertFalse(os.path.isdir("_test-data/d/A.B"))
      _.assertFalse(os.path.isdir("_test-data/d/A.c"))  # even if file doesn't exist
      _.assertTrue(os.path.isfile("_test-data/d/A.b"))
      _.assertFalse(os.path.isfile("_test-data/d/A.c"))  # even if file doesn't exist
      _.assertFalse(os.path.islink("_test-data/d"))
      _.assertFalse(os.path.islink("_test-data/d/a.b"))
      with open("_test-data/d/tmp", "w"): pass  # touch
      os.unlink("_test-data/d/tmp")
      _.assertFalse(os.path.exists("_test-data/d/tmp"))
      try: os.makedirs("_test-data/tmp/2", exist_ok = True)
      except Exception as E: _.fail(str(E))
      _.assertTrue(os.path.exists("_test-data/tmp/2"))
      try: os.makedirs("_test-data/tmp/2", exist_ok = False); _.fail("Should have thrown OSError")
      except OSError: pass
      _.assertTrue(os.path.exists("_test-data/tmp/2"))
      os.rmdir("_test-data/tmp/2")
      os.rmdir("_test-data/tmp")  # TODO fails because not empty? .tagsplorer.cfg
      _.assertFalse(os.path.exists("_test-data/tmp"))
      os.mkdir("_test-data/tmp2")
      _.assertTrue(os.path.exists("_test-data/tmp2"))
      os.rmdir("_test-data/tmp2")
      _.assertFalse(os.path.exists("./_test-data/tmp2"))


  def load_tests(loader, tests, ignore):
    ''' Queried by unittest. '''
    tests.addTests(doctest.DocTestSuite("tagsplorer.simfs"))
    return tests

else: SIMFS = False


if __name__ == '__main__':
  logging.basicConfig(level = logging.DEBUG if os.environ.get("DEBUG", "False").lower() == "true" else logging.INFO, stream = sys.stderr, format = "%(asctime)-23s %(levelname)-8s %(name)s:%(lineno)d | %(message)s")
  if sys.platform == 'win32': print("Testing on Windows makes no sense. This is a Windows file system simulator!"); exit(1)
  _chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # main repo folder
  unittest.main()  # warnings = "ignore")
  for file in ("_X.x", "_x.X"): wrapExc(lambda: _unlink(file))
