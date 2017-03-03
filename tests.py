import os
import subprocess
import sys
import unittest
import lib
import tp
if sys.version_info.major < 3:
  from StringIO import StringIO
else:
  from io import StringIO

PYTHON = os.path.realpath(sys.executable)
REPO = '_test-data'
SVN = tp.findRootFolder(None, '.svn') is not None
print("Using VCS '%s'" % "SVN" if SVN else "Git")

logFile = None


def call(argstr): return subprocess.Popen(argstr, shell = True, bufsize = 1000000, stdout = subprocess.PIPE).communicate()[0]

def runP(argstr):  # instead of script call via Popen, to allow for full coverage stats
  def tmp():
    sys.argv = ["tp.py", "-r", REPO] + argstr.split(" ")
    tp.Main().parse()  # initiates script run due to overriding sys.path above
  logFile.write("TEST: " + argstr + "\n")
  try: res = wrapChannels(tmp)
  except Exception as E: logFile.write(str(E) + "\n"); raise E
  logFile.write(res)
  logFile.write("\n")
  return res

def wrapChannels(func):
  oldv, oldo, olde = sys.argv, sys.stdout, sys.stderr
  buf = StringIO()
  sys.stdout = sys.stderr = buf
  func()
  sys.argv, sys.stdout, sys.stderr = oldv, oldo, olde
  return buf.getvalue()

def setUpModule():
  ''' Test suite setup: missing SKIP removes index and reverts config '''
  os.environ["DEBUG"] = "True"
  global logFile
  logFile = open(".testRun.log", "w")
  if not os.environ.get("SKIP", "False").lower() == "true":
    try: os.unlink(REPO + os.sep + lib.INDEX)
    except: pass  # if earlier tests finished without errors
    if SVN:  call("svn revert %s" % (REPO + os.sep + lib.CONFIG))  # for subversion
    else:    call("git checkout %s/%s" % (REPO, lib.CONFIG))  # for git
  runP("-u -v")  # initial indexing, invisible

def tearDownModule():
  logFile.close()
  if not os.environ.get("SKIP", "False").lower() == "true":
    os.unlink(REPO + os.sep + lib.INDEX)
    if SVN: call("svn revert %s" % (REPO + os.sep + lib.CONFIG))  # for subversion
    else:   call("git checkout %s/%s" % (REPO, lib.CONFIG))  # for git


class TestRepoTestCase(unittest.TestCase):
  ''' All tests are run through the command-line interface of tp.py. '''

  def assertAllIn(_, lizt, where):
    ''' Helper assert. '''
    [_.assertIn(a, where) for a in lizt]

  @unittest.SkipTest
  def testFilenameCaseSetting(_):
    ''' This test confirms that case setting works (only executed on Linux). '''
    _.assertIn("Modified global configuration entry", runP("--set case_sensitive=False -l1"))
    _.assertIn("Wrote", runP("-u -v"))  # TODO swap order when bug has been fixed to match initial .cfg
    _.assertIn("1 files found", runP("-s x.x -l1"))
    _.assertIn("1 files found", runP("-s X.x -l1"))
    _.assertIn("Modified global configuration entry", runP("--set case_sensitive=True"))
    _.assertIn("Wrote", runP("-u -v"))
    _.assertIn("1 files found", runP("-s x.x -l1"))
    _.assertIn("0 files found", runP("-s X.x -l1"))

  def testConfigs(_):
    ''' This test tests global configuration CRUD. '''
    _.assertIn("Added global configuration entry", runP("--set __test=123 -l1"))
    _.assertIn("Modified global configuration entry", runP("--set __test=234 -l1"))
    ret = runP("--get __test -l1")
    _.assertIn("__test = 234", ret)
    _.assertIn("Get global configuration", ret)
    _.assertIn("Removed global configuration entry", runP("--unset __test -l1"))

  def testGlobalIgnoreDir(_):
    _.assertIn("No folder match", runP("-s filea.exta"))
    _.assertNotIn("filea.exta", runP("-s filea.exta"))

  def testGlobalSkipDir(_):
    _.assertIn("No folder match", runP("-s filec.extb"))
    _.assertNotIn("filec.extb", runP("-s filec.extb"))

  def testLocalIgnoreDir(_):
    _.assertIn("0 files found", runP("-s 3.3 -l1"))  # not filtering on folder tags
    _.assertIn("1.2", runP("-s 1.2 -l1"))  #
    _.assertIn("2.1", runP("-s 2.1 -l1"))

  def testLocalSkipDir(_):
    _.assertIn("0 files found", runP("-s ignore_skip,marker-files,b,1.1 -l1"))
    _.assertIn("1 files found", runP("-s ignore_skip,marker-files,b,2.2 -l1"))

  def testLocalTag(_):
    _.assertIn("1 files found", runP("-s b1,tag1 -l1"))  # The other file is excluded manually TODO separate testswith inc/exc and file/glob

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
    _.assertIn("No folder match", runP("-s 2.2 -l1"))
    _.assertIn("3 files found", runP("-s 2.2 -l1"))

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
      print(i.findFolders(["folders", "folder2"])[0])
    _.assertIn('/folders/folder2', wrapChannels(tmp))

  def testAddRemove(_):
    ''' Add a tag, check and remove. '''
    try: os.unlink(os.path.join(REPO, "tagging", "anyfile1"))
    except: pass
    _.assertIn("0 files found", runP("-s missing -v"))
    _.assertIn("File or glob not found", runP("--tag missing,-exclusive /tagging/anyfile1 -v"))
    _.assertIn("0 files found", runP("-s missing -v"))  # shouldn't be modified above
    # TODO test adding on existing file, then search
    # test adding non-existing file, then search
    _.assertIn("added anyway", runP("--tag missing,-exclusive /tagging/anyfile1 -v --relaxed"))
    _.assertIn("0 files found", runP("-s missing -v"))  # because file doesn't exist, regardless of tag being defined or not
    with open(os.path.join(REPO, "tagging", "anyfile1"), "w") as fd: fd.close()  # touch to create file
    _.assertIn("1 files found", runP("-s missing -v"))
    try: os.unlink(os.path.join(REPO, "tagging", "anyfile1"))
    except: pass
    _.assertIn("skipping", runP("--untag missing,-exclusive /tagging/anyfile1 -l 2"))
    _.assertIn("anyway", runP("--untag missing,-exclusive /tagging/anyfile1 -l 2 --relax"))
    _.assertIn("0 files found", runP("-s missing -l 2"))

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
  sys.unittesting = None
  unittest.main()
