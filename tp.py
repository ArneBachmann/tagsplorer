# tagsPlorer command-line application  (C) Arne Bachmann https://github.com/ArneBachmann/tagsplorer
# This is the main entry point of the tagsPlorer utility
# TODO tp: using full path not normalized to root in untag/tag
# TODO allow relative root-absolute paths for add tag (contained in remove tag)


import optparse
from lib import *  # direct namespace import is necessary to enable correct unpickling; also pulls in all other imports
from version import __version_info__, __version__  # used by setup.py

# Version-dependent imports
if sys.version_info.major == 3: from functools import reduce  # not built-in


# Little helper functions
def xany(pred, lizt): return reduce(lambda a, b: a or pred(b), lizt if type(lizt) == list else list(lizt), False)  # short-circuit cross-2/3 implementation
def xall(pred, lizt): return reduce(lambda a, b: a and pred(b), lizt if type(lizt) == list else list(lizt), True)
def withoutFilesAndGlobs(tags): return [t for t in tags if not isglob(t) and DOT not in t[1:]]

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
      if new == path: break  # avoid endless loop
      path = new
    if os.path.exists(os.path.join(path, filename)):
      path = os.path.join(path, filename)
      if options and options.log >= 1: info("Found root configuration %s" % path)
      return path
  except: pass
  return None  # error

def getRoot(options, args):
  ''' Determine root folder by checking arguments and some fall-back logic.
  >>> class O: pass
  >>> import tp
  >>> tmp = tp.findRootFolder; tp.findRootFolder = lambda o, f: "/z/a.b"  # mock away this function
  >>> o = O(); o.index = None; o.root = None
  >>> print(getRoot(o, []))
  /z
  >>> tp.findRootFolder = tmp  # restore function
  >>> o.root = "/x"; print(getRoot(o, []))
  /x
  >>> o.index = "/y"; print(getRoot(o, []))
  /x
  >>> o.root = o.index = None; print(getRoot(o, ["/y"]))
  /y
  >>> o.root = None; o.index = "/abc"; print(getRoot(o, []))  # this combination should never occur
  None
  '''
  if options.index: return options.root  # -i and -r always go together
  folder = options.root if options.root else (args[0] if len(args) > 0 else None)
  if folder is None:
    folder = findRootFolder(options, CONFIG)
    if folder is not None: folder = os.path.dirname(folder)
  if folder is None: folder = os.curdir
  return folder


class CatchExclusionsParser(optparse.OptionParser):
  ''' Allows to process undefined options as non-option arguments. '''
  def __init__(_):
    optparse.OptionParser.__init__(_, prog = "tagsPlorer", usage = "python tp.py <tags or options>", version = "tagsPlorer Release " + __version__)  # , formatter = optparse.TitledHelpFormatter(),
  def _process_args(_, largs, rargs, values):
    while rargs:
      try: optparse.OptionParser._process_args(_, largs, rargs, values)
      except (optparse.BadOptionError, optparse.AmbiguousOptionError) as E: largs.append(E.opt_str)

