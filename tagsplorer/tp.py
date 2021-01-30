''' tagsPlorer command-line interface  (C) 2016-2021  Arne Bachmann  https://github.com/ArneBachmann/tagsplorer '''

import logging, optparse, os, sys, time
assert sys.version_info >= (3, 6), "tagsPlorer requires Python 3.6+"

from tagsplorer.constants import ALL, COMB, CONFIG, DOT, GLOBAL, INDEX, SLASH, ST_MTIME
from tagsplorer.lib import Configuration, Indexer
from tagsplorer.utils import caseCompareKey, casefilter, dd, dictGetSet, isGlob, isUnderRoot, lindex, normalizer, pathNorm, removeTagPrefixes, safeSplit, safeRSplit, sjoin, splitByPredicate, splitTags, wrapExc, xany
with open(os.path.join(os.path.dirname(__file__), 'VERSION'), encoding = 'utf-8') as fd: VERSION = fd.read()
from tagsplorer import lib, simfs, utils  # for setting the log level dynamically

logging.basicConfig(
  level =  logging.DEBUG if '-V' in sys.argv or '--debug'   in sys.argv or os.environ.get("DEBUG",   "False").lower() == "true" else
          (logging.INFO  if '-v' in sys.argv or '--verbose' in sys.argv or os.environ.get("VERBOSE", "False").lower() == "true" else
           logging.WARNING),  # must be set here to already limit writing to info and debug (e.g. "Started at...")
  stream = sys.stdout if '--stdout' in sys.argv else sys.stderr,  # log to stderr, write results to stdout
  format =  '%(asctime)-8s.%(msecs)03d %(levelname)-4s %(module)s:%(funcName)s:%(lineno)d | %(message)s',
  datefmt = '%H:%M:%S')
_log = logging.getLogger(__name__)
def log(func): return (lambda *s: func(sjoin([_() if callable(_) else _ for _ in s]), **({"stacklevel": 2} if sys.version_info >= (3, 8) else {})))
debug, info, warn, error = log(_log.debug), log(_log.info), log(_log.warning), log(_log.error)

RIGHTS  = 0o755  # for creating new folders
APPNAME = "tagsPlorer"  # or something clunky like "virtdirview"
APPSTR  = APPNAME + " version %s  (C) 2016-2021  Arne Bachmann" % VERSION


def findRootFolder(filename, start = None):
  ''' Utility function that tries to auto-detect a filename in any parent folder.
      filename: file to find
      returns: existing file path or None if not found
  >>> findRootFolder(os.path.basename(os.path.abspath(__file__)), start = os.path.join(os.path.abspath(__file__), 'a', 'b')) == os.path.abspath(__file__)
  True
  '''
  path = start if start else os.path.abspath(os.getcwd())
  try:
    while not os.path.exists(os.path.join(path, filename)):
      new = os.path.dirname(path)
      if new == path: return None  # avoid infinite loop when hitting root
      path = new
    return os.path.join(path, filename)
  except Exception as E: error(E)


def getRoot(options, args):
  ''' Determine tagsPlorer repository root folder by checking program arguments with some fall-back logic.
      returns 2-tuple(root folder absolute path, index file folder absolute path), depending on options
  >>> class O:
  ...   def __init__(_): _.index = _.root = None  # options object
  >>> os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "_test-data"))  # change into folder that contains .tagsplorer.cfg
  >>> o = O(); rela = lambda a, b: (os.path.relpath(a, start = os.getcwd()), os.path.relpath(b, start = os.getcwd()))  # helper to pass with any current folder
  >>> rela(*getRoot(o, []))  # no options nor arguments: root folder == index folder
  ('.', '.')
  >>> o.root = "./x"; rela(*getRoot(o, []))  # given a root: root = index
  ('x', 'x')
  >>> o.index = "./y"; rela(*getRoot(o, []))  # given both
  ('x', 'y')
  >>> o.root = None; o.index = "/abc"; rela(*getRoot(o, []))
  Traceback (most recent call last):
  ...
  Exception: Cannot omit root folder and specify index file folder
  '''
  if options.index:
    if options.root is None: raise Exception("Cannot omit root folder and specify index file folder")
    return (os.path.abspath(options.root), os.path.abspath(options.index))  # the options "-i" and "-r" always go together
  folder = options.root
  if folder is None:
    folder = findRootFolder(CONFIG)
    if folder: folder = os.path.relpath(os.path.dirname(folder))
  if folder is None: folder = os.curdir  # fallback to '.'
  root, index = os.path.abspath(folder), os.path.abspath(options.index if options.index else folder)
  debug(f"Root and index folders found at {root} {index}")
  return root, index


