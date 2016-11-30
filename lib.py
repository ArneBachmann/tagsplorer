# Tagging library to augment OS folder structures by tags (and queries over tags)
# This code is written for maximum OS and Python version interoperability and should run fine on any Linux, Windows, Python2, Python3.

# Main idea: folder names are considered tags (unless marked otherwise) to make everything backwards compatible with normal folder-tree metaphor.
#   single files and globs can additionally be tagged in any folder (using a central configuration file, which also defines the root directory of all files indexed)
#   folder contents can virtually be mapped into other folders (creating an augmented view and retaining any additional tags from the mapped folder)
# Search Algorithm:
#   The index maps tags to folders, with the risk for false positives (optimistic index, including manual tag settings and tags mapped from other folders, also potentially ignoring case and adding file extension information)
#     After determination of potential folders, the current folder contents are filtered by potential further tags, and inclusive or exclusive file name patterns.

# System integration:
#   Windows allows Explorer extensions with additonal context menu actions to access the tag functionality. Existing load/save dialogs cannot be extended for safety reasons. Command line operation may still be very useful, and stand-alone GUIs can be created from this library easily, either as a thin layer to CRUD operations or in a more active design that keeps the index in memory and serves as a quick starter app.

# Design decisions:
#   Different implementations and replacements for the built-in config parser have been tested; there is, however, no version that both a) allows reading values for duplicate keys, and b) is fully compatible between Python 2 and 3. The alternative of using JSON may be considered, albeit worse to edit by humans and potentially slower (profiling pending).
#   The index itself is designed to be both low on memory consumption and fast to load from disk. After profiling compression vs. no compression, the level 2 zlib approach delivered optimal results on resource restricted and office devices (with only minimal difference in compacted file size even to bz2 level 9, but almost as fast as pure uncompressed object pickling (which was faster than any bz2 level)).
#   For the skip-folder logic, we could use an "index the folder, but don't recurse into sub folders" instead, but we prefer skipping the entire current folder, which is more flexible.
#   All tags are indexed in a case depending on the global configuration parameter case_sensitive (because index is recreated on every change anyway), which has a per-OS default but can be set manually.

import collections, copy, fnmatch, os, sys, time, zlib

DEBUG = 3; INFO = 2; WARN = 1; ERROR = 0
LOG = INFO # select maximum log level

# Version-dependent imports
if sys.version_info.major >= 3:
  intern = sys.intern # not global anymore
  import pickle
  from functools import reduce # not built-in
  from sys import intern
  dictviewkeys, dictviewvalues, dictviewitems = dict.keys, dict.values, dict.items # returns generators in Python 3, operating on underlying data
  def xreadlines(fd): return fd.readlines()
  debug = eval('lambda s: print("Debug:   " + s, file = sys.stderr)') if LOG >= DEBUG else lambda _: None
  info = eval('lambda s:  print("Info:    " + s, file = sys.stderr)') if LOG >= INFO else lambda _: None
  warn = eval('lambda s:  print("Warning: " + s, file = sys.stderr)') if LOG >= WARN else lambda _: None
  error = eval('lambda s: print("Error:   " + s, file = sys.stderr)') if LOG >= ERROR else lambda _: None
else: # is Python 2
  import cPickle as pickle
  dictviewkeys, dictviewvalues, dictviewitems = dict.iterkeys, dict.itervalues, dict.iteritems
  def xreadlines(fd): return fd.xreadlines()
  debug, info, warn, error = [lambda _: None] * 4
  if LOG >= DEBUG:
    def debug(s): print >> sys.stderr, "Debug:   ", s
  if LOG >= INFO:
    def info(s):  print >> sys.stderr, "Info:    ", s
  if LOG >= WARN:
    def warn(s):  print >> sys.stderr, "Warning: ", s
  if LOG >= ERROR:
    def error(s): print >> sys.stderr, "Error:   ", s
# OS-dependent definitions
filenorm = None # filenorm function undefined, updated in config object to 
globmatch = None # dito


