# Tagging script to augment OS folder structures by tags
# This script is written for easiest command-line access
#
# Globbing on tags not supported by design
# TODO separate timestamp from conf once more - better to exclude from vcs (?) or use modtim?
# TODO simplify find, add from, add map option (?)

VERSION = "2016.Q4"

import optparse
from lib import * # direct namespace import is necessary to enable correct unpickling; also pulls in all other imports

# Version-dependent imports
if sys.version_info.major == 3:
  from functools import reduce # not built-in
  printo = eval("lambda s: print(s)") # perfectly legal use of eval - supporting P2/P3
  printe = eval("lambda s: print(s, file = sys.stderr)")
else:
  printo = eval("lambda s: sys.stdout.write(str(s) + '\\n') and sys.stdout.flush()")
  printe = eval("lambda s: sys.stderr.write(str(s) + '\\n') and sys.stderr.flush()")


# Little helper functions
def any(pred, lizt): return reduce(lambda a, b: a or pred(b), lizt if type(lizt) == list else list(lizt), False) # short-circuit cross-2/3 implementation
def all(pred, lizt): return reduce(lambda a, b: a and pred(b), lizt if type(lizt) == list else list(lizt), True)

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
  return [p if p[0] != '+' else p[1:] for p in poss], [n[1:] if n[0] == '-' else n for n in negs] # remove leading +/-

def findRootFolder(options, filename):
  ''' Utility function that tries to auto-detect the given filename in parent folders.
      options: only for logging option
      filename: file to find
      returns: actual file path or None if not found
  '''
  path = os.getcwd() # start in current folder, check parent until found or stopped
  try:
    while not os.path.exists(os.path.join(path, filename)):
      new = os.path.dirname(path)
      if new == path: break # avoid endless loop
      path = new
    if os.path.exists(os.path.join(path, filename)):
      path = os.path.join(path, filename)
      if options.log >= 1: info("Found root configuration %s" % path)
      return path
  except: pass
  return None # error

def getRoot(options, args):
  ''' Determine root folder by checking arguments and some fall-back logic.
  >>> class O: pass
  >>> def findRootFolder(o, f): return "/z/a.b" # TODO doesn't override def
  >>> o = O()
  >>> o.root = "/x"; print(getRoot(o, []))
  /x

  >>> # o.root = None; print(getRoot(o, []))
  None
  >>> # print(getRoot(o, ["/y"]))
  /y
  '''
  folder = options.root if options.root else (args[0] if len(args) > 0 else None)
  if folder is None:
    folder = findRootFolder(options, CONFIG)
    if folder is not None: folder = os.path.dirname(folder)
  if folder is None: folder = os.curdir
  return folder


class CatchExclusionsParser(optparse.OptionParser):
  def __init__(_):
    optparse.OptionParser.__init__(_,
      prog = "TagsPlorer",
      usage = "python tp.py <tags or options>",
  #    formatter = optparse.TitledHelpFormatter(),
      version = "Tagsplorer Release " + VERSION
    )
  def _process_args(_, largs, rargs, values):
    while rargs:
      try: optparse.OptionParser._process_args(_,largs, rargs, values)
      except (optparse.BadOptionError, optparse.AmbiguousOptionError) as E: largs.append(E.opt_str)

