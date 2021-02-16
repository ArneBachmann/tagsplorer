# coding=utf-8

''' tagsPlorer library  (C) 2016-2021  Arne Bachmann  https://github.com/ArneBachmann/tagsplorer '''

import logging, os, pickle, sys, zlib
from functools import reduce

from tagsplorer.constants import ALL, COMB, CONFIG, DOT, FROM, GLOBAL, IGNFILE, IGNORE, IGNORED, ON_WINDOWS, PICKLE_PROTOCOL, SEPA, SKIP, SKIPD, SKPFILE, SLASH, ST_MTIME, ST_SIZE, TAG, TOKENIZER
from tagsplorer.utils import anyParentIsSkipped, appendnew, dd, dictGet, dictGetSet, findIndexOrAppend, getTsMs, isDir, isFile, isGlob, lappend, normalizer, pathHasGlobalIgnore, pathHasGlobalSkip, pathNorm, safeSplit, sjoin, splitByPredicate, wrapExc, xall, xany


_log = logging.getLogger(__name__)
def log(func): return (lambda *s: func(sjoin([_() if callable(_) else _ for _ in s]), **({"stacklevel": 2} if sys.version_info >= (3, 8) else {})))
debug, info, warn, error = log(_log.debug), log(_log.info), log(_log.warning), log(_log.error)


class ConfigParser(object):  # TODO #89 is there a faster serialization protocol?
  ''' Much simplified ini-style config file. No line continuation, no colon separation, no symbolic replacement, no comments, no empty lines. '''

  def __init__(_): _.sections = {}  # there is always a global section [] and optionally exactly one section per root-relative path

  def load(_, fd):
    ''' Load the .cfg file.
        fd: file-like object to enable reading from arbitrary data source and position in resource (e.g. after consuming the timestamp)
        returns: only the global section []
    '''
    title = ''; section = dd()
    for line in fd.readlines():
      line = line.strip()  # just in case of incorrect formatting IDEA could be optimized away, or comments allowed
      if line.startswith('['):  # new section detected: before processing, store the last section
        if len(section): _.sections[title] = section  # stores empty global section when encountering beginning of first (and even global) section
        title = line[1:line.index(']')]; section = dd()  # for the next section
      elif line != '':  # content found
        try:
          idx = line.index('=')  # try to parse
          key, value = line[:idx].lower(), line[idx+1:]  # HINT: was .lower().rstrip(), but when accessing only via this script's API there's no need for that
          if value != '' and (key in [TAG, FROM]\
          or title == "" and  key in [SKIPD, IGNORED, GLOBAL]): section[key].append(value)  # allows several values per key
          elif key in [IGNORE, SKIP] and key not in section:    section[key] = None  # only keep key as marker
          else: warn(f"Encountered illegal configuration key '{key}'. Skip entry")
        except: warn(f"Key without value for illegal key '{line}'")
      else: break  # an empty line terminates file
    if len(section): _.sections[title] = section  # store last section
    return {k: v if v.strip().lower() not in ("true", "false") else v.strip().lower() == "true" for k, v in (wrapExc(lambda: kv.split("=")[:2], lambda: (kv, None)) for kv in _.sections.get("", {}).get(GLOBAL, []))}

  def store(_, fd, parent = None):
    ''' Store the .cfg file.
        fd: file-like object to allow for writing additional contents (e.g. the timestamp)
        parent: optional global settings
    '''
    if parent is not None:  # store parent's properties
      if "" not in _.sections: _.sections[""] = dd()
      _.sections[""][GLOBAL] = sorted([f"{k.lower()}={parent.__dict__[k]}" for k, v in (kv.split("=")[:2] for kv in _.sections.get("", {}).get(GLOBAL, []))])  # store updated config
    for title, _map in sorted(_.sections.items()):  # ordered is better for VCS
      if len(_map) == 0 or xall(lambda v: len(v) == 0, _map.values()): continue
      fd.write(f"[{title}]\n")
      for key, values in sorted(_map.items()):  # no need for iteritems, as supposedly small (max. size = 4)
        if values is None: fd.write(f"{key}=\n")  # skip or ignore
        else:
          for value in sorted(values): fd.write(f"{key}={value}\n")  # tag or from
    fd.write("\n")  # termination of config contents