# Constants
PICKLE_VERSION = 2 # since Python 3 comes with different protocol, we pin the protocol here
CONFIG =  ".tagsplorer.cfg" # main tag configuration file
INDEX =   ".tagsplorer.idx" # index file (re-built when timestamps differ)
SKPFILE = ".tagsplorer.skp" # marker file (can also be configured in configuration instead) 
IGNFILE = ".tagsplorer.ign" # marker file (dito)
IGNORE, SKIP, TAG, FROM, SKIPD, IGNORED, GLOBAL = intern("ignore"), intern("skip"), intern("tag"), intern("from"), intern("skipd"), intern("ignored"), intern("global") # can be augmented to excludef for files
SEPA, SLASH, DOT = intern(";"), intern("/"), intern(".")

# Functions
def wrapExc(func, otherwise = lambda: None):
  ''' Wrap an exception and compute return value lazily if an exception is raised. Useful for recursive function application.
  >>> print(wrapExc(lambda: 1))
  1
  >>> print(wrapExc(lambda: 1 / 0))
  None
  '''
  try: return func()
  except: return otherwise()

def lappend(lizt, elem): lizt.append(elem); return lizt  # functional list.append that returns self afterwards to avoid new array creation (lizt + [elem])

def lindex(list, value, otherwise = lambda list, value: None):
  ''' List index function with lazy computation if not found.
  >>> print(lindex([1, 2], 2))
  1
  >>> print(lindex([], 1))
  None
  '''
  return wrapExc(lambda: list.index(value), lambda: otherwise(list, value)) # ValueError

def consec(lambdas):
  ''' Consecutive function calls.
  >>> print(consec([lambda a, b: sys.stdout.write(str(a * b + 1) + ","), (lambda a, b: a * b / 2) if sys.version_info.major == 2 else (lambda a, b: a * b // 2)])(2, 3))
  7,3
  '''
  def _consec(*args, **kwargs):
    for _lambda in lambdas: ret = _lambda(*args, **kwargs)
    return ret
  return _consec

def splitCrit(lizt, pred):
  ''' Split lists by a binary predicate.
  >>> print(splitCrit([1,2,3,4,5], lambda e: e % 2 == 0))
  ([2, 4], [1, 3, 5])
  '''
  return reduce(lambda acc, next: (lappend(acc[0], next), acc[1]) if pred(next) else (acc[0], lappend(acc[1], next)), lizt, ([], []))
def isdir(f): return os.path.isdir(f) and not os.path.islink(f) and not os.path.ismount(f)
def isfile(f): return wrapExc(lambda: os.path.isfile(f) and not os.path.ismount(f) and not os.path.isdir(f), lambda: False) # on error "no file"
norm = (lambda s: s.replace("\\", SLASH)) if sys.platform == 'win32' else (lambda s: s)
appendandreturnindex = consec([lambda l, v: l.append(v), lambda l, v: len(l) - 1])
def isunderroot(root, folder): return os.path.commonprefix([root, folder]).startswith(root)
def isglob(f): return '*' in f or '?' in f
def getTs(): return int(time.time() * 10.)
def safeSplit(s, d): return s.split(d) if s != '' else []
def safeRSplit(s, d): return s[s.rindex(d) + 1:] if d in s else s
def dd(tipe = list): return collections.defaultdict(tipe)
def dictget(dikt, key, default):
  ''' Improved dict.get(key, default).
  >>> a = {}; b = a.get(0, 0); print((a, b)) # normal dict get
  ({}, 0)
  >>> a = {}; b = dictget(a, 0, 0); print((a, b)) # improved dict get
  ({0: 0}, 0)
  >>> a = {}; b = dictget(a, 0, lambda: 1); print((a, b))
  ({0: 1}, 1)
  '''
  try: return dikt[key]
  except: dikt[key] = ret = default() if callable(default) else default; return ret


