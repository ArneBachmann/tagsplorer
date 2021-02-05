# coding=utf-8

''' tagsPlorer test suite  (C) 2016-2021  Arne Bachmann  https://github.com/ArneBachmann/tagsplorer '''

# HINT Set environment variable SKIP=true to avoid reverting test data prior to test run

import doctest, inspect, logging, os, subprocess, sys, unittest, traceback
from io import StringIO

from tagsplorer import constants, lib, simfs, tp, utils  # entire files

REPO = '_test-data'


def call(argstr, cwd = os.path.dirname(os.path.abspath(__file__))):
  ''' Run in a subprocess, no code coverage. '''
  return subprocess.Popen(argstr, cwd = cwd, shell = True, bufsize = 1000000, stdout = subprocess.PIPE, stderr = subprocess.STDOUT).communicate()[0].decode(sys.stdout.encoding)


def runP(argstr, repo = None):  # instead of script call via Popen, this allows coverage collection
  sys.argv = ["tp.py", "-r", repo if repo else REPO] + (["--simulate-winfs"] if simfs.SIMFS else []) + utils.safeSplit(argstr, " ")  # fake arguments
  def tmp():
    logFile.write("TEST: %s " % inspect.stack()[3].function + " ".join(sys.argv) + "\n")
    try: tp.Main().parse_and_run()
    except SystemExit as e: logFile.write(f"EXIT: {e.code}\n")
  res = wrapChannels(tmp)
  logFile.write(res)
  logFile.write("\n")
  return res


def wrapChannels(func):
  oldv, oldo, olde = sys.argv, sys.stdout, sys.stderr
  buf = StringIO()
  sys.stdout = sys.stderr = buf
  handler = logging.StreamHandler(buf)
#  debug, info, warn, error = map(lambda func: lambda *s: func(" ".join([str(e) for e in s])), [_log.debug, _log.info, _log.warning, _log.error])
  tp._log.addHandler(handler)
  lib._log.addHandler(handler)
  utils._log.addHandler(handler)
#  utils.debug, utils.info, utils.warn, utils.error =\
#  lib.debug, lib.info, lib.warn, lib.error =\
#  tp.debug, tp.info, tp.warn, tp.error = debug, info, warn, error
  try: func()
  except Exception as E: buf.write(str(E) + "\n"); traceback.print_exc(file = buf)
  finally:
    sys.argv, sys.stdout, sys.stderr = oldv, oldo, olde
    tp._log.removeHandler(handler)
    lib._log.removeHandler(handler)
    utils._log.removeHandler(handler)
  return buf.getvalue()


def setUpModule():
  ''' Run once before the entire test suite. '''
  global logFile
  logFile = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".testRun.log"), "w")


def tearDownModule():
  ''' Run once after the entire test suite. '''
  logFile.close()
  if not os.environ.get("SKIP", "False").lower() == "true":
    try: os.unlink(REPO + os.sep + constants.INDEX)
    except: pass
    if SVN: call(f'svn revert   "{REPO + os.sep + constants.CONFIG}"')
    else:   call(f'git checkout "{REPO + os.sep + constants.CONFIG}"')


