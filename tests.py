import os
import subprocess
import sys
import unittest

import lib, tp

PYTHON = os.path.realpath(sys.executable)
REPO = '_test-data'
CFG = '.tagsplorer.cfg'
IDX = '.tagsplorer.idx'

def call(argstr): return subprocess.Popen(argstr, shell = True, bufsize = 1000000, stdout = subprocess.PIPE).communicate()[0]
def runP(argstr): return subprocess.Popen(PYTHON + " tp.py " + argstr, shell = True, bufsize = 1000000, stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0]


def setUpModule():
  try: os.unlink(REPO + os.sep + IDX)
  except: pass # if earlier tests finished without errors
  try:
    call("svn revert %s" % (REPO + os.sep + CFG)) # for subversion
#    call("git checkout %s/%s" % (REPO, CFG)) # for git
  except: pass
  print(runP("-r %s -u -l1" % REPO)) # initial indexing, invisible

def tearDownModule():
  os.unlink(REPO + os.sep + IDX)


class TestRepoTestCase(unittest.TestCase):
  ''' All tests are run through the command-line interface of tp.py. '''

  def testFilenameCaseSetting(_):
    ''' This test confirms that case setting works (only executed on Linux). '''
    _.assertIn("Modified global configuration entry", runP("-r %s --set case_sensitive=False -l1" % REPO))
    _.assertIn("Wrote", runP("-r %s -u -l1" % REPO)) # TODO swap order when bug has been fixed to match initial .cfg
    _.assertIn("1 files found", runP("-r %s -s x.x -l1" % REPO))
    _.assertIn("1 files found", runP("-r %s -s X.x -l1" % REPO))
    _.assertIn("Modified global configuration entry", runP("-r %s --set case_sensitive=True" % REPO))
    _.assertIn("Wrote", runP("-r %s -u -l1" % REPO))
    _.assertIn("1 files found", runP("-r %s -s x.x -l1" % REPO))
    _.assertIn("0 files found", runP("-r %s -s X.x -l1" % REPO))

  def testConfigs(_):
    ''' This test tests global configuration CRUD. '''
    _.assertIn("Added global configuration entry", runP("-r %s --set __test=123 -l1" % REPO))
    _.assertIn("Modified global configuration entry", runP("-r %s --set __test=234 -l1" % REPO))
    ret = runP("-r %s --get __test -l1" % REPO)
    _.assertIn("__test = 234", ret)
    _.assertIn("Get global configuration", ret)
    _.assertIn("Removed global configuration entry", runP("-r %s --unset __test -l1" % REPO))


  def testGlobalIgnoreDir(_):
    _.assertIn("No folder match", runP("-r %s -s filea.exta" % REPO)) # TODO should not find

  def testGlobalSkipDir(_):
    _.assertIn("No folder match", runP("-r %s -s filec.extb" % REPO)) # TODO should not find

  def testLocalIgnoreDir(_):
    _.assertIn("No folder match", runP("-r %s -s a.b -l1" % REPO)) # TODO should not find
    _.assertIn("1 files found", runP("-r %s -s x.c -l1" % REPO)) # should show number of instances found

  def testLocalSkipDir(_):
    _.assertIn("No folder match", runP("-r %s -s x.d -l1" % REPO)) # TODO should not find

  def testLocalTag(_):
    pass

  def testMappedTag(_):
    pass

  def testMappedGlobExclude(_):
    pass

  def testOnlyDirSearch(_):
    pass

@unittest.SkipTest
def findTest_():
  cfg = Config(); cfg.log = 1
  cfg.load(os.path.join("..", "..", CONFIG))
  i = Indexer("../..")
  i.log = 1 # set log level
  i.walk(cfg) # index files
  print(i.findFolders(["docman", "recrawl"])) # ['/projects/ADocManB/target/classes/de/arnebachmann/docman/recrawl', '/projects/ADocManB/src/de/arnebachmann/docman/recrawl']
  print(i.findFolders(["owncloud", "pascal"])) # ['/projects/owncloud']
  print(i.findFolders(["docman", "recrawl"], ["target"])) # ['/projects/ADocManB/src/de/arnebachmann/docman/recrawl']
  print([i.findFiles(x, ["owncloud", "pascal"], []) for x in i.findFolders(["owncloud", "pascal"])])
  print(i.findFolders(sys.argv[1:]))

@unittest.SkipTest
def unwalkTest_():
  i.store(os.path.join("..", "..", INDEX), config_too = False)
  i.load(os.path.join("..", "..", INDEX)) # try to reload index - has mismatching timestamp and will recreate index
  i.unwalk()
  print(i.tagdir2paths)
  for x, v in dictviewitems(i.tagdir2paths):
    print(i.tagdirs[x], list(i.getPaths(v)))
  print(i.find(["Toolsold", "de"]))

@unittest.SkipTest
def compressionTest_():
  import timeit
  for j in range(10):
    i.compressed = j
    i.store(INDEX)
    s = os.stat(INDEX)[6]
    print("Level %d: %f %d" % (j, timeit.Timer(lambda: i.load(INDEX)).timeit(number = 20), s))

def load_tests(loader, tests, ignore):
  ''' The function suffix of "_tests" is the conventional way of telling unittest about a test case. '''
  import doctest
  tests.addTests(doctest.DocTestSuite(lib))
  tests.addTests(doctest.DocTestSuite(tp))
  return tests

if __name__ == '__main__':
  import unittest
  sys.unittesting = None
  unittest.main()