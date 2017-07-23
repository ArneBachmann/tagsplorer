# tagsPlorer test suite  (C) Arne Bachmann https://github.com/ArneBachmann/tagsplorer
# Test suite. Please export environment variable DEBUG=True
# Export SKIP=true to avoid revert of test data prior to test run

import logging
import os
import shutil
import subprocess
import sys
import unittest
import traceback
StringIO = (__import__("StringIO" if sys.version_info.major < 3 else "io")).StringIO  # enables import via ternary expression


# Custom modules
import lib
import simfs
import tp


def call(argstr): so = subprocess.Popen(argstr, shell = True, bufsize = 1000000, stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]; return so.decode('ascii') if sys.version_info.major >= 3 else so

def runP(argstr, repo = None):  # instead of script call via Popen, to allow for full test coverage collection
  def tmp():
    sys.argv = ["tp.py", "-r", REPO if repo is None else repo] + (["--simulate-winfs"] if SIMFS else []) + lib.safeSplit(argstr, " ")
    logFile.write("TEST: " + " ".join(sys.argv) + " " + repr(argstr) + "\n")
    tp.Main().parse()  # initiates script run due to overriding sys.path above
  res = wrapChannels(tmp)
  logFile.write(res)
  logFile.write("\n")
  return res

def wrapChannels(func):
  oldv, oldo, olde = sys.argv, sys.stdout, sys.stderr
  buf = StringIO()
  sys.stdout = sys.stderr = buf
  handler = logging.StreamHandler(buf)
  logging.basicConfig(level = logging.DEBUG, format = "%(asctime)-25s %(levelname)-8s %(name)-12s | %(message)s")
  _log = logging.getLogger(__name__)
  debug, info, warn, error = map(lambda func: lambda *s: func(" ".join([str(e) for e in s])), [_log.debug, _log.info, _log.warn, _log.error])
  _log.addHandler(handler)
  lib.debug, lib.info, lib.warn, lib.error = debug, info, warn, error
  tp.debug, tp.info, tp.warn, tp.error = debug, info, warn, error
  try: func()
  except Exception as E: buf.write(str(E) + "\n"); traceback.print_exc(file = buf)
  sys.argv, sys.stdout, sys.stderr = oldv, oldo, olde
  return buf.getvalue()

def setUpModule():
  ''' Test suite setup: missing SKIP environment variable removes previous index and reverts config file. '''
  global logFile
  logFile = open(".testRun.log", "w")

def tearDownModule():
  logFile.close()
  if not os.environ.get("SKIP", "False").lower() == "true":
    try: os.unlink(REPO + os.sep + lib.INDEX)
    except: pass
    if SVN: call("svn revert %s" % (REPO + os.sep + lib.CONFIG))  # for subversion (development system)
    else:   call("git checkout %s/%s" % (REPO, lib.CONFIG))  # for git (CI system)


