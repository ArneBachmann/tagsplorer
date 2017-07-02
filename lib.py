# tagsPlorer main library  (C) 2016-2017  Arne Bachmann  https://github.com/ArneBachmann/tagsplorer
# This is the tagging library to augment OS folder structures by tags (and provide virtual folder view plus queries over tags)
# This code is written for maximum OS and Python version interoperability and should run fine on any Linux and Windows, in both Python 2 and Python 3.

# markers in this file: TODO (open tasks) and HINT (to think about)
# TODO add option to interrupt find or walk (probably on process level via SIGINT?)
# TODO replace %s by %r or use invalid character replacing in logger?


import collections, copy, fnmatch, os, re, sys, time, zlib  # standard library
if sys.version_info.major >= 3: from os import listdir
else: from dircache import listdir

DEBUG = 3; INFO = 2; WARN = 1; ERROR = 0  # log levels
LOG = DEBUG if os.environ.get("DEBUG", "false").lower() == "true" else INFO  # maximum log level
ON_WINDOWS = sys.platform == 'win32'  # there exists a different detection schema, but I don't remember

# Version-dependent imports
trace, debug, info, warn, error = [lambda _: None] * 5
if sys.version_info.major >= 3:
  import pickle  # instead of cPickle
  from sys import intern
  from functools import reduce  # not built-in anymore
  lmap = lambda pred, lizt: list(map(pred, lizt))  # don't return a generator
  dictviewkeys, dictviewvalues, dictviewitems = dict.keys, dict.values, dict.items  # returns generators operating on underlying data in Python 3
  cmp = lambda a, b: -1 if a < b else (1 if a > b else 0)
  def xreadlines(fd): return fd.readlines()
  from functools import reduce  # not built-in
  printo = eval("lambda s: print(s)")  # perfectly legal use of eval - supporting P2/P3
  printe = eval("lambda s: print(s, file = sys.stderr)")
  debug, info, warn, error = (eval("lambda *s: printe(\"%s\" + \" \".join([str(_) for _ in s]))" % mesg) if LOG >= levl else (lambda _: None) for mesg, levl in zip((_.ljust(8) + " " for _ in ("Debug:",  "Info:", "Warning:", "Error:")), (DEBUG, INFO, WARN, ERROR)))
else:  # is Python 2 (for old versions like e.g. 2.4 this might fail)
  import cPickle as pickle
  lmap = map
  dictviewkeys, dictviewvalues, dictviewitems = dict.iterkeys, dict.itervalues, dict.iteritems
  def xreadlines(fd): return fd.xreadlines()
  printo = eval("lambda s: sys.stdout.write(str(s) + '\\n') and sys.stdout.flush()")
  printe = eval("lambda s: sys.stderr.write(str(s) + '\\n') and sys.stderr.flush()")
  if LOG >= ERROR:
    def error(*s): print >> sys.stderr, "Error:  ", " ".join([str(_) for _ in s])
    if LOG >= WARN:
      def warn(*s): print >> sys.stderr, "Warning:", " ".join([str(_) for _ in s])
      if LOG >= INFO:
        def info(*s): print >> sys.stderr, "Info:   ", " ".join([str(_) for _ in s])
        if LOG >= DEBUG:
          def debug(*s): print >> sys.stderr, "Debug:  ", " ".join([str(_) for _ in s])


# Constants
PICKLE_VERSION = 2  # since Python 3 comes with different protocol, we pin the protocol here
CONFIG =  ".tagsplorer.cfg"  # main tag configuration file
INDEX =   ".tagsplorer.idx"  # index file (re-built when timestamps differ)
SKPFILE = ".tagsplorer.skp"  # marker file (can also be configured in configuration instead)
IGNFILE = ".tagsplorer.ign"  # marker file (dito)
IGNORE, SKIP, TAG, FROM, SKIPD, IGNORED, GLOBAL = map(intern, ("ignore", "skip", "tag", "from", "skipd", "ignored", "global"))  # config file options
SEPA, SLASH, DOT = map(intern, (";", "/", os.extsep))


# Functions

def wrapExc(func, otherwise = None):
  ''' Wrap an exception and compute return value lazily if an exception is raised. Useful for recursive function application.
  >>> print(wrapExc(lambda: 1))
  1
  >>> print(wrapExc(lambda: 1 / 0))  # return default
  None
  >>> print(wrapExc(lambda: 1 / 0, lambda: 1 + 1))  # return default by function call
  2
  '''
  try: return func()
  except: return otherwise() if callable(otherwise) else otherwise

def lindex(lizt, value, otherwise = lambda _lizt, _value: None):
  ''' List index function with lazy append computation.
      Returns index if found, or new index if not found.
      Default fallback logic if no computation function is given: do nothing and return None.
  >>> print(lindex([1, 2], 2))
  1
  >>> print(lindex([], 1))
  None
  >>> print(lindex([1], 2, lambda _lizt, _value: _lizt.index(_value - 1)))
  0
  '''
  return wrapExc(lambda: lizt.index(value), lambda: otherwise(lizt, value))  # ValueError