class Main(object):

  def initIndex(_):
    ''' Set up empty index, defining a root folder. '''
    folder = getRoot(_.options, _.args)
    index = folder if not _.options.index else _.options.index
    cfg = Config(); cfg.log = _.options.log
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
    cfg = Config(); cfg.log = _.options.log
    cfg.load(os.path.join(index, CONFIG))
    if _.options.log >= 1: info("Updating index")
    idx = Indexer(folder); idx.log = _.options.log  # set log level
    idx.walk(cfg)  # index all files
    if not _.options.simulate: idx.store(os.path.join(index, INDEX), idx.timestamp)
    return idx

  def find(_):
    ''' Find all folders that match the provided tags, excluding those from _.options.excludes.
        _.options: options structure from optparse
        poss, negs: lists of tags to include or exlcude. poss can also be aggregated comma-separated tag1,-tag2,... including excludes
        returns: None
        side-effect: print found files to stdout, logging to stderr
    '''
    poss, negs = splitCrit(commaArgsIntoList(_.args), lambda e: e[0] != '-')  # potentially including +/-
    poss.extend(commaArgsIntoList(_.options.find))
    negs.extend(commaArgsIntoList(_.options.excludes))  # each argument could contain , or not
    poss, negs = removeTagPrefixes(poss, negs)
    if len([p for p in poss if p.startswith(DOT)]) > 1: error("Cannot have multiple positive extension filters (would always return empty match)"); return
    folder = getRoot(_.options, _.args)
    index = folder if not _.options.index else _.options.index
    indexFile = os.path.join(index, INDEX)
    if not os.path.exists(indexFile):
      error("No index file found. Crawling file tree")
      idx = _.updateIndex()  # crawl file tree
    else:
      idx = Indexer(index); idx.log = _.options.log  # initiate indexer
      idx.load(indexFile)
    normalizer.setupCasematching(idx.cfg.case_sensitive)
    poss, negs = map(lambda l: lmap(normalizer.filenorm, l), (poss, negs))
    if _.options.log >= 1: info("Effective filters +<%s> -<%s>" % (",".join(poss), ",".join(negs)))
    if _.options.log >= 1: info("Searching for tags +<%s> -<%s> in %s" % (','.join(poss), ','.join(negs), os.path.abspath(idx.root)))
    paths = idx.findFolders(withoutFilesAndGlobs(poss), withoutFilesAndGlobs(negs))
    if _.options.log >= 1: info("Potential matches found in %d folders" % (len(paths)))
    if _.options.log >= 2: [debug(path) for path in paths]  # optimistic: all folders "seem" to match all tags, but only some might actually be (due to excludes etc)
    if len(paths) == 0 and xany(lambda x: isglob(x) or DOT in x, poss + negs):
      if _.options.onlyfolders: warn("Nothing found."); return
      warn("No folder match; cannot filter on folder names. Checking entire folder tree")  # the logic is wrong: we ignore lots of tags while finding folders, and the continue filtering. better first filter on exts or all, then continue??
      paths = idx.findFolders([], [], True)  # return all folders names unfiltered (except ignore/skip without marker files)
    if _.options.onlyfolders:
      info((paths, poss, negs))
      for p in poss: paths[:] = [x for x in paths if not isglob(p) or normalizer.globmatch(safeRSplit(x, SLASH), p)]  # successively reduce paths down to matching positive tags, as in --dirs mode tags currently have to be folder names TODO later we should reflect actual mapping
      for n in negs: paths[:] = [x for x in paths if not isglob(n) or not normalizer.globmatch(safeRSplit(x, SLASH), n)]  # TODO is this too strict and ignores configured tags and the index entirely?
      if _.options.log >= 1: info("Found %d folders for +<%s> -<%s> in index" % (len(paths), ",".join(poss), ".".join(negs)))
      info("%d folders found for +<%s> -<%s>." % (len(paths), ",".join(poss), ".".join(negs)))
      try:
        if len(paths) > 0: printo("\n".join(paths))#idx.root + path + SLASH + file for file in files)); counter += len(files)  # incremental output
      except KeyboardInterrupt: pass  #idx.root + path + SLASH + file for file in files)); counter += len(files)  # incremental output
      return
    dcount, counter, skipped = 0, 0, []  # if not only folders, but also files
    for path, (files, skip) in ((path, idx.findFiles(path, poss, negs, not _.options.strict)) for path in paths):
      if skip: skipped.append(path); continue  # memorize to skip all folders with this prefix TODO is this always ordered correctly (breadth first)?
      if any([path.startswith(skp) if skp != '' else (path == '') for skp in skipped]): continue  # is in skipped folder tree
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
    cfg = Config(); cfg.log = _.options.log
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
    cfg = Config(); cfg.log = _.options.log  # need to load config early for case_sensitive flag
    cfg.load(os.path.join(index, CONFIG))

    filez = _.args  # process function arguments
    tags = safeSplit(_.options.tag)
    poss, negs = splitCrit(tags, lambda e: e[0] != '-')
    poss, negs = removeTagPrefixes(poss, negs)
    normalizer.setupCasematching(cfg.case_sensitive)
    poss, negs = map(lambda l: lmap(normalizer.filenorm, l), (poss, negs))
    if (len(poss) + len(negs)) == 0: error("No tag(s) given to assign for %s" % ", ".join(file)); return
    if xany(lambda p: p in negs, poss): error("Won't allow same tag in both inclusive and exclusiv file assignment: %s" % ', '.join(["'%s'" % p for p in poss if p in negs])); return

    modified = False
    for file in filez:
      repoRelative = file.startswith("/")
      while file.startswith("/"): file = file[1:]  # prune repo-relative marker(s)
      if not (os.path.exists(os.path.join(folder, file) if repoRelative else file) or fnmatch.filter(dircache.listdir(folder if repoRelative else os.getcwd()), file)):
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
    cfg = Config(); cfg.log = _.options.log  # need to load config early for case_sensitive flag
    cfg.load(os.path.join(index, CONFIG))

    filez = _.args  # process function arguments
    tags = safeSplit(_.options.untag)
    poss, negs = splitCrit(tags, lambda e: e[0] != '-')
    poss, negs = removeTagPrefixes(poss, negs)
    normalizer.setupCasematching(cfg.case_sensitive)
    poss, negs = map(lambda l: lmap(normalizer.filenorm, l), (poss, negs))
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
      info("Tags and folders")
      byOccurrence = dd()
      for i, _ in enumerate(idx.tagdirs):
        if i in idx.tagdir2paths: byOccurrence[len(idx.tagdir2paths[i])].append(_)
      for n, t in sorted(byOccurrence.items()):  # TODO move above two lines into one dict comprehension
        info(" ".join(["    %d occurrences for %s " % (n, ", ".join(sorted(t)) if t[0] != '' else "/")]))
    info("Configuration stats")
    info("  Number of tags:", len(idx.cfg.paths))
    info("  Average number of entries per folder: %.2f" % (float(sum([len(_) for _ in idx.cfg.paths.values()])) / len(idx.cfg.paths)))
    # TODO show config file timestamp


  def parse(_):
    ''' Main logic that analyses the command line arguments and starts an opteration. '''
    ts = time.time()  # https://docs.python.org/3/library/optparse.html#optparse-option-callbacks
    op = CatchExclusionsParser()
    op.add_option('--init', action = "store_true", dest = "init", help = "Create empty index (repository root)")
    op.add_option('-u', '--update', action = "store_true", dest = "update", help = "Update index, crawling files in folder tree")
    op.add_option('-s', '--search', action = "append", dest = "find", default = [], help = "Find files by tags (default action if no option given)")
    op.add_option('-t', '--tag', action = "store", dest = "tag", help = "Set tag(s) for given file(s) or glob(s): tp.py -t tag,tag2,-tag3... file,glob...")
    op.add_option('-d', '--untag', action = "store", dest = "untag", help = "Unset tag(s) for given file(s) or glob(s): tp.py -d tag,tag2,-tag3... file,glob...")
    op.add_option('-r', '--root', action = "store", dest = "root", type = str, default = None, help = "Specify root folder for index and configuration")
    op.add_option('-i', '--index', action = "store", dest = "index", type = str, default = None, help = "Specify alternative index location independent of root folder")
    op.add_option('-l', '--log', action = "store", dest = "log", type = int, default = 0, help = "Set log level (0=none, 1=debug, 2=trace)")
    op.add_option('-x', '--exclude', action = "append", dest = "excludes", default = [], help = "Tags to ignore")
    op.add_option('--no', action = "append", dest = "excludes", default = [], help = "Same as --exclude or -tag")  # same as above
    op.add_option('--get', action = "store", dest = "getconfig", default = None, help = "Get global configuration parameter")
    op.add_option('--set', action = "store", dest = "setconfig", default = None, help = "Set global configuration parameter key=value")
    op.add_option('--unset', action = "store", dest = "unsetconfig", default = None, help = "Unset global configuration parameter")
    op.add_option('--relaxed', action = "store_false", dest = "strict", default = True, help = "Relax safety net")
    op.add_option('-n', '--simulate', action = "store_true", dest = "simulate", help = "Don't write anything")
    op.add_option('--dirs', action = "store_true", dest = "onlyfolders", help = "Only find directories that contain matches")
    op.add_option('-v', action = "store_true", dest = "verbose", help = "Switch only for unit test")
    op.add_option('--stats', action = "store_true", dest = "stats", help = "Show internal index data")
    _.options, _.args = op.parse_args()
    if _.options.log >= 2: debug("Options: " + str(_.options))
    if _.options.log >= 2: debug("Arguments: " + str(_.args))
    _.args, excludes = splitCrit(_.args, lambda e: e[:2] != '--')  # remove "--" from "--mark", allows to use --mark to exclude this tag (unless it's an option switch)
    _.options.excludes.extend([e[2:] for e in excludes])
    _.options.log = max(1 if _.options.verbose else 0, _.options.log)
    if _.options.index is not None and _.options.root is None: error("Index location specified (-i) without specifying root (-r)"); return
    if _.options.log >= 1: info("Started at %s" % (time.strftime("%H:%M:%S")))
    debug("Running in debug mode.")
    if _.options.log >= 2: debug("Parsed options: " + str(_.options))
    if _.options.log >= 2: debug("Parsed arguments: " + str(_.args))
    if _.options.init: _.initIndex()
    elif _.options.update: _.updateIndex()
    elif _.options.tag: _.add()
    elif _.options.untag: _.remove()
    elif _.options.setconfig: _.config()
    elif _.options.getconfig: _.config(get = True)
    elif _.options.unsetconfig: _.config(unset = True)
    elif _.options.stats: _.stats()
    elif len(_.args) > 0 or _.options.find or _.options.excludes: _.find()  # default action is always find
    else: error("No option given.")
    if _.options.log >= 1: info("Finished at %s after %.1fs" % (time.strftime("%H:%M:%S"), time.time() - ts))


if __name__ == '__main__':
  Main().parse()
