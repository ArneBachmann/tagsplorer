''' tagsPlorer command-line application  (C) 2016-2017  Arne Bachmann  https://github.com/ArneBachmann/tagsplorer '''

# This is the main entry point of the tagsPlorer utility (the command line interface is the first and currently only interface available, except a web server implementation)


import logging
import optparse
import os
import sys

if "--simulate-winfs" in sys.argv or os.environ.get("SIMULATE_WINFS", "false").lower() == "true":  # don't move to optparse handling, which is not in __main__
  ON_WINDOWS = True; from simfs import *  # monkey-patch current namespace

from lib import *  # direct namespace import is necessary to enable correct unpickling; also pulls in all other imports that need't be repeated here
from version import __version_info__, __version__  # used by setup.py

# Version-dependent imports
if sys.version_info.major == 3: from functools import reduce  # not built-in anymore, but not enough to create a dependency on six.py

APPNAME = "tagsPlorer"


# Little helper functions
def withoutFilesAndGlobs(tags): return [t for t in tags if not isglob(t) and os.extsep not in t[1:]]
def caseCompare(a, b):
  ''' Advanced case-normalized comparison for better output.
  >>> print(caseCompare("a", "a"))
  0
  >>> print(caseCompare("a", "b"))
  -1
  >>> print(caseCompare("b", "a"))
  1
  >>> print(caseCompare("A", "a"))
  -1
  >>> print(caseCompare("a", "A"))
  1
  '''
  aa = caseNormalize(a)
  bb = caseNormalize(b)
  ret = cmp(aa, bb)
  return ret if ret != 0 else cmp(a, b)

def commaArgsIntoList(lizt):
  '''
  >>> print(commaArgsIntoList([]))
  []
  >>> print(commaArgsIntoList(["a,b"]))
  ['a', 'b']
  >>> print(commaArgsIntoList(["ab"]))
  ['ab']
  '''
  assert type(lizt) is list
  return reduce(lambda a, b: a + ([b] if "," not in b else b.split(",")), lizt, [])

def removeTagPrefixes(poss, negs):
  '''
  >>> print(removeTagPrefixes(["a"], []))
  (['a'], [])
  >>> print(removeTagPrefixes(["+a", "b"], ["-c", "d"]))
  (['a', 'b'], ['c', 'd'])
  '''
  return [p[1:] if p[0] == '+' else p for p in poss], [n[1:] if n[0] == '-' else n for n in negs]  # remove leading +/-

def findRootFolder(options, filename):
  ''' Utility function that tries to auto-detect the given filename in parent folders.
      options: only for logging option
      filename: file to find
      returns: actual file path or None if not found
  '''
  path = os.getcwd()  # start in current folder, check parent until found or stopped
  try:
    while not os.path.exists(os.path.join(path, filename)):
      new = os.path.dirname(path)
      if new == path: break  # avoid infinite loop
      path = new
    if os.path.exists(os.path.join(path, filename)):  # found something
      path = os.path.join(path, filename)
      if options and options.log >= 1: info("Found root configuration at '%s'" % path)
      return path
  except Exception as E: debug(E)
  return None  # report as error

def getRoot(options, args):
  ''' Determine root folder by checking arguments and some fall-back logic.
  >>> class O: pass
  >>> import tp  # necessary to monkey-patch
  >>> tmp = tp.findRootFolder; tp.findRootFolder = lambda o, f: "/z/a.b"  # mock away this function
  >>> o = O(); o.index = None; o.root = None; o.log = 1
  >>> print(getRoot(o, []))
  /z
  >>> tp.findRootFolder = tmp  # restore function
  >>> o.root = "/x"; print(getRoot(o, []))
  /x
  >>> o.index = "/y"; print(getRoot(o, []))
  /x
  >>> o.root = None; o.index = "/abc"; print(getRoot(o, []))  # this combination should never occur
  None
  '''
  if options.index: return options.root  # -i and -r always go together
  folder = options.root
  if folder is None:
    folder = findRootFolder(options, CONFIG)
    if folder is not None: folder = os.path.dirname(folder)
  if folder is None: folder = os.curdir  # '.'
  return folder