# Classes
class ConfigParser(object):
  ''' Much simplified config file (ini file) reader. No line continuation, no colon separation, no symbolic replacement, no comments, no empty lines. '''
  def __init__(_): _.sections = collections.OrderedDict() # to assure same order on every load/write operation
  def load(_, fd):
    ''' Read from file object to enable reading from arbitrary data source and position.
        returns global config
    '''
    title = None; section = dd() # this dict initializes any missing value with an empty list
    for line in xreadlines(fd):
      line = line.strip() # just in case of incorrect formatting
      if line.startswith('['): # new section detected: first store last section
        if len(section) > 0: _.sections[title] = section # OLD: and title is not None
        title = line[1:-1]; section = dd() # default-dictionary of (standard) type map
      elif line != '':
        try:
          idx = line.index('=') # try to parse
          key, value = line[:idx], line[idx+1:] # HINT: was .lower() and .rstrip(), but when reading/writing only via this script's API there's no need for that
          if key in [TAG, FROM] and value != '':
            section[intern(key)].append(intern(value)) # this dict allows several values per key
          elif key in [IGNORE, SKIP] and key not in section:
            section[intern(key)] = None # only keep key instead of default-appending empty string
          elif title == "" and key in [SKIPD, IGNORED, GLOBAL] and value != '':
            section[intern(key)].append(intern(value)) # global dir skip or ignore pattern, or global config setting
          else: warn("Encountered illegal key <%s>. Skipping entry." % key)
        except: warn("Key with no value for illegal key %s" % repr(line))
      else: break # an empty line terminates file
    if len(section) > 0: _.sections[title] = section # last store OLD:  and title is not None
    return { k.lower(): v if v.lower() not in ("true", "false") else v.lower().strip() == "true" for k, v in (wrapExc(lambda: kv.split("=")[:2], lambda: (kv, None)) for kv in _.sections.get("", {}).get(GLOBAL, [])) } # return global config map for convenience
  def store(_, fd, parent = None): # write to file object to alloyw for additional contents
    if parent is not None: # store parent's properties
      if "" not in _.sections: _.sections[intern("")] = dd()
      _.sections[""][GLOBAL] = sorted(["%s=%s" % (k.lower(), str(parent.__dict__[k])) for k, v in (kv.split("=")[:2] for kv in _.sections.get("", {}).get(GLOBAL, []))]) # store updated config
    for title, _map in dictviewitems(_.sections): # in added order
      fd.write("[%s]\n" % (title))
      for key, values in sorted(_map.items()): # no need for iteritems, as supposedly small (max. size = 4)
        if values is None: fd.write("%s=\n" % (key.lower())) # skip or ignore
        else:
          for value in sorted(values): fd.write("%s=%s\n" % (key.lower(), value)) # tag or from
    fd.write("\n") # termination of config contents


