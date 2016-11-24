# Tagging script to augment OS folder structures by tags
# This script is written for easiest command-line access
#
# Globbing on tags not supported by design
# TODO separate timestamp from conf once more - better to exclude from vcs
# TODO implement delete option similar to add - safety checks for removal of patterns
# TODO simplify find, add from, add map option
# TODO use argparse instead, to allow for many arguments after --no, and dependent options
# TODO option to create xml or json output for query outputs files
# TODO create graphical interface, copy to clipboard, explorer integration etc.

import fnmatch,optparse,os,sys,time
from lib import Config,Indexer,CONFIG,INDEX,DOT,SLASH,GLOBAL,splitCrit,norm,isunderroot,safeSplit,isglob,debug,info,warn,error,wrapExc,lindex,getTs # direct namespace import is necessary to enable correct unpickling
# Python version dependent imports
if sys.version_info.major == 3:
  from functools import reduce # not built-in
  printe = eval("lambda s: print(s, file = sys.stderr)")
else:
  printe = eval("lambda s: sys.stderr.write(str(s) + '\\n') and sys.stderr.flush()")

# Little helper functions
def any(pred, lizt): return reduce(lambda a, b: a or pred(b), lizt if type(lizt) == list else list(lizt), False) # performs faster than built-in any when using Python 3, because explicit conversion to list would be required otherwise
def all(pred, lizt): return reduce(lambda a, b: a and pred(b), lizt if type(lizt) == list else list(lizt), True)

def commaArgsIntoList(lizt):
  '''
  >>> print(commaArgsIntoList(["a,b"]))
  ['a', 'b']
  >>> print(commaArgsIntoList(["ab"]))
  ['ab']
  '''
  assert type(lizt) is list
  return reduce(lambda a, b: a + ([b] if "," not in b else b.split(",")), lizt, [])

def removeTagPrefixes(poss, negs):
  '''
  >>> print(removeTagPrefixes(["+a", "b"], ["-c", "d"]))
  (['a', 'b'], ['c', 'd'])
  '''
  return [p if not p.startswith('+') else p[1:]for p in poss], [n[1:] if n.startswith('-') else n for n in negs] # remove leading +/-

def dotidx(p): return p.index(DOT) + 1
def lowerExtensions(patterns):
  '''
  Used in the find() and add() calls for the inclusive/exclusive tag arguments.
  >>> print(lowerExtensions(["a.B", "c??X*y.RX", ".TXT"]))
  ['a.b', 'c??X*y.rx', '.txt']
  '''
  return [pattern[:dotidx(pattern)] + pattern[dotidx(pattern):].lower() if DOT in pattern[:-1] else pattern for pattern in patterns]

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
  >>> def findRootFolder(o, f): return "/z/a.b" # TODO doesn'T override def
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