class TestRepoTestCase(unittest.TestCase):
  ''' All tests are run through the command-line interface of tp.py. '''

  def setUp(_):
    try: os.unlink(REPO + os.sep + lib.INDEX)
    except: pass  # if earlier tests finished without errors
    if SVN:  call("svn revert %s" % (REPO + os.sep + lib.CONFIG))  # for subversion
    else: call("git checkout %s/%s" % (REPO, lib.CONFIG))  # for git
    runP("-u")  # initial indexing, invisible

  def assertAllIn(_, lizt, where):
    ''' Helper assert. '''
    [_.assertIn(a, where) for a in lizt]

  def testSjoin(_):
    _.assertEqual("", lib.sjoin())
    _.assertEqual("", lib.sjoin(""))
    _.assertEqual("", lib.sjoin("", ""))
    _.assertEqual("a b", lib.sjoin("a", "b"))

  def testFunctions(_):
    def x(a):
      if a == None: raise Exception("should not have been processed")
      return a == 3
    _.assertTrue(tp.xany(x, [1, 2, 3, None]))
    _.assertTrue(tp.xall(x, [3, 3, 3]))
    _.assertTrue(lib.isfile("tests.py"))
    _.assertFalse(lib.isdir("tests.py"))
    _.assertFalse(lib.isfile(os.getcwd()))
    _.assertTrue(lib.isdir(os.getcwd()))
    x = [1, 2]
    i = id(x)
    _.assertTrue(i == id(lib.lappend(x, 3)))
    _.assertTrue(i == id(lib.lappend(x, [4, 5])))
    _.assertEqual([1, 2, 3, 4, 5], x)
    _.assertEqual(0, lib.appendandreturnindex([], 1))
    _.assertEqual(1, lib.appendandreturnindex([1], 1))
    _.assertEqual([], lib.safeSplit(''))
    _.assertEqual(["1"], lib.safeSplit('1'))
    _.assertEqual(["1", "2"], lib.safeSplit('1,2'))
    _.assertEqual(["1", "2"], lib.safeSplit('1;2', ";"))
    d = lib.dd()
    d[1].append(1)
    _.assertEqual([1], d[1])

  def testGlobCheck(_):
    _.assertFalse(lib.isglob(""))
    _.assertTrue(lib.isglob("*"))
    _.assertTrue(lib.isglob("???"))
    _.assertTrue(lib.isglob("*a.c"))
    _.assertTrue(lib.isglob("*a*.c"))
    _.assertTrue(lib.isglob("*a*.c"))
    _.assertTrue(lib.isglob("a??.c"))
    _.assertTrue(lib.isglob("how.do?"))
    _.assertTrue(lib.isglob("sbc.*"))
    _.assertFalse(lib.isglob("sbc.a"))
    _.assertFalse(lib.isglob("sbca"))

  def testSafesplit(_):
    _.assertEqual([], lib.safeSplit(""))
    _.assertEqual([], lib.safeSplit(","))
    _.assertEqual(["a"], lib.safeSplit("a"))
    _.assertEqual(["a"], lib.safeSplit("a,"))
    _.assertEqual(["a"], lib.safeSplit(",a"))
    _.assertEqual(["a", "b"], lib.safeSplit("a,b"))
    _.assertEqual(["a", "b"], lib.safeSplit("a;b", ";"))

  def testOnlySearchTerms(_):
    _.assertIn("1 files found", runP(".x -l2"))

  def testReduceCaseStorage(_):
    _.assertIn("Tags: 87" if lib.ON_WINDOWS else "Tags: 83", runP("--stats"))
    _.assertIn("2 files found", runP("Case -v"))  # contained in /cases/Case
    _.assertIn("0 files found", runP("case -v"))  # wrong case writing, can't find
    _.assertIn("2 files found", runP("case -v -C"))  # ignore case: should find
#    _.assertIn("2 files found" if lib.ON_WINDOWS else "0 files found", runP("CASE -v"))  # TODO
    _.assertIn("Added global configuration entry", runP("--set reduce_case_storage=True -v"))
    runP("-u")  # trigger update index after config change (but should automatically do so anyway)
    _.assertIn("Tags: 47", runP("--stats"))
    _.assertIn("0 files found" if lib.ON_WINDOWS else "2 files found", runP("Case -v"))  # update after config change
    _.assertIn("0 files found", runP("case -v"))  # update after config change
