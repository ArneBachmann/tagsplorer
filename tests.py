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
CFG = '.tagsplorer.cfg'
IDX = '.tagsplorer.idx'
SVN = os.path.exists('.svn')

def call(argstr): return subprocess.Popen(argstr, shell = True, bufsize = 1000000, stdout = subprocess.PIPE).communicate()[0]

def runP(argstr):  # instead of script call via Popen, to allow for full coverage stats
  oldv, oldo, olde = sys.argv, sys.stdout, sys.stderr
  sys.argv = ["tp.py", "-r", REPO] + argstr.split(" ")
  buf = StringIO()
  sys.stdout = sys.stderr = buf
  tp.Main().parse()  # initiates script run due to overriding sys.path above
  sys.argv, sys.stdout, sys.stderr = oldv, oldo, olde
  return buf.getvalue()

def setUpModule():
  ''' Test suite setup: missing SKIP removes index and reverts config '''
  if not os.environ.get("SKIP", False):
    try: os.unlink(REPO + os.sep + IDX)
    except: pass  # if earlier tests finished without errors
    if SVN:  call("svn revert %s" % (REPO + os.sep + CFG))  # for subversion
    else:    call("git checkout %s/%s" % (REPO, CFG))  # for git
  runP("-u -l1")  # initial indexing, invisible

def tearDownModule():
  if not os.environ.get("SKIP", False):
    os.unlink(REPO + os.sep + IDX)
    if SVN: call("svn revert %s" % (REPO + os.sep + CFG))  # for subversion
    else:   call("git checkout %s/%s" % (REPO, CFG))  # for git


class TestRepoTestCase(unittest.TestCase):
  ''' All tests are run through the command-line interface of tp.py. '''

  def assertAllIn(_, lizt, where):
    ''' Helper assert. '''
    [_.assertIn(a, where) for a in lizt]

  @unittest.SkipTest
  def testFilenameCaseSetting(_):
    ''' This test confirms that case setting works (only executed on Linux). '''
    _.assertIn("Modified global configuration entry", runP("--set case_sensitive=False -l1"))
    _.assertIn("Wrote", runP("-u -l1"))  # TODO swap order when bug has been fixed to match initial .cfg
    _.assertIn("1 files found", runP("-s x.x -l1"))
    _.assertIn("1 files found", runP("-s X.x -l1"))
    _.assertIn("Modified global configuration entry", runP("--set case_sensitive=True"))
    _.assertIn("Wrote", runP("-u -l1"))
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

@unittest.SkipTest
def findTest_():
  cfg = lib.Config(); cfg.log = 1
  cfg.load(os.path.join("..", "..", lib.CONFIG))
  i = lib.Indexer("../..")
  i.log = 1  # set log level
  i.walk(cfg)  # index files
  print(i.findFolders(["docman", "recrawl"]))  # ['/projects/ADocManB/target/classes/de/arnebachmann/docman/recrawl', '/projects/ADocManB/src/de/arnebachmann/docman/recrawl']
  print(i.findFolders(["owncloud", "pascal"]))  # ['/projects/owncloud']
  print(i.findFolders(["docman", "recrawl"], ["target"]))  # ['/projects/ADocManB/src/de/arnebachmann/docman/recrawl']
  print([i.findFiles(x, ["owncloud", "pascal"], []) for x in i.findFolders(["owncloud", "pascal"])])
  print(i.findFolders(sys.argv[1:]))

@unittest.SkipTest
def unwalkTest_():
  i = lib.Indexer("../..")
  i.store(os.path.join("..", "..", lib.INDEX), config_too = False)
  i.load(os.path.join("..", "..", lib.INDEX))  # try to reload index - has mismatching timestamp and will recreate index
  i.unwalk()
  print(i.tagdir2paths)
  for x, v in lib.dictviewitems(i.tagdir2paths):
    print(i.tagdirs[x], list(i.getPaths(v)))
  print(i.find(["Toolsold", "de"]))

@unittest.SkipTest
def compressionTest_():
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