class Config(object):
  ''' Contains all tag configuration. '''
  def __init__(_):
    _.log = 0 # level
    _.paths = {} # map from relative dir path to dict of marker -> [entries]
    _.case_sensitive = sys.platform != 'win32' # dynamic default unless specified in the config file
    global filenorm, globmatch # modify global function reference
    filenorm = (lambda s: s) if _.case_sensitive else str.lower
    globmatch = fnmatch.fnmatch if _.case_sensitive else lambda f, g: fnmatch.fnmatch(f.lower(), g.lower()) # define tag matching logic
  
  def load(_, filename, index_ts = None):
    ''' Load configuration from file, if timestamp differs from index' timestamp. '''
    with open(filename, 'r') as fd: # HINT: don't use rb, because in Python 3 this return bytes objects
      if _.log >= 1: info("Comparing configuration timestamp for " + filename)
      timestamp = float(fd.readline().rstrip())
      if (index_ts is not None) and round(100 * timestamp) == round(100 * index_ts):
        if _.log >= 1: info("Skip loading configuration, because index is up to date")
        return False # no skew detected, allow using old index' interned configuration ("self" will be discarded)
      if _.log >= 1: info("Loading configuration from file system" + ("" if index_ts is None else " because index is outdated"))
      cp = ConfigParser(); dat = cp.load(fd); _.__dict__.update(dat)
      _.paths = cp.sections
      global filenorm, globmatch # modify global function reference
      filenorm = (lambda s: s) if _.case_sensitive else str.lower
      globmatch = fnmatch.fnmatch if _.case_sensitive else lambda f, g: fnmatch.fnmatch(f.lower(), g.lower()) # update tag matching logic
      return True

  def store(_, filename, timestamp):
    ''' Store configuration to file, prepending data by the timestamp. '''
    cp = ConfigParser(); cp.sections = _.paths
    with open(filename, "w") as fd: # don't use wb for Python 3 compatibility
      if _.log >= 1: info("Writing configuration to " + filename)
      fd.write("%d\n" % timestamp); cp.store(fd, parent = _)
    if _.log >= 1: info("Wrote %d config bytes" % os.stat(filename)[6])
  
  def addTag(_, folder, pattern, poss, negs, force = False):
    ''' For given  folder, add poss and negs tags to file or glob pattern.
        folder: folder to operate on (relative to root)
        pattern: the file or glob pattern to add to the configuration
        poss: inclusive tags or globs to add
        negs: exclusive tags or globs to add
        force: allows
        returns: modified?
    '''
    conf = dictget(_.paths, folder, {}) # creates empty config entry if it doesn't exist
    is_glob = isglob(pattern)
    pname = "Glob" if is_glob else "File"
    keep_pos, keep_neg = dd(), dd()

    for tag in poss + negs:
      keep = True # marker
      for line in conf.get(TAG, []):
        tg, inc, exc = line.split(SEPA)
        if tg == tag: # if positive tag specified in configuration
          for i in safeSplit(inc, ","):
            if isglob(i) and not is_glob and globmatch(pattern, i): # is file matched by inclusive glob
              keep = force
              (warn if force else error)("File '%s' already included by glob pattern '%s' for tag '%s'%s" % (pattern, i, tag, "" if force else ", skipping"), file = sys.stderr)
              break
            elif i == pattern: # file/glob already contained
              keep = False; error("%s '%s' already%s specified for tag '%s'%s" % (pname, pattern, " inversely" if tag in negs else "", tag, "" if force else ", skipping")); break
          for e in safeSplit(exc, ","):
            if isglob(e) and not is_glob and globmatch(pattern, e): # is file matched by exclusive glob
              keep = force
              (warn if force else error)("File '%s' excluded by glob pattern '%s' for tag '%s'%s" % (pattern, e, tag, "" if force else ", skipping"))
              break
            elif e == pattern: # file/glob already contained
              keep = False; error("%s '%s' already%s specified for tag '%s'%s" % (pname, pattern, " inversely" if tag in poss else "", tag, "" if force else ", skipping")); break
          break # because tag was found
      if keep: (keep_pos if tag in poss else keep_neg)[tag].append(pattern)

    # Now really add new patterns to config
    modified = list(keep_pos.keys()) + list(keep_neg.keys())
    for tag in modified:
      entry = dictget(conf, TAG, [])
      missing = True
      for i, line in enumerate(entry):
        tg, inc, exc = line.split(SEPA)
        if tg == tag: # found: augment existing entry
          entry[i] = "%s;%s;%s" % (tag, ",".join(safeSplit(inc, ",") + keep_pos.get(tag, [])), ",".join(safeSplit(exc, ",") + keep_neg.get(tag, [])))
          missing = False # tag already exists
          break # line iteration
      if missing: entry.append("%s;%s;%s" % (tag, ",".join(keep_pos.get(tag, [])), ",".join(keep_neg.get(tag, [])))) # if new: create entry
    return len(modified) > 0
 