#    _.assertIn("2 files found" if lib.ON_WINDOWS else "0 files found", runP("CASE -v"))  # TODO

  def testFilenameCaseSetting(_):
    ''' This test confirms that case setting works (only executed on Linux). '''
    # Start with tag/dir search
    if lib.ON_WINDOWS: return  # TODO only skip the minimal part that is Linux-specific, but not all
    _.assertIn("Modified global configuration entry", runP("--set case_sensitive=True -v"))
    _.assertIn("0 files found", runP("-s case -v"))
    _.assertIn("2 files found", runP("-s Case -v"))
    _.assertIn("0 files found", runP("-s CASE -v"))
    _.assertIn("2 files found", runP("-s case -v --ignore-case"))  # should be same as next line above
    _.assertIn("Modified global configuration entry", runP("--set case_sensitive=False -v"))
    _.assertIn("Wrote", runP("-u -v"))  # update after config change
    _.assertIn("2 files found", runP("-s case -v"))
    _.assertIn("2 files found", runP("-s Case -v"))
    # Now file-search
    _.assertIn("1 files found", runP("-s x.x -v"))  # doesn't find because case-normalized X.X doesn't exist
    _.assertIn("1 files found", runP("-s x.x -v"))  # TODO also test --relaxed for removed file
    _.assertIn("1 files found", runP("-s X.x -v --ignore-case"))
    _.assertIn("1 files found", runP("-s x.x --ignore-case -v"))  # TODO stupid to use --relaxed everywhere - better replace by real case
    _.assertIn("Modified global configuration entry", runP("--set case_sensitive=True"))
    _.assertIn("Wrote", runP("-u -v"))
    _.assertIn("1 files found", runP("-s x.x -v"))
    _.assertIn("0 files found", runP("-s X.x -v"))
    _.assertIn("1 files found", runP("-s X.x -v -C"))

  def testConfigs(_):
    ''' This test tests global configuration CRUD. '''
    _.assertAllIn(["debug mode", "Added global configuration entry"], runP("--set __test=123 -v"))
    _.assertIn("Modified global configuration entry", runP("--set __test=234 -l1"))
    ret = runP("--get __test -l1")
    _.assertIn("__test = 234", ret)
    _.assertIn("Get global configuration", ret)
    _.assertIn("Removed global configuration entry", runP("--unset __test -l1"))

  def testIllegalConfig(_):
    class MyIO(StringIO):
      def readlines(_):
        return iter(_.read().split("\n"))
      def xreadlines(_):
        return _.readlines()
    def tmp():
      buf = MyIO("1494711739628\n[]\nfoo=bar\n")
      cp = lib.ConfigParser()
      cp.load(buf)
    res = wrapChannels(tmp)
    _.assertIn('Encountered illegal', res)
    def tmp2():
      buf = MyIO("1494711739628\n[]\nfoo\n")
      cp = lib.ConfigParser()
      cp.load(buf)
    res = wrapChannels(tmp2)
    _.assertIn('Key with no value', res)

  def testGlobalIgnoreDir(_):
    _.assertAllIn(["0 files found"], runP("-s filea.exta -v"))  # was "No folder match" earlier, but searching files reduces the "includes" list to [] which returns all paths now
    _.assertNotIn("filea.exta", runP("-s filea.exta"))

  def testGlobalSkipDir(_):
    _.assertIn("0 files found", runP("-s filec.extb -v"))  # should not been found due to skipd setting
    _.assertNotIn("filec.extb", runP("-s filec.extb"))

  def testLocalIgnoreDir(_):
    _.assertIn("0 files found", runP("-s 3.3 -l1"))  # not filtering on folder tags
    _.assertIn("1.2", runP("-s 1.2 -l1"))  #
    _.assertIn("2.1", runP("-s 2.1 -l1"))
    _.assertIn("0 files found", runP("-s .3 -l2"))  # due to local ignore marker file

  def testLocalSkipDir(_):
    _.assertIn("0 files found", runP("-s ignore_skip,marker-files,b,1.1 -l1"))
    _.assertIn("1 files found", runP("-s ignore_skip,marker-files,b,2.2 -l1"))
    _.assertNotIn(".3", runP("--stats -v"))

  def testLocalTag(_):
    _.assertAllIn(["found in 1 folders", "1 folders found"], runP("-s b1,tag1 -v --dirs"))  #
    _.assertIn("1 files found", runP("-s b1,tag1 -v"))  # The other file is excluded by the tag1 exclude in the config TODO separate testswith inc/exc and file/glob
    _.assertIn("1 files found", runP("-s b1 -s tag1 -v"))  # Different interface, same result

  def testMappedInclude(_):
    _.assertIn("2 files found", runP("-s two,test -l1"))  # one direct match and one mapped
    _.assertIn("/a.a", runP("-s two,test"))  # direct match for test in /two
    _.assertIn("/2.2", runP("-s two,test"))  # mapped match for test from /one

  def testMappedExclude(_):
    _.assertIn("2 files found", runP("-s one,test -l1"))  # one direct match and one mapped
    _.assertIn("/2.2", runP("-s two,test -l1"))  # direct match for test in /one
    _.assertIn("/a.a", runP("-s two,test -l1"))  # mapped match for test from /two

  def testMappedOnlyFilename(_):
    ''' Find a certain filename, crawling entire tree. '''
    _.assertIn("2 files found", runP("-s 2.2 -l1"))

  def testExtensionOnly(_):
    _.assertIn("No folder match", runP(".xyz -l2"))

  def testMappedGlobExclude(_):
    pass

  def testOnlyDirsOption(_):
    _.assertIn("1 folders found", runP("-s folder1 -l1 --dirs"))
    _.assertIn("/folders/folder1", runP("-s folder1 -l1 --dirs"))
    _.assertIn("3 folders found", runP("-s folder? -l1 --dirs"))
    _.assertAllIn(["/folders", "/folders/folder1", "/folders/folder2"], runP("-s folder? -l1 --dirs"))
    _.assertIn("3 folders found", runP("-s folder* -l1 --dirs"))

  def testExtensions(_):
    _.assertIn("2 files found", runP("-s .ext1 -l1"))
    _.assertIn("Cannot have multiple", runP("-s .ext1 .ext2 -l1"))
    _.assertIn("1 files found", runP("-s .ext1,extension -l1"))

  def testFindFolder(_):
    def tmp():
      i = lib.Indexer(REPO)
      i.log = 1  # set log level
      i.load(os.path.join(REPO, lib.INDEX), True, False)
      print(i.findFolders(["folders", "folder2"]))
    res = wrapChannels(tmp)
    _.assertIn('/folders/folder2', res)
    _.assertEqual(3, len(res.split("\n")))  # Info:    Reading index from _test-data/.tagsplorer.idx\nDebug:   Setting up case-sensitive matching\n['/folders/folder2']\n
    def tmp():
      i = lib.Indexer(REPO)
      i.log = 2  # set log level
      i.load(os.path.join(REPO, lib.INDEX), True, False)
      print(lib.wrapExc(lambda: set(i.getPaths(i.tagdir2paths[i.tagdirs.index("a")], cache)), lambda: set()))
    _.assertIn(repr(set()), wrapChannels(tmp))  # "a" not in index TODO but should be

  def testStats(_):
    _.assertNotIn(" 0 occurrences", runP("--stats -v"))

  @unittest.SkipTest
  def testGlobs(_):
    _.assertIn("1 files found", runP('"dot.*" -l1'))

  def testInit(_):
    _.assertAllIn(["Writing configuration to", "Wrote", "config bytes"], runP("-I -l2", repo = os.path.join("_test-data", "tmp")))
    _.assertAllIn(["Index already exists", "--relaxed"], runP("-I -l2", repo = os.path.join("_test-data", "tmp")))
    _.assertAllIn(["Writing configuration to", "Wrote", "config bytes"], runP("-I -l2 --relaxed", repo = os.path.join("_test-data", "tmp")))