class CatchExclusionsParser(optparse.OptionParser):
  ''' Allows to process undefined options as non-option arguments (e.g. --tag as an additional exclusive tag marked via --). '''
  def __init__(_):
    ihf = optparse.IndentedHelpFormatter(2, 60, 120)  # , formatter = optparse.TitledHelpFormatter(),
    optparse.OptionParser.__init__(_, prog = APPNAME, usage = "python tp <tags and options>", description = APPSTR, version = VERSION, formatter = ihf)

  def _process_args(_, largs, rargs, values):
    while rargs:
      try: optparse.OptionParser._process_args(_, largs, rargs, values)
      except (optparse.BadOptionError, optparse.AmbiguousOptionError) as E: largs.append(E.opt_str)


class Main:
  ''' This is the main business logic, operated by the command-line commands. '''

  def initIndex(_):
    ''' Set up and store an empty index, thus marking the repository root folder. '''
    if not _.options.root: _.options.root = os.getcwd()
    folder, index = getRoot(_.options, _.args)
    cfg = Configuration()
    if _.options.strict and os.path.exists(os.path.join(index, CONFIG)):
      error("Index already exists. Use --force or -f to override")
      return
    info("Create root configuration at '%s'" % index)
    if not _.options.simulate:
      try: os.makedirs(index, mode = RIGHTS, exist_ok = True)
      except OSError as E: debug("Cannot create folder. %r" % E)
      if not os.path.exists(index): error("Could not create index for that folder. Check access rights and path errors"); return
      cfg.store(os.path.join(index, CONFIG))

  def updateIndex(_):
    ''' Crawl the folder tree and (re)create the index file.
        _.options: options structure from optparse, set in parse
        _.args:    arguments list from optparse, set in parse
        returns: created Index
    '''
    folder, index = getRoot(_.options, _.args)
    cfg = Configuration()
    cfg.load(os.path.join(index, CONFIG))
    idx = Indexer(folder)  # no need to load the old index
    idx.walk(cfg)  # track all files using the configuration settings
    if not _.options.simulate: idx.store(os.path.join(index, INDEX), idx.timestamp)
    return idx

  def find(_):
    ''' Find and display all folders that match the provided tags in _.options.includes while excluding those from _.options.excludes.
        returns: exit code
    '''
    poss, negs = splitByPredicate(splitTags(_.args), lambda e: e[0] != '-')  # allows direct arguments, potentially suffixed by +/-
    poss.extend(splitTags(_.options.includes))
    negs.extend(splitTags(_.options.excludes))
    poss, negs = removeTagPrefixes(poss, negs)

    folder, index = getRoot(_.options, _.args)
    indexFile = os.path.join(index, INDEX)
    if not os.path.exists(indexFile):  # e.g. first run after root initialization
      error("No index file found. %s" % ("Exit" if _.options.keep_index else "Crawl folder tree"))
      if _.options.keep_index: return 2
      idx = _.updateIndex()  # crawl folder tree immediately and return search index TODO also update if outdated
    else:
      idx = Indexer(index)
      idx.load(indexFile, ignore_skew = _.options.keep_index)  # load search index from root
    if _.options.ignore_case or not idx.cfg.case_sensitive:  # TODO this changes the settings only for search?
      normalizer.setupCasematching(False)  # case option defaults to true, but can be overriden by --ignore-case TODO does this work if index was created with a different option?
    poss, negs = map(lambda l: list(map(normalizer.filenorm, l)), (poss, negs))  # convert search terms to normalized case, if necessary
    debug("Effective search filters +<%s> -<%s>"        % (COMB.join(poss), COMB.join(negs)))
    _exts = [ext for ext in poss + negs if ext and ext[0] == DOT]
    if len(_exts) > 1:
      error("Cannot match anything if more than one file extension is specified (%s)" % COMB.join(_exts)); return 1

    info(f"Search '{idx.root}' for tags +<%s> -<%s>" % (COMB.join(poss), COMB.join(negs)))
    paths = idx.findFolders(poss, negs)
    debug(f"Found {len(paths)} potential path matches")
    #[debug(path) for path in paths]  # optimistic: all folders "seem" to match given tags, but only some might actually do (e.g. due to excludes)

    if not len(paths) and xany(lambda x: isGlob(x) or DOT in x, poss + negs):  # glob or extension
      paths = idx.findFolders([], [], True)  # return all folders names unfiltered (except ignore/skip without marker files)
    if _.options.onlyfolders:
      for p in poss: paths[:] = [x for x in paths if not isGlob(p) or     normalizer.globmatch(safeRSplit(x), p)]  # successively reduce paths down to matching positive tags: in --dirs mode tags currently have to be folder names TODO later we should reflect actual mapping
      for n in negs: paths[:] = [x for x in paths if not isGlob(n) or not normalizer.globmatch(safeRSplit(x), n)]  # TODO is this too strict and ignores configured tags and the index entirely? TODO also handle tokenization here
      info(f"Found {len(paths)} folders for +<%s> -<%s>" % (COMB.join(poss), COMB.join(negs)))
      #paths[:] = removeCasePaths(folder, paths)  # remove case doubles TODO this should already been done inside findFolders?
      try:
        if len(paths): print("\n".join((idx.root if not _.options.relative else '') + path for path in paths))
      except KeyboardInterrupt: pass  #idx.root + path + SLASH + file for file in files)); counter += len(files)  # incremental output
      return 0  # no file filtering requested

    dcount, counter, skipped = 0, 0, []  # if showing also files
    for path, fskip in ((p, idx.findFiles(p, poss, negs)) for p in paths):
      files, skip = fskip  # deconstruct 2-tuple
      if skip: skipped.append(path); continue  # memorize to skip all folders with this prefix TODO is this always ordered correctly? (breadth first traversal)
      if xany(lambda skp: path.startswith(skp) if skp != '' else (path == ''), skipped): continue  # is in skipped folder tree
      dcount += 1
      try:
        if len(files) > 0: print("\n".join((idx.root if not _.options.relative else '') + path + SLASH + file for file in files)); counter += len(files)  # incremental output
      except KeyboardInterrupt: pass
    info(f"Found {counter} files in {dcount} folders for +<%s> -<%s>" % (COMB.join(poss), COMB.join(negs)))  # TODO dcount reflect mapped as well?
    return 0

  def config(_, unset = False, get = False):
    ''' Define, display or remove a global configuration parameter. '''
    value = ((_.options.setconfig if not get else _.options.getconfig) if not unset else _.options.unsetconfig)
    if value is None: warn("No configuration key provided"); return 1
    if not unset and not get and "=" not in value: warn("Configuration entry must be specified in the form key=value"); return 2
    key, value = safeSplit(value, "=")[:2] if not unset and not get else (value, None)
    key = key.lower()  # config keys are normalized to lower case
    folder, indexPath = getRoot(_.options, _.args)
    cfg = Configuration()
    cfg.load(os.path.join(indexPath, CONFIG))
    if get:  # get operation
      if key in cfg.__dict__: warn(f"Configuration entry: {key} = {cfg.__dict__[key]}"); return 0
      else: warn("Configuration key '%s' not found" % key); return 3
    if '' not in cfg.paths: cfg.paths[''] = dd()  # create global section
    entries = dictGetSet(cfg.paths[''], GLOBAL, [])
    index = wrapExc(lambda: lindex([kv.split("=")[0].lower() for kv in entries], key))  # find index for specified key, or None
    if not unset:  # set operation
      if index is not None: entries[index] = f"{key}={value}"; warn(f"Updated configuration entry: {key} = {value}")
      else: entries.append(f"{key}={value}"); warn(f"Added configuration entry: {key} = {value}")
      cfg.__dict__[key] = value if value.lower() not in ("true", "false") else value.lower() == "true"
    else:  # unset operation
      if index is not None: del entries[index]; warn("Removed configuration entry for key '%s'" % key)
      else: warn("Configuration entry not found, nothing to do")
      try: del cfg.__dict__[key]  # remove in-memory global configuration
      except: pass
    if not _.options.simulate: cfg.store(os.path.join(indexPath, CONFIG))
    return 0

  def assign(_):
    ''' Add one or more tags for the given (inclusive and/or exclusive) globs.
        TODO detect if all existing patterns are mutually exclusive or always covered by other globs
    '''
    folder, index = getRoot(_.options, _.args)
    root = pathNorm(folder)
    cfg = Configuration()
    cfg.load(os.path.join(index, CONFIG))

    tags = safeSplit(_.options.tag)  # from -t option
    poss, negs = splitByPredicate(tags, lambda e: e[0] != '-')  # TODO only additive tags allowed (index is over-specified and removing is hard?)
    poss, negs = removeTagPrefixes(poss, negs)
    if (len(poss) + len(negs)) == 0: error("No tag(s) provided to assign for " + COMB.join(_.args)); return 1
    if xany(lambda p: p in negs, poss): error("Same tag in both inclusive and exclusive pattern " + ', '.join(["'%s'" % p for p in poss if p in negs])); return 2

    args = [pathNorm(arg) for arg in _.args]
    modified = False
    for pathpatterns in args:
      path, patterns = (pathpatterns[:pathpatterns.rindex(SLASH)], pathpatterns[pathpatterns.rindex(SLASH) + 1:]) if SLASH in pathpatterns else (os.getcwd(), pathpatterns)
      inc, exc = splitByPredicate(patterns.split(COMB), lambda e: e[0] != '-')
      inc, exc = removeTagPrefixes(inc, exc)
      path = pathNorm(os.path.abspath(os.path.normpath(path)))
      if not isUnderRoot(root, path):
        error(f"Specified pattern path '{path}' is outside indexed folder tree '{root}'; skip '{pathpatterns}'"); continue
      if not os.path.exists(path):
        error(f"Specified pattern path '{path}' does not exist; skip '{pathpatterns}'"); continue
      path = path[len(root):]  # make repo-relative
      for p in (poss + negs):
        if p in safeSplit(path, SLASH):  # tag should not be part of any path constituents
          error(f"Specified tag <{p}> must not match any path constituents of '{path}'"); continue  # TODO unless folder is ignored
      assert path[0] == SLASH
      files = os.listdir(root + path)  # check current state on file system
      _i, _e = [], []
      for ps, l, t in zip((inc, exc), (_i, _e), ("Inclusive", "Exclusive")):  # performs sanity checks on inclusive and exclusive patterns
        for p in ps:
          exists = False
          if   p == '': error(f"{t} tag pattern for '{path}' cannot be empty, skip"); continue
          if p[0] == DOT: exists = len(casefilter(files, p)) > 0
          elif  p == ALL: exists = len(files) > 0
          elif isGlob(p): exists = len(casefilter(files, p)) > 0
          else:           exists = p in files
          if not exists:
            warn(f"No file matches for glob '{path}/{p}'%s'" % (", skip" if _.options.strict else ", add anyway"))
            if _.options.strict: continue
          l.append(p)
      if len(_i + _e):
        for tag in poss: modified = cfg.addTag(path, tag, _i, _e, not _.options.strict) or modified  # TODO also add negs, if semantics clear
    if not modified: error("Nothing was added")
    if modified and not _.options.simulate: cfg.store(os.path.join(index, CONFIG))
    return 0

  def remove(_):
    ''' Remove one or more tags for the given (inclusive and/or exclusive) globs. '''
    folder, index = getRoot(_.options, _.args)
    root = pathNorm(folder)
    cfg = Configuration()
    cfg.load(os.path.join(index, CONFIG))

    tags = safeSplit(_.options.untag)  # from -u option
    poss, negs = splitByPredicate(tags, lambda e: e[0] != '-')
    poss, negs = removeTagPrefixes(poss, negs)
    if (len(poss) + len(negs)) == 0: error("No tag(s) provided to remove for %s" % COMB.join(_.args)); return 1
    if xany(lambda p: p in negs, poss): error("Same tag in both inclusive and exclusive pattern " + ', '.join(["'%s'" % p for p in poss if p in negs])); return 2

    args = [pathNorm(arg) for arg in _.args]
    modified = False
    for pathpatterns in args:
      path, patterns = (pathpatterns[:pathpatterns.rindex(SLASH)], pathpatterns[pathpatterns.rindex(SLASH) + 1:]) if SLASH in pathpatterns else (os.getcwd(), pathpatterns)
      inc, exc = splitByPredicate(patterns.split(COMB), lambda e: e[0] != '-')
      inc, exc = removeTagPrefixes(inc, exc)
      path = pathNorm(os.path.abspath(os.path.normpath(path)))
      if not isUnderRoot(root, path):
        error(f"Specified pattern path '{path}' is outside indexed folder tree '{root}'; skip '{pathpatterns}'"); continue
      path = path[len(root):]  # make repo-relative
      assert path[0] == SLASH
      files = os.listdir(root + path)  # check current state on file system
      _i, _e = [], []
      for ps, l, t in zip((inc, exc), (_i, _e), ("Inclusive", "Exclusive")):  # performs sanity checks on inclusive and exclusive patterns
        for p in ps:
          exists = False
          if   p == '': error(f"{t} tag pattern for '{path}' cannot be empty, skip"); continue
          if p[0] == DOT: exists = len(casefilter(files, p)) > 0
          elif  p == ALL: exists = len(files) > 0
          elif isGlob(p): exists = len(casefilter(files, p)) > 0
          else:           exists = p in files
          if not exists:
            warn(f"No file matches for glob '{path}/{p}'%s'" % (", skip" if _.options.strict else ", remove anyway"))
            if _.options.strict: continue
          l.append(p)

      if len(_i + _e):
        for tag in poss: modified = cfg.delTag(path, tag, _i, _e) or modified
    if not modified: error("Nothing was removed")
    if modified and not _.options.simulate: cfg.store(os.path.join(index, CONFIG))
    return 0

  def show(_):
    folder, index = getRoot(_.options, _.args)
    root = pathNorm(folder)
    cfg = Configuration()  # load config early for the case_sensitive flag
    cfg.load(os.path.join(index, CONFIG))

    for folder in ([os.getcwd()] if not _.args else _.args):
      folder = pathNorm(os.path.abspath(folder))
      folder = folder.strip(SLASH + os.sep)
      if not isUnderRoot(root, folder):  # outside folder tree
        warn(f"Relative path '{folder}' is outside indexed folder tree '{root}'; skip"); continue
      cfg.showTags(folder[len(root):])


  def stats(_):
    ''' Show index stats, optionally including very detailed information.
        returns: exit code
    '''
    folder, index = getRoot(_.options, _.args)
    indexFile = os.path.join(index, INDEX)
    if not os.path.exists(indexFile):
      error("No index file found. %s" % ("Exit" if _.options.keep_index else "Crawl folder tree"))
      if _.options.keep_index: return 2
      idx = _.updateIndex()  # crawl folder tree immediately and return search index
    else:
      idx = Indexer(index)
      idx.load(indexFile, ignore_skew = _.options.keep_index)
    _.options.relative = True  # don't output full paths here
    warn("Configuration stats:")
    warn("  Number of configured paths: %d" % len(idx.cfg.paths))
    warn("  Average number of markers per folder: %.2f" % ((sum([len(_) for _ in idx.cfg.paths.values()]) / len(idx.cfg.paths)) if idx.cfg.paths else 0.))  # e.g. skip, ignore, manual tags
    warn("  Average number of entries per folder: %.2f" % ((sum([sum([len(__) for __ in _.values()]) for _ in idx.cfg.paths.values()]) / len(idx.cfg.paths)) if idx.cfg.paths else 0.))  # e.g. skip
    warn("  Last update: " + time.strftime("%Y-%m-%d@%H:%M", time.localtime(os.stat(index)[ST_MTIME])))
    warn("Index stats:")
    warn("  Root folder:", idx.root)
    warn("  Timestamp:", time.strftime("%Y-%m-%d@%H:%M", time.localtime(idx.timestamp / 1000.)))
    warn("  Timestamp (ms epoch):", idx.timestamp)
    warn("  Compression level:",    idx.compression)
    warn("  Number of tags:",   len(idx.tagdirs))
    info("Tags and folders:")  # (occurrence = same name for different folder name references")
    if not _.options.verbose and not _.options.debug_on: return 0
    byOccurrence = dd()
    for i, t in enumerate(frozenset(idx.tagdirs)):
      byOccurrence[idx.tagdirs.count(t)].append(i)  # map number of tag occurrences in index to their tagdir indices
    _cache = {}
    for n, ts in sorted(byOccurrence.items()):
      info(f"  {n} occurence%s for entries %s" % ("s" if n > 1 else "", COMB.join([str(_) for _ in sorted(ts)])))
      if not _.options.debug_on: return 0
      byMapping = dd()
      for t in ts: byMapping[idx.tagdirs[t]].extend(idx.tagdir2paths[t])  # aggregate all mappings
      for t in sorted(byMapping.keys(), key = caseCompareKey):
        debug(f"    Entry '{t}' (%s) maps to: %s" % (COMB.join([str(i) for i, x in enumerate(idx.tagdirs) if x == t]), ', '.join(["%s (%d)" % (idx.getPath(_i, _cache), _i) for _i in byMapping[t]])))
    return 0

  def parse_and_run(_):
    ''' Main logic that analyses the command line arguments and starts an operation. '''
    ts = time.time()
    info("Started at %s" % (time.strftime("%H:%M:%S", time.localtime(ts))))
    op = CatchExclusionsParser()  # https://docs.python.org/3/library/optparse.html#optparse-option-callbacks HINT options default to None!
    op.add_option('-I', '--init',           action = "store_true",  dest = "init",        default = False,             help = "Create empty index (repository root)")
    op.add_option('-r', '--root',           action = "store",       dest = "root",        default = None,  type = str, help = "Specify root folder for index (and configuration), default: current folder")
    op.add_option('-i', '--index',          action = "store",       dest = "index",       default = None,  type = str, help = "Specify alternative index folder (if separate from root)")
    op.add_option('-U', '--update',         action = "store_true",  dest = "update",      default = False,             help = "Force-update the index, crawl files in folder tree")
    op.add_option('-s', '--search',         action = "append",      dest = "includes",    default = [],                help = "Find files by tags (default action if no option specified)")
    op.add_option('-x', '--exclude',        action = "append",      dest = "excludes",    default = [],                help = "Tags to ignore. Same as -<tag>")
    op.add_option('-t', '--tag',            action = "store",       dest = "tag",         default = None,  type = str, help = "Set   tag(s) for given file(s) or glob(s): tp -t tag,tag2,-tag3... file,glob...")
    op.add_option('-T', '--untag',          action = "store",       dest = "untag",       default = None,  type = str, help = "Unset tag(s) for given file(s) or glob(s): tp -d tag,tag2,-tag3... file,glob...")
    op.add_option(      '--tags',           action = "store_true",  dest = "show_tags",   default = False,             help = "List defined tags for a folder")
    op.add_option(      '--get',            action = "store",       dest = "getconfig",   default = None,  type = str, help = "Get global configuration parameter")
    op.add_option(      '--set',            action = "store",       dest = "setconfig",   default = None,  type = str, help = "Set global configuration parameter key=value")
    op.add_option(      '--unset',          action = "store",       dest = "unsetconfig", default = None,  type = str, help = "Unset global configuration parameter")  # add '--clear -C' TODO remove/reset all settings
    op.add_option(      '--run',            action = "store_true",  dest = "run",         default = False,             help = "Attempt to run file, if search results in exactly one match")  # TODO implement
    op.add_option('-f', '--force',          action = "store_false", dest = "strict",      default = True,              help = "Force operation, relax safety measures")  # mapped to inverse "strict" flag
    op.add_option('-c', '--ignore-case',    action = "store_true",  dest = "ignore_case", default = False,             help = "Search case-insensitive (overrides option in index)")
    op.add_option('-n', '--simulate',       action = "store_true",  dest = "simulate",    default = False,             help = "Don't write anything")
    op.add_option('-k', '--keep-index',     action = "store_true",  dest = "keep_index",  default = False,             help = "Don't update the index, even if configuration was changed")
    op.add_option(      '--dirs',           action = "store_true",  dest = "onlyfolders", default = False,             help = "Only find folders that contain matches")
    op.add_option('-v', '--verbose',        action = "store_true",  dest = "verbose",     default = False,             help = "Show more information")
    op.add_option('-V', '--debug',          action = "store_true",  dest = "debug_on",    default = False,             help = "Show internal data state")
    op.add_option(      '--stats',          action = "store_true",  dest = "stats",       default = False,             help = "List index internals")
    op.add_option(      '--simulate-winfs', action = "store_true",  dest = "winfs",       default = True,              help = "Simulate case-insensitive file system")  # but option is checked outside parser TODO hide this option?
    op.add_option(      '--relative',       action = "store_true",  dest = "relative",    default = False,             help = "Output files with root-relative paths only")  # instead of absolute file system paths
    _.options, _.args = op.parse_args()  # TODO replace with argparse?
    reserved1, reserved2 = (set(_) for _ in splitByPredicate([_.get_opt_string() for _ in op.option_list], lambda e: e[:2] != '--'))  # handle reserved option switches that must be masked by a dash to operate as an exclude tag
    _.args, excludes = splitByPredicate(_.args,   lambda e: e[:2] != '---')      # split definitive excludes (triple dash)
    _.args, exclude_ = splitByPredicate(_.args,   lambda e: e[:2] != '--')       # split potential  excludes (double dash)
    add2, exclude2 =   splitByPredicate(exclude_, lambda e: e not in reserved2)  # filter out program options with double dash
    add1, exclude1 =   splitByPredicate(exclude2, lambda e: e not in reserved1)  # filter out program options with single dash
    _.options.excludes.extend([_.strip("---") for _ in excludes] + [_.strip("--") for _ in add2] + [_.strip("-") for _ in add1])  # update excludes option
    if _.options.index and not _.options.root: error("Index location specified (-i) without specifying root (-r)"); sys.exit(1)
    logLevel = logging.DEBUG if _.options.debug_on else (logging.INFO if _.options.verbose else logging.WARNING)
    _log.setLevel(logLevel)
    for mod in (lib, simfs, utils): mod._log.setLevel(logLevel)
    debug(f"Options:   {_.options}")
    debug(f"Arguments: {_.args}")
    code = 0  # exit code
    if   _.options.init:        _.initIndex()
    elif _.options.update:      _.updateIndex()
    elif _.options.tag:         code = _.assign()
    elif _.options.untag:       code = _.remove()
    elif _.options.show_tags:          _.show()
    elif _.options.setconfig:   code = _.config()
    elif _.options.getconfig:   code = _.config(get = True)
    elif _.options.unsetconfig: code = _.config(unset = True)
    elif _.options.stats:       code = _.stats()
    elif _.args \
      or _.options.includes \
      or _.options.excludes:    code = _.find()
    else: error("No option specified. Use '--help' to list all options")
    info("Finished at %s after %.1fs" % (time.strftime("%H:%M:%S"), time.time() - ts))
    sys.exit(code)


def main(): Main().parse_and_run()  # Main entry point for console tools (setuptools)


if __name__ == '__main__':
  if '--test' in sys.argv: import doctest; sys.exit(doctest.testmod(optionflags = doctest.ELLIPSIS)[0])
  main()
