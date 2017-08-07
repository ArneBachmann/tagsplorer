# tagsPlorer main library  (C) 2016-2017  Arne Bachmann  https://github.com/ArneBachmann/tagsplorer
# This is the tagging library to augment OS folder structures by tags (and provide virtual folder view plus queries over tags)
# This code is written for maximum OS and Python version interoperability and should run fine on any Linux and Windows, in both Python 2 and Python 3

# Markers in this file: TODO (open tasks) and HINT (to think about)


import collections
import copy
import fnmatch
import logging
import os
import re
import sys
import time
import zlib  # standard library
if sys.version_info.major >= 3: from os import listdir
else: from dircache import listdir
if '--simulate-winfs' in sys.argv or os.environ.get("SIMULATE_WINFS", "False").lower() == "true":
  ON_WINDOWS = True; SIMFS = True; from simfs import *
else: ON_WINDOWS = sys.platform == 'win32'  # there exists a different detection schema for OS, but I don't remember. https://github.com/easybuilders/easybuild/wiki/OS_flavor_name_version


# Version-dependent imports
if sys.version_info.major >= 3:
  import pickle  # instead of cPickle in the Python 2 family
  from sys import intern
  from functools import reduce  # not built-in anymore
  lmap = lambda pred, lizt: list(map(pred, lizt))  # don't return a generator
  dictviewkeys, dictviewvalues, dictviewitems = dict.keys, dict.values, dict.items  # returns generators operating on underlying data in Python 3
  cmp = lambda a, b: -1 if a < b else (1 if a > b else 0)
  def xreadlines(fd): return fd.readlines()
else:  # is Python 2 (for old versions like e.g. 2.4 this might fail)
  import cPickle as pickle
  lmap = map
  dictviewkeys, dictviewvalues, dictviewitems = dict.iterkeys, dict.itervalues, dict.iteritems
  def xreadlines(fd): return fd.xreadlines()

# Constants
PICKLE_VERSION = 2  # since Python 3 comes with different protocol, we pin the protocol to two
CONFIG =  ".tagsplorer.cfg"  # main tag configuration file
INDEX =   ".tagsplorer.idx"  # index file (re-built when timestamps differ)
SKPFILE = ".tagsplorer.skp"  # marker file (can also be configured in configuration instead)
IGNFILE = ".tagsplorer.ign"  # marker file (dito)
IGNORE, SKIP, TAG, FROM, SKIPD, IGNORED, GLOBAL = map(intern, ("ignore", "skip", "tag", "from", "skipd", "ignored", "global"))  # config file options
SEPA, SLASH, DOT = map(intern, (";", "/", os.extsep))
TOKENIZER = re.compile(r"[\s\-_\.]")
RE_SANITIZER = re.compile(r"([\.\[\]\(\)\^\$\+\*\?\{\}])")


# Functions
def sjoin(*s): return " ".join([str(e) for e in s if e != ''])

def xany(pred, lizt): return reduce(lambda a, b: a or pred(b), lizt if hasattr(lizt, '__iter__') else list(lizt), False)  # short-circuit Python 2/3 implementation. could also use wrapExc(lambda: iter(lizt), lizt) instead. intentionally doesn't iterate over string characters. converts string and other data types to a one-element list instead

def xall(pred, lizt): return reduce(lambda a, b: a and pred(b), lizt if hasattr(lizt, '__iter__') else list(lizt), True)