ilong = eval("lambda s: int(s)") if sys.version_info.major >= 3 else eval("lambda s: long(s)")
def ident(_): return _  # definition to be conditionally used instead of a more complex transformation
def isdir(f): return os.path.isdir(f) and not os.path.islink(f) and not os.path.ismount(f)
def isfile(f): return wrapExc(lambda: os.path.isfile(f) and not os.path.ismount(f) and not os.path.isdir(f), lambda: False)  # on error "no file"
pathnorm = (lambda s: s.replace("\\", SLASH)) if ON_WINDOWS else ident  # as lambda to allow dynamic definition
def lappend(lizt, elem): (lizt.extend if type(elem) is list else lizt.append)(elem); return lizt   # functional list.append that returns self afterwards to avoid new array creation (lizt + [elem])
def appendandreturnindex(lizt, elem): return len(lappend(lizt, elem)) - (len(elem) if type(elem) is list else 1)  # returns index of appended element or first index of elements added
def isunderroot(root, folder): return os.path.commonprefix([root, folder]).startswith(root)
def isglob(f): return '*' in f or '?' in f
def getTs(): return ilong(time.time() * 1000.)
def safeSplit(s, d = ","): return [_ for _ in s.split(d) if _ != '']  # remove empty strings that appear e.g. for "  ".split(" ") or "".split(" ")
def safeRSplit(s, d): return s[s.rindex(d) + 1:] if d in s else s
def dd(tipe = list): return collections.defaultdict(tipe)
def step(): import pdb; pdb.set_trace()
def dictget(dikt, key, default):
  ''' Improved dict.get(key, default).
  >>> a = {}; b = a.get(0, 0); print((a, b))  # normal dict get
  ({}, 0)
  >>> a = {}; b = dictget(a, 0, 0); print((a, b))  # improved dict get
  ({0: 0}, 0)
  >>> a = {}; b = dictget(a, 0, lambda: 1); print((a, b))
  ({0: 1}, 1)
  '''
  try: return dikt[key]
  except: dikt[key] = ret = default() if callable(default) else default; return ret
def splitCrit(lizt, pred):
  ''' Split lists by a binary predicate.
  >>> print(splitCrit([1,2,3,4,5], lambda e: e % 2 == 0))
  ([2, 4], [1, 3, 5])
  '''
  return reduce(lambda acc, next: (lappend(acc[0], next), acc[1]) if pred(next) else (acc[0], lappend(acc[1], next)), lizt, ([], []))
def caseNormalize(s): return s.upper()


# Classes
class Normalizer(object):
  def setupCasematching(_, case_sensitive):
    ''' Setup normalization.
    >>> n = Normalizer(); n.setupCasematching(True); print(n.filenorm("Abc"))
    Abc
    >>> print(n.globmatch("abc", "?Bc"))
    False
    >>> n.setupCasematching(False); print(n.filenorm("Abc"))
    ABC
    >>> print(n.globmatch("abc", "?Bc"))
    True
    '''
    _.filenorm = ident if case_sensitive else caseNormalize  # we can't use "str if case_sensitive else str.upper" because for unicode strings this fails, as the function reference comes from the str object
    _.globmatch = fnmatch.fnmatchcase if case_sensitive else lambda f, g: fnmatch.fnmatch(f.upper(), g.upper())  # fnmatch behavior depends on file system, therefore fixed here
normalizer = Normalizer()  # to keep a static module-reference. TODO move to main instead?

class ConfigParser(object):
  ''' Much simplified config file (ini file) reader. No line continuation, no colon separation, no symbolic replacement, no comments, no empty lines. '''

  def __init__(_): _.sections = {}

  def load(_, fd):
    ''' Read from file object to enable reading from arbitrary data source and position.
        returns global config
    '''
    title = None; section = dd()  # this dict initializes any missing value with an empty list TODO make ordered default dict, but couldn't find any compatible solution
    for line in xreadlines(fd):
      line = line.strip()  # just in case of incorrect formatting
      if line.startswith('['):  # new section detected: first store last section
        if len(section) > 0: _.sections[title] = section  # OLD: and title is not None
        title = line[1:-1]; section = dd()  # default-dictionary of (standard) type map
      elif line != '':
        try:
          idx = line.index('=')  # try to parse
          key, value = line[:idx], line[idx+1:]  # HINT: was .lower() and .rstrip(), but when reading/writing only via this script's API there's no need for that
          if key in [TAG, FROM] and value != '':
            section[intern(key)].append(intern(value))  # this dict allows several values per key
          elif key in [IGNORE, SKIP] and key not in section:
            section[intern(key)] = None  # only keep key instead of default-appending empty string
          elif title == "" and key in [SKIPD, IGNORED, GLOBAL] and value != '':
            section[intern(key)].append(intern(value))  # global dir skip or ignore pattern, or global config setting
          else: warn("Encountered illegal key <%s>. Skipping entry." % key)
        except: warn("Key with no value for illegal key %s" % repr(line))
      else: break  # an empty line terminates file
    if len(section) > 0: _.sections[title] = section  # last store OLD:  and title is not None
    return { k.lower(): v if v.lower() not in ("true", "false") else v.lower().strip() == "true" for k, v in (wrapExc(lambda: kv.split("=")[:2], lambda: (kv, None)) for kv in _.sections.get("", {}).get(GLOBAL, [])) }  # return global config map for convenience

  def store(_, fd, parent = None):  # write to file object to alloyw for additional contents
    if parent is not None:  # store parent's properties
      if "" not in _.sections: _.sections[intern("")] = dd()
      _.sections[""][GLOBAL] = sorted(["%s=%s" % (k.lower(), str(parent.__dict__[k])) for k, v in (kv.split("=")[:2] for kv in _.sections.get("", {}).get(GLOBAL, []))])  # store updated config
    for title, _map in sorted(dictviewitems(_.sections)):  # in added order
      if len(_map) == 0: continue  # this is probably not sufficient, as the map's contents may also be empty
      fd.write("[%s]\n" % (title))
      for key, values in sorted(_map.items()):  # no need for iteritems, as supposedly small (max. size = 4)
        if values is None: fd.write("%s=\n" % (key.lower()))  # skip or ignore
        else:
          for value in sorted(values): fd.write("%s=%s\n" % (key.lower(), value))  # tag or from
    fd.write("\n")  # termination of config contents