#    try: shutil.rmtree(os.path.join("_test-data", "tmp"))  # , onerror = lambda func, path, exc_info: _.fail("Could not remove temporarily created path in testInit(). Clean up before running tests again."))  # TODO fails on python3 with "TypeError: remove() got an unexpected keyword argument 'dir_fd'"
    try: os.unlink(os.path.join("_test-data", "tmp", ".tagsplorer.cfg")); os.rmdir(os.path.join("_test-data", "tmp"))
    except Exception as E: _.fail(str(E))

  def testAddRemove(_):
    ''' Add a tag, check and remove. '''
    try: os.unlink(os.path.join(REPO, "tagging", "anyfile1"))
    except: pass
    _.assertIn("0 files found", runP("-s missing -v"))
    _.assertIn("File or glob not found", runP("--tag missing,-exclusive /tagging/anyfile1 -v"))
    _.assertIn("0 files found", runP("-s missing -v"))  # shouldn't be modified above
    # test adding non-existing file, then search
    _.assertAllIn(["Adding tags", "added anyway"], runP("--tag missing,-exclusive /tagging/anyfile1 -v --relaxed"))
    _.assertIn("0 files found", runP("-s missing -v"))  # because file doesn't exist, regardless of tag being defined or not
    _.assertAllIn(["removing anyway", "Removing positive entry"], runP("--untag missing,-exclusive /tagging/anyfile1 -v --relaxed"))
    _.assertIn("0 files found", runP("-s missing -v"))  # because neither file nor tagging exists
    # test adding on existing file, then search
    with open(os.path.join(REPO, "tagging", "anyfile1"), "w") as fd: fd.close()  # touch to create file
    _.assertIn("Adding tags", runP("--tag missing,-exclusive /tagging/anyfile1 -v"))  # now possible without --relaxed
    _.assertIn("1 files found", runP("-s missing -v"))
    try: os.unlink(os.path.join(REPO, "tagging", "anyfile1"))  # remove again
    except: pass
    _.assertIn("skipping", runP("--untag missing,-exclusive /tagging/anyfile1 -v"))  # now possible without --relaxed
    _.assertIn("anyway", runP("--untag missing,-exclusive /tagging/anyfile1 -l 2 --relax"))
    _.assertIn("0 files found", runP("-s missing -l 2"))

  def testNoOption(_):
    _.assertIn("No option", runP(""))

  def testNegativeSearch(_):
    _.assertAllIn(["4 folders found for +<a> -<>.",   "/a", "/a/a1", "/a/a2"], runP("-s a -l2 --dirs").split("\n"))  # only include only dirs
    _.assertAllIn(["3 folders found for +<a> -<a1>.", "/a", "/a/a2"], runP("-s a -x a1 -v --dirs").split("\n"))  # with exclude only dirs
    _.assertAllIn(["Potential matches found in 4 folders", "6 files found in 4 checked paths", "file3.ext1", "file3.ext2", "file3.ext3"], runP("-s a -v"))  # only include with files
    _.assertAllIn(["Potential matches found in 3 folders", "3 files found in 3 checked paths", "file3.ext1", "file3.ext2", "file3.ext3"], runP("-s a -x a1 -l2"))  # with exclude with files

  def testTestLib(_):
    _.assertAllIn(["passed all tests", "0 failed", "Test passed"], call(PYTHON + " lib.py --test -v"))

  def testExtensionAndTag(_):
    _.assertAllIn(["/b/b1/file3.ext1", "1 files found"], runP("b .ext1 -v"))
    _.assertAllIn(["No folder match", "/ignore_skip/marker-files/a/1/1.2", "1 files found"], runP("a .2 -v"))  # no match due to skip file marker

  def testNegativeExtension(_):
    _.assertAllIn(["/a/a2/file3.ext3", "1 files found"], runP("a,-.ext1,-.ext2 -v"))

  def testUnwalk(_):
    def unwalk(_, idx = 0, path = ""):
      ''' Walk entire tree from index (slow but proof of correctness). '''
      tag = _.tagdirs[idx]  # name of head element
      children = (f[0] for f in filter(lambda a: a[1] == idx and a[0] != idx, ((e, v) for e, v in enumerate(_.tagdir2parent))))  # using generator expression
      if _.log >= 1: print(path + tag + lib.SLASH)
      for child in children: _.unwalk(child, path + tag + lib.SLASH)

    def tmp():
      lib.Indexer.unwalk = unwalk  # monkey-path function
      i = lib.Indexer(REPO)
      i.log = 1  # set log level
      i.load(os.path.join(REPO, lib.INDEX), True, False)
      i.unwalk()
    res = wrapChannels(tmp).replace("\r", "")
    logFile.write(res + "\n")
    _.assertEqual(len(res.split("\n")), 67 if lib.ON_WINDOWS else 63)  # TODO why?