class TestRepoTestCase(unittest.TestCase):
  ''' All tests are run through the command-line interface of tp.py. '''

  def setUp(_):
    ''' Run before each testCase. '''
    try: os.unlink(REPO + os.sep + constants.INDEX)
    except FileNotFoundError: pass  # if earlier tests finished without errors
    if SVN:  call(f'svn revert   "{REPO + os.sep + constants.CONFIG}"')
    else:    call(f'git checkout "{REPO + os.sep + constants.CONFIG}"')
    try: os.unlink(os.path.join(REPO, "tagging", "anyfile1"))
    except: pass
    _.assertIn("Updated configuration entry", runP("--set case_sensitive=True -v"))  # fixed value for reproducibility TODO allow all combinations on all platforms
    runP("-U")  # initial indexing, invisible

  def assertAllIn(_, what, where):
    ''' Assert all elements of what have an exact match in where. '''
    [_.assertIn(a, where) for a in what]

  def assertAllInAny(_, what, where):
    ''' Assert all elements of what are contained in at least one of where's entries. '''
    [_.assertTrue([a in entry for entry in where]) for a in what]  # TODO check if not same as above and used correctly

  def testSjoin(_):
    _.assertEqual("",    utils.sjoin())
    _.assertEqual("",    utils.sjoin(""))
    _.assertEqual("",    utils.sjoin("", ""))
    _.assertEqual("a b", utils.sjoin("a", "b"))

  def testFunctions(_):
    def x(a):
      if a == None: raise Exception("xany should not process this part!")
      return bool(a)
    _.assertTrue(tp.xany(x, [3, 3, 3, None]))
    _.assertFalse(tp.xany(x, []))
    _.assertTrue(utils.xall(x, [3, 3, 3]))
    _.assertFalse(utils.xall(x, [0, None]))
    _.assertTrue(utils.isFile("tests.py"))
    _.assertFalse(os.path.isdir("tests.py"))
    _.assertFalse(utils.isFile(os.getcwd()))
    _.assertTrue(os.path.isdir(os.getcwd()))
    x = [1, 2]
    i = id(x)
    _.assertTrue(i == id(utils.lappend(x, 3)))  # returns existing object
    _.assertTrue(i == id(utils.lappend(x, [4, 5])))  # ???
    _.assertEqual([1, 2, 3, 4, 5], x)
    _.assertEqual(0, utils.findIndexOrAppend([], 1))
    _.assertEqual(0, utils.findIndexOrAppend([1], 1))
    _.assertEqual(1, utils.findIndexOrAppend([1], 2))
    _.assertEqual([], utils.safeSplit(''))
    _.assertEqual(["1"], utils.safeSplit('1'))
    _.assertEqual(["1", "2"], utils.safeSplit('1,2'))
    _.assertEqual(["1", "2"], utils.safeSplit('1;2', ";"))
    d = utils.dd()
    d[1].append(1)
    _.assertEqual([1], d[1])

  def testGlobCheck(_):
    _.assertFalse(utils.isGlob(""))
    _.assertTrue(utils.isGlob("*"))
    _.assertTrue(utils.isGlob("???"))
    _.assertTrue(utils.isGlob("*a.c"))
    _.assertTrue(utils.isGlob("*a*.c"))
    _.assertTrue(utils.isGlob("*a*.c"))
    _.assertTrue(utils.isGlob("a??.c"))
    _.assertTrue(utils.isGlob("how.do?"))
    _.assertTrue(utils.isGlob("sbc.*"))
    _.assertFalse(utils.isGlob("sbc.a"))
    _.assertFalse(utils.isGlob("sbca"))

  def testSafesplit(_):
    _.assertEqual([], utils.safeSplit(""))
    _.assertEqual([], utils.safeSplit(","))
    _.assertEqual(["a"], utils.safeSplit("a"))
    _.assertEqual(["a"], utils.safeSplit("a,"))
    _.assertEqual(["a"], utils.safeSplit(",a"))
    _.assertEqual(["a"], utils.safeSplit(",a,"))
    _.assertEqual(["a", "b"], utils.safeSplit("a,b"))
    _.assertEqual(["a", "b"], utils.safeSplit("a;b", ";"))

  def testOnlySearchTerms(_):
    _.assertAllIn(["Found 1 files", "/b/b2/b2a/x.x"], runP(".x -v"))

  def testReduceCaseStorage(_):
    #_.assertIn("Added configuration entry: reduce_storage = False", runP("--set reduce_storage=False"))
    _.assertIn("tags: 49", runP("--stats"))  # only few upper-case entries exist, therefore no big difference if reduce_storage is used
    _.assertIn("Found 2 files in %d folders" % (2 if constants.ON_WINDOWS or simfs.SIMFS else 1), runP("Case -v"))  # contained in /cases/Case
    _.assertIn("Found 0 files", runP("CASE -v"))  # wrong case writing, can't find
    _.assertIn("Found %d files in %d folders" % ((4, 2) if constants.ON_WINDOWS or simfs.SIMFS else (2, 1)), runP("case -v -c"))  # ignore case: should find Case and case (no combination because different findFiles calls)
    _.assertIn("Added configuration entry", runP("--set reduce_storage=True -v"))
    _.assertAllIn(["Configuration entry: case_sensitive = True", "Configuration entry: reduce_storage = True"], runP("--config -v"))
    runP("-U")  # trigger update index after config change (but should automatically do so anyway)
    _.assertIn("tags: 49", runP("--stats"))  # now also small on Windows Windows
    _.assertIn("Found 2 files in 1 folders", runP("Case -v"))  # index contains original case only
    _.assertIn("Found 0 files in 0 folders", runP("case -v"))  # normalized version not in index anymore