class Main(object):

  def initIndex(_):
    ''' Set up empty index, defining a root folder. '''
    folder = getRoot(_.options, _.args)
    cfg = Config(); cfg.log = _.options.log
    if _.options.log >= 1: info("Creating root configuration at %s" % folder)
    if not _.options.simulate: cfg.store(os.path.join(folder, CONFIG), getTs())

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
    poss, negs = map(lowerExtensions, (poss, negs))
    if len([p for p in poss if p.startswith(DOT)]) > 1: error("Cannot have multiple extension filters (would always return empty match)"); return
    if _.options.log >= 1: info("Effective filters +<%s> -<%s>" % (",".join(poss), ",".join(negs)))
    filename = os.path.join(getRoot(_.options, []), INDEX)
    if filename is None or not os.path.exists(filename):
      error("No configuration file found. Use -u to update the index."); return
    filename = os.path.join(os.path.dirname(filename), INDEX)
    if not os.path.exists(filename):
      error("No index file found. Crawling file tree")
      idx = updateIndex(_.options, []) # crawl file tree
    else:
      idx = Indexer(os.path.dirname(filename)); idx.log = _.options.log
      idx.load(filename)
    if _.options.log >= 1: info("Searching for tags <%s>%s in %s" % (','.join(poss), "" if len(negs) == 0 else " excluding <%s>" % ','.join(negs), os.path.dirname(filename)))
    paths = idx.findFolders([p for p in poss if not isglob(p) and DOT not in p[1:]], [n for n in negs if not isglob(n) and DOT not in n[1:]])
    if _.options.onlyfolders or _.options.log >= 2: info("Potential matches found in %d folders" % (len(paths))); [debug(path) for path in paths] # optimistic: all folders "seem" to match all tags, but only some might actually be (due to excludes etc)
    if _.options.onlyfolders:
      if len(paths) > 0: printe("%d paths found for +%s / -%s." % (len(paths), ",".join(poss), ".".join(negs)))
      return # don't filter actual files, and omit from mappings
    if len(paths) == 0 and any(lambda x: isglob(x) or DOT in x, poss + negs):
      warn("Cannot filter on folder names. Checking entire folder tree") # the logic is wrong: we ignore lots of tags while finding folders, and the continue filtering. better first filter on exts or all, then continue??
      paths = idx.findFolders([], [], True) # return all folders unfiltered
    dcount, counter = 0, 0
    for path, files in ((path, idx.findFiles(path, poss, negs)) for path in paths):
      dcount += 1
      if len(files) > 0: print("\n".join(idx.root + path + SLASH + file for file in files)); counter += len(files) # incremental output
    if counter > 0: info("%d files found in %d checked paths for +%s / -%s." % (counter, dcount, ",".join(poss), ".".join(negs)))

  def add(_):
    ''' Add one or more (inclusive adn/or exclusive) tag(s) to the appended file and glob argument(s).
        We don't detect glob specifications that are subsets of or contradict existing tag globs.
        But we can detect files as subsets of existing globs, and vice versa, to issue warnings (inc/exc).
        _.options: options structure from optparse, using root, log, tag, strict, simulate
        filez: list of files or glob patterns
        returns: None
    '''
    folder = getRoot(_.options, _.args)
    root = norm(os.path.abspath(folder))
    if _.options.log >= 1: info("Using configuration from %s" % folder)
    cfg = Config(); cfg.log = _.options.log # need to load config early for case_sensitive flag
    cfg.load(os.path.join(folder, CONFIG))

    filez = _.tags # process function arguments
    tags = safeSplit(_.options.tag, ",")
    poss, negs = splitCrit(tags, lambda e: e[0] != '-') # HINT: faster than "not e.startswoth('-')"
    poss, negs = removeTagPrefixes(poss, negs)
    if not cfg.case_sensitive: poss, negs = map(lowerExtensions, (poss, negs))
    if (len(poss) + len(negs)) == 0: error("No tag(s) given for %s" % ", ".join(file)); return
    if any(lambda p: p in negs, poss): error("Won't allow same tag in both inclusive and exclusiv file assignment: %s" % ', '.join(["'%s'" % p for p in poss if p in negs])); return

    modified = False  
    for file in filez: # first, handle single files TODO same as globs; allow to assign tags to globs here! already done, but issue warning?
      if _.options.strict and not os.path.exists(file):
        warn("File not found, skipping %s" % file)
      parent, file = os.path.split(file)
      parent = norm(os.path.abspath(parent)) # check if this is a relative path
      if not isunderroot(root, parent): # if outside folder tree
        warn("Relative file path outside indexed folder tree; skipping %s" % file); continue
      if cfg.addTag(parent[len(root):], file, poss, negs, options.force): modified = True
    if modified and not options.simulate: cfg.store(os.path.join(folder, CONFIG), getTs())

  def setConfig(_, unset = False, get = False):
    ''' Define a global configuration parameter. '''
    value = ((_.options.setconfig if not get else _.options.getconfig) if not unset else _.options.unsetconfig)
    if value is None: warn("Missing global configuration key argument"); return
    if not unset and not get and "=" not in value: warn("Global configuration entry must be specified in the form key=value"); return
    key, value = value.split("=")[:2] if not unset and not get else (value, None)
    key = key.lower() # config keys are normalized to lower case
    folder = getRoot(_.options, _.args)
    root = norm(os.path.abspath(folder))
    if _.options.log >= 1: info("Using configuration from %s" % folder)
    cfg = Config(); cfg.log = _.options.log
    cfg.load(os.path.join(folder, CONFIG))
    if get:
      if key in cfg.__dict__: info("Get global configuration entry: %s = %s" % (key, cfg.__dict__[key])); return
      else: info("Global configuration entry '%s' not found" % key); return
    entries = cfg.paths[""][GLOBAL]
    index = lindex([kv.split("=")[0].lower() for kv in entries], key)
    if "" not in cfg.paths: cfg.paths[""] = {}
    if GLOBAL not in cfg.paths[""]: cfg.paths[""]["GLOBAL"] = []
    if not unset: # set
      if index is not None: cfg.__dict__[key] = value if value.lower() not in ("true", "false") else value.lower() == "true"; entries[index] = "%s=%s" % (key, value); info("Modified global configuration entry")
      else: entries.append("%s=%s" % (key, value)); info("Added global configuration entry")
    else: # unset
      if index is not None: del cfg.__dict__[key]; del entries[index]; info("Removed global configuration entry")
      else: info("Configuration entry not found, nothing to do") # Not contained - nothing to do
    if not _.options.simulate: cfg.store(os.path.join(folder, CONFIG), getTs())

  def parse(_):
    ''' Main logic that analyses the command line arguments and starts an opteration. '''
    ts = time.time() # https://docs.python.org/3/library/optparse.html#optparse-option-callbacks
    op = optparse.OptionParser(
      prog = "TagsPlorer",
      usage = "python tp.py <tags or options>",
  #    formatter = optparse.TitledHelpFormatter(),
      version = "Tagsplorer Release 2016.Q3")
    op.add_option('--init', action = "store_true", dest = "init", help = "Create empty index (repository root)")
    op.add_option('-u', '--update', action = "store_true", dest = "update", help = "Update index, crawling files in folder tree")
    op.add_option('-s', '--search', action = "store_true", dest = "find", help = "Find files by tags (default action if no option given)")
    op.add_option('-t', '--tag', action = "store", dest = "tag", help = "Set tag(s) for given file(s): tp.py -t tag1,tag2,-tag3... file1,glob1...")
    op.add_option('-r', '--root', action = "store", dest = "root", type = str, help = "Specify root folder for index and configuration")
    op.add_option('-l', '--log', action = "store", dest = "log", type = int, default = 0, help = "Set log level (0=none, 1=debug, 2=trace)")
    op.add_option('-x', '--exclude', action = "append", dest = "excludes", default = [], help = "Tags to ignore") # allow multiple args
    op.add_option('-n', '--no', action = "append", dest = "excludes", default = [], help = "Same as --exclude or -tag") # same as above TODO allow multiple arguments
    op.add_option('--get', action = "store", dest = "getconfig", default = None, help = "Get global configuration parameter")
    op.add_option('--set', action = "store", dest = "setconfig", default = None, help = "Set global configuration parameter key=value")
    op.add_option('--unset', action = "store", dest = "unsetconfig", default = None, help = "Unset global configuration parameter")
    op.add_option('--strict', action = "store_true", dest = "strict", help = "Force strict checks")
    op.add_option('--simulate', action = "store_true", dest = "simulate", help = "Don't write anything")
    op.add_option('--dirs', action = "store_true", dest = "onlyfolders", help = "Only find directories that contain matches")
    op.add_option('-f', '--force', action = "store_true", dest = "force", help = "Override safety warnings")
    op.add_option('--test', action = "store_true", help = "Perform self-tests")
    # --no-reindex?
    op.add_option('-v', action = "store_true", dest = "verbose", help = "Switch only for unit test")
    _.options, _.args = op.parse_args()
    if _.options.init: _.initIndex()
    elif _.options.update: _.updateIndex()
    elif _.options.tag: _.add()
    elif _.options.getconfig: _.setConfig(get = True)
    elif _.options.setconfig: _.setConfig()
    elif _.options.unsetconfig: _.setConfig(unset = True)
    elif len(_.args) > 0: _.find() # default action is always find
    elif _.options.test: import doctest; doctest.testmod(verbose = _.options.verbose); os.system(sys.executable + " tests.py"); sys.exit(0)
    else: error("No option given.")
    if _.options.log >= 1: info("Finished after %.1fs" % (time.time() - ts))


if __name__ == '__main__':
  Main().parse()