@unittest.SkipTest
def compressionTest_():
  ''' This is not a unit test, rather a benchmark test code. '''
  i = lib.Indexer("../..")
  import timeit
  for j in range(10):
    i.compressed = j
    i.store(lib.INDEX)
    s = os.stat(lib.INDEX)[6]
    print("Level %d: %f %d" % (j, timeit.Timer(lambda: i.load(lib.INDEX)).timeit(number = 20), s))

def load_tests(loader, tests, ignore):
  ''' Queried by unittest. '''
  import doctest
  tests.addTests(doctest.DocTestSuite(lib))
  tests.addTests(doctest.DocTestSuite(tp))
  tests.addTests(doctest.DocTestSuite(simfs))
  return tests


if __name__ == '__main__':
  DEBUG = os.environ.get("DEBUG", "False").lower() == "true"  # cannot use --debug as it is caught by the unittest handling
  if not DEBUG: print("Error: Set environment variable DEBUG=True to run the test suite"); sys.exit(1)
  try: del sys.argv[sys.argv.index("--simulate-winfs")]; SIMFS = True
  except: SIMFS = os.environ.get("SIMULATE_WINFS", "false").lower() == "true"
  PYTHON = os.path.realpath(sys.executable) if SIMFS or not lib.ON_WINDOWS else '"' + os.path.realpath(sys.executable) + '"'
  logFile = None  # declare global variable
#  logging.basicConfig(level = logging.DEBUG, stream = sys.stderr, format = "%(asctime)-25s %(levelname)-8s %(name)-12s | %(message)s")
  REPO = '_test-data'
  SVN = tp.findRootFolder(None, '.svn') is not None
  print("Using VCS '%s' to revert test data" % "SVN" if SVN else "Git")
  unittest.main()  # warnings = "ignore")