class Indexer(object):
  ''' Main index creation. Goes through all recursive file paths and indexes the folder tags. Addtionally, tags for single files or globs, and those mapped by the FROM tag are included in the index. File-specific tags are only determined during the find phase. '''
  def __init__(_, startDir):
    _.log = 0 # log level
    _.compressed = 2 # pure pickling is faster than any bz2 compression, but zlib level 2 had best size/speed combination. if changed to 0, index needs to be re-created (or removed) manually
    _.timestamp = 1.23456789 # for comparison with configuration timestamp
    _.cfg = None # reference to latest corresponding configuration
    _.root = norm(os.path.abspath(startDir))
    _.tagdirs = [] # array of tags (plain dirnames and manually set tags (not represented in parent)
    _.tagdir2parent = {} # index of dir -> index of parent to represent tree structure (exclude folder links)
    _.tagdir2paths = dd() # dirname index (first occurrence?) to [all path indices containing dirname]
  
  def load(_, filename, ignore_skew = False, recreate_index = True):
    ''' Load a pickled index into memory. Optimized for speed. '''
    with open(filename, "rb") as fd:
      if _.log >= 1: info("Reading index from " + filename)
      c = pickle.loads(zlib.decompress(fd.read()) if _.compressed else fd.read())
      _.cfg, _.timestamp, _.tagdirs, _.tagdir2parent, _.tagdir2paths = c.cfg, c.timestamp, c.tagdirs, c.tagdir2parent, c.tagdir2paths
      cfg = Config(); cfg.log = _.log # partially read existing configuration to compare with unpickled version, or read fully if timestamp differs
      if (ignore_skew or cfg.load(os.path.join(os.path.dirname(os.path.abspath(filename)), CONFIG), _.timestamp)) and recreate_index:
        if _.log >= 1: info("Recreating index considering configuration")
        _.walk() # re-create this index
        _.cfg = cfg
        _.store(filename)

  def store(_, filename, config_too = True):
    ''' Persist index in a file, including currently active configuration. '''
    with open(filename, "wb") as fd:
      _.timestamp = getTs() # assign new date
      if _.log >= 1: info("Writing index to " + filename)
      fd.write(zlib.compress(pickle.dumps(_, protocol = PICKLE_VERSION), _.compressed) if _.compressed else pickle.dumps(_, protocol = PICKLE_VERSION)) # WARN: make sure not to have callables on the pickled objects!
      if config_too:
        if _.log >= 1: info("Updating configuration to match new index timestamp")
        _.cfg.store(os.path.join(os.path.dirname(os.path.abspath(filename)), CONFIG), _.timestamp) # update timestamp in configuration
    if _.log >= 1: info("Wrote %d index bytes (%d tag entries -> %d mapped path entries)" % (os.stat(filename)[6], len(_.tagdirs), sum([len(p) for p in _.tagdir2paths.values()])))
  
  def walk(_, cfg = None):
    ''' Build index. cfg: if set, use that configuration instead of contained one. '''
    if _.log >= 1: info("Walking folder tree")
    if cfg is not None: _.cfg = cfg
    if _.cfg is None: error("No configuration loaded. Cannot walk folder tree"); return
    _.tagdirs.append("") # this is root
    _.tagdir2parent[0] = 0 # marker for root (the only self-reference)
    _.tags, _.tag2paths = [], dd() # temporary structures for manual tag and extension mapping, and respective paths
    _._walk(_.root)
    tagdirs = len(_.tagdirs)
    _.mapTagsIntoDirs() # unified with folder entries for simple lookup and filtering
    tags = len(_.tags)
    del _.tags, _.tag2paths # remove temporary structures
    rm = [tag for tag, dirs in dictviewitems(_.tagdir2paths) if len(dirs) == 0] # finding entries that were emptied due to ignores
    for r in rm: _.tagdir2paths.pop(r) # remove empty lists from index (was too optimistic, removed by ignore or skip)
    if _.log >= 1: info("Indexed %d folders and %d tags/globs/extensions." % (tagdirs, tags))
  
  def _walk(_, aDir, parent = 0, tags = []):
    ''' Recursive walk through folder tree.
        Adds all directories as tags unless ignored; considers manually set configuration
        aDir: path relative to root (always with preceding and no trailing forward slash)
    '''
    if _.log >= 2: print(aDir)
    
    # First check folder's configuration
    skip, ignore = False, False # marks dir as "no recursion"/"no taggin" respectively
    adds = [] # additional tags for single files in this folder, not to be promoted to sub-directories
    marks = _.cfg.paths.get(aDir[len(_.root):], {})
    if SKIP in marks or (aDir != '' and aDir[aDir.rindex(SLASH) + 1:] in dictget(dictget(_.cfg.paths, '', {}), SKIPD, [])):
      if _.log >= 1: info("  Skip %s%s" % (aDir, '' if SKIP in marks else ' due to global skip setting'))
      return # completely ignore sub-tree
    elif IGNORE in marks or (aDir != '' and aDir[aDir.rindex(SLASH) + 1:] in dictget(dictget(_.cfg.paths, '', {}), IGNORED, [])):
      ignore = True # ignore this directory as tag, don't index contents
      if _.log >= 1: info("  Ignore %s%s" % (aDir, '' if IGNORE in marks else ' due to global ignore setting'))
    else:
      if TAG in marks:
        for t in marks[TAG]:
          if _.log >= 1: info("  Tag '%s' in %s" % (t, aDir))
          tag, pos, neg = t.split(SEPA) # tag name, includes, excludes
          i = lindex(_.tags, tag, appendandreturnindex)
          adds.append(i); _.tag2paths[i].append(parent)
      if FROM in marks: # use tags from that folder to include here
        for f in marks[FROM]:
          if _.log >= 1: info("  Map from %s into %s" % (f, aDir))
          other = norm(os.path.abspath(os.path.join(aDir, f))[len(_.root):] if not f.startswith(SLASH) else os.path.join(_.root, f))
          _marks = _.cfg.paths.get(other, {})
          if TAG in _marks:
            for t in _marks[TAG]:
              tag, pos, neg = t.split(SEPA) # tag name, includes, excludes
              i = lindex(_.tags, tag, appendandreturnindex)
              adds.append(i); _.tag2paths[i].append(parent)

    # Second recurse folder-wise
    files = wrapExc(lambda: os.listdir(aDir), lambda: [])
    if SKPFILE in files:
      if _.log >= 1: info("  Skip %s due to local skipfile" % aDir)
      return
    ignore = ignore or (IGNFILE in files)
    if ignore:
      _.tagdir2paths[tags[-1]].remove(parent) # remove from index and children markers

    for file in (f for f in files if DOT in f[1:]): # only index files with real extension
      ext = filenorm(file[file.rindex(DOT):])
      i = lindex(_.tags, ext, appendandreturnindex) # add file extension to local dir's tags only
      adds.append(i); _.tag2paths[i].append(parent)
    tags = tags[:-1] if ignore else [t for t in tags] # copy
    children = (f[len(aDir) + 1:] for f in filter(isdir, (os.path.join(aDir, d) for d in files)))
    for child in children:
      idx = len(_.tagdirs) # add new element at next index
      _.tagdir2parent[idx] = parent
      _.tagdirs.append(intern(child)) 
      tags.append(_.tagdirs.index(_.tagdirs[idx])) # temporary addition of first occurence of that tag string
      for tag in frozenset(tags + adds): _.tagdir2paths[tag].append(idx)
      _._walk(aDir + SLASH + child, idx, tags) # store first occurence index only
      tags.pop() # remove temporary add after recursion
  
  def mapTagsIntoDirs(_):
    ''' After all manual tags have been added, we map them into the tagdir structure. '''
    if _.log >= 1: info("Mapping tags into index")
    for itag, tag in enumerate(_.tags):
      idx = lindex(_.tagdirs, tag, appendandreturnindex) # get index in list, or append
      _.tagdir2paths[idx] += _.tag2paths[itag]
  
  def unwalk(_, idx = 0, path = ""):
    ''' Walk entire tree from index (slow but proof of correctness). '''
    tag = _.tagdirs[idx] # name of head element
    children = (f[0] for f in filter(lambda a: a[1] == idx and a[0] != idx, dictviewitems(_.tagdir2parent))) # using generator expression
    if _.log >= 1: info(path + tag + SLASH)
    for child in children: _.unwalk(child, path + tag + SLASH)
  
  def getPath(_, id, cache):
    ''' Return one root-relative path for the given index id by recursively going through index-> name mappings. '''
    assert id < len(_.tagdirs) # otherwise hell on earth
    if id == 0: return "" # root path special case
    parent = _.tagdir2parent[id] # get parent id
    found = dictget(cache, parent, lambda: _.getPath(parent, cache)) # recursive folder name resolution
    new = found + SLASH + _.tagdirs[id]
    cache[id] = new
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
    retain = []
    for path in excludedPaths:
      conf = _.cfg.paths.get(path, {})
      if len(conf) == 0: retain.append(path); continue # keep for removal, because no inclusion information available
      tags = conf.get(TAG, [])
      if len(tags) == 0:
        froms = conf.get(FROM, [])
        if len(froms) == 0: retain.append(path); continue # keep for removal, no manual tags in config or mapped config
        retainit = True
        for other in froms:
          conf2 = _.cfg.paths.get(other, {})
          if len(conf2) == 0: # this should not happen, but in case of missing reference
            error("Encountered missing FROM source config in '%s': '%s'; please repair" % (path, other))
            break
          tags2 = conf2.get(TAG, [])
          if len(tags2) == 0: break # found from config, but has no tags: no need to consider for removal from removes -> retain
          for value2 in tags2:
            tg, inc, exc = value.split(SEPA)
            if tag in includedTags: retainit = False; break
        if retainit: retain.append(path)
        continue # removed from removal, go to next path
      retainit = True
      for value in tags:
        tg, inc, exc = value.split(SEPA)
        if tg in includedTags: retainit = False; break # removed from retained paths
      if retainit: retain.append(path)
    return set(retain)
  
  def findFolders(_, include, exclude = [], returnAll = False):
    ''' Find intersection of all directories with matching tags.
        include: list of cleaned tag names to include
        exclude: list of cleaned tag names to exclude
        returnAll: shortcut flag that simply returns all paths from index
    '''
    if returnAll: return list(_.getPaths(list(reduce(lambda a, b: a | set(b), dictviewvalues(_.tagdir2paths), set())))) # all existing paths
    paths, first, cache = set(), True, {}
    for tag in include: # positive restrictive matching
      if _.log >= 2: info("Filtering paths by inclusive tag %s" % tag)
      if isglob(tag):
        if DOT in tag: # [:-1]: # contains an extension in non-final position (in final should not be possible)
          ext = filenorm(tag[tag.index(DOT):])
          if isglob(ext): # glob search with glob extension
            new = reduce(lambda a, b: a | set(_.getPaths(_.tagdir2paths[_.tagdirs.index(b)], cache)), fnmatch.filter(_.tagdirs, ext), set()) # filters all extensions in index by glob (e.g. .c??)
          else: # glob search with fixed extension
            new = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(ext)], cache)), lambda: set()) # exception is unknown index in getPath()
        else: # no extension: cannot filter folder; ignore glob altogether
          warn("Preliminarily ignoring glob <%s> while filtering folders (no file extension in glob)" % tag)
          new = set() # ignore glob in folder filtering altogether
      elif tag.startswith(DOT): # explicit file extension filtering
        new = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(tag)], cache)), lambda: set()) # directly from index
      else: # no glob, no extension
        new = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(tag)], cache)), lambda: set()) # directly from index
      paths = new if first else paths & new
      first = False
    for tag in exclude: # we don't excluded globs here, because we would also exclude potential candidates (because index is over-specified)
      if _.log >= 2: info("Filtering paths by exclusive tag %s" % tag)
      potentialRemove = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(tag)], cache)), lambda: set()) # can only be removed, if no manual tag/file extension/glob in config or "from"
      new = _.removeIncluded(include, potentialRemove) # remove paths with includes from "remove" list (adding back...)
      if first: # start with all all paths, except determined excluded paths
        allPaths = list(_.getPaths(list(reduce(lambda a, b: a | set(b), dictviewvalues(_.tagdir2paths), set())))) # get paths from index data structure
        paths = allPaths - new
      else:
        paths -= new # reduce found paths
      first = False
    return list(paths)

  def findFiles(_, aFolder, poss, excludes = [], strict = True):
    ''' Determine files for the given folder.
        aFolder: folder to filter
        remainder: positive tags, extension, or file/glob to consider
        excludes: negative assertions
        strict: perform real file existence checks
        returns: returns list of filenames for given folder
    '''
    remainder = set(poss) - set(aFolder.split(SLASH)[1:]) # split folder path into tags and remove from remaining criteria
    if _.log >= 1: info("Filtering folder %s%s" % (aFolder, (" by remaining tags: " + (", ".join(remainder)) if len(remainder) > 0 else DOT)))
    conf = _.cfg.paths.get(aFolder, {}) # if empty, files remains unchanged, we return all 
    folders = [aFolder] + [norm(os.path.abspath(os.path.join(_.root + aFolder, mapped)))[len(_.root):] if not mapped.startswith(SLASH) else os.path.join(_.root, mapped) for mapped in conf.get(FROM, [])] # all mapped folders
    if _.log >= 1 and len(folders) > 1: info("Considering (mapped) folders: %s" % str(folders[1:]))

    allfiles = set() # contains files from current or mapped folders (without path, since "mapped", but could have local symlink - TODO
    for folder in folders:
      if _.log >= 1: debug("Checking folder %s" % folder)
      files = set(wrapExc(lambda: [f for f in os.listdir(_.root + folder) if isfile(_.root + folder + SLASH + f)], lambda: [])) # all from current folder, exc: folder name (unicode etc.)
      conf = _.cfg.paths.get(folder, {}) # if empty, files remains unchanged, we return all of them regularly
      if _.log >= 2: debug("Conf found for %s: %s" % (folder, str(conf)))
      tags = conf.get(TAG, [None])
      keep = set(files) # start with all to keep, then restrict set

      for tag in remainder: # for every tag remaining to filter, we check if action on current files is necessary
        if tag.startswith(DOT): keep &= set([f for f in files if filenorm(f[-len(tag):]) == tag]); continue # file extension
        elif isglob(tag) or tag in files: keep &= set([f for f in files if globmatch(f, tag)]); continue # this branch for glob and direct file name
        found = False # marker for the case that not even a manual tag matched
        for value in tags:
          if value is None: keep = set(); found = True; break
          tg, inc, exc = value.split(SEPA) # tag name, includes, excludes
          if tg == tag: # mark that matches the find criterion: we can remove all others!
            found = True
            news = set(files) # collect all files subsumed under the tag that should remain. hint: this is not a tag ^ tag match!
            for i in inc.split(","): # if tag manually specified, only keep those included files
              if isglob(i): news &= set([f for f in files if globmatch(f, i)]) # is glob
              else: news &= set([i] if i in files and (not strict or isfile(_.root + folder + SLASH + i)) else []) # is no glob: add only if file exists
            for e in exc.split(","): # if tag is manually specified, exempt these files (add back)
              if isglob(e): news |= set([n for n in news if globmatch(n, e)])
              else: news.add(e)
            keep = keep & news
            break # TODO froms checking missing before break!
        if not found: keep = set() # if no inclusive tag 

      remo = set() # start with none to remove, than enlarge set
      for tag in excludes:
        if tag.startswith(DOT): remo |= set([f for f in files if f[-len(tag):] == tag]); continue
        elif isglob(tag) or tag in files: remo |= set([f for f in files if globmatch(f, tag)]); continue
        found = False # marker for case not even a manual tag matched
        for value in tags:
          if value is None: keep = set(files); found = True; break
          tg, inc, exc = value.split(SEPA)
          if tg == tag:
            news = set() # collect all file that should be excluded
            for i in inc.split(","):
              if isglob(i): news |= set([f for f in files if globmatch(f, i)]) # is glob
              else: news |= set([i] if i in files and (not strict or isfile(_.root + folder + SLASH + i)) else []) # is no glob: add, only if exists
            for e in exc.split(","):
              if isglob(e): news -= set([n for n in news if globmatch(n, e)])
              else: news.discard(e)
            remo |= news
            break
        if not found: keep = set(files)
      files = (files & keep) - remo
      allfiles |= files
    return list(allfiles)
  

if __name__ == '__main__':
  ''' This code is just for testing. Run in svn/projects by tagsplorer/lib.py '''
  if len(sys.argv) > 1 and sys.argv[1] == '--test': import doctest; doctest.testmod(); os.system(sys.executable + " tests.py")