class Config(object):
  ''' Contains all tag configuration. '''
  def __init__(_):
    _.log = 0  # level
    _.paths = {}  # map from relative dir path to dict of marker -> [entries]
    _.case_sensitive = not ON_WINDOWS  # dynamic default unless specified differently in the config file
    _.reduce_case_storage = False  # default is always store case-noramlized plus true case
    normalizer.setupCasematching(_.case_sensitive)  # default, overridden by load

  def load(_, filename, index_ts = None):
    ''' Load configuration from file, if timestamp differs from index' timestamp. '''
    if _.log >= 2: debug("load " + str((filename, index_ts)))
    with open(filename, 'r') as fd:  # HINT: don't use rb, because in Python 3 this return bytes objects
      if _.log >= 1: info("Comparing configuration timestamp for " + filename)
      timestamp = float(fd.readline().rstrip())
      if (index_ts is not None) and timestamp == index_ts:
        if _.log >= 1: info("Skip loading configuration, because index is up to date")
        return False  # no skew detected, allow using old index' interned configuration ("self" will be discarded)
      if _.log >= 1: info("Loading configuration from file system" + ("" if index_ts is None else " because index is outdated"))
      cp = ConfigParser(); dat = cp.load(fd); _.__dict__.update(dat)  # update with global options
      _.paths = cp.sections
      normalizer.setupCasematching(_.case_sensitive)
      return True

  def store(_, filename, timestamp = None):
    ''' Store configuration to file, prepending data by the timestamp, or the current time. '''
    if _.log >= 2: debug("store " + str((filename, timestamp)))
    if timestamp is None: timestamp = getTs()  # for all cases we modify only config file (e.g. tag, untag, config)
    cp = ConfigParser(); cp.sections = _.paths
    with open(filename, "w") as fd:  # don't use wb for Python 3 compatibility
      if _.log >= 1: info("Writing configuration to " + filename)
      fd.write("%d\n" % timestamp); cp.store(fd, parent = _)
    if _.log >= 1: info("Wrote %d config bytes" % os.stat(filename)[6])

  def addTag(_, folder, pattern, poss, negs, force = False):
    ''' For given folder, add poss and negs tags to file or glob pattern.
        folder: folder to operate on (relative to root)
        pattern: the file or glob pattern to add to the configuration
        poss: inclusive tags or globs to add
        negs: exclusive tags or globs to add
        force: allows adding tags already subsumed by globs
        returns: modified?
    '''
    if _.log >= 2: debug("addTag " + str((folder, pattern, poss, negs, force)))
    conf = dictget(_.paths, folder, {})  # creates empty config entry if it doesn't exist
    is_glob = isglob(pattern)
    pname = "Glob" if is_glob else "File"
    keep_pos, keep_neg = dd(), dd()

    for tag in poss + negs:  # iterate over both, because sub-processing is more complex than making this distinction below
      keep = True  # marker
      for line in conf.get(TAG, []):  # all tag markers for the given folder
        tg, inc, exc = line.split(SEPA)
        if tg == tag:  # if tag specified in configuration line
          for i in safeSplit(inc):
            if isglob(i) and not is_glob and normalizer.globmatch(pattern, i):  # is file matched by inclusive glob
              keep = force
              (warn if force else error)("File '%s' already included by glob pattern '%s' for tag '%s'%s" % (pattern, i, tag, "" if force else ", skipping"))
              break
            elif i == pattern:  # file/glob already contained
              keep = False; error("%s '%s' already%s specified for tag '%s'%s" % (pname, pattern, " inversely" if tag in negs else "", tag, "" if force else ", skipping")); break
          for e in safeSplit(exc):
            if isglob(e) and not is_glob and normalizer.globmatch(pattern, e):  # is file matched by exclusive glob
              keep = force
              (warn if force else error)("File '%s' excluded by glob pattern '%s' for tag '%s'%s" % (pattern, e, tag, "" if force else ", skipping"))
              break
            elif e == pattern:  # file/glob already contained
              keep = False; error("%s '%s' already%s specified for tag '%s'%s" % (pname, pattern, " inversely" if tag in poss else "", tag, "" if force else ", skipping")); break
          break  # because tag was found
      if keep: (keep_pos if tag in poss else keep_neg)[tag].append(pattern)

     # Now really add new patterns to config
    for tag in (list(keep_pos.keys()) + list(keep_neg.keys())):
      if _.log >= 1: debug("Adding tags <%s>/<%s>" % (",".join(keep_pos.get(tag, [])), ",".join(keep_neg.get(tag, []))))
      entry = dictget(conf, TAG, [])
      missing = True
      for i, line in enumerate(entry):
        tg, inc, exc = line.split(SEPA)
        if tg == tag:  # found: augment existing entry
          entry[i] = "%s;%s;%s" % (tag, ",".join(sorted(set(safeSplit(inc, ",") + keep_pos.get(tag, [])))), ",".join(sorted(set(safeSplit(exc) + keep_neg.get(tag, [])))))
          missing = False  # tag already exists
          break  # line iteration
      if missing: entry.append("%s;%s;%s" % (tag, ",".join(keep_pos.get(tag, [])), ",".join(keep_neg.get(tag, []))))  # if new: create entry
    return len(keep_pos.keys()) + len(keep_neg.keys()) > 0

  def delTag(_, folder, pattern, poss, negs):
    ''' For given folder, remove poss and negs tags to file or glob pattern.
        folder: folder to operate on (relative to root)
        pattern: the file or glob pattern to remove from the configuration
        poss: inclusive tags or globs to remove
        negs: exclusive tags or globs to remove
        returns: modified?
    '''
    if _.log >= 2: debug("delTag " + str((folder, pattern, poss, negs)))
    conf = dictget(_.paths, folder, {})  # creates empty config entry if it doesn't exist
    changed = False
    for tag in poss + negs:
      removes = []  # indices not to update, but to remove entirely
      for confindex, line in enumerate(conf.get(TAG, [])):  # all tag markers for the given folder
        tg, inc, exc = line.split(SEPA)
        if tg == tag:  # if tag specified in configuration line
          ii = safeSplit(inc)
          ee = safeSplit(exc)
          if pattern in ii and tag in poss:
            changed = True
            ii.remove(pattern)
            if _.log >= 1: debug("Removing positive entry '%s' for tag '%s'" % (pattern, tag))
          elif pattern in ee and tag in negs:
            changed = True
            ee.remove(pattern)
            if _.log >= 1: debug("Removing negative entry '%s' for tag '%s'" % (pattern, tag))
          if len(ii + ee) > 0: conf.get(TAG)[confindex] = ";".join([tg, ",".join(ii), ",".join(ee)])  # update conf entry
          else: removes.append(confindex)
      for remindex in reversed(removes): conf.get(TAG).pop(remindex)  # decreasing order to keep valid indices during modification
    return changed