class CatchExclusionsParser(optparse.OptionParser):
  ''' Allows to process undefined options as non-option arguments (e.g. --tag as an additional exclusive tag). '''
  def __init__(_):
    ihf = optparse.IndentedHelpFormatter(2, 60, 120)
    optparse.OptionParser.__init__(_, prog = APPNAME, usage = "python tp.py <tags or options>", version = APPNAME + "  (C) Arne Bachmann  Release version " + __version__, formatter = ihf)  # , formatter = optparse.TitledHelpFormatter(),
  def _process_args(_, largs, rargs, values):
    while rargs:
      try: optparse.OptionParser._process_args(_, largs, rargs, values)
      except (optparse.BadOptionError, optparse.AmbiguousOptionError) as E: largs.append(E.opt_str)

class Main(object):

  def initIndex(_):
    ''' Set up empty index, defining a root folder. '''
    folder = getRoot(_.options, _.args)
    index = folder if not _.options.index else _.options.index
    cfg = Config(_.options.log)
    if _.options.log >= 1: info("Creating root configuration at %s" % index)
    if not _.options.simulate:
      if _.options.strict and os.path.exists(os.path.join(index, CONFIG)):
        error("Index already exists. Use --relaxed to override. Aborting.")
      else:
        cfg.store(os.path.join(index, CONFIG))

  def updateIndex(_):
    ''' Crawl the folder tree and create a new index file.
        _.options: options structure from optparse, using rot and log
        _.args: arguments list from optparse, using as root folder if given
    '''
    folder = getRoot(_.options, _.args)
    index = folder if not _.options.index else _.options.index
    if _.options.log >= 1: info("Using configuration from %s" % index)
    cfg = Config(_.options.log)
    cfg.load(os.path.join(index, CONFIG))
    if _.options.log >= 1: info("Updating index")
    idx = Indexer(folder); idx.log = _.options.log  # set log level
    idx.walk(cfg)  # index all files
    if not _.options.simulate: idx.store(os.path.join(index, INDEX), idx.timestamp)
    return idx

  def find(_):
    ''' Find all folders that match the provided tags in _.options.find, excluding those from _.options.excludes.
        returns: None
        side-effect: print found files to stdout, logging to stderr
    '''
    poss, negs = splitCrit(commaArgsIntoList(_.args), lambda e: e[0] != '-')  # potentially including +/-
    poss.extend(commaArgsIntoList(_.options.find))
    negs.extend(commaArgsIntoList(_.options.excludes))  # each argument could contain , or not
    poss, negs = removeTagPrefixes(poss, negs)
    if len([p for p in poss if p.startswith(DOT)]) > 1: error("Cannot have multiple positive file extension filters (would always return no match)"); return
    folder = getRoot(_.options, _.args)
    index = folder if not _.options.index else _.options.index
    indexFile = os.path.join(index, INDEX)
    if not os.path.exists(indexFile):
      error("No index file found. Crawling file tree")
      idx = _.updateIndex()  # crawl file tree immediately and return search index
    else:
      idx = Indexer(index); idx.log = _.options.log  # initiate indexer
      idx.load(indexFile)  # load search index
    if _.options.ignore_case:
      idx.cfg.case_sensitive = False  # if false, don't touch setting (not the same as "not ignore_case")
      normalizer.setupCasematching(idx.cfg.case_sensitive)  # case option defaults to true, but can be overriden by --ignore-case
    poss, negs = map(lambda l: lmap(normalizer.filenorm, l), (poss, negs))  # convert search terms to normalized case, if necessary
    if _.options.log >= 1: info("Effective filters +<%s> -<%s>" % (",".join(poss), ",".join(negs)))
    if _.options.log >= 1: info("Searching for tags +<%s> -<%s> in %s" % (','.join(poss), ','.join(negs), os.path.abspath(idx.root)))
    paths = idx.findFolders(withoutFilesAndGlobs(poss), withoutFilesAndGlobs(negs))  # use only real folder tags
    if _.options.log >= 1: info("Potential matches found in %d folders" % (len(paths)))
    if _.options.log >= 2: [debug(path) for path in paths]  # optimistic: all folders "seem" to match all tags, but only some might actually be (due to excludes etc)
    if len(paths) == 0 and xany(lambda x: isglob(x) or os.extsep in x, poss + negs):
      if _.options.onlyfolders: warn("Nothing found."); return
      warn("No folder match; cannot filter on folder names. Checking entire folder tree")  # the logic is wrong: we ignore lots of tags while finding folders, and the continue filtering. better first filter on exts or all, then continue??
      paths = idx.findFolders([], [], True)  # return all folders names unfiltered (except ignore/skip without marker files)
    if _.options.onlyfolders:
      info((paths, poss, negs))
      for p in poss: paths[:] = [x for x in paths if not isglob(p) or normalizer.globmatch(safeRSplit(x, SLASH), p)]  # successively reduce paths down to matching positive tags, as in --dirs mode tags currently have to be folder names TODO later we should reflect actual mapping
      for n in negs: paths[:] = [x for x in paths if not isglob(n) or not normalizer.globmatch(safeRSplit(x, SLASH), n)]  # TODO is this too strict and ignores configured tags and the index entirely?
      if _.options.log >= 1: info("Found %d folders for +<%s> -<%s> in index" % (len(paths), ",".join(poss), ".".join(negs)))
      paths[:] = removeCasePaths(paths)  # remove case doubles
      info("%d folders found for +<%s> -<%s>." % (len(paths), ",".join(poss), ".".join(negs)))
      try:
        if len(paths) > 0: printo("\n".join(paths))#idx.root + path + SLASH + file for file in files)); counter += len(files)  # incremental output
      except KeyboardInterrupt: pass  #idx.root + path + SLASH + file for file in files)); counter += len(files)  # incremental output
      return
    dcount, counter, skipped = 0, 0, []  # if not only folders, but also files
    for path, (files, skip) in ((path, idx.findFiles(path, poss, negs, not _.options.strict)) for path in paths):
      if skip: skipped.append(path); continue  # memorize to skip all folders with this prefix TODO is this always ordered correctly (breadth first)?
      if xany(lambda skp: path.startswith(skp) if skp != '' else (path == ''), skipped): continue  # is in skipped folder tree
      dcount += 1
      try:
        if len(files) > 0: printo("\n".join(idx.root + path + SLASH + file for file in files)); counter += len(files)  # incremental output
      except KeyboardInterrupt: pass
    if _.options.log >= 1: info("%d files found in %d checked paths for +<%s> -<%s>." % (counter, dcount, ",".join(poss), ".".join(negs)))  # TODO dcount reflect mapped as well?

  def config(_, unset = False, get = False):
    ''' Define, retrieve or remove a global configuration parameter. '''
    value = ((_.options.setconfig if not get else _.options.getconfig) if not unset else _.options.unsetconfig)
    if value is None: warn("Missing global configuration key argument"); return
    if not unset and not get and "=" not in value: warn("Global configuration entry must be specified in the form key=value"); return
    key, value = value.split("=")[:2] if not unset and not get else (value, None)  # assume safe split
    key = key.lower()  # config keys are normalized to lower case
    folder = getRoot(_.options, _.args)
    indexPath = folder if not _.options.index else _.options.index