#    _.assertIn("Found 2 files in ? folders", runP("case -c -v"))  # find anyway TODO should work but gets 0 in 0
    _.assertIn("Reset configuration parameters", runP("--reset"))  # TODO test if parameters reset to default

  def testFilenameCaseSetting(_):
    ''' This test confirms that case setting works (only executed on Linux). '''
    if utils.ON_WINDOWS or simfs.SIMFS: return  # TODO only skip the minimal part that is Linux-specific, but not all TODO or run always with simfs?
    _.assertIn("Found 0 files", runP("-s case --debug"))  # lower-case
    _.assertIn("Found 2 files", runP("-s Case --debug"))  # mixed-case
    _.assertIn("Found 0 files", runP("-s CASE --debug"))
    _.assertIn("Found 2 files", runP("-s case --debug --ignore-case"))  # should be same as next line above
    _.assertIn("Updated configuration entry", runP("--set case_sensitive=False -v"))
    _.assertIn("Wrote", runP("-U -v"))  # update after config change
    _.assertIn("Found 2 files", runP("-s Case -V"))
    _.assertIn("Found 2 files", runP("-s case -v"))  # TODO should be found no matter what
    # Now file-search
    _.assertIn("Found 1 files", runP("-s x.x -v"))  # doesn't find because case-normalized X.X doesn't exist
    _.assertIn("Found 1 files", runP("-s x.x -v"))  # TODO also test --force for removed file
    _.assertIn("Found 1 files", runP("-s X.x -v --ignore-case"))
    _.assertIn("Found 1 files", runP("-s x.x --ignore-case -v"))
    _.assertIn("Updated configuration entry", runP("--set case_sensitive=True"))  # revert
    _.assertIn("Wrote", runP("-U -v"))
    _.assertIn("Found 1 files", runP("-s x.x -v"))
    _.assertIn("Found 0 files", runP("-s X.x -v"))
    _.assertIn("Found 1 files", runP("-s X.x -v -c"))

  def testConfigs(_):
    ''' This test tests global configuration CRUD. '''
    _.assertAllIn(["Added configuration entry"], runP("--set __test=123 -v"))
    _.assertIn("Updated configuration entry", runP("--set __test=234 -v"))
    ret = runP("--get __test -v")
    _.assertIn("__test = 234", ret)
    _.assertIn("Configuration entry", ret)
    _.assertIn("Removed configuration entry", runP("--unset __test -v"))

  def testIllegalConfig(_):
    class MyIO(StringIO):
      def readlines(_):  return iter(_.read().split("\n"))
      def xreadlines(_): return _.readlines()
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
    _.assertIn('Key without value', res)

  def testGlobalIgnoreDir(_):
    _.assertAllIn(["Found 0 files"], runP("-s filea.exta -v"))  # was "No folder match" earlier, but searching files reduces the "includes" list to [] which returns all paths now
    _.assertNotIn("filea.exta", runP("-s filea.exta"))

  def testGlobalSkipDir(_):  # should skip /c/c2 which contains "filec.extb"
    _.assertIn("Found 0 files", runP("-s filec.extb -v"))  # should not been found due to skipd setting
    _.assertNotIn("filec.extb", runP("-s filec.extb"))

  def testLocalIgnoreDir(_):
    _.assertIn("Found 0 files", runP("-s 3.3 -v"))  # not filtering on folder tags
    _.assertIn("1.2", runP("-s 1.2 -v"))  #
    _.assertIn("2.1", runP("-s 2.1 -v"))
    _.assertIn("Found 0 files", runP("-s .3 -v"))  # due to local ignore marker file

  def testLocalSkipDir(_):
    _.assertIn("Found 0 files", runP("-s ignore_skip,marker-files,b,1.1 -v"))
    _.assertIn("Found 1 files", runP("-s ignore_skip,marker-files,b,2.2 -v"))
    _.assertNotIn("'.3'", runP("--stats -V"))
    _.assertIn("'.2'", runP("--stats -V"))

  def testLocalTag(_):
    _.assertIn("Found 1 folders", runP("-s b1,tag1 -v --dirs"))  #
    _.assertIn("Found 3 files in 1 folders", runP("-s b1,tag1 -v"))  # TODO correct but we should change semantics for exclusive patterns
    _.assertIn("Found 3 files in 1 folders", runP("-s b1 -s tag1 -v"))  # different interface, same result

  def testMappedInclude(_):
    _.assertAllIn(["Found 1 file", "/mapping/two/2.2"], runP("-s two,test -v"))  # finds folder two with a mapped direct tag test

  def testExtensionOnly(_):
    _.assertIn("Found 0 files in %d folders" % (27 if constants.ON_WINDOWS or simfs.SIMFS else 26), runP(".xyz -v"))  # /cases/case is added on Windows, and '' is not filtered on Windows

  def testMappedGlobExclude(_):
    pass

  def testOnlyDirsOption(_):
    _.assertAllIn(["Found 1 folder", "/folders/folder1"], runP("-s folder1 -v --dirs"))
    _.assertAllIn(["Found 3 folders", "/folders", "/folders/folder1", "/folders/folder2"], runP('-v -s folder? --dirs'))  # must be quoted on command-line, though
    _.assertAllIn(["Found 4 folders", "folder2", "folder1", "folders", "dot.folder"], runP('-s folder* -v --dirs'))

  def testExtensions(_):
    _.assertIn("Found 3 files in 2 folders", runP("-s .ext1 -v"))
    _.assertIn("more than one file extension", runP("-s .ext1 .ext2 -v"))
    _.assertIn("Found 1 files", runP("-s .ext1,extension -v"))

  def testFindFolder(_):
    def tmp():
      i = lib.Indexer(REPO)
      i.load(os.path.join(REPO, constants.INDEX), ignore_skew = True, recreate_index = False)
      print(i.findFolders(["folders", "folder2"], []))
    res = wrapChannels(tmp)
    _.assertAllIn(['/folders/folder2'], res)  # , 'Found potential matches in 1 folders'
    def tmp2():
      i = lib.Indexer(REPO)
      i.load(os.path.join(REPO, constants.INDEX), ignore_skew = True, recreate_index = False)
      print(utils.wrapExc(lambda: set(i.getPaths(i.tagdir2paths[i.tagdirs.index("a")], {})), lambda: set()))  # print output is captured
    _.assertAllIn(['/a/a2', '/a', '/a/a1', '/ignore_skip/marker-files/a'], wrapChannels(tmp2))

  def testStats(_):
    _.assertNotIn(" 0 occurrences", runP("--stats -v"))

  def testTokenization(_):
    _.assertAllIn(["Found 1 files",  "_test-data/dot.folder/one"], runP("folder -v"))  # find dot.folder via token
    _.assertAllIn(["Found 1 files",  "_test-data/dot.folder/one"], runP("dot -v"))
    _.assertAllIn(["Found 1 folder", "_test-data/ignore_skip"],    runP("skip -v --dirs"))

  def testGlobs(_):
    _.assertIn("Found 1 files in 1 folders", runP('dot.* -v'))

  def testInit(_):
    _.assertAllIn(["Create root configuration", "Wrote", "config bytes"], runP("-I -v --force", repo = os.path.join("_test-data", "tmp")))
    _.assertAllIn(["Index already exists", "--force"], runP("-I -v", repo = os.path.join("_test-data", "tmp")))
    _.assertAllIn(["Create root configuration", "Wrote", "config bytes"], runP("-I -v --force", repo = os.path.join("_test-data", "tmp")))
    try: os.unlink(os.path.join("_test-data", "tmp", ".tagsplorer.cfg")); os.rmdir(os.path.join("_test-data", "tmp"))
    except Exception as E: _.fail(str(E))

  def testAddRemove(_):
    ''' Add a tag, check and remove. '''
    _.assertIn("Found 0 files", runP("-s missing -v"))
    _.assertIn("No file matches", runP("--tag missing,-exclusive _test-data/tagging/anyfile1 -v"))
    _.assertNotIn("Wrote", runP("--tag missing,-exclusive _test-data/tagging/anyfile1 -v"))
    _.assertAllIn(["folders", "folder2"], runP("--tags _test-data/folders/folder2"))
    _.assertNotIn("Recreate", runP("-s missing -v"))  # should not reindex due to absence of above cfg update
    _.assertIn("Found 0 files", runP("-s missing -v"))  # should still not find anything
    # test adding non-existing file, then search
    _.assertAllIn(["Tag <missing> in '/tagging' for +anyfile1 -", "add anyway"], runP("--tag missing,-exclusive _test-data/tagging/anyfile1 -v --force"))
    _.assertIn("Found 0 files in 1 folders", runP("-s missing -v"))
    _.assertIn("remove anyway", runP("--untag missing,-exclusive _test-data/tagging/anyfile1 -v --force"))
    _.assertIn("Found 0 files", runP("-s missing -v"))  # because neither file nor tagging exists
    # test adding on existing file, then search
    with open(os.path.join(REPO, "tagging", "anyfile1"), "w") as fd: fd.close()  # touch to create file
    _.assertIn("Tag <missing> in '/tagging' for +anyfile1 -", runP("--tag missing,-exclusive _test-data/tagging/anyfile1 -v"))
    _.assertIn("Found 1 files", runP("-s missing -v"))  # is now find, since existing
    try: os.unlink(os.path.join(REPO, "tagging", "anyfile1"))  # remove again
    except: pass
    _.assertIn("skip", runP("--untag missing,-exclusive _test-data/tagging/anyfile1 -v"))
    _.assertIn("anyway", runP("--untag missing,-exclusive _test-data/tagging/anyfile1 -V --force"))
    _.assertIn("Found 0 files", runP("-s missing -v"))

  def testNoOption(_):
    _.assertIn("No option", runP(""))

  def testNegativeSearch(_):
    _.assertAllInAny(["Found 4 folders for +<a> -<>", "/a", "/a/a1", "/a/a2"], runP("-s a -v --dirs").split("\n"))  # only display dirs
    _.assertAllInAny(["Found 3 folders for +<a> -<a1>", "/a", "/a/a2"], runP("-s a -x a1 -v --dirs").split("\n"))  # with exclude only dirs
    _.assertIn("Found 7 files in 4 folders", runP("-s a -v"))  # only include with files
    _.assertAllIn(["Found 4 files in 3 folders", "file3.ext1", "file3.ext2", "file3.ext3"], runP("-s a -x a1 -v"))  # with exclude with files

  @unittest.skip("doesn't run on CI because No module named 'tagsplorer'")
  def testTestLib(_):
    _.assertAllIn(["Test passed", "Test passed"], call(PYTHON + " lib.py -v", cwd = os.path.dirname(os.path.abspath(__file__)) + os.sep + "tagsplorer"))
    _.assertAllIn(["Test passed", "Test passed"], call(PYTHON + " tp.py --test -v", cwd = os.path.dirname(os.path.abspath(__file__)) + os.sep + "tagsplorer"))
    _.assertAllIn(["Test passed", "Test passed"], call(PYTHON + " utils.py -v", cwd = os.path.dirname(os.path.abspath(__file__)) + os.sep + "tagsplorer"))

  def testExtensionAndTag(_):
    _.assertAllIn(["Found 2 files in 1 folders", "/b/b1/file3.ext1"], runP("b .ext1 -v"))
    _.assertAllIn(["Found 2 files in 1 folders", "/b/b1/file3.ext1"], runP(".ext1 b -v"))  # should be same (regression test)
    _.assertAllIn(["Found 0 files"], runP("a .3 -v"))  # doesn't exist
    _.assertAllIn(["Found 0 files"], runP("a .2 -v"))  # while a lists all files in folder, filtering with .2 doesn't match any a
    _.assertAllIn(["Found 1 folders", "/b/b1"], runP(".ext1 b -v --dirs"))  # was returning all folders previously

  def testNegativeExtension(_):
    _.assertIn("more than one file extension", runP("a,-.ext1,-.ext2 -v"))
    _.assertIn("Found 5 files in 4 folders", runP("-s a -x .ext1 -v"))
    _.assertNotIn(".ext1", runP("-s a -x .ext1"))
    _.assertIn("Found 3 files in 1 folders", runP("a1 -x .ext1 -v"))
    _.assertIn("Found 3 files in 3 folders", runP("-s a -x .ext2 -v"))
    _.assertIn("Found 2 files in %d folders" % (27 if constants.ON_WINDOWS or simfs.SIMFS else 26), runP("b1 -x .ext2 -v"))

  def testUnwalk(_):
    def unwalk(_, idx = 0, path = ""):
      ''' Walk entire tree from index (slow but proof of correctness). '''
      tag = _.tagdirs[idx]  # name of head element
      children = (f[0] for f in filter(lambda a: a[1] == idx and a[0] != idx, ((e, v) for e, v in enumerate(_.tagdir2parent))))  # using generator expression
      print(path + tag + constants.SLASH)
      for child in children: unwalk(_, idx = child, path = path + tag + constants.SLASH)

    def tmp():
      i = lib.Indexer(REPO)
      i.load(os.path.join(REPO, constants.INDEX), True, False)
      unwalk(i)
    result = wrapChannels(tmp).replace("\r", "")
    logFile.write(result + "\n")
    _.assertEqual(31, len(result.split("\n")))  # TODO check if correct