class Indexer(object):
  ''' Main index creation. Goes through all recursive file paths and indexes the folder tags. Addtionally, tags for single files or globs, and those mapped by the FROM tag are included in the index. File-specific tags are only determined during the find phase. '''
  def __init__(_, startDir):
    _.log = 0  # log level
    _.compressed = 2  # pure pickling is faster than any bz2 compression, but zlib level 2 had best size/speed combination. if changed to 0, index needs to be re-created (or removed) manually
    _.timestamp = 1.23456789  # for comparison with configuration timestamp
    _.cfg = None  # reference to latest corresponding configuration
    _.root = pathnorm(os.path.abspath(startDir))
    _.tagdirs = []  # array of tags (plain dirnames and manually set tags (not represented in parent), both case-normalized and as-is)
    _.tagdir2parent = []  # index of dir entry (tagdirs) -> index of parent to represent tree structure (exclude folder links)
    _.tagdir2paths = dd()  # dirname/tag index -> list of [all path indices relevant for that dirname/tag]

  def load(_, filename, ignore_skew = False, recreate_index = True):
    ''' Load a pickled index into memory. Optimized for speed. '''
    if _.log >= 2: debug("load " + str((filename, ignore_skew, recreate_index)))
    with open(filename, "rb") as fd:
      if _.log >= 1: info("Reading index from " + filename)
      c = pickle.loads(zlib.decompress(fd.read()) if _.compressed else fd.read())
      _.cfg, _.timestamp, _.tagdirs, _.tagdir2parent, _.tagdir2paths = c.cfg, c.timestamp, c.tagdirs, c.tagdir2parent, c.tagdir2paths
      cfg = Config(); cfg.log = _.log  # partially read existing configuration to compare with unpickled version, or read fully if timestamp differs
      if (ignore_skew or cfg.load(os.path.join(os.path.dirname(os.path.abspath(filename)), CONFIG), _.timestamp)) and recreate_index:
        if _.log >= 1: info("Recreating index considering configuration")
        _.cfg = cfg  # set more recent config and update
        normalizer.setupCasematching(cfg.case_sensitive)  # update after loading current state from config file, otherwise keep interned value from pickled object
        _.walk()  # re-create this index
        _.store(filename)

  def store(_, filename, config_too = True):
    ''' Persist index in a file, including currently active configuration. '''
    if _.log >= 2: debug("store " + str((filename, config_too)))
    with open(filename, "wb") as fd:
      nts = getTs()
      _.timestamp = _.timestamp + 0.001 if nts <= _.timestamp else nts  # assign new date, ensure always differing from old value
      if _.log >= 1: info("Writing index to " + filename)
      fd.write(zlib.compress(pickle.dumps(_, protocol = PICKLE_VERSION), _.compressed) if _.compressed else pickle.dumps(_, protocol = PICKLE_VERSION))  # WARN: make sure not to have callables on the pickled objects!
      if config_too:
        if _.log >= 1: info("Updating configuration to match new index timestamp")
        _.cfg.store(os.path.join(os.path.dirname(os.path.abspath(filename)), CONFIG), _.timestamp)  # update timestamp in configuration
    if _.log >= 1: info("Wrote %d index bytes (%d tag entries -> %d mapped path entries)" % (os.stat(filename)[6], len(_.tagdirs), sum([len(p) for p in _.tagdir2paths.values()])))

  def walk(_, cfg = None):
    ''' Build index by recursively walking folder tree.
        cfg: if set, use that configuration instead of contained one.
    '''
    if _.log >= 1: info("Walking folder tree")
    if cfg is not None: _.cfg = cfg  # allow config injection
    if _.cfg is None: error("No configuration loaded. Cannot walk folder tree"); return
    if _.log >= 2: debug("Configuration: case_sensitive = %s, reduce_case_storage = %s" % (_.cfg.case_sensitive, _.cfg.reduce_case_storage))
    _.tagdirs = [""]  # list of directory names, duplicates allowed and required to represent true tree structure. "" is root, element zero of tagdirs
    _.tagdir2parent = [0]  # marker for root (the only self-reference in the structure. each index position responds to one entry in tagdirs TODO check this invariant somewhere)
    _.tagdir2paths = dd()  # maps index of tagdir entries to list of path leaf indexes, duplicates merged
    _.tags = []  # temporary structure for list of (manually set) tag names and file extensions, which gets mapped into the tagdirs structure after walking
    _.tag2paths = dd()  # temporary structures for manual tag and extension mapping, and respective paths
    _._walk(_.root, 0)  # recursive indexing: folder to index and parent's dirname index (from _.tagdirs)
    tagdirs_num = len(_.tagdirs)  # not the same as _.tagdirs, here we only memorize the length for stats output
    tags_num = len(_.tags)
    rm_num = _.mapTagsIntoDirsAndCompressIndex()  # unified with folder entries for simple lookup and filtering
    del _.tags, _.tag2paths  # remove temporary structures
    if _.log >= 1: info("Indexed %d folders and %d tags/globs/extensions, pruned %d unused entries." % (tagdirs_num, tags_num, rm_num))

  def _walk(_, aDir, parent, tags = []):
    ''' Recursive walk through folder tree. Function call will index the folder 'aDir' and then recurse into its children folders.
        Adds all parent names (up to root) as tags plus the current directory's name, unless told to ignore current one by configuration or file marker.
        General approach is to add children's tags in the parent, then recurse, potentially removing added tags in the recursion if necessary.
        Flow of execution:
          1.  get folder configuration, if any
          1a. set skip or ignore flags from configuration
          1b. read additional tags for folder and folder mapping from configuration into "tags" and "adds", no matter if inclusive or exclusive
          2.  process contained file names
          2a. index all folders' file and sub-folder file names' extensions
          3.  prepare recursion
          3a. add sub-folder name to "tagdirs" and "tagdir2parent" 
          3b. recurse
        aDir: path relative to root (always with preceding and no trailing forward slash)
        parent: the parent folder's index in the index (usually the one in the original case)
        tags: list of aggregated tags (folder names) of parent directories: indexes of
    '''
    if _.log >= 2: info("_walk " + aDir)
    # 1.  get folder configuration, if any
    skip, ignore = False, False  # marks folder as "no further recursion" or "no tagging for this folder only", respectively, according to local or global settings
    adds = []  # indexes of additional tags valid for current folder only (single files, extensions), not to be promoted to children folders (which are index separately as folder tag names)
    marks = _.cfg.paths.get(aDir[len(_.root):], {})  # contains configuration for current folder
    # 1a: check folder's configuration
    if SKIP in marks or ((aDir[aDir.rindex(SLASH) + 1:] if aDir != '' and SLASH in aDir else '') in dictget(dictget(_.cfg.paths, '', {}), SKIPD, [])):
      if _.log >= 1: info("  Skip %s%s" % (aDir, '' if SKIP in marks else ' due to global skip setting'))
      return  # completely ignore sub-tree and break recursion
    elif IGNORE in marks or ((aDir[aDir.rindex(SLASH) + 1:] if aDir != '' and SLASH in aDir else '') in dictget(dictget(_.cfg.paths, '', {}), IGNORED, [])):  # former checks path cfg, latter checks global ignore TODO allow glob check?
      if _.log >= 1: info("  Ignore %s%s" % (aDir, '' if IGNORE in marks else ' due to global ignore setting'))
      ignore = True  # ignore this directory as tag, don't index contents
    # 1b: check folder's configuration
    elif TAG in marks:  # neither SKIP nor IGNORE in config: consider manual folder tagging
      for t in marks[TAG]:
        if _.log >= 1: info("  Tag '%s' in %s" % (t, aDir))
        tag, pos, neg = t.split(SEPA)  # tag name, includes, excludes
        i = lindex(_.tags, intern(tag), appendandreturnindex)  # find existing index of that tag, or create a new and return its index
        adds.append(i); _.tag2paths[i].append(parent)
    elif FROM in marks:  # consider tags from mapped folder
      for f in marks[FROM]:
        if _.log >= 1: info("  Map from %s into %s" % (f, aDir))
        other = pathnorm(os.path.abspath(os.path.join(aDir, f))[len(_.root):] if not f.startswith(SLASH) else os.path.join(_.root, f))
        _marks = _.cfg.paths.get(other, {})
        if TAG in _marks:
          for t in _marks[TAG]:
            tag, pos, neg = t.split(SEPA)  # tag name, includes, excludes
            i = lindex(_.tags, intern(tag), appendandreturnindex)
            adds.append(i); _.tag2paths[i].append(parent)

    #  2.  process folder's file names
    files = wrapExc(lambda: listdir(aDir), lambda: [])  # read file list
    if SKPFILE in files:  # TODO what about file name case? should be no problem, as even Windows allows lower-case file names and should match here
      if _.log >= 1: info("  Skip %r due to local skip file" % aDir[len(_.root):])
      return  # completely ignore sub-tree and break recursion here
    ignore = ignore or (IGNFILE in files)  # short-circuit logic: config setting or file marker
    if ignore:  # ignore this directory as tag, don't index its contents, but continue with children
      if _.log >= 1: info("  Ignore %r due to local ignore setting" % aDir[len(_.root):])
      if not _.cfg.reduce_case_storage and len(tags) >= 2 and caseNormalize(_.tagdirs[tags[-2]]) == _.tagdirs[tags[-1]]: _.tagdir2paths[_.tagdirs.index(_.tagdirs[tags[-2]])].pop()  # in case parent caller added true case *and also* case-normalized version, remove latter. if reduce_storage, there was only one added anyway
      if len(tags) >= 1: _.tagdir2paths[_.tagdirs.index(_.tagdirs[tags[-1]])].pop()  # TODO may leave empty list behind
    else:  # no ignore, so index extensions as additional tags, folders and files alike
      # 2a. index all folders' contents' names file extensions
      debug("Indexing files in folder %r" % aDir[len(_.root):])
      for _file in (ff for ff in files if DOT in ff[1:]):  # index only file extensions (also for folders!) in this folder, without propagation to sub-folders TODO dot-first files could be ignored or handled differenly
        ext = _file[_file.rindex(DOT):]  # split off extension, even if "empty" extension (filename ending in dot)
        iext = caseNormalize(ext)
        i = lindex(_.tags, intern(ext), appendandreturnindex)  # get or add file extension to local dir's tags only
        adds.append(i); _.tag2paths[i].append(parent)  # add current dir to index of that extension
        if not _.cfg.reduce_case_storage and iext != ext:  # differs from normalized version: store normalized as well
          i = lindex(_.tags, intern(iext), appendandreturnindex)  # add file extension to local dir's tags only
          adds.append(i); _.tag2paths[i].append(parent)  # add current dir to index of that extension
    # TODO don't use adds reference? never used?
    # 3.  prepare recursion
    newtags = [t for t in ((tags[:-2] if len(tags) >=2 and caseNormalize(_.tagdirs[tags[-2]]) == _.tagdirs[tags[-1]] else tags[:-1]) if ignore else tags)]  # if ignore: propagate all tags except current folder name variant(s) to children TODO reuse "tags" reference from here on instead
    children = (f[len(aDir) + (1 if not aDir.endswith(SLASH) else 0):] for f in filter(isdir, (os.path.join(aDir, ff) for ff in files)))  # only consider folders. ternary condition is necessary for the backslash in "D:\" = "D:/", a Windows root dir special case
    for child in children:  # iterate sub-folders using above generator expression
      idxs = []  # first element in "idx" is next index to use in recursion (future parent, current child), no matter if true-case or case-normalized mode is selected
      # 3a. add sub-folder name to "tagdirs" and "tagdir2parent"
      if not (ON_WINDOWS and _.cfg.reduce_case_storage):  # Windows: only store true-case if not reducing storage, Linux: always store
        if _.log >= 1: debug("Storing true-case folder name %r for %r" % (child, _.getPath(parent, {})))
        idxs.append(len(_.tagdirs))  # for this child folder, add one new element at next index's position (no matter if name already exists in index (!), because it always has a different parent). it's not a fully normalized index, more a tree structure
        _.tagdirs.append(intern(child))  # now add the child folder name (duplicates allowed, because we build the tree structure here)
        _.tagdir2parent.append(parent)  # at at same index as tagdirs "next" position
        assert len(_.tagdirs) == len(_.tagdir2parent)
      iname = caseNormalize(child)
      if iname != child and (ON_WINDOWS or (not _.cfg.reduce_case_storage)):  # Linux: only store case-normalized if not reducing storage, Windows: always store
        if _.log >= 1: debug("Storing case-normalized folder name %r for %r" % (iname, _.getPath(parent, {})))
        idxs.append(len(_.tagdirs))  # for this child folder, add one new element at next index's position (no matter if name already exists in index (!), because it always has a different parent). it's not a fully normalized index, more a tree structure
        _.tagdirs.append(intern(iname))  # now add the child folder name
        _.tagdir2parent.append(parent)  # at at same index as tagdirs
        assert len(_.tagdirs) == len(_.tagdir2parent)
      del iname  # prior to recursion
      if _.log >= 2: debug("Tagging folder %r with tags +<%s> *<%s>" % (child, ",".join([_.tagdirs[x] for x in (newtags + idxs)]), ",".join([_.tags[x] for x in adds])))  # TODO can contain root (empty string)
      # 3b. recurse
      if not ignore:
        for tag in newtags + idxs: _.tagdir2paths[_.tagdirs.index(_.tagdirs[tag])].extend(idxs)  # add subfolder reference(s) for all collected tags from root to child to tag name
      trace(repr((newtags, _.tagdirs, _.tagdir2paths)))
      _._walk(aDir + SLASH + child, idxs[0], newtags + ([] if ignore else idxs))  # as parent, always use original case index, not case-normalized one (unless configured to reduce space)

  def mapTagsIntoDirsAndCompressIndex(_):
    ''' After recursion finished, map extensions or manually set tags into the tagdir structure to save space. '''
    if _.log >= 1: info("Mapping tags into index")
    for itag, tag in enumerate(_.tags):
      idx = lindex(_.tagdirs, tag, appendandreturnindex)  # get (first) index in list, or append if not found yet
      _.tagdir2paths[idx].extend(_.tag2paths[itag])  # tag2paths contains true parent folder index from _.tagdirs
    rm = [tag for tag, dirs in dictviewitems(_.tagdir2paths) if len(dirs) == 0]  # finding entries that were emptied due to ignores
    for r in rm:
      del _.tagdir2paths[r]
      if _.log >= 2: debug("Removing no-children tag %s" % _.tagdirs[r])  # remove empty lists from index (was too optimistic, removed by ignore or skip)
    if _.log >= 1: debug("Removed no-children tags from index for %d tags" % len(rm))
    found = 0
    for tag, dirs in dictviewitems(_.tagdir2paths):
      _l = len(_.tagdir2paths[tag])  # get size of mapped paths
      _.tagdir2paths[tag] = frozenset(dirs)  # remove duplicates
      found += len(_.tagdir2paths[tag]) < _l  # check any removed TODO replace set by list makes test addremove pass, but should not
    if found > 0: info("Removed duplicates from index for %d tags" % found)
    return len(rm)

  def unwalk(_, idx = 0, path = ""):
    ''' Walk entire tree from index (slow but proof of correctness). '''
    if _.log >= 2: debug("unwalk " + str((idx, path)))
    tag = _.tagdirs[idx]  # name of head element
    children = (f[0] for f in filter(lambda a: a[1] == idx and a[0] != idx, dictviewitems(_.tagdir2parent)))  # using generator expression
    if _.log >= 1: info(path + tag + SLASH)
    for child in children: _.unwalk(child, path + tag + SLASH)

  def getPath(_, idx, cache):
    ''' Return one root-relative path for the given index idx by recursively going through index-> name mappings. '''
    assert idx < len(_.tagdirs) and idx >= 0  # otherwise hell on earth
    found = cache.get(idx, None)
    if found is not None: return found
    if idx == 0: return ""  # root path special case
    parent = _.tagdir2parent[idx]  # get parent index
    found = dictget(cache, parent, lambda: _.getPath(parent, cache))  # recursive folder name resolution
    new = found + SLASH + _.tagdirs[idx]
    cache[idx] = new
    return new

  def getPaths(_, ids, cache = {}):
    ''' Returns generator for all paths for the given list of ids, using intermediate caching. '''
    return (_.getPath(i, cache) for i in ids)

  def removeIncluded(_, includedTags, excludedPaths):
    ''' Return those paths, that have no manual tags or from tags from inclusion list; subtract from the exclusion list to reduce set of paths to ignore.
        includedTags: search tags (no extensions, no globs) to keep included: will be removed from the excludedPaths list returned
        excludedPaths: the paths not found in the index, scheduled for removal
        there is no need to check all tags in configuration, because they could be inclusive or exclusive, and are on per-file basis. the existence of a tag suffices for retaining paths
    '''
    if _.log >= 2: debug("removeIncluded " + str((includedTags, excludedPaths)))
    retain = []
    for path in excludedPaths:
      conf = _.cfg.paths.get(path, {})
      if len(conf) == 0: retain.append(path); continue  # keep for removal, because no inclusion information available
      tags = conf.get(TAG, [])
      if len(tags) == 0:
        froms = conf.get(FROM, [])
        if len(froms) == 0: retain.append(path); continue  # keep for removal, no manual tags in mapped config
        retainit = True
        for other in froms:
          conf2 = _.cfg.paths.get(other, {})
          if len(conf2) == 0:  # the mapped folder has no manual tags specified