class Configuration(object):
  ''' Contains all tag configuration. '''

  def __init__(_, case_sensitive = None):
    _.paths = {}  # {relative dir path -> {marker -> [entries]}}
    _.reset(case_sensitive)
    normalizer.setupCasematching(_.case_sensitive, suppress = True)  # initialize normalizer, but can be overridden during load()

  def reset(_, case_sensitive = None):
    _.case_sensitive = (not ON_WINDOWS) if case_sensitive is None else case_sensitive  # search behavior
    _.reduce_storage = False           # storage behavior
    _.compression = 2                  # good fast compromise: uncompressed pickling is faster than any bz2 compression, but zlib level 2 seems to get best trade-off. 0 means uncompressed

  def logConfiguration(_):
    ''' Display debug info. '''
    info("Configuration:  " + "  ".join(f"{k}: %s" % ("On" if v else "Off") for k, v in [
        ("case_sensitive",  _.case_sensitive),
        ("reduce_storage",  _.reduce_storage),
        ("on_windows",      ON_WINDOWS)
      ]))

  def load(_, folder, index_ts = None):
    ''' Load configuration from file, unless up to date.
        folder:   the configuration folder to load from
        index_ts: timestamp from inside the index file, or None (force load)
        returns:  False if index is still current, otherwise True (configuration loaded and a new index must be created)
    '''
    with open(os.path.join(folder, CONFIG), 'r', encoding = "utf-8") as fd:
      timestamp = float(fd.readline().rstrip())
      file_time = int(os.stat(os.path.join(folder, CONFIG))[ST_MTIME] * 1000)
      if index_ts and max(timestamp, file_time) == index_ts:
        debug("Index is up to date")  # skip loading configuration
        _.logConfiguration()
        return False  # no skew detected, allow using old index's interned configuration ("self" will be discarded)
      debug(f"Load configuration from {folder}{'' if not index_ts else ' because index is outdated'}")
      cp = ConfigParser(); dat = cp.load(fd); _.__dict__.update(dat)  # update Configuration() object with loaded global options
      _.paths = cp.sections
      normalizer.setupCasematching(_.case_sensitive)  # update with just loaded setting
      _.logConfiguration()
      return True

  def store(_, folder, timestamp = None):
    ''' Store configuration to file, prepending data by the timestamp, or the current time. '''
    debug(f"Store configuration to {folder}" + (" (%.1f)" % timestamp if timestamp else ""))
    if not timestamp: timestamp = getTsMs()  # for those cases, in which we modify only the config file (e.g. tag, untag, config)
    cp = ConfigParser(); cp.sections = _.paths
    with open(os.path.join(folder, CONFIG), "w", encoding = "utf-8") as fd: fd.write(f"{timestamp}\n"); cp.store(fd, parent = _)
    info(f"Wrote {os.stat(os.path.join(folder, CONFIG))[ST_SIZE]} config bytes")

  def addTag(_, folder, tag, poss, negs, force = False):
    ''' For a given folder, add a tag for inclusive and exclusive conjunctive globs.
        folder: root-relative folder to operate on (section key in the configuration)
        tag: the tag to add to the configuration for the given folder
        poss: list of inclusive globs to apply the tag to
        negs: list of exclusive globs to apply the tag not to
        force: allows adding tags already covered inclusively or exclusively by existing globs TODO #90 reimplement safety checks
        returns: was successfully added?
    '''
    debug(f"addTag +{COMB.join(poss)} -{COMB.join(negs)} to {folder}/{tag}{' force' if force else ''}")
    conf = dictGet(_.paths, folder, {})
    to_add = f"{tag};{SEPA.join(sorted(poss))};{SEPA.join(sorted(negs))}"
    for line in conf.get(TAG, []):  # all pattern markers for the given folder
      if line.strip() == to_add:
        warn(f"Tag <{tag}> in {folder} for +{COMB.join(sorted(poss))} -{COMB.join(sorted(negs))} already defined, skip")
        return False
    info(f"Tag <{tag}> in '{folder}' for +{COMB.join(poss)} -{COMB.join(negs)}")
    conf = dictGetSet(_.paths, folder, {})  # creates empty config entry if it doesn't exist
    dictGetSet(conf, TAG, []).append(to_add)
    return True

  def delTag(_, folder, tag, poss, negs):
    ''' For a given folder, remove a tag for inclusive and exclusive conjuntive globs.
        folder: root-relative folder to operate on (section key in the configuration)
        tag: the tag to remove from the configuration for the given folder
        poss: list of inclusive globs to remove the tag from
        negs: list of exclusive globs to remove the tag from
        returns: was successfully removed?
    '''
    debug(f"delTag +{COMB.join(poss)} -{COMB.join(negs)} from {folder}/{tag}")
    conf = dictGet(_.paths, folder, {})  # no need to create if missing, since we are removing anyway
    to_del = f"{tag};{SEPA.join(sorted(poss))};{SEPA.join(sorted(negs))}"
    found = False
    for line in conf.get(TAG, []):
      if line.strip() == to_del: found = True
    if found:
      warn(f"Untag '{tag}' in {folder} for +{COMB.join(sorted(poss))} -{COMB.join(sorted(negs))}")
      conf.get(TAG)[:] = [entry for entry in conf.get(TAG) if entry != to_del]  # remove matches
    return found

  def showTags(_, folder):
    ''' For a given folder, show all defined tags.
        folder: root-relative folder to operate one
    '''
    debug(f"showTags for {folder}")
    inPath = set(safeSplit(folder, SLASH))  # break path into constituents
    inPath.update(reduce(lambda prev, step: prev + TOKENIZER.split(step) + TOKENIZER.split(normalizer.filenorm(step)), inPath, []))
    warn("Tags derived from path: " + COMB.join(inPath))  # TODO #91 filter output by ignore and skip
    conf = dictGet(_.paths, folder, {})
    tags = dd()
    for line in conf.get(TAG, []): tags[line.split(SEPA)[0]].append(line)
    for key, defs in sorted(tags.items()): print("\n".join(defs))