#    root = pathnorm(os.path.abspath(folder))
    if _.options.log >= 1: info("Using configuration from %s" % indexPath)
    cfg = Config(_.options.log)
    cfg.load(os.path.join(indexPath, CONFIG))
    if get:
      if key in cfg.__dict__: info("Get global configuration entry: %s = %s" % (key, cfg.__dict__[key])); return
      else: info("Global configuration entry '%s' not found" % key); return
    if '' not in cfg.paths: cfg.paths[''] = dd()
    entries = dictget(cfg.paths[''], GLOBAL, [])
    index = wrapExc(lambda: lindex([kv.split("=")[0].lower() for kv in entries], key))  # find index for specified key, or return None (by wrap mechanics)
    if not unset:  # must be set
      if index is not None: entries[index] = "%s=%s" % (key, value); info("Modified global configuration entry")
      else: entries.append("%s=%s" % (key, value)); info("Added global configuration entry")
      cfg.__dict__[key] = value if value.lower() not in ("true", "false") else value.lower() == "true"
    else:  # unset
      if index is not None: del entries[index]; info("Removed global configuration entry")
      else: info("Configuration entry not found, nothing to do")  # Not contained - nothing to do
      try: del cfg.__dict__[key]
      except: pass
    if not _.options.simulate: cfg.store(os.path.join(indexPath, CONFIG))

  def add(_):
    ''' Add one or more (inclusive adn/or exclusive) tag(s) to the appended file and glob argument(s).
        We don't detect glob specifications that are subsets of or contradict existing tag globs.
        But we can detect files as subsets of existing globs, and vice versa, to issue warnings (inc/exc).
    '''
    folder = getRoot(_.options, _.args)
    index = folder if not _.options.index else _.options.index
    root = pathnorm(os.path.abspath(folder))
    if _.options.log >= 1: info("Using configuration from %s" % index)
    cfg = Config(_.options.log)  # need to load config early for case_sensitive flag
    cfg.load(os.path.join(index, CONFIG))

    filez = _.args  # process function arguments
    tags = safeSplit(_.options.tag)
    poss, negs = splitCrit(tags, lambda e: e[0] != '-')
    poss, negs = removeTagPrefixes(poss, negs)