#            error("Encountered missing FROM source config in '%s': '%s'; please repair" % (path, other))  # TODO can be removed? what to do here?
            retainit = True  # TODO is this correct? we don't know anything about the mapped files?
          tags2 = conf2.get(TAG, [])
          if len(tags2) == 0: break  # found from config, but has no tags: no need to consider for removal from removes -> retain
          for value2 in tags2:
            tg, inc, exc = value.split(SEPA)
            if tag in includedTags: retainit = False; break
        if retainit: retain.append(path)
        continue  # removed from removal, go to next path
      retainit = True
      for value in tags:
        tg, inc, exc = value.split(SEPA)
        if tg in includedTags: retainit = False; break  # removed from retained paths
      if retainit: retain.append(path)
    return set(retain)

  def findFolders(_, include, exclude = [], returnAll = False):
    ''' Find intersection of all directories with matching tags.
        include: list of cleaned tag names to include
        exclude: list of cleaned tag names to exclude
        returnAll: shortcut flag that simply returns all paths from index
        returns: list of folder paths
    '''
    if _.log >= 2: debug("findFolders +<%s> -<%s> ALL=%s" % (",".join(include), ",".join(exclude), "Yes" if returnAll else "No"))
    idirs, sdirs = dictget(dictget(_.cfg.paths, '', {}), IGNORED, []), dictget(dictget(_.cfg.paths, '', {}), SKIPD, [])  # get lists of ignored or skipped paths
    currentPathInGlobalIgnores = lambda path: (path[path.rindex(SLASH) + 1:] if path != '' else '') in idirs
    partOfAnyGlobalSkipPath = lambda path: any([wrapExc(lambda: re.search(r"((^%s$)|(^%s/)|(/%s/)|(/%s$))" % ((skp,) * 4), path).groups()[0].replace("/", "") == skp, False) for skp in sdirs])
    anyParentIsSkipped = lambda path: any([SKIP in dictget(_.cfg.paths, SLASH.join(path.split(SLASH)[:p + 1]), {}) for p in range(path.count(SLASH))])
    _.allPaths = wrapExc(lambda: _.allPaths, lambda: set(_.getPaths(list(reduce(lambda a, b: a | set(b), dictviewvalues(_.tagdir2paths), set())))))
    if returnAll or len(include) == 0:
      if _.log >= 2: debug("Building list of all paths")
      alls = [path for path in _.allPaths if not currentPathInGlobalIgnores(path) and not partOfAnyGlobalSkipPath(path) and not anyParentIsSkipped(path) and IGNORE not in dictget(_.cfg.paths, path, {})]  # all existing paths except globally ignored/skipped paths TODO add marker file logic below TODO move checks fo _.allPaths cache
      alls = [a for a in alls if isdir(_.root + os.sep + a)]
      if _.cfg.log >= 2: debug("findFolders: " + str(alls))
      if returnAll: return alls
    paths, first, cache = set() if len(include) > 0 else alls, True, {}
    for tag in include:  # positive restrictive matching
      if _.log >= 2: info("Filtering paths by inclusive tag '%s'" % tag)
      if isglob(tag):
        if DOT in tag:  # [:-1]:  # contains an extension in non-final position (in final should not be possible)
          ext = normalizer.filenorm(tag[tag.index(DOT):])
          if isglob(ext):  # glob search with glob extension
            new = reduce(lambda a, b: a | set(_.getPaths(_.tagdir2paths[_.tagdirs.index(b)], cache)), fnmatch.filter(_.tagdirs, ext), set())  # filters all extensions in index by glob (e.g. .c??). update returns updated same object instead of a | set() or a.union(set())
          else:  # glob search with fixed extension
            new = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(ext)], cache)), lambda: set())  # exception is unknown index in getPath()
        else:  # no extension: cannot filter folder; ignore glob altogether
          warn("Preliminarily ignoring glob <%s> while filtering folders (no file extension in glob)" % tag)
          new = set()  # ignore glob in folder filtering altogether
      elif tag.startswith(DOT):  # explicit file extension filtering
        new = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(tag)], cache)), lambda: set())  # directly from index TODO same as below
      else:  # no glob, no extension: can be tag or file name
        new = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(tag)], cache)), lambda: set())  # directly from index
      if first: paths = new
      else: paths.intersection_update(new)
      first = False
    for tag in exclude:  # we don't excluded globs here, because we would also exclude potential candidates (because index is over-specified)
      if _.log >= 2: info("Filtering paths by exclusive tag '%s'" % tag)
      potentialRemove = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(tag)], cache)), lambda: set())  # can only be removed, if no manual tag/file extension/glob in config or "from"
      new = _.removeIncluded(include, potentialRemove)  # remove paths with includes from "remove" list (adding back...)
      if first:  # start with all all paths, except determined excluded paths
        paths = set(_.getPaths(list(reduce(lambda a, b: a | set(b), dictviewvalues(_.tagdir2paths), set())))) - new  # get paths from index data structure
      else:
        paths.difference_update(new)  # reduce found paths
      first = False
    # Now convert to return list (!)
    paths = [p for p in paths if not currentPathInGlobalIgnores(p) and not partOfAnyGlobalSkipPath(p)]  # check "global ignore dir" condition, then check on all "global skip dir" condition, which includes all sub folders as well TODO remove filtering, as should be reflected by index anyway (in contrast to above getall?))
    if not _.cfg.case_sensitive:  # eliminate different case writings
      caseMapping = dd()
      for path in paths: caseMapping[caseNormalize(path)].append(path)
      paths[:] = [l[1] if len(l) > 1 else l[0] for l in (list(sorted(ll)) for ll in caseMapping.values())]  # first entry [0] is always all-uppercase (lower ASCII character than lower case), therefore order is always ABC, Abc (abC, abc), and no more than two entries are expected
    paths[:] = [p for p in paths if isdir(_.root + os.sep + p)]
    if _.cfg.log >= 2: debug("findFolders: " + str(paths))
    return paths

  def findFiles(_, aFolder, poss, negs = [], force = False):
    ''' Determine files for the given folder.
        aFolder: folder to filter files in
        poss: (potentially case-normalized) positive tags, file extensions, file names or glob patternss to consider, or an empty list (falls back to considering all files to ensure negative tags work at all)
        negs: negative assertions, same options as for 'poss'
        force: don't perform true file existence checks, might return false positives for special files or directories (usually no problem)
        returns: 2-tuple (list [filenames] for given folder, bool: has a skip marker file - don't recurse into)
    '''
    if _.log >= 2: debug("findFiles " + str((aFolder, poss, negs, force)))
    inPath = set(safeSplit(aFolder, SLASH))
    if not _.cfg.case_sensitive: inPath.update(set([caseNormalize(f) for f in safeSplit(aFolder, SLASH)]))  # all path elements to remove from positive tags
    remainder = set([p for p in poss if (p if _.cfg.case_sensitive else caseNormalize(p)) not in inPath])  # split folder path into tags and remove from remaining criteria, considering case-sensitivity unless deselected or case same as normalized variant
    if _.log >= 1: info("Filtering folder %s%s" % (aFolder, (" by remaining tags: " + ((", ".join(remainder)) if len(remainder) > 0 else '') + DOT)))
    conf = _.cfg.paths.get(aFolder, {})  # if empty, files remain unchanged, we return all
    folders = [aFolder] + [pathnorm(os.path.abspath(os.path.join(_.root + aFolder, mapped)))[len(_.root):] if not mapped.startswith(SLASH) else os.path.join(_.root, mapped) for mapped in conf.get(FROM, [])]  # list of original and all mapped folders
    if _.log >= 1 and len(folders) > 1: info("Mapped folders to check: %s" % os.pathsep.join(folders[1:]))

    allfiles, willskip = set(), False  # contains files from current or mapped folders (without path, since "mapped", but could have local symlink - TODO
    for folder in folders:
      if _.log >= 1: debug("Checking %sfolder %s" % ("root " if folder == "" else '', folder))
      files = set(wrapExc(lambda: [f for f in listdir(_.root + folder) if isfile(_.root + folder + SLASH + f)], []))  # all from current folder, potential excecption: folder name (unicode etc.)
      if IGNFILE in files: continue  # skip is more difficult to handle than ignore, cf. return tuple here and code in tp.find() with return
      if folder == aFolder and SKPFILE in files:
        willskip = True
        if _.log >= 1: info("Skip %s due to local marker file" % folder)
        continue  # return ([], True)  # TODO semantics: handle mapped folder even for skip local marker?
      caseMapping = {caseNormalize(f): f for f in files}  # from noramlized to real names
      if not _.cfg.case_sensitive: files.update(set(caseMapping.keys()))  # add case-normalized file names to enable matching
      conf = _.cfg.paths.get(folder, {})  # if empty, files remains unchanged, we return all of them regularly
      if _.log >= 2: debug("Conf used for %s'%s': %s" % ("mapped folder " if folder != aFolder else "", folder, str(conf)))
      tags = conf.get(TAG, [None])
      keep = set(files)  # start with all to keep, then restrict set

      for tag in remainder:  # for every tag remaining to filter, we check if action on current files is necessary
        if tag.startswith(DOT): keep.intersection_update(set([f for f in files if f[-len(tag):] == tag])); continue  # filter by file extension
        elif isglob(tag) or tag in files: keep.intersection_update(set(fnmatch.filter(files, tag))); continue  # filter globs and direct file names
        found = False  # marker for the case that none of the provided extension/glob/file tags matched: check tags in configuration
        for value in tags:
          if value is None: keep = set(); found = True; break  # None means no config found, therefore due to remaining provided tags we don't match any for this (mapped) folder
          tg, inc, exc = value.split(SEPA)  # tag name, includes, excludes
          if tg == tag:  # mark that matches the find criterion: we can remove all others!
            found = True
            news = set(files)  # collect all files subsumed under the tag that should remain
            for i in safeSplit(inc):  # if tag manually specified, only keep those included files
              if isglob(i): news.intersection_update(set(fnmatch.filter(files, i)))  # is glob
              else: news = set([i] if i in files and (force or isfile(_.root + folder + SLASH + i)) else [])  # is a file: add only if exists, otherwise add nothing
            for e in safeSplit(exc):  # if tag is manually specified, exempt these files (add back)
              if isglob(e): news.update(set(fnmatch.filter(news, e)))
              else: news.discard(e)  # add file to keep
            keep.intersection_update(news)
            break
        if not found: keep = set()  # if no remaining tag matched

      remo = set()  # start with none to remove, than enlarge set
      for tag in negs:
        if tag.startswith(DOT): remo.update(set([f for f in files if f[-len(tag):] == tag])); continue  # filter by file extension
        elif isglob(tag) or tag in files: remo.update(set(fnmatch.filter(files, tag))); continue  # filter globs and direct file names
        found = False  # marker for the case that none of the provided extension/glob/file tags matched: check tags in configuration
        for value in tags:
          if value is None: remo = set(); found = True; break  # None means no config found, no further matching needed
          tg, inc, exc = value.split(SEPA)
          if tg == tag:
            found = True
            news = set()  # collect all file that should be excluded
            for i in safeSplit(inc):
              if isglob(i): news.update(set(fnmatch.filter(files, i)))  # is glob
              else: news.update(set([i] if i in files and (force or isfile(_.root + folder + SLASH + i)) else []))  # is no glob: add, only if exists
            for e in safeSplit(exc):
              if isglob(e): news.difference_update(set(fnmatch.filter(news, e)))
              else: news.add(e)  # add file to remove
            remo.update(news)
            break
      files.intersection_update(keep)
      files.difference_update(remo)
      if _.log >= 2: debug("Files for folder '%s': %s (Keep/Remove: <%s>/<%s>)" % (folder, ",".join(files), ",".join(keep), ",".join(remo)))
      allfiles.update(files)
    result = ([ff for ff in set([caseMapping.get(f, f) for f in allfiles])], willskip)  # In contrast to findFolder, no file existence checks (necessary)
    if _.log >= 2: debug("findFiles: " + str(result))
    return result


if __name__ == '__main__':
  ''' This code is just for testing. Run in svn/projects by tagsplorer/lib.py '''
  if len(sys.argv) > 1 and sys.argv[1] == '--test': import doctest; doctest.testmod()