def wrapExc(func, otherwise = None):
  ''' Wrap an exception and compute return value lazily if an exception is raised. Useful for recursive function application.
  >>> print(wrapExc(lambda: 1))
  1
  >>> print(wrapExc(lambda: 1 / 0))  # return default fallback value (None)
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
def isdir(f): return os.path.isdir(f) and not os.path.islink(f) and not os.path.ismount(f)  # TODO is this really benefitial?
def isfile(f): return wrapExc(lambda: os.path.isfile(f) and not os.path.ismount(f) and not os.path.isdir(f), lambda: False)  # on error "no file"
pathnorm = (lambda s: s.replace("\\", SLASH)) if ON_WINDOWS else ident  # as lambda to allow dynamic definition
def lappend(lizt, elem): (lizt.extend if type(elem) is list else lizt.append)(elem); return lizt   # functional list.append that returns self afterwards to avoid new array creation (lizt + [elem])
def appendandreturnindex(lizt, elem): return len(lappend(lizt, elem)) - (len(elem) if type(elem) is list else 1)  # returns index of appended element or first index of elements added
def isunderroot(root, folder): return os.path.commonprefix([root, folder]).startswith(root)
def isglob(f): return '*' in f or '?' in f  # TODO add type hint str
def getTsMs(): return ilong(time.time() * 1000.)  # timestamp in milliseconds
def safeSplit(s, d = ","): return [_ for _ in s.split(d) if _ != '']  # remove empty strings that appear e.g. for "  ".split(" ") or "".split(" ")
def safeRSplit(s, d): return s[s.rindex(d) + 1:] if d in s else s
def dd(tipe = list): return collections.defaultdict(tipe)
def even(a): return (a // 2) * 2 == a
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

def removeCasePaths(paths):
  ''' Intelligently remove duplicate paths that differ only in case (of the last path component). '''
  caseMapping = dd()
  for path in paths: caseMapping[caseNormalize(path)].append(path)  # assign original and case-normalized version as values to the case-normalized key
  return [l[1] if len(l) > 1 else l[0] for l in (list(sorted(ll)) for ll in dictviewvalues(caseMapping))]  # first entry [0] is always all-uppercase (lower ASCII character than lower case), therefore order is always ABC, Abc (abC, abc), and no more than two entries are expected

def currentPathInGlobalIgnores(path, idirs): return (path[path.rindex(SLASH) + 1:] if path != '' else '') in idirs  # function definitions used only in this local context
def re_sanitize(name): return RE_SANITIZER.sub(r"\\\1", name)
def partOfAnyGlobalSkipPath(path, sdirs): return xany(lambda skp: wrapExc(lambda: re.search(r"((^%s$)|(^%s/)|(/%s/)|(/%s$))" % ((re_sanitize(skp),) * 4), path).groups()[0].replace("/", "") == skp, False), sdirs)  # dynamic RE generation TODO sanitize path names?
def anyParentIsSkipped(path, paths): return xany(lambda p: SKIP in dictget(paths, SLASH.join(path.split(SLASH)[:p + 1]), {}), range(path.count(SLASH)))  # e.g. /a checks once at [:1] "/".join(["", "a"])


# Classes
class Logger(object):
  def __init__(_, log): _._log = log
  def debug(_, *s): _._log.debug(sjoin(*s))
  def info(_, *s): _._log.info(sjoin(*s))
  def warn(_, *s): _._log.warn(sjoin(*s))
  def error(_, *s): _._log.error(sjoin(*s))


class Normalizer(object):
  def setupCasematching(_, case_sensitive, quiet = False):
    ''' Setup normalization.
    >>> n = Normalizer(); n.setupCasematching(True, quiet = True); print(n.filenorm("Abc"))
    Abc
    >>> print(n.globmatch("abc", "?Bc"))
    False
    >>> n.setupCasematching(False, quiet = True); print(n.filenorm("Abc"))
    ABC
    >>> print(n.globmatch("abc", "?Bc"))
    True
    >>> print(n.globfilter(["ab1", "Ab2"], "a??"))
    ['ab1', 'Ab2']
    >>> print(n.globfilter(["dot.folder"], "DOT*"))  # regression test
    ['dot.folder']
    >>> print(n.globfilter(["ab", "Ab"], "a?"))  # TODO what about duplicates in normalized results? Is this possible?
    ['ab', 'Ab']
    >>> n.setupCasematching(True, quiet = True)
    >>> print(n.globfilter(["ab1", "Ab2"], "a*"))
    ['ab1']
    '''
    if not quiet: debug("Setting up case-%ssensitive matching" % ("" if case_sensitive else "in"))
    _.filenorm = ident if case_sensitive else caseNormalize  # we can't use "str if case_sensitive else str.upper" because for unicode strings this fails, as the function reference comes from the str object
    _.globmatch = fnmatch.fnmatchcase if case_sensitive else lambda f, g: fnmatch.fnmatch(f.upper(), g.upper())  # fnmatch behavior depends on file system, therefore fixed here
    _.globfilter = fnmatch.filter if case_sensitive else lambda lizt, pat: [name for name in lizt if _.globmatch(name, pat)]
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
      for key, values in sorted(dictviewitems(_map)):  # no need for iteritems, as supposedly small (max. size = 4)
        if values is None: fd.write("%s=\n" % (key.lower()))  # skip or ignore
        else:
          for value in sorted(values): fd.write("%s=%s\n" % (key.lower(), value))  # tag or from
    fd.write("\n")  # termination of config contents


class Config(object):
  ''' Contains all tag configuration. '''
  def __init__(_, log, case_sensitive = not ON_WINDOWS):
    _.log = log  # level
    _.case_sensitive = case_sensitive  # dynamic default unless specified differently in the config file
    _.paths = {}  # map from relative dir path to dict of marker -> [entries]
    _.reduce_case_storage = False  # default is always store case-noramlized plus true case
    normalizer.setupCasematching(case_sensitive, quiet = True)  # default, overridden by load

  def printConfig(_):
    ''' Display debugging info. '''
    if _.log >= 1: debug("Config options: %r" % {"case_sensitive": _.case_sensitive, "reduce_case_storage": _.reduce_case_storage, "on_windows": ON_WINDOWS})

  def load(_, filename, index_ts = None):
    ''' Load configuration from file, if timestamp differs from index' timestamp. '''
    if _.log >= 2: debug("Loading configuration %r" % ((filename, index_ts),))
    with open(filename, 'r') as fd:  # HINT: don't use rb, because in Python 3 this returns bytes objects
      if _.log >= 1: info("Comparing configuration timestamp for " + filename)  # TODO root-normalize path to save output letters
      timestamp = float(fd.readline().rstrip())
      if (index_ts is not None) and timestamp == index_ts:
        if _.log >= 1: info("Skip loading configuration, because index is up to date")
        _.printConfig()
        return False  # no skew detected, allow using old index's interned configuration ("self" will be discarded)
      if _.log >= 1: info("Loading configuration from file system" + ("" if index_ts is None else " because index is outdated"))
      cp = ConfigParser(); dat = cp.load(fd); _.__dict__.update(dat)  # update with global options
      _.paths = cp.sections
      normalizer.setupCasematching(_.case_sensitive, _.log == 0)  # TODO remove and let caller handle this?
      _.printConfig()
      return True

  def store(_, filename, timestamp = None):
    ''' Store configuration to file, prepending data by the timestamp, or the current time. '''
    if _.log >= 2: debug("Storing configuration %r" % ((filename, timestamp),))
    if timestamp is None: timestamp = getTsMs()  # for all cases we modify only config file (e.g. tag, untag, config)
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
    _.log = 0  # log level (default: no logging, only result printing)
    _.compressed = 2  # pure pickling is faster than any bz2 compression, but zlib level 2 seems to have best size/speed combination. if changed to 0, data will be stored uncompressed and the index needs to be re-created
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
      cfg = Config(_.log, _.cfg.case_sensitive)
      if (ignore_skew or cfg.load(os.path.join(os.path.dirname(os.path.abspath(filename)), CONFIG), _.timestamp)) and recreate_index:
        if _.log >= 1: info("Recreating index considering configuration")
        _.cfg = cfg  # set more recent config and update
        _.walk()  # re-create this index
        _.store(filename)

  def store(_, filename, config_too = True):
    ''' Persist index in a file, including currently active configuration. '''
    if _.log >= 2: debug("store " + str((filename, config_too)))
    with open(filename, "wb") as fd:
      nts = getTsMs()
      _.timestamp = _.timestamp + 0.001 if nts <= _.timestamp else nts  # assign new date, ensure always differing from old value
      if _.log >= 1: info("Writing index to " + filename)
      fd.write(zlib.compress(pickle.dumps(_, protocol = PICKLE_VERSION), _.compressed) if _.compressed else pickle.dumps(_, protocol = PICKLE_VERSION))  # WARN: make sure not to have callables on the pickled objects!
      if config_too:
        if _.log >= 1: info("Updating configuration to match new index timestamp")
        _.cfg.store(os.path.join(os.path.dirname(os.path.abspath(filename)), CONFIG), _.timestamp)  # update timestamp in configuration
    if _.log >= 1: info("Wrote %d index bytes (%d tag entries -> %d mapped path entries)" % (os.stat(filename)[6], len(_.tagdirs), sum([len(p) for p in _.tagdir2paths])))

  def walk(_, cfg = None):
    ''' Build index by recursively walking folder tree.
        cfg: if set, use that configuration instead of contained one.
        returns: None
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
    empty = []
    _.tagdir2paths = [_.tagdir2paths[i] if i in _.tagdir2paths else empty for i in range(max(_.tagdir2paths) + 1)]  # save variant of converting map values to list positions (as we don't know if all exist)
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
          4.  recurse
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
      if _.log >= 1: debug("  Skip %s%s" % (aDir, '' if SKIP in marks else ' due to global skip setting'))
      return  # completely ignore sub-tree and break recursion
    elif IGNORE in marks or ((aDir[aDir.rindex(SLASH) + 1:] if aDir != '' and SLASH in aDir else '') in dictget(dictget(_.cfg.paths, '', {}), IGNORED, [])):  # former checks path cfg, latter checks global ignore TODO allow glob check?
      if _.log >= 1: debug("  Ignore %s%s" % (aDir, '' if IGNORE in marks else ' due to global ignore setting'))
      ignore = True  # ignore this directory as tag, don't index contents
    # 1b: check folder's configuration
    elif TAG in marks:  # neither SKIP nor IGNORE in config: consider manual folder tagging
      for t in marks[TAG]:
        if _.log >= 1: debug("  Tag '%s' in %s" % (t, aDir))
        tag, pos, neg = t.split(SEPA)  # tag name, includes, excludes
        i = lindex(_.tags, intern(tag), appendandreturnindex)  # find existing index of that tag, or create a new and return its index
        adds.append(i); _.tag2paths[i].append(parent)
    elif FROM in marks:  # consider tags from mapped folder
      for f in marks[FROM]:
        if _.log >= 1: debug("  Map from %s into %s" % (f, aDir))
        other = pathnorm(os.path.abspath(os.path.join(aDir, f))[len(_.root):] if not f.startswith(SLASH) else os.path.join(_.root, f))
        _marks = _.cfg.paths.get(other, {})
        if TAG in _marks:
          for t in _marks[TAG]:
            tag, pos, neg = t.split(SEPA)  # tag name, includes, excludes
            i = lindex(_.tags, intern(tag), appendandreturnindex)
            adds.append(i); _.tag2paths[i].append(parent)

    #  2.  process folder's file names
    files = wrapExc(lambda: listdir(aDir), lambda: [])  # read file list
    if SKPFILE in files:  # HINT use always lower case file name? should be no problem, as even Windows allows lower-case file names and should match here
      if _.log >= 1: debug("  Skip %r due to local skip file" % aDir[len(_.root):])
      return  # completely ignore sub-tree and break recursion here
    ignore = ignore or (IGNFILE in files)  # short-circuit logic: config setting or file marker
    if not ignore:
      # 2a. index all folders' contents' names file extensions
      if _.log >= 1: info("Indexing files in folder %r" % aDir[len(_.root):])
      for _file in (ff for ff in files if DOT in ff[1:]):  # index only file extensions (also for folders!) in this folder, without propagation to sub-folders TODO dot-first files could be ignored or handled differenly
        ext = _file[_file.rindex(DOT):]  # split off extension, even if "empty" extension (filename ending in dot)
        iext = caseNormalize(ext)
        i = lindex(_.tags, intern(ext), appendandreturnindex)  # get or add file extension to local dir's tags only
        adds.append(i); _.tag2paths[i].append(parent)  # add current dir to index of that extension
        if not _.cfg.reduce_case_storage and iext != ext:  # differs from normalized version: store normalized as well
          i = lindex(_.tags, intern(iext), appendandreturnindex)  # add file extension to local dir's tags only
          adds.append(i); _.tag2paths[i].append(parent)  # add current dir to index of that extension

    # 3.  prepare recursion
    newtags = [t for t in ((tags[:-2] if len(tags) >= 2 and caseNormalize(_.tagdirs[tags[-2]]) == _.tagdirs[tags[-1]] else tags[:-1]) if ignore else tags)]  # if ignore: propagate all tags except current folder name variant(s) to children TODO reuse "tags" reference from here on instead
    children = (f[len(aDir) + (1 if not aDir.endswith(SLASH) else 0):] for f in filter(isdir, (os.path.join(aDir, ff) for ff in files)))  # only consider folders. ternary condition is necessary for the backslash in "D:\" = "D:/", a Windows root dir special case
    for child in children:  # iterate sub-folders using above generator expression
      # 3a. add sub-folder name to "tagdirs" and "tagdir2parent"
      cache = {}
      idxs = []  # first element in "idx" is next index to use in recursion (future parent, current child), no matter if true-case or case-normalized mode is selected
      if not (ON_WINDOWS and _.cfg.reduce_case_storage):  # for Windows: only store true-case if not reducing storage, Linux: always store
        if _.log >= 1: debug("Storing original folder name %r for %r" % (child, _.getPath(parent, cache)))
        idxs.append(len(_.tagdirs))  # for this child folder, add one new element at next index's position (no matter if name already exists in index (!), because it always has a different parent). it's not a fully normalized index, more a tree structure
        _.tagdirs.append(intern(child))  # now add the child folder name (duplicates allowed, because we build the tree structure here)
        _.tagdir2parent.append(parent)  # at at same index as tagdirs "next" position
        assert len(_.tagdirs) == len(_.tagdir2parent)
      iname = caseNormalize(child)
      if ON_WINDOWS or (iname != child and not _.cfg.reduce_case_storage):  # Linux: only store case-normalized if not reducing storage, Windows: always store
        if _.log >= 1: debug("Storing case-normalized folder name %r for %r" % (iname, _.getPath(parent, cache)))
        idxs.append(len(_.tagdirs))
        _.tagdirs.append(intern(iname))
        _.tagdir2parent.append(parent)
      tokens = [r for r in TOKENIZER.split(child) if r not in ("", child)]
      for token in tokens:  # HINT: for folders, we also split at dots ("extension") TODO document this difference (also stores .folder extension for the folder)
        if _.log >= 2: debug("Storing original tokenized name %r for %r" % (token, _.getPath(parent, cache)))
        i = lindex(_.tags, intern(token), appendandreturnindex)
        adds.append(i); _.tag2paths[i].append(idxs[-2] if len(idxs) > 0 and even(len(idxs)) else idxs[-1])
        itoken = caseNormalize(token)
        if not _.cfg.reduce_case_storage and itoken != token:
          if _.log >= 2: debug("Storing case-normalized tokenized name %r for %r" % (itoken, _.getPath(parent, cache)))
          i = lindex(_.tags, intern(itoken), appendandreturnindex)
          adds.append(i); _.tag2paths[i].append(idxs[-2] if len(idxs) > 0 and even(len(idxs)) else idxs[-1])
      assert len(_.tagdirs) == len(_.tagdir2parent)
      if _.log >= 2: debug("Tagging folder %r with tags +<%s> *<%s>" % (iname, ",".join([_.tagdirs[x] for x in (newtags + idxs)]), ",".join([_.tags[x] for x in adds])))  # TODO can contain root (empty string) HINT adds is only collected for displaying this message
      # 4. recurse
      if not ignore:  # indexing of current folder
        for tag in newtags + idxs: _.tagdir2paths[_.tagdirs.index(_.tagdirs[tag])].extend(idxs)  # add subfolder reference(s) for all collected tags from root to child to tag name
      _._walk(aDir + SLASH + child, idxs[-2] if len(idxs) > 0 and even(len(idxs)) else idxs[-1], newtags + ([] if ignore else idxs))  # as parent, always use original case index, not case-normalized one (unless configured to reduce space)

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
    if found > 0 and _.log >= 1: info("Removed duplicates from index for %d tags" % found)
    return len(rm)

  def getPath(_, idx, cache):
    ''' Return one root-relative path for the given index idx by recursively going through index->name mappings.
        idx: folder entry index from _.tagdirs
        cache: dictionary for speeding up consecutive calls (remembers already collected parent path mappings)
        returns: root-relative path string
    >>> i = Indexer("bla")
    >>> i.tagdirs =       ["", "a", "b", "c"]
    >>> i.tagdir2parent = [0,  0,   1,   1]  # same popsitions as in tagdirs
    >>> c = {}
    >>> print(repr(i.getPath(0, c)))
    ''
    >>> print(c)
    {}
    >>> print(i.getPath(1, c))
    /a
    >>> print(c)
    {1: '/a'}
    >>> print(i.getPath(3, c))
    /a/c
    >>> print(sorted(c.items()))
    [(1, '/a'), (3, '/a/c')]
    '''
    assert idx < len(_.tagdirs) and idx >= 0  # otherwise hell on earth
    if idx == 0: return ""  # root path special case
    found = cache.get(idx, None)
    if found is not None: return found
    parent_idx = _.tagdir2parent[idx]  # get parent index from tree-structure
    parent = dictget(cache, parent_idx, lambda: _.getPath(parent_idx, cache)) if parent_idx != 0 else ""  # recursive folder name resolution
    new = parent + SLASH + _.tagdirs[idx]
    cache[idx] = new
    return new

  def getPaths(_, ids, cache):
    ''' Returns a generator for all paths for the given list of ids, using intermediate caching.
        ids: iterable of tagdirs ids
        cache: dictionary for speeding up consecutive calls to _.getPath
        returns: generator that returns root-relative path strings
    >>> i = Indexer("blupp")
    >>> i.tagdirs =       ["", "a", "b", "c"]
    >>> i.tagdir2parent = [0,  0,   1,   1]  # same positions as in tagdirs
    >>> c = {}
    >>> print(" ".join(list(i.getPaths(range(4), c))))
     /a /a/b /a/c
    >>> print(len(c))
    3
    '''
    return (_.getPath(i, cache) for i in ids)

  def removeIncluded(_, includedTags, excludedPaths):
    ''' Return those paths, that have no manual tags or from tags from the inclusion list; subtract from the exclusion list to reduce set of paths to ignore.
        includedTags: search tags (no extensions, no globs) to keep included: will be removed from the excludedPaths list
        excludedPaths: all paths for exclusive tags, scheduled for removal from search results
        returns: list of paths to retain
        hint: there is no need to check all tags in configuration, because they could be inclusive or exclusive, and are on a per-file basis
        the existence of a tag suffices for retaining paths
    '''
    if _.log >= 2: debug("removeIncluded " + str((includedTags, excludedPaths)))
    retain = []
    for path in excludedPaths:
      conf = _.cfg.paths.get(path, {})
      if len(conf) == 0: retain.append(path); continue  # keep for removal, because no inclusion information available
      tags = conf.get(TAG, [])
      if len(tags) == 0:  # if no direct tags, it depends on the froms
        froms = conf.get(FROM, [])
        if len(froms) == 0: retain.append(path); continue  # keep for removal, no manual tags in mapped config
        retainit = True
        for other in froms:
          conf2 = _.cfg.paths.get(other, {})
          if len(conf2) == 0:  # the mapped folder has no manual tags specified
            error("Encountered missing FROM source config in '%s': '%s'; please repair" % (path, other))  # TODO can be removed? what to do here?
            # TODO is this correct? we don't know anything about the mapped files?
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
    ''' Find intersection of all directories with matching tags, from over-generic index.
        include: list of tag names to include
        exclude: list of tag names to exclude
        returnAll: shortcut flag that simply returns all paths from index instead of finding and filtering results
        returns: list of folder paths (case-normalized or both normalized and as is, depending on the case-sensitive option)
    '''

    if _.log >= 2: debug("findFolders +<%s> -<%s>%s" % (",".join(include), ",".join(exclude), " (Return all)" if returnAll else ""))
    idirs, sdirs = dictget(dictget(_.cfg.paths, '', {}), IGNORED, []), dictget(dictget(_.cfg.paths, '', {}), SKIPD, [])  # get lists of ignored and skipped paths
    if _.log >= 2: debug("Building list of all paths. Global ignores/skips: %r -- %r" % (idirs, sdirs))
    _.allPaths = wrapExc(lambda: _.allPaths, lambda: set(_.getPaths(list(reduce(lambda a, b: a | set(b), _.tagdir2paths, set())), {})))  # try cache first, otherwise compute union of all paths and put into cache to speed up consecutive calls (e.g. when used in a server loop) TODO avoid this step? make lazy? run parallel?
    if returnAll or len(include) == 0:  # for only exclusive tags, we first need all candidates and then strip down
      if _.log >= 2: debug("Pruning skipped and ignored paths from %d" % len(_.allPaths))
      alls = [path for path in _.allPaths if not currentPathInGlobalIgnores(path, idirs) and not partOfAnyGlobalSkipPath(path, sdirs) and not anyParentIsSkipped(path, _.cfg.paths) and IGNORE not in dictget(_.cfg.paths, path, {})]  # all existing paths except globally ignored/skipped paths TODO add marker file logic below?
      alls = [a for a in alls if isdir(_.root + os.sep + a)]  # perform true folder check TODO make this skippable to speed up? e.g. via --relaxed
      if _.cfg.log >= 2: debug("Remaining %d paths" % len(alls))
      if _.cfg.log >= 2: debug("findFolders: %r" % alls)
      if returnAll: return alls
    paths, first, cache = set() if len(include) > 0 else alls, True, {}  # initialize filtering process
    for tag in include:  # positive restrictive matching
      if _.log >= 2: info("Filtering paths by inclusive tag '%s'" % tag)
      if isglob(tag):
        new = reduce(lambda a, b: a | set(_.getPaths(_.tagdir2paths[_.tagdirs.index(b)], cache)), normalizer.globfilter(_.tagdirs, tag), set())  # filters all extensions in index by extension's glob (e.g. .c??) TODO if * will find everything TODO use set.update() or did this cause trouble?
      elif DOT in tag:
        new = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(normalizer.filenorm(tag[tag.index(DOT):]))], cache)), lambda: set())  # directly from index
      else:  # no glob, no extension: can be tag or file name
        new = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(tag)], cache)), lambda: set())  # directly from index, can also be a DOT-leading file/folder name
      if first: paths = new; first = False
      else: paths.intersection_update(new)
    for tag in exclude:  # we don't excluded globs here, because we would also exclude potential candidates (because index is over-specified)
      if _.log >= 2: info("Filtering paths by exclusive tag '%s'" % tag)
      potentialRemove = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(tag)], cache)), lambda: set())  # these paths can only be removed, if no manual tag or file extension or glob defined in config or "from" TODO what if positive extension looked for? already handled?
      new = _.removeIncluded(include, potentialRemove)  # remove paths with includes from "remove" list (adding back...)
      if first:  # start with all paths, except determined excluded paths
        paths = set(_.getPaths(list(reduce(lambda a, b: a | set(b), _.tagdir2paths, set())), cache)) - new  # get paths from index data structure
        first = False
      else:
        paths.difference_update(new)  # reduce found paths
    # Now convert to return list, which may differ from previously computed set of paths
    if _.log >= 2: debug("Filtered down to %d paths" % len(paths))
    paths = [p for p in paths if not currentPathInGlobalIgnores(p, idirs) and not partOfAnyGlobalSkipPath(p, sdirs)]  # check "global ignore dir" condition, then check on all "global skip dir" condition, which includes all sub folders as well TODO remove filtering, as should be reflected by index anyway (in contrast to above getall?))
    if _.cfg.case_sensitive:  # eliminate different case writings, otherwise return both, although only one may physically exist on the file system
      if _.log >= 2: debug("Found %d paths before removing duplicates" % len(paths))
      paths[:] = removeCasePaths(paths)  # remove case doubles
      if _.log >= 2: debug("Retained %d paths after removing duplicates" % len(paths))
      #paths[:] = [p for p in paths if isdir(_.root + os.sep + p)]  # TODO same as logic above? this ensures on case-sensitive file systems that only correct case versions are retained
#    else:
#      if _.log >= 2: debug("Retained %d paths after checking file system" % len(paths))
    if _.cfg.log >= 2: debug("findFolders: %r" % paths)
    return paths

  def findFiles(_, aFolder, poss, negs = [], force = False):
    ''' Determine files for the given folder.
        aFolder: root-relative folder to filter files in
        poss: (potentially case-normalized) positive tags, file extensions, file names or glob patternss to consider, or an empty list (falls back to considering all files to ensure negative tags work at all)
        negs: negative assertions, same options as for 'poss'
        force: don't perform true file existence checks, might return false positives for special files or directories (usually no problem)
        returns: 2-tuple (list [filenames] for given folder, bool: has a skip marker file - don't recurse into)
    '''
    if _.log >= 2: debug("findFiles " + str((aFolder, poss, negs, force)))
    inPath = set(safeSplit(aFolder, SLASH))  # break path into folder names
    inPath.update(reduce(lambda prev, step: prev + TOKENIZER.split(step), inPath, []))  # add tokenized path steps
    if not _.cfg.case_sensitive: inPath.update(set([caseNormalize(f) for f in safeSplit(aFolder, SLASH)]))  # add case-normalized folder names
    remainder = set([p for p in poss if not normalizer.globfilter(inPath, p)])  # split folder path into tags and remove from remaining criterions, considering case-sensitivity unless deselected
    if _.log >= 1: info("Filtering folder %s%s" % (aFolder, " by remaining tags: " + (", ".join(remainder) if len(remainder) > 0 else '<none>')))
    conf = _.cfg.paths.get(aFolder, {})  # if empty, files remain unchanged, we return all
    folders = [aFolder] + [pathnorm(os.path.abspath(os.path.join(_.root + aFolder, mapped)))[len(_.root):] if not mapped.startswith(SLASH) else os.path.join(_.root, mapped) for mapped in conf.get(FROM, [])]  # list of original and all mapped folders
    if _.log >= 1 and len(folders) > 1: info("Mapped folders to check: %s" % os.pathsep.join(folders[1:]))

    allfiles, willskip = set(), False  # contains files from current or mapped folders (without path, since "mapped", but could have local symlink - TODO
    for folder in folders:
      if _.log >= 1: debug("Checking %sfolder%s" % (("root ", "") if folder == "" else ('', " " + folder)))
      files = set(wrapExc(lambda: [f for f in listdir(_.root + folder) if isfile(_.root + folder + SLASH + f)], []))  # all from current folder, potential exception: folder name (unicode etc.)
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
              if isglob(i): news.intersection_update(set(normalizer.globfilter(files, i)))  # is glob
              else: news = set([i] if i in files and (force or isfile(_.root + folder + SLASH + i)) else [])  # is a file: add only if exists, otherwise add nothing
            for e in safeSplit(exc):  # if tag is manually specified, exempt these files (add back)
              if isglob(e): news.update(set(normalizer.globfilter(news, e)))
              else: news.discard(e)  # add file to keep
            keep.intersection_update(news)
            break
        if not found: keep = set()  # if no remaining tag matched

      remo = set()  # start with none to remove, than enlarge set
      for tag in negs:
        if tag.startswith(DOT): remo.update(set([f for f in files if f[-len(tag):] == tag])); continue  # filter by file extension
        elif isglob(tag) or tag in files: remo.update(set(normalizer.globfilter(files, tag))); continue  # filter globs and direct file names TODO case/normalization here?
        found = False  # marker for the case that none of the provided extension/glob/file tags matched: check tags in configuration
        for value in tags:
          if value is None: remo = set(); found = True; break  # None means no config found, no further matching needed
          tg, inc, exc = value.split(SEPA)
          if tg == tag:
            found = True
            news = set()  # collect all file that should be excluded
            for i in safeSplit(inc):
              if isglob(i): news.update(set(normalizer.globfilter(files, i)))  # is glob
              else: news.update(set([i] if i in files and (force or isfile(_.root + folder + SLASH + i)) else []))  # is no glob: add, only if exists
            for e in safeSplit(exc):
              if isglob(e): news.difference_update(set(normalizer.globfilter(news, e)))
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

_log = Logger(logging.getLogger(__name__)); debug, info, warn, error = _log.debug, _log.info, _log.warn, _log.error  # _log is not exported


if __name__ == '__main__':
  ''' This main section is just for testing. '''
  if '--test' in sys.argv[1]: import doctest; doctest.testmod()