#    normalizer.setupCasematching(cfg.case_sensitive)  # TODO OK to use normalization in adding?
    poss, negs = map(lambda l: lmap(normalizer.filenorm, l), (poss, negs))
    if (len(poss) + len(negs)) == 0: error("No tag(s) given to assign for %s" % ", ".join(file)); return
    if xany(lambda p: p in negs, poss): error("Won't allow same tag in both inclusive and exclusiv file assignment: %s" % ', '.join(["'%s'" % p for p in poss if p in negs])); return

    modified = False
    for file in filez:
      repoRelative = file.startswith("/")
      while file.startswith("/"): file = file[1:]  # prune repo-relative marker(s)
      if not (os.path.exists(os.path.join(folder, file) if repoRelative else file) or fnmatch.filter(listdir(folder if repoRelative else os.getcwd()), file)):
        warn("File or glob not found%s %s%s" % (", skipping" if _.options.strict else ", but added anyway", "/" if repoRelative else "./", file))
        if _.options.strict: continue
      parent, file = os.path.split(file)
      parent = pathnorm(os.path.abspath(os.path.join(_.options.root, parent)))  # check if this is a relative path
      if not isunderroot(root, parent):  # if outside folder tree
        warn("Relative file path '%s' outside indexed folder tree '%s'; skipping %s" % (parent, root, file)); continue
      if cfg.addTag(parent[len(root):], file, poss, negs, not _.options.strict): modified = True
    if modified and not _.options.simulate: cfg.store(os.path.join(index, CONFIG))

  def remove(_):
    ''' Remove previously defined file or glob taggings. '''
    folder = getRoot(_.options, _.args)
    index = folder if not _.options.index else _.options.index
    root = pathnorm(os.path.abspath(folder))
    if _.options.log >= 1: info("Using configuration from %s" % index)
    cfg = Config(_.options.log)  # need to load config early for case_sensitive flag
    cfg.load(os.path.join(index, CONFIG))

    filez = _.args  # process function arguments
    tags = safeSplit(_.options.untag)
    poss, negs = splitCrit(tags, lambda e: e[0] != '-')
    poss, negs = removeTagPrefixes(poss, negs)