def _compressionTest():
  ''' This is not a unit test, rather a benchmark test code. '''
  import timeit
  i = lib.Indexer("../..")
  for j in range(10):
    print(f"Compression level {j}")
    i.compressed = j
    i.store("../_test-data/" + constants.INDEX)
    s = os.stat(constants.INDEX)[6]  # get compressed size
    print("Level %d: %f %d" % (j, timeit.Timer(lambda: i.load(constants.INDEX)).timeit(number = 20), s))


def load_tests(loader, tests, ignore):
  ''' Added up by unittest. '''
  tests.addTests(doctest.DocTestSuite(tp))
  tests.addTests(doctest.DocTestSuite(lib))
  tests.addTests(doctest.DocTestSuite(simfs))
  tests.addTests(doctest.DocTestSuite(utils))
  return tests


if __name__ == '__main__':
  os.chdir(os.path.dirname(os.path.abspath(__file__)))  # change to own folder
  PYTHON = '"' + os.path.realpath(sys.executable) + '"' if constants.ON_WINDOWS else os.path.realpath(sys.executable)
  logFile = None
  SVN = tp.findRootFolder('.svn') is not None
  print("Using VCS '%s' to revert test data" % "Subversion" if SVN else "Git")
  unittest.main()  # warnings = "ignore")