class Indexer(object):
  ''' Main index creation. Walks through file tree and indexes folder tags.
      Addtionally, tags for single files or globs, and those mapped by FROM markers are included in the index.
      File-specific tags are only determined during the find phase.
      TODO #92 test and benchmark other methods of serialization, e.g. shelve, pickleDB and others
  '''

  def __init__(_, startDir):
    ''' startDir: absolute path. '''
    if startDir.endswith(":"):  # drive-relative path
      cwd = os.getcwd()
      os.chdir(startDir)
      startDir = os.getcwd()  # get actual folder on drive
      os.chdir(cwd)  # return to original drive/folder
    _.root = pathNorm(startDir.rstrip("/\\"))  # slash-normalized absolute path
    _.timestamp = 1.23456789  # for comparison with configuration timestamp
    _.cfg = None  # reference to latest corresponding configuration
    _.tagdirs = []  # array of tags (plain dirnames and manually set tags (not represented in parent), both case-normalized and as-is)
    _.tagdir2parent = []  # index of dir entry (tagdirs) -> index of parent to represent tree structure (excluding folder links)
    _.tagdir2paths = dd()  # dirname/tag index -> list of [all path indices relevant for that dirname/tag]

  def load(_, filename, ignore_skew = False, recreate_index = False):
    ''' Load a pickled index into memory. Optimized for speed.
        filename: absolute path to the index file
        ignore_skew:    if True, ignore the fact that index and config timestamps deviate. used in tests and for --keep-index
        recreate_index: if True, create a new index even if timestamps still match
    '''
    debug(f"load('{filename}': ignore_skew %s, recreate_index %s)" % ("Yes" if ignore_skew else "No", "Yes" if recreate_index else "No"))
    try: del _.allPaths  # cache flag used when run as a web server
    except AttributeError: pass  # delete cache when reloading
    with open(filename, "rb") as fd:
      info("Read index from " + filename)
      c = pickle.loads(wrapExc(lambda: zlib.decompress(fd.read()), fd.read))
      _.cfg, _.timestamp, _.tagdirs, _.tagdir2parent, _.tagdir2paths = c.cfg, c.timestamp, c.tagdirs, c.tagdir2parent, c.tagdir2paths
      cfg = Configuration(_.cfg.case_sensitive)
      if (recreate_index or cfg.load(os.path.dirname(os.path.abspath(filename)), _.timestamp)) and not ignore_skew:
        info("Recreate index considering configuration")
        _.cfg = cfg  # set more recent config and update
        _.walk()  # re-create this index
        _.store(filename)
      normalizer.setupCasematching(_.cfg.case_sensitive)  # update with just loaded setting

  def store(_, filename, config_too = True):
    ''' Persist index in a file, including currently active configuration. '''
    with open(filename, "wb") as fd:
      nts = getTsMs()
      _.timestamp = _.timestamp + 0.001 if nts <= _.timestamp else nts  # assign new date, ensure always differing from old value
      debug("Store index to " + filename)
      fd.write(zlib.compress(pickle.dumps(_, protocol = PICKLE_PROTOCOL), _.cfg.compression) if _.cfg.compression else pickle.dumps(_, protocol = PICKLE_PROTOCOL))
      if config_too:
        debug("Update configuration to match new index timestamp")
        _.cfg.store(os.path.dirname(os.path.abspath(filename)), _.timestamp)  # update timestamp in configuration
    info(f"Wrote {os.stat(filename)[6]} index bytes ({len(_.tagdirs)} entries and %d paths)" % (sum([len(p) for p in _.tagdir2paths])))

  def walk(_, cfg = None):
    ''' Build index by recursively traversing the folder tree.
        cfg: if set, use that configuration instead of the one in the root.
    '''
    info("Walk folder tree to update index")
    if cfg: _.cfg = cfg
    if _.cfg is None: raise Exception("No configuration loaded. Cannot traverse folder tree")
    debug(f"Configuration: case_sensitive = {_.cfg.case_sensitive}, reduce_storage = {_.cfg.reduce_storage}")
    _.tagdirs = [""]       # list of directory names, duplicates allowed and required to represent the tree structure. "" represents the root folder
    _.tagdir2parent = [0]  # pointer to parent directory. the self-reference at index 0 marks root. each index position responds to one entry in tagdirs (!)
    _.tagdir2paths = dd()  # maps index of tagdir entries to list of path leaf indexes, to find all paths ending in that suffix
    _.tags = []            # temporary data structure for "set" of (manually set or folder-derived) tag names and file extensions, which gets mapped into the tagdirs structure
    _.tag2paths = dd()     # temporary data structure for config-specified tag and extension mapping to matching respective paths
    _._walk(_.root, 0)     # recursive indexing
    _.mapTagsIntoDirsAndCompressIndex()  # manual tags are combined in the index with folder names for simple lookup and filtering
    del _.tags, _.tag2paths  # remove temporary structures
    _.tagdir2paths = [_.tagdir2paths[i] if i in _.tagdir2paths else [] for i in range(max(_.tagdir2paths) + 1)] if _.tagdir2paths else []  # safely convert map values to list positions (as we don't know if all exist)
    info(f"Indexed {len(_.tagdirs)} folders with {len(_.tagdir2paths)} tags")

  def _walk(_, folder, findex, tags = None, last = 0):
    ''' Recursive traversal through folder tree.
        This will index the folder 'folder' and then recurse into its children folders.
        The function adds all parent folder names (up to root) plus the current directory's name as tags, unless told to ignore the current name by a configuration setting or file marker.
        The general approach is to add children's tags in the parent, then recurse, potentially removing added tags in the recursion if necessary.
        folder:  absolute folder path to add to the index (slash-normalized to one preceding and no trailing forward slash)
        findex:  specified folder's index number in the data structures (parent for the children processed here = current folder)
        tags:    list of aggregated tag indexes (folder names) of parent directories
        last:    number of last indexes used to store the current folder (1 if normalized only ot reduced storage, otherwise 2, 0 if ignored)
        returns: interrupted
    '''
    debug(f"_walk '{folder}' findex {findex} {last} {tags}")
    if tags is None: tags = []  # because using default `= []` is a bad idea in Python
    ignore = False  # marks folder as "no tagging for this specific folder", according to local or global settings
    adds = set()    # for display only: indexes of additional tags valid for the current folder only, not to be promoted to children calls

    # 1.  get folder configuration, if any
    marks = _.cfg.paths.get(folder[len(_.root):], {})  # contains configuration for current folder, if any
    # 1a. check skip or ignore flags from configuration
    if SKIP   in marks or xany(lambda ignore: normalizer.globmatch(folder[folder.rindex(SLASH) + 1:] if folder and SLASH in folder else folder, ignore), dictGet(dictGet(_.cfg.paths, '', {}), SKIPD, [])):
      info(f"Skip '{folder[len(_.root):]}' due to " + ('path skip' if SKIP in marks else 'global folder name skip'))
      return  # completely ignore sub-tree and break recursion
    if IGNORE in marks or xany(lambda ignore: normalizer.globmatch(folder[folder.rindex(SLASH) + 1:] if folder and SLASH in folder else folder, ignore), dictGet(dictGet(_.cfg.paths, '', {}), IGNORED, [])):
      info(f"Ignore '{folder[len(_.root):]}' due to " + ('path ignore' if IGNORE in marks else 'global folder name ignore'))
      ignore = True  # ignore this directory as a tag, and don't index its contents, but still continue recursion
    # 1b. read configured additional tags for folder and folder mapping from configuration into "tags" and "adds"
    elif TAG in marks:  # neither SKIP nor IGNORE in config: consider manual folder tagging
      for t in marks[TAG]:
        tag, pos, neg = t.split(SEPA)  # tag name, includes, excludes
        info(f"Tag <{tag}> (+<{pos}> -<{neg}>) in '{folder[len(_.root):]}'")
        i = findIndexOrAppend(_.tags, tag); adds.add(i)  # find existing index of that tag, or create return new index
        appendnew(_.tag2paths[i], findex)  # add tag and create link to the current folder ("tag" is a match for the current folder?)
    if FROM in marks:  # consider tags from mapped folders, even if proper folder is ignored
      for f in marks[FROM]:  # map configured tags, even if it contains an ignored marker
        info(f"Map from '{f}' into '{folder[len(_.root):]}'")
        other = os.path.normpath(os.path.join(folder, pathNorm(f)))[len(_.root):] if not f.startswith(SLASH) else pathNorm(f)
        _marks = _.cfg.paths.get(other, {})  # marks of mapped folder
        for t in _marks.get(TAG, []):
          tag, pos, neg = t.split(SEPA)  # HINT the actual pattern filtering is implemented in findFiles
          info(f"Tag <{tag}> (+<{pos}> -<{neg}>) in '{folder[len(_.root):]}'")
          i = findIndexOrAppend(_.tags, tag); adds.add(i)
          appendnew(_.tag2paths[i], findex)

    # 2. process folder's file names
    files, folders = wrapExc(lambda: splitByPredicate(os.listdir(folder), lambda f: isFile(folder + SLASH + f)), ([], []))  # HINT right-hand side is not automatically a directory, thus filtered below:
    folders[:] = sorted([f for f in folders if isDir(folder + SLASH + f)])  # remove special files like ".desktop"
    if SKPFILE in files:  # HINT allow other than lower case skip file? should be no problem, as even Windows allows lower-case file names and should match here
      info(f"Skip '{folder[len(_.root):]}' due to local skip marker file")
      return  # ignore entire sub-tree and break recursion
    if IGNFILE in files:
      info(f"Ignore '{folder[len(_.root):]}' due to local ignore marker file")
      ignore = True
    if not ignore:
      debug(f"Index file types for '{folder[len(_.root):]}'")
      for _file in (ff for ff in files if DOT in ff[1:]):  # index file extensions (including this in sub-folders), without propagation to sub-folders HINT dot-first files are ignored. see below
        ext = _file[_file.rindex(DOT):]  # split off extension, even when "empty" extension (filename ending in dot)
        if ext not in adds:
          i = findIndexOrAppend(_.tags, ext); adds.add(i)  # get or add file extension to local dir's tags only
          _.tag2paths[i].append(findex)  # add current dir to index of that extension
        iext = ext.lower()
        if iext != ext and not _.cfg.reduce_storage:  # store normalized extension if different from literal, unless told not to
          i = findIndexOrAppend(_.tags, iext); adds.add(i)  # add file extension to local dir's tags only
          _.tag2paths[i].append(findex)  # add current dir to index of that extension
      # TODO #93 optionally also index file names and their tokens! this would also cover dot-first files ignored above

    # 3.  prepare recursion
    newtags = [t for t in tags[:-last if ignore else None]]  # tags to propagate into subfolders (except current folder names if ignored)
    cache = {}  # for faster path computation during output logging HINT cache was formerly in side folders loop
    for subfolder in ([] if ignore else folders):  # iterate sub-folders
      # 3a. add sub-folder name to "tagdirs" and "tagdir2parent"
      idxs  = []  # *first* element in "idx" is parent index to use in recursion for the currently processed subfolder
      addt  = set()  # per-subfolder local additional tokens
      added = 0

      info(f"Store literal folder '{subfolder}' for '{_.getPath(findex, cache)}'")
      idxs.append(len(_.tagdirs))  # for this subfolder, always add a *new* element, no matter if name already exists in the index, because parent differs (to keep tree structure)
      _.tagdirs.append(subfolder)  # now add the subfolder name to the list of known tags/folders (duplicates allowed, because we build the tree structure here)
      _.tagdir2parent.append(findex)  # placed at same index as tagdirs "next" position
      added += 1
      assert len(_.tagdirs) == len(_.tagdir2parent)  # invariant

      iname = subfolder.lower()
      if not _.cfg.reduce_storage and iname != subfolder:
        info(f"Store case-normalized folder '{iname}' for '{_.getPath(findex, cache)}'")
        idxs.append(len(_.tagdirs))     # new index
        _.tagdirs.append(iname)         # add to both
        _.tagdir2parent.append(findex)  # data structures
        added += 1
        assert len(_.tagdirs) == len(_.tagdir2parent)  # invariant

      tokens = [r for r in TOKENIZER.split(subfolder) if r not in ("", subfolder)]  # in addition to the folder parent mapping, split folder name into tokens
      for token in set(tokens):
        debug(f"Store literal token '{token}' for '{_.getPath(findex, cache)}'")
        i = findIndexOrAppend(_.tags, token); addt.add(i)
        _.tag2paths[i].append(idxs[-added])  # link token index to stored path constituent

        itoken = token.lower()
        if not _.cfg.reduce_storage and itoken != token:
          debug(f"Store case-normalized token '{itoken}' for '{_.getPath(findex, cache)}'")
          i = findIndexOrAppend(_.tags, itoken); addt.add(i)
          _.tag2paths[i].append(idxs[-added])
      assert len(_.tagdirs) == len(_.tagdir2parent)  # invariant

      if not ignore:  # then index current folder
        debug(f"Mark folder '{folder[len(_.root):]}{SLASH}{subfolder}' with " + "<%s>" % (COMB.join(set([_.tagdirs[x] for x in (newtags + idxs)]) | set([_.tags[x] for x in (adds | addt)]))))  # per subfolder, not promoted to recursive call
        for tag in newtags + idxs:
          _.tagdir2paths[_.tagdirs.index(_.tagdirs[tag])].extend(idxs)  # add sub-folder reference(s) for all collected parent folder tags to the tag name

      # 4. recurse into subfolder
      try:
        if _._walk(folder = folder + SLASH + subfolder, findex = idxs[-added], tags = newtags + ([] if ignore else idxs), last = added): return True  # recursion
      except KeyboardInterrupt: return True

  def mapTagsIntoDirsAndCompressIndex(_):
    ''' After recursion finished, map extensions or manually set tags into the tagdir structure to save space. '''
    info("Map tags into folder index")
    for itag, tag in enumerate(_.tags):
      idx = findIndexOrAppend(_.tagdirs, tag)  # get (first) index in list, or append if not found yet
      _.tagdir2paths[idx].extend(_.tag2paths[itag])  # tag2paths contains true parent folder index from _.tagdirs
    rm = [tag for tag, dirs in _.tagdir2paths.items() if len(dirs) == 0]  # find entries that are empty due to ignores
    for r in rm:
      del _.tagdir2paths[r]
      debug(f"Remove childless tag '{_.tagdirs[r]}'")  # remove empty lists from index (was too optimistic, removed by ignore or skip)
    debug(f"Removed {len(rm)} childless tags from index")
    found = 0
    for tag, dirs in _.tagdir2paths.items():
      _l = len(_.tagdir2paths[tag])  # get size of mapped paths
      _.tagdir2paths[tag] = set(dirs)  # remove duplicates
      found += (_l - len(_.tagdir2paths[tag]))  # check any removed
    if found: debug(f"Removed {found} duplicates from index")

  def getPath(_, idx, cache):
    ''' Return one root-relative path for the given index by recursively going through {index: name} mappings and combining them into a full path.
        idx:     folder entry index from _.tagdirs
        cache:   dictionary for speeding up consecutive calls (remembers already collected parent path mappings)
        returns: root-relative path string
    >>> i = Indexer("bla"); c = {}
    >>> i.tagdirs = ["", "a", "b", "c"]
    >>> i.tagdir2parent = [0,  0,   1,   1]  # same positions as in tagdirs
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
    if idx == 0: return ""  # root
    assert 0 <= idx < len(_.tagdirs)
    found = cache.get(idx, None)
    if found is not None: return found
    parent_idx = _.tagdir2parent[idx]  # get parent index from tree-structure
    parent = dictGetSet(cache, parent_idx, _.getPath(parent_idx, cache)) if parent_idx != 0 else ""  # recursive folder name resolution
    cache[idx] = new_ = parent + SLASH + _.tagdirs[idx]
    return new_

  def getPaths(_, ids, cache):
    ''' Returns a generator for respective paths of the given path index list.
        ids:     iterable of tagdirs ids
        cache:   dictionary for speeding up consecutive calls to _.getPath()
        returns: generator that yields root-relative path strings
    >>> i = Indexer("blupp")
    >>> i.tagdirs =       ["", "a", "b", "c"]
    >>> i.tagdir2parent = [0,  0,   1,   1]  # same positions as in tagdirs
    >>> c = {}; g = i.getPaths(range(4), c)
    >>> print(" ".join([next(g), next(g), next(g), next(g)]))  # indented because of empty root path
     /a /a/b /a/c
    >>> print(len(c))  # cache size
    3
    '''
    return (_.getPath(i, cache) for i in ids)

  def removeIncluded(_, includedTags, excludedPaths):
    ''' Return those paths, that have no manual tags or FROM tags from the inclusion list; subtract from the exclusion list to reduce set of paths to ignore.
        includedTags:  search tags to keep included (no extensions, no globs). Will be removed from the excludedPaths list
        excludedPaths: all paths for exclusive tags, scheduled for removal from search results
        returns:       list of paths to retain
        HINT: there is no need to check all tags in configuration, because they could be inclusive or exclusive, and are on a per-file basis
        the existence of a tag suffices for retaining paths
    '''
    retain = []
    for path in excludedPaths:
      conf = _.cfg.paths.get(path, {})
      if len(conf) == 0: retain.append(path); continue  # accept for removal, because no further tagging information exists
      tags, froms = conf.get(TAG, []), conf.get(FROM, [])
      for other in froms: tags.extend(_.cfg.paths.get(other, {}).get(TAG, []))
      retainit = True
      for value in tags:  # all explicit tags count, no matter if globs match anything or not (over-generic folder list)
        tg, inc, exc = value.split(SEPA)
        if tg in includedTags: retainit = False; break  # deny removal
      if retainit: retain.append(path)
    return set(retain)

  def findFolders(_, include, exclude, returnAll = False, checkPaths = True):
    ''' Find intersection of all indexed folders with specified tags, from over-generic index.
        include:   list of tag names that must be present
        exclude:   list of tag names that must not be present
        returnAll: shortcut flag that simply returns *all paths* from the index instead of finding and filtering results (from tp.find())
        returns:   list of folder paths (case-normalized or both normalized and as is, depending on the case-sensitive option)
    '''
    idirs, sdirs = dictGet(dictGet(_.cfg.paths, '', {}), IGNORED, []), dictGet(dictGet(_.cfg.paths, '', {}), SKIPD, [])  # get lists of ignored and skipped paths
    cache = {}
    def rebuild():
      debug(f"Build list of all paths.  Global ignores: {idirs}  Global skips: {sdirs}")
      return set(_.getPaths(list(reduce(lambda a, b: a.update(set(b)) or a, _.tagdir2paths, set())), cache))  # compute union of all paths (cached when running as a server)
    _.allPaths = wrapExc(lambda: _.allPaths, rebuild)  # lazy computation. fails and computes if property not defined
    alls = [path for path in _.allPaths if not pathHasGlobalIgnore(path, idirs) and not pathHasGlobalSkip(path, sdirs) and not anyParentIsSkipped(path, _.cfg.paths) and IGNORE not in dictGet(_.cfg.paths, path, {})]
    if returnAll or len(include) == 0:  # if only exclusive tags, we need all paths and prune them later
      debug(f"Prune skipped and ignored paths from {len(_.allPaths)} to {len(alls)} paths")
      if returnAll:
        alls = [a for a in alls if not checkPaths or os.path.isdir(_.root + os.sep + a)]  # ensure that only correct letter cases are retained on case-sensitive file systems
        return alls
    paths, first = (set() if len(include) else alls), True  # first filtering action (inclusive or exclusive)
    for tag in include:  # positive restrictive matching
      debug(f"Filter {len(alls if first else paths)} paths by inclusive tag <{tag}>")
      if isGlob(tag):  # filters indexed extensions by extension's glob (".c??"")
        new = reduce(lambda a, b: a.update(set(_.getPaths(_.tagdir2paths[_.tagdirs.index(b)], cache))) or a, normalizer.globfilter(_.tagdirs, tag), set())  # in-place version
      elif DOT in tag:
        new = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(normalizer.filenorm(tag[tag.index(DOT):]))], cache)), set())  # directly from index
      else:  # no glob, no extension: tag or file name
        new = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(tag)], cache)), set())  # directly from index, or a DOT-leading file/folder name
      if first: paths = new; first = False
      else: paths.intersection_update(new)
    for tag in exclude:  # we don't excluded globs here, because we would also exclude potential candidates (because index is over-specified)
      debug(f"Filter {len(paths)} paths by exclusive tag <{tag}>")
      potentialRemove = wrapExc(lambda: set(_.getPaths(_.tagdir2paths[_.tagdirs.index(tag)], cache)), set())  # these paths can only be removed, if no manual tag/file extension/glob in config or FROM
      new = _.removeIncluded(include, potentialRemove)  # remove paths with includes from "remove" list (adding back)
      if first:  # start with all paths, except determined excluded paths
        paths = _.allPaths - new
        first = False
      else:
        paths.difference_update(new)  # reduce found paths by exclude matches
    # Now convert to return list, which may differ from previously computed set of paths
    paths = list(paths)
    debug(f"Found {len(paths)} path matches")
    if _.cfg.case_sensitive:  # eliminate different letter cases, otherwise return both, although only one physically exists TOOD why not use "not"?
      paths[:] = [p for p in paths if not checkPaths or os.path.basename(p) in os.listdir(_.root + (os.sep + os.path.dirname(p) if SLASH in p else '')) and os.path.isdir(_.root + os.sep + p)]  # ensure that only correct letter cases are retained on case-sensitive file systems
      debug(f"Retained {len(paths)} paths after removing duplicates")  # TODO on windows, all checks may succeed although case differs!
    assert all(path.startswith(SLASH) or path == '' for path in paths), paths  # only return root-relative paths
    return paths

  def findFiles(_, current, poss, negs):
    ''' Determine files for the given folder (from findFolders() with potential matchs).
        current: root-relative folder to filter files in
        poss:    list of (opt. case-normalized) positive (including) tags, file extensions, file names or globs
        negs:    list of negative (excluding) tags, file extensions, file names or globs
        returns: 2-tuple([filenames], skip?)
    '''
    debug(f"findFiles '{current}' {poss} {negs}")
    if current: assert current[0] == SLASH and current[-1] not in '/\\' and  _.root[-1] not in '/\\', f"{current} {_.root}"
    inPath = set(safeSplit(current, SLASH))  # break path into folder names
    inPath.update(reduce(lambda prev, step: prev + TOKENIZER.split(step), inPath, []))  # add tokenized path steps
    inPath.discard('')  # tokenizer may split an empty string
    inPath.update([normalizer.filenorm(f) for f in inPath])  # adds case-normalized versions if case_sensitive
    extrap, extran = list(poss), list(negs)  # shallow copy
    for unique in set(poss): extrap.remove(unique)  # parameters contained more than once:
    for unique in set(negs): extran.remove(unique)  # filter once in folder index, and once more in files
    poss = list(set([p for p in poss if not normalizer.globfilter(inPath, p)])) + extrap  # remove already true positive tags (folder name match)
    negs += extran
    info(f"Filter folder '{current}' " + (("by remaining including tags <%s>" % (COMB.join(poss)) if len(poss) else (("by remaining excluding tags " + COMB.join(negs)) if len(negs) else "with no constraint"))))
    conf = _.cfg.paths.get(current, {})  # if empty we return all files
    mapped = [pathNorm(m if m.startswith(SLASH) else os.path.normpath(current + SLASH + m)) for m in conf.get(FROM, [])]  # root-absolute or folder-relative path
    if len(mapped): debug(f"Mapped folders: {os.pathsep.join(mapped)}")  # root-relative paths
    skipFilter = len(poss) + len(negs) + len(mapped) == 0

    willskip = False  # contains files from current or mapped folders (without path, since "mapped", but could get a local symlink - TODO
    found = set() if not skipFilter else set(wrapExc(lambda: [f for f in os.listdir(_.root + current) if isFile(_.root + current + os.sep + f)], []))  # TODO what if folder doesn't exist TODO duplicate of below as special case for no further constraints -> returns all
    if IGNFILE in found: skipFilter, found = True, set()  # enable skip but don't return anything
    for _f, folder in enumerate([] if skipFilter else [current] + mapped):
      info(("Check %s %%sfolder%%s" % ('mapped' if _f else 'proper')) % (('', f" '{folder}'") if folder else ("root ", "")))
      files = set(wrapExc(lambda: [f for f in os.listdir(_.root + folder) if isFile(_.root + folder + os.sep + f)], []))  # TODO silently catches for OS errors, e.g. encoding problems
      if IGNFILE in files: continue  # ignore is easy
      if folder == current and SKPFILE in files:  # only applies to non-mapped folder
        willskip = True  # skip is more difficult to handle than ignore, cf. return 2-tuple (call in tp.find())
        info(f"Skip '{folder}' due to local marker file")
        continue  # no break, process mapped folders
      caseMapping = dd()  # store mapping from case-normalized to actual filenames
      for f in files: caseMapping[normalizer.filenorm(f)].append(f)
      files.update(set(caseMapping.keys()))  # adds case-normalized file names for matching, used if case_sensitive == False

      tags = _.cfg.paths.get(folder, {}).get(TAG, [])

      keep = set(files)  # shallow copy. start with all files to keep, then reduce by remaining matching tag patterns
      for tag in poss:  # for every inclusive tag, check if action on current files is necessary
        if tag[0] == DOT:  keep.intersection_update(set(f for f in files if f[-len(tag):] == tag)); continue  # filter by file extension
        elif isGlob(tag):  keep.intersection_update(set(normalizer.globfilter(files, tag))); continue  # filter globs
        elif tag in files: keep.intersection_update(set([tag])); continue  # TODO cannot detect tokenized file globs here, we operate only on actual file system contents TODO what if same tag defined in remove

        diskeep = set()  # collect all disjunctive "keep" results for configured tag
        for value in (t for t in tags if t.startswith(tag + SEPA)):  # restrict by additional matching tags from the folder configuration
          assert value.count(SEPA) == 2
          tg, inc, exc = value.split(SEPA)  # tag name, includes, excludes
          conkeep = set(keep)  # all conjunctive filter expressions start with previously filtered set
          for i in safeSplit(inc):  # keep conjunction of inclusive files
            if i[0] == DOT: conkeep.intersection_update(set(f for f in conkeep if f[-len(i):] == i))  # TODO also check normalized extension here for user convenience? NO
            elif  i == ALL: continue  # keep all, nothing to do
            elif isGlob(i): conkeep.intersection_update(set(normalizer.globfilter(conkeep, i)))  # "set &"
            else:           conkeep.intersection_update(set([i]) if i in conkeep and isFile(_.root + folder + os.sep + i) else set())  # add file only if exists
          conrmve = set(keep) if exc else set()  # no excludes mean remove nothing TODO mirror this logic below?
          for e in safeSplit(exc):  # remove conjunction of exclusive files
            if e[0] == DOT: conrmve.intersection_update(set(f for f in conrmve if f[-len(e):] == e))
            elif isGlob(e): conrmve.intersection_update(set(normalizer.globfilter(conrmve, e)))
            else:           conrmve.intersection_update(set([i]) if i in conrmve and isFile(_.root + folder + os.sep + i) else set())
          diskeep.update(conkeep - conrmve)  # "set |" disjunctive combination of all filters for a tag
        keep.intersection_update(diskeep)
        if not keep: break  # no need to further check, if no matches remain after tag

      remove = set(files if negs else [])
      for tag in negs:
        if tag[0] == DOT:  remove.intersection_update(set(f for f in files if f[-len(tag):] == tag)); continue  # filter by file extension
        elif isGlob(tag):  remove.intersection_update(set(normalizer.globfilter(files, tag))); continue  # filter globs
        elif tag in files: remove.intersection_update(set([tag])); continue

        disremove = set()
        for value in (t for t in tags if t.startswith(tag + SEPA)):
          assert value.count(SEPA) == 2
          tg, inc, exc = value.split(SEPA)
          conremove = set(remove)  # collect all file that should be excluded
          for i in safeSplit(inc):
            if i[0] == DOT: conremove.intersection_update(set(f for f in conremove if normalizer.filenorm(f[-len(i):]) == normalizer.filenorm(i)))
            elif  i == ALL: continue
            elif isGlob(i): conremove.intersection_update(set(normalizer.globfilter(conremove, i)))
            else:           conremove.intersection_update(set([i]) if i in conremove and isFile(_.root + folder + os.sep + i) else set())
          conkeep = set(remove) if exc else set()
          for e in safeSplit(exc):
            if e[0] == DOT: conkeep.intersection_update(set(f for f in conkeep if normalizer.filenorm(f[-len(e):])))
            elif isGlob(e): conkeep.intersection_update(set(normalizer.globfilter(conkeep, e)))
            else:           conkeep.intersection_update(set([i]) if i in conkeep and isFile(_.root + folder + os.sep + i) else set())
          disremove.update(conremove - conkeep)
        remove.intersection_update(disremove)
        if not remove: break
      files.intersection_update(keep)
      files.difference_update(remove)
      debug(f"Files for folder '{folder}': {COMB.join(files)} (Keep/Remove: <{COMB.join(keep - remove)}>/<{COMB.join(remove)}>)")
      found.update(set(reduce(lambda l, f: lappend(l, caseMapping.get(f, f)), files, set())))  # TODO may lead to different cases or shadowing if using mapped dirs
    debug(f"findFiles '{current}' returns {list(found)} skip: {willskip}")  # TODO in contrast to findFolder no file exist checks (mapped entries are harder to check). ? only partially with config TAGS
    return found, willskip


if __name__ == '__main__': import doctest; doctest.testmod()
