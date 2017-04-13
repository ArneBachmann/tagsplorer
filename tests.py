# tagsPlorer test suite  (C) Arne Bachmann https://github.com/ArneBachmann/tagsplorer
# Test suite. Please export environment variable DEBUG=True
# TODO check D: vs. D:\ logic

import os
import subprocess
import sys
import unittest
import traceback
StringIO = (__import__("StringIO" if sys.version_info.major < 3 else "io")).StringIO  # enables import via ternary expression

# Custom modules
import lib
import tp

PYTHON = os.path.realpath(sys.executable) if sys.platform != 'win32' else '"' + os.path.realpath(sys.executable) + '"'
REPO = '_test-data'
SVN = tp.findRootFolder(None, '.svn') is not None
print("Using VCS '%s'" % "SVN" if SVN else "Git")

logFile = None


def call(argstr): so = subprocess.Popen(argstr, shell = True, bufsize = 1000000, stdout = subprocess.PIPE).communicate()[0]; return so.decode('ascii') if sys.version_info.major >= 3 else so

def runP(argstr):  # instead of script call via Popen, to allow for full coverage stats
  def tmp():
    sys.argv = ["tp.py", "-r", REPO] + lib.safeSplit(argstr, " ")
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
  try: func()
  except Exception as E: buf.write(str(E) + "\n"); traceback.print_exc(file = buf)
  sys.argv, sys.stdout, sys.stderr = oldv, oldo, olde
  return buf.getvalue()

def setUpModule():
  ''' Test suite setup: missing SKIP environment variable removes previous index and reverts config file. '''
  lib.LOG = lib.DEBUG
  global logFile
  logFile = open(".testRun.log", "w")

def tearDownModule():
  logFile.close()
  if not os.environ.get("SKIP", "False").lower() == "true":
    try: os.unlink(REPO + os.sep + lib.INDEX)
    except: pass
    if SVN: call("svn revert %s" % (REPO + os.sep + lib.CONFIG))  # for subversion
    else:   call("git checkout %s/%s" % (REPO, lib.CONFIG))  # for git


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

  def testFunctions(_):
    def x(a):
      if a == None: raise Exception("should not have been processed")
      return a == 3
    _.assertTrue(tp.xany(x, [1, 2, 3, None]))
    _.assertTrue(tp.xall(x, [3, 3, 3]))
    _.assertEqual(["abc", ".ext", "d"], tp.withoutFilesAndGlobs(["abc", ".ext", "a?v.c", "ab.c", "*x*", "d"]))
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

  def testOnlySearchTerms(_):
    _.assertIn("1 files found", runP(".x -l2"))

  def testReduceCaseStorage(_):
    _.assertIn("Tags: 81" if sys.platform != 'win32' else "Tags: 85", runP("--stats"))
    _.assertIn("2 files found", runP("Case -v"))
    _.assertIn("0 files found", runP("case -v"))
    _.assertIn("2 files found", runP("case -v -C"))
    _.assertIn("0 files found" if sys.platform != 'win32' else "2 files found", runP("CASE -v"))
    _.assertIn("Added global configuration entry", runP("--set reduce_case_storage=True -v"))
    runP("-u")  # trigger update index after config change (but should automatically do so anyway)
    _.assertIn("Tags: 46", runP("--stats"))
    _.assertIn("2 files found" if sys.platform != 'win32' else "0 files found", runP("Case -v"))  # update after config change
    _.assertIn("0 files found", runP("case -v"))  # update after config change
    _.assertIn("0 files found" if sys.platform != 'win32' else "2 files found", runP("CASE -v"))

  def testFilenameCaseSetting(_):
    ''' This test confirms that case setting works (only executed on Linux). '''
    # Start with tag/dir search
    if sys.platform == 'win32': return  # TODO only skip the minimal part that is Linux-specific, but not all
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

  def testGlobalIgnoreDir(_):
    _.assertAllIn(["0 files found"], runP("-s filea.exta -v"))  # was "No folder match" earlier, but searching files reduces the "includes" list to [] which returns all paths now
    _.assertNotIn("filea.exta", runP("-s filea.exta"))

  def testGlobalSkipDir(_):
    _.assertIn("0 files found", runP("-s filec.extb -v"))
    _.assertNotIn("filec.extb", runP("-s filec.extb"))

  def testLocalIgnoreDir(_):
    _.assertIn("0 files found", runP("-s 3.3 -l1"))  # not filtering on folder tags
    _.assertIn("1.2", runP("-s 1.2 -l1"))  #
    _.assertIn("2.1", runP("-s 2.1 -l1"))

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
    _.assertIn("3 files found", runP("-s 2.2 -l1"))

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
      i.log = lib.WARN  # set log level
      i.load(os.path.join(REPO, lib.INDEX), True, False)
      print(i.findFolders(["folders", "folder2"])[0])
    _.assertIn('/folders/folder2', wrapChannels(tmp))

  def testStats(_):
    _.assertNotIn(" 0 occurrences", runP("--stats -v"))

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
#    _.assertAllIn(["Case: /cases/Case/c (25), /cases/Case (23)", "CASE: /cases/Case/c (25), /cases/Case (23)"], runP("--stats -v"))
    # TODO why does 'a' finds all kinds of things?
    _.assertAllIn(["Info:    3 folders found for +<a> -<>.",   "/a", "/a/a1", "/a/a2"], runP("-s a -l2 --dirs").split("\n"))  # only include only dirs
    _.assertAllIn(["Info:    2 folders found for +<a> -<a1>.", "/a", "/a/a2"], runP("-s a -x a1 -v --dirs").split("\n"))  # with exclude only dirs
    _.assertAllIn(["Potential matches found in 3 folders", "6 files found in 3 checked paths", "file3.ext1", "file3.ext2", "file3.ext3"], runP("-s a -v"))  # only include with files
    _.assertAllIn(["Potential matches found in 2 folders", "3 files found in 2 checked paths", "file3.ext1", "file3.ext2", "file3.ext3"], runP("-s a -x a1 -l2"))  # with exclude with files

  def testTest(_):
    _.assertEqual("", call(PYTHON + " lib.py --test"))

  @unittest.SkipTest
  def testUnwalk(_):
    def tmp():
      i = lib.Indexer(REPO)
      i.log = 1  # set log level
      i.load(os.path.join(REPO, lib.INDEX), True, False)
      i.unwalk()
    res = wrapChannels(tmp).replace("\r", "")
    logFile.write(res + "\n")
    _.assertEqual(len(res.split("\n")), 32)

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
  ''' The "_tests" suffix is the conventional way of telling unittest about a test case. '''
  import doctest
  tests.addTests(doctest.DocTestSuite(lib))
  tests.addTests(doctest.DocTestSuite(tp))
  return tests


if __name__ == '__main__':
  import unittest
  sys.unittesting = None  # flag to enable functions to know they are being tested (may help sometimes)
  unittest.main()