class Main(object):

  def initIndex(_):
    ''' Set up empty index, defining a root folder. '''
    folder = getRoot(_.options, _.args)
    cfg = Config(); cfg.log = _.options.log
    if _.options.log >= 1: info("Creating root configuration at %s" % folder)
    if not _.options.simulate:
      if not _.options.force or os.path.exists(os.path.join(folder, CONFIG)):
        error("Index already exists. Use --force to create anew anyway. Aborting.")
      else:
        cfg.store(os.path.join(folder, CONFIG), getTs())

  def updateIndex(_):
    ''' Crawl the folder tree and create a new index file.
        _.options: options structure from optparse, using rot and log
        _.args: arguments list from optparse, using as root folder if given
    '''
    folder = getRoot(_.options, _.args)
    if _.options.log >= 1: info("Using configuration from %s" % folder)
    cfg = Config(); cfg.log = _.options.log
    cfg.load(os.path.join(folder, CONFIG))
    if _.options.log >= 1: info("Updating index")
    idx = Indexer(folder); idx.log = _.options.log # set log level
    idx.walk(cfg) # index all files
    if not _.options.simulate: idx.store(os.path.join(folder, INDEX))
    return idx

  def find(_):
    ''' Find all folders that match the provided tags, excluding those from _.options.excludes.
        _.options: options structure from optparse, using rot and log
        poss, negs: lists of tags to include or exlcude. poss can also be comma-separated tag1,-tag2,...
        returns: None
        side-effect: print found files
    '''
    poss = commaArgsIntoList(_.args)
    poss, negs = splitCrit(poss, lambda e: e[0] != '-') # potentially including +/-
    negs.extend(commaArgsIntoList(_.options.excludes)) # each argument could contain , or not
    poss, negs = removeTagPrefixes(poss, negs)
    poss, negs = map(filenorm, (poss, negs))
    if _.options.log >= 1: info("Effective filters +<%s> -<%s>" % (",".join(poss), ",".join(negs)))
    if len([p for p in poss if p.startswith(DOT)]) > 1: error("Cannot have multiple positive extension filters (would always return empty match)"); return
    filename = os.path.join(getRoot(_.options, []), INDEX)
    if filename is None or not os.path.exists(filename):
      error("No configuration file found. Use -u to update the index."); return
    if not os.path.exists(filename):
      error("No index file found. Crawling file tree")
      idx = updateIndex(_.options, []) # crawl file tree
    else:
      idx = Indexer(os.path.dirname(filename)); idx.log = _.options.log
      idx.load(filename)
    if _.options.log >= 1: info("Searching for tags +<%s> -<%s> in %s" % (','.join(poss), ','.join(negs), os.path.dirname(filename)))
    paths = idx.findFolders([p for p in poss if not isglob(p) and DOT not in p[1:]], [n for n in negs if not isglob(n) and DOT not in n[1:]])
    if _.options.log >= 1: info("Potential matches found in %d folders" % (len(paths)))
    if _.options.log >= 2: [debug(path) for path in paths] # optimistic: all folders "seem" to match all tags, but only some might actually be (due to excludes etc)
    if len(paths) == 0 and any(lambda x: isglob(x) or DOT in x, poss + negs):
      warn("No folder match; cannot filter on folder names. Checking entire folder tree") # the logic is wrong: we ignore lots of tags while finding folders, and the continue filtering. better first filter on exts or all, then continue??
    paths = idx.findFolders([], [], True) # return all folders names unfiltered
    if _.options.onlyfolders:
      for p in poss: paths[:] = [x for x in paths if globmatch(safeRSplit(x, SLASH), p)]
      for n in negs: paths[:] = [x for x in paths if not globmatch(safeRSplit(x, SLASH), n)]
      if _.options.log >= 1: info("Found %d paths for +<%s> -<%s> in index" % (len(paths), ",".join(poss), ".".join(negs)))
      [printo(path) for path in paths]
      info("%d directories found for +%s / -%s." % (len(paths), ",".join(poss), ".".join(negs)))
      return
    dcount, counter = 0, 0 # if not only folders, but also files
    for path, files in ((path, idx.findFiles(path, poss, negs)) for path in paths):
      dcount += 1
      if len(files) > 0: printo("\n".join(idx.root + path + SLASH + file for file in files)); counter += len(files) # incremental output
    if _.options.log >= 1: info("%d files found in %d checked paths for +%s / -%s." % (counter, dcount, ",".join(poss), ".".join(negs)))
    print idx.tagdirs

  def add(_):
    ''' Add one or more (inclusive adn/or exclusive) tag(s) to the appended file and glob argument(s).
        We don't detect glob specifications that are subsets of or contradict existing tag globs.
        But we can detect files as subsets of existing globs, and vice versa, to issue warnings (inc/exc).
        _.options: options structure from optparse, using root, log, tag, strict, simulate
        filez: list of files or glob patterns
        returns: None
    '''
    folder = getRoot(_.options, _.args)
    root = pathnorm(os.path.abspath(folder))
    if _.options.log >= 1: info("Using configuration from %s" % folder)
    cfg = Config(); cfg.log = _.options.log # need to load config early for case_sensitive flag
    cfg.load(os.path.join(folder, CONFIG))

    filez = _.tags # process function arguments
    tags = safeSplit(_.options.tag, ",")
    poss, negs = splitCrit(tags, lambda e: e[0] != '-')
    poss, negs = removeTagPrefixes(poss, negs)
    poss, negs = map(filenorm, (poss, negs))
    if (len(poss) + len(negs)) == 0: error("No tag(s) given for %s" % ", ".join(file)); return
    if any(lambda p: p in negs, poss): error("Won't allow same tag in both inclusive and exclusiv file assignment: %s" % ', '.join(["'%s'" % p for p in poss if p in negs])); return

    modified = False
    for file in filez:
      if _.options.strict and not (os.path.exists(file) or any(fnmatch.filter(os.listdir("."), file))): warn("File or glob not found, skipping %s" % file) # TODO allow other relative/absolute paths than CWD
      parent, file = os.path.split(file)
      parent = pathnorm(os.path.abspath(parent)) # check if this is a relative path
      if not isunderroot(root, parent): # if outside folder tree
        warn("Relative file path outside indexed folder tree; skipping %s" % file); continue
      if cfg.addTag(parent[len(root):], file, poss, negs, options.force): modified = True
    if modified and not options.simulate: cfg.store(os.path.join(folder, CONFIG), getTs())

  def setConfig(_, unset = False, get = False):
    ''' Define, retrieve or remove a global configuration parameter. '''
    value = ((_.options.setconfig if not get else _.options.getconfig) if not unset else _.options.unsetconfig)
    if value is None: warn("Missing global configuration key argument"); return
    if not unset and not get and "=" not in value: warn("Global configuration entry must be specified in the form key=value"); return
    key, value = value.split("=")[:2] if not unset and not get else (value, None)
    key = key.lower() # config keys are normalized to lower case
    folder = getRoot(_.options, _.args)
    root = pathnorm(os.path.abspath(folder))
    if _.options.log >= 1: info("Using configuration from %s" % folder)
    cfg = Config(); cfg.log = _.options.log
    cfg.load(os.path.join(folder, CONFIG))
    if get:
      if key in cfg.__dict__: info("Get global configuration entry: %s = %s" % (key, cfg.__dict__[key])); return
      else: info("Global configuration entry '%s' not found" % key); return
    if '' not in cfg.paths: cfg.paths[''] = dd()
    entries = dictget(cfg.paths[''], GLOBAL, [])
    index = wrapExc(lambda: lindex([kv.split("=")[0].lower() for kv in entries], key)) # find index for specified key, or return None (by wrap mechanics)
    if not unset: # must be set
      if index is not None: entries[index] = "%s=%s" % (key, value); info("Modified global configuration entry")
      else: entries.append("%s=%s" % (key, value)); info("Added global configuration entry")
      cfg.__dict__[key] = value if value.lower() not in ("true", "false") else value.lower() == "true"
    else: # unset
      if index is not None: del entries[index]; info("Removed global configuration entry")
      else: info("Configuration entry not found, nothing to do") # Not contained - nothing to do
      try: del cfg.__dict__[key]
      except: pass
    if not _.options.simulate: cfg.store(os.path.join(folder, CONFIG), getTs())

  def parse(_):
    ''' Main logic that analyses the command line arguments and starts an opteration. '''
    ts = time.time() # https://docs.python.org/3/library/optparse.html#optparse-option-callbacks
    op = CatchExclusionsParser()
    op.add_option('--init', action = "store_true", dest = "init", help = "Create empty index (repository root)")
    op.add_option('-u', '--update', action = "store_true", dest = "update", help = "Update index, crawling files in folder tree")
    op.add_option('-s', '--search', action = "store_true", dest = "find", help = "Find files by tags (default action if no option given)")
    op.add_option('-t', '--tag', action = "store", dest = "tag", help = "Set tag(s) for given file(s): tp.py -t tag1,tag2,-tag3... file1,glob1...")
    op.add_option('-r', '--root', action = "store", dest = "root", type = str, help = "Specify root folder for index and configuration")
    op.add_option('-l', '--log', action = "store", dest = "log", type = int, default = 0, help = "Set log level (0=none, 1=debug, 2=trace)")
    op.add_option('-x', '--exclude', action = "append", dest = "excludes", default = [], help = "Tags to ignore") # allow multiple args
    op.add_option('--no', action = "append", dest = "excludes", default = [], help = "Same as --exclude or -tag") # same as above TODO allow multiple arguments
    op.add_option('--get', action = "store", dest = "getconfig", default = None, help = "Get global configuration parameter")
    op.add_option('--set', action = "store", dest = "setconfig", default = None, help = "Set global configuration parameter key=value")
    op.add_option('--unset', action = "store", dest = "unsetconfig", default = None, help = "Unset global configuration parameter")
    op.add_option('--relaxed', action = "store_false", dest = "strict", default = True, help = "Force strict checks")
    op.add_option('-n', '--simulate', action = "store_true", dest = "simulate", help = "Don't write anything")
    op.add_option('--dirs', action = "store_true", dest = "onlyfolders", help = "Only find directories that contain matches")
    op.add_option('-f', '--force', action = "store_true", dest = "force", help = "Override safety warnings")
    op.add_option('--test', action = "store_true", help = "Perform self-tests")
    # --no-reindex?
    op.add_option('-v', action = "store_true", dest = "verbose", help = "Switch only for unit test")
    _.options, _.args = op.parse_args()
    _.args, excludes = splitCrit(_.args, lambda e: e[0] != '-')
    _.options.excludes.extend([e[e.rindex('-') + 1:] for e in excludes]) # remove "--" from "--tag"
    _.options.log = max(1 if _.options.verbose else 0, _.options.log)
    if _.options.log >= 1: info("Started at %s" % (time.strftime("%H:%M:%S")))
    if _.options.init: _.initIndex()
    elif _.options.update: _.updateIndex()
    elif _.options.tag: _.add()
    elif _.options.getconfig: _.setConfig(get = True)
    elif _.options.setconfig: _.setConfig()
    elif _.options.unsetconfig: _.setConfig(unset = True)
    elif len(_.args) > 0: _.find() # default action is always find
    elif _.options.test: import doctest; doctest.testmod(verbose = _.options.verbose); sys.exit(0)
    else: error("No option given.")
    if _.options.log >= 1: info("Finished at %s after %.1fs" % (time.strftime("%H:%M:%S"), time.time() - ts))


if __name__ == '__main__':
  Main().parse()