#    normalizer.setupCasematching(cfg.case_sensitive)
    poss, negs = map(lambda l: lmap(normalizer.filenorm, l), (poss, negs))  # TODO as in adding, OK to use?
    if (len(poss) + len(negs)) == 0: error("No tag(s) given to remove for %s" % ", ".join(file)); return

    modified = False
    for file in filez:
      repoRelative = file.startswith("/")  # TODO not used in code below!
      while file.startswith("/"): file = file[1:]  # prune repo-relative marker(s)
      parent, file = os.path.split(file)
      parent = pathnorm(os.path.abspath(os.path.join(_.options.root, parent)))  # check if this is a relative path
      if not isunderroot(root, parent):  # if outside folder tree
        warn("Relative file path outside indexed folder tree; skipping %s" % file); continue
      if not isglob(file) and not os.path.exists(os.path.join(parent, file)):
          warn("Attempting to untag missing file '%s'%s" % (file, ", skipping" if _.options.strict else ", removing anyway"))
          if _.options.strict: continue
      if cfg.delTag(parent[len(root):], file, poss, negs): modified = True
    if modified and not _.options.simulate: cfg.store(os.path.join(index, CONFIG))

  def stats(_):
    folder = getRoot(_.options, _.args)
    index = folder if not _.options.index else _.options.index
    root = pathnorm(os.path.abspath(folder))
    if _.options.log >= 1: info("Using configuration from %s" % index)
    indexFile = os.path.join(index, INDEX)
    if not os.path.exists(indexFile):
      error("No index file found. Cannot show stats")
      return
    idx = Indexer(index); idx.log = _.options.log  # initiate indexer
    idx.load(indexFile)
    info("Indexer stats")
    info("  Compression level:", idx.compressed)
    info("  Timestamp:", idx.timestamp)
    info("  Root folder:", idx.root)
    info("  Tags:", len(idx.tagdirs))
    if idx.log >= 1:
      info("Tags and folders (occurrence = same name for different folder name references")
      byOccurrence = dd()
      for i, t in enumerate(frozenset(idx.tagdirs)):  # TODO why "a" double (1 and 45?)
        byOccurrence[idx.tagdirs.count(t)].append(i)  # map number of tag occurrences in index to their tagdir indices
      _cache = {}
      for n, ts in sorted(byOccurrence.items()):  # TODO move above two lines into one dict comprehension
        info("  %d occurences for entries %s" % (n, str(sorted(ts))))
        if idx.log >= 2:  # TODO root element mapped to some paths, should not be! TODO all tags mapped to same folder
          byMapping = dd()
          for _t in ts: byMapping[idx.tagdirs[_t]].extend(idx.tagdir2paths[_t])  # aggregate all mappings
          for _t in sorted(byMapping.keys(), caseCompare):
            debug("    Entries %s (%s) map to: " % ("'" + _t + "'" if _t != '' else "/", ",".join([str(i) for i, x in enumerate(idx.tagdirs) if x == _t])) + ", ".join(["%s (%d)" % (idx.getPath(_i, _cache), _i) for _i in byMapping[_t]]))
    info("Configuration stats")
    info("  Number of tags:", len(idx.cfg.paths))
    debug([len(_) for _ in dictviewvalues(idx.cfg.paths)])
    info("  Average number of entries per folder: %.2f" % (float(sum([len(_) for _ in dictviewvalues(idx.cfg.paths)])) / len(idx.cfg.paths)))
    # TODO show config file timestamp


  def parse(_):
    ''' Main logic that analyses the command line arguments and starts an opteration. '''
    ts = time.time()
    op = CatchExclusionsParser()  # https://docs.python.org/3/library/optparse.html#optparse-option-callbacks
    op.add_option('-I', '--init',        action = "store_true",  dest = "init",       default = False, help = "Create empty index (repository root)")
    op.add_option('-u', '--update',      action = "store_true",  dest = "update",     default = False, help = "Update index, crawling files in folder tree")
    op.add_option('-s', '--search',      action = "append",      dest = "find",       default = [], help = "Find files by tags (default action if no option given)")
    op.add_option('-t', '--tag',         action = "store",       dest = "tag", help = "Set tag(s) for given file(s) or glob(s): tp.py -t tag,tag2,-tag3... file,glob...")
    op.add_option('-T', '--untag',       action = "store",       dest = "untag", help = "Unset tag(s) for given file(s) or glob(s): tp.py -d tag,tag2,-tag3... file,glob...")
    op.add_option('-r', '--root',        action = "store",       dest = "root", type = str, default = None, help = "Specify root folder for index (and configuration)")
    op.add_option('-i', '--index',       action = "store",       dest = "index", type = str, default = None, help = "Specify alternative index folder (other than root)")
    op.add_option('-l', '--log',         action = "store",       dest = "log", type = int, default = 0, help = "Set log level (0=none, 1=debug, 2=trace)")
    op.add_option('-x', '--exclude',     action = "append",      dest = "excludes",    default = [], help = "Tags to ignore. Same as --no, or -<tag>")
    op.add_option('-N', '--no',          action = "append",      dest = "excludes",    default = [], help = "Tags to ignore. Same as --exclude, or -<tag>")  # same as above
    op.add_option('-C', '--ignore-case', action = "store_true",  dest = "ignore_case", default = False, help = "Always search case-insensitive (overrides option in index)")
    op.add_option('--get',               action = "store",       dest = "getconfig",   default = None,  help = "Get global configuration parameter")
    op.add_option('--set',               action = "store",       dest = "setconfig",   default = None,  help = "Set global configuration parameter key=value")
    op.add_option('--unset',             action = "store",       dest = "unsetconfig", default = None,  help = "Unset global configuration parameter")
    op.add_option('--clear',             action = "store",       dest = "unsetconfig", default = None,  help = "Clear global configuration parameter. Same as --unset")  # TODO or let clear remove all presets?
    op.add_option('-R', '--relaxed',     action = "store_false", dest = "strict",      default = True,  help = "Relax safety measures")  # mapped to inverse "strict" flag
    op.add_option('-n', '--simulate',    action = "store_true",  dest = "simulate",    default = False, help = "Don't write anything")  # TODO confirm nothing modified on FS
    op.add_option('--dirs',              action = "store_true",  dest = "onlyfolders", default = False, help = "Only find directories that contain matches")
    op.add_option('-v',                  action = "store_true",  dest = "verbose",     default = False, help = "Same as -l1. Also displays unit test details")
    op.add_option('--stats',             action = "store_true",  dest = "stats",       default = False, help = "List index internals (combine with -l1, -l2)")
    op.add_option('--simulate-winfs',    action = "store_true",  dest = "winfs",       default = True,  help = "Simulate case-insensitive file system")  # but option checked outside parser
    _.options, _.args = op.parse_args()
    if _.options.log >= 2: debug("Raw options: " + str(_.options))
    if _.options.log >= 2: debug("Raw arguments: " + str(_.args))
    _.args, excludes = splitCrit(_.args, lambda e: e[:2] != '--')  # remove "--" from "--mark", allows to use --mark to exclude this tag (unless it's an option switch)
    _.options.excludes.extend([e[2:] for e in excludes])  # additional non-option flags are interpreted as further exclusive tags
    _.options.log = max(1 if _.options.verbose else 0, _.options.log)
    if _.options.index is not None and _.options.root is None: error("Index location specified (-i) without specifying root (-r)"); sys.exit(1)
    if _.options.log >= 1: info("Started at %s" % (time.strftime("%H:%M:%S")))
    if _.options.log >= 1: debug("Running in debug mode.")
    if _.options.log >= 2: debug("Updated options: " + str(_.options))
    if _.options.log >= 2: debug("Updated arguments: " + str(_.args))
    if _.options.init: _.initIndex()
    elif _.options.update: _.updateIndex()
    elif _.options.tag: _.add()
    elif _.options.untag: _.remove()
    elif _.options.setconfig: _.config()
    elif _.options.getconfig: _.config(get = True)
    elif _.options.unsetconfig: _.config(unset = True)
    elif _.options.stats: _.stats()
    elif len(_.args) > 0 or _.options.find or _.options.excludes: _.find()  # default action is always find
    else: error("No option given. Use '--help' to list all options.")
    if _.options.log >= 1: info("Finished at %s after %.1fs" % (time.strftime("%H:%M:%S"), time.time() - ts))


if __name__ == '__main__':
  Main().parse()
