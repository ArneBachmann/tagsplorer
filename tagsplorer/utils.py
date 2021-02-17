''' tagsPlorer utilities  (C) 2016-2021  Arne Bachmann  https://github.com/ArneBachmann/tagsplorer '''

import collections, fnmatch, logging, os, sys, time
from functools import reduce

from tagsplorer.constants import COMB, ON_WINDOWS, SKIP, SLASH


_log = logging.getLogger(__name__)
def log(func): return (lambda *s: func(sjoin([_() if callable(_) else _ for _ in s]), **({"stacklevel": 2} if sys.version_info >= (3, 8) else {})))
debug, info, warn, error = log(_log.debug), log(_log.info), log(_log.warning), log(_log.error)


pathNorm = (lambda s: s.replace(os.sep, SLASH)) if ON_WINDOWS else lambda _: _  # HINT do not convert into a function to allow ternary expression here
casefilter = lambda lizt, pat: [name for name in lizt if fnmatch.fnmatchcase(name, pat)]  # case-sensitive filter


class Normalizer(object):
  ''' Class that provides all case-normalization functions. '''

  def setupCasematching(_, case_sensitive, suppress = False):
    ''' Setup normalization.
    >>> n = Normalizer(); n.setupCasematching(case_sensitive = True)
    >>> print((n.filenorm("Abc"), n.globmatch("abc", "?Bc"), n.globfilter(["ab1", "Ab2"], "a??")))
    ('Abc', False, ['ab1'])
    >>> print(n.globfilter(["ab1", "Ab2"], "a*"))
    ['ab1']
    >>> n.setupCasematching(False)
    >>> print((n.filenorm("Abc"), n.globmatch("abc", "?Bc"), n.globfilter(["ab1", "Ab2"], "a??")))
    ('abc', True, ['ab1', 'Ab2'])
    >>> print(n.globfilter(["ab", "Ab"], "a?"))
    ['ab', 'Ab']
    >>> print(n.globfilter(["dot.folder"], "DOT*"))  # regression test
    ['dot.folder']
    '''
    if not suppress: debug("Case-sensitive matching: " + ("On" if case_sensitive else "Off"))
    _.filenorm   = (lambda _: _)       if case_sensitive else str.lower
    _.globmatch  = fnmatch.fnmatchcase if case_sensitive else lambda f, g: fnmatch.fnmatch(f.lower(), g.lower())
    _.globfilter = casefilter if case_sensitive else \
                   (lambda lizt, pat: [name for name in lizt if fnmatch.fnmatch(name.lower(), pat.lower())])  # HINT lower maybe not necessary
normalizer = Normalizer()  # keep a static module-reference


def dd(): return collections.defaultdict(list)


def safeSplit(s, d = COMB):
  ''' Split a string removing empty sub-strings.
  >>> safeSplit("a,b,,d")
  ['a', 'b', 'd']
  >>> safeSplit(",x,")
  ['x']
  >>> safeSplit(',')
  []
  '''
  return [_.strip() for _ in s.split(d) if _ != '']  # remove empty strings that appear e.g. for "  ".split(" ") or "".split(" ")


def safeRSplit(s, d = SLASH):
  ''' A right-split that avoids an error if the delimiter is not contained.
  >>> safeRSplit('a')
  'a'
  >>> safeRSplit('/a/')
  ''
  >>> safeRSplit('/a')
  'a'
  '''
  return s[s.rindex(d) + 1:] if d in s else s


def sjoin(*string, sep = " "):
  ''' Join strings.
  >>> sjoin("a", "b")
  'a b'
  >>> sjoin([1, 2, 3])
  '1 2 3'
  >>> sjoin(["a", None, 2, ""])
  'a 2'
  '''
  if not string: return ""
  string = string[0] if isinstance(string[0], (list, set)) else string
  return sep.join([str(elem) for elem in string if elem])


def xany(pred, lizt):
  ''' Lazy any implementation. '''
  return any(pred(elem) for elem in lizt)  # works with all iterables and generators, using short-circuit logic


def xall(pred, lizt):
  ''' Predicate-first implementation. '''
  return all([pred(elem) for elem in lizt])


def wrapExc(func, otherwise = None):
  ''' Wrap a no-args function; catch any exception and compute return value lazily.
  >>> print(wrapExc(lambda: 1))
  1
  >>> None is wrapExc(lambda: 1 / 0)  # return default fallback value (None)
  True
  >>> print(wrapExc(lambda: 1 / 0, lambda: 2))  # return defined default by function call
  2
  '''
  try: return func()
  except Exception: return otherwise() if callable(otherwise) else otherwise


def appendnew(lizt, value):
  ''' Only add if not yet contained.
  >>> print(appendnew([1, 2], 3))
  [1, 2, 3]
  >>> appendnew([1, 2], 1)
  [1, 2]
  '''
  if value not in lizt: lizt.append(value)
  return lizt


def lindex(lizt, value, otherwise = lambda _lizt, _value: None):
  ''' List index function with lazy append computation.
      Returns index if found, otherwise appends and returns new index
      Default fallback logic if no computation function is given: do nothing and return None.
  >>> print(lindex([1, 2], 2))  # returns index of value 2 in search array
  1
  >>> print(lindex([], 1))  # default not-found computation:
  None
  >>> print(lindex([1], 2, lambda _lizt, _value: _lizt.index(_value - 1)))  # computes index of previous value
  0
  '''
  return wrapExc(lambda: lizt.index(value), lambda: otherwise(lizt, value))  # ValueError


def lappend(listOrSet, elem):
  ''' Append one or more element(s) to a set or list, returning the updated set or list (in-place).
  >>> a = [1, 2, 3]; lappend(a, 4)  # check return list
  [1, 2, 3, 4]
  >>> a == [1, 2, 3, 4]  # was updated in-place
  True
  >>> lappend(a, [1, 2])  # append several values
  [1, 2, 3, 4, 1, 2]
  >>> list(sorted(lappend(set([1]), {2, 0})))  # append using a set
  [0, 1, 2]
  '''
  assert isinstance(listOrSet, (list, set))
  ((listOrSet.extend if isinstance(listOrSet, list) else listOrSet.update) if isinstance(elem, (list, set)) else (listOrSet.append if isinstance(listOrSet, list) else listOrSet.add))(elem)
  return listOrSet


def findIndexOrCreateNext(lizt, elem):  # TODO unused
  ''' Returns index of element or next available index. This differs from lindex by providing the "otherwise next" part.
  >>> findIndexOrCreateNext([1, 2, 5], 4)
  3
  >>> findIndexOrCreateNext([1, 2, 5], 2)
  1
  '''
  assert isinstance(lizt, list)
  assert not isinstance(elem, (list, set))
  return lindex(lizt, elem, otherwise = lambda l, v: len(l))


def findIndexOrAppend(lizt, elem):
  ''' Find index of element if existing, else add and return its index.
  This differs from findIndexOrCreateNext by actually appending the elemnt to the list.
  >>> l = [1, 2, 3]; findIndexOrAppend(l, 2)
  1
  >>> l = [1, 2, 3]; findIndexOrAppend(l, 4)
  3
  >>> print(l)
  [1, 2, 3, 4]
  '''
  return lindex(lizt, elem, otherwise = lambda l, v: l.append(v) or len(l) - 1)


def isDir(f):  return wrapExc(lambda: os.path.isdir(f) and not os.path.islink(f), False)  # HINT silently catches encoding errors


def isFile(f): return wrapExc(lambda: os.path.isfile(f), False)  # handle "no file" errors


def isGlob(f):
  ''' Is the specified pattern a potential glob?
      HINT TODO doesn't allow yet square bracket patterns like "[123] or "[a-z]""
  >>> isGlob("a*b.jp?")
  True
  >>> isGlob("sdf.txt")
  False
  >>> isGlob("folder?")
  True
  '''
  return '*' in f or '?' in f


def isUnderRoot(root, folder):
  r''' Check if a filepath is under the discovered repository root.
  >>> isUnderRoot("C:\\", "D:\\file.txt")
  False
  >>> isUnderRoot("C:\\Windows", "C:\\Windows\\System")
  True
  >>> isUnderRoot("C:\\Windows", "C:\\Windows")  # same path
  True
  '''
  return os.path.commonprefix([root, folder]).startswith(root)



def getTsMs(): return int(time.time() * 1000.)  # timestamp rounded to milliseconds for metadata comparison


def dictGet(dikt, key, default, set = False):
  ''' dict.get() that returns default when missing.
      dikt: a dictionary
      key:  key to find value of
      default: value or callable (to compute value) to use if key missing
  >>> dictGet({}, 'a', dictGet({'a': 1}, 'b', 2))
  2
  >>> dictGet({}, 'a', dictGet({'a': 1}, 'b', lambda: 3))
  3
  '''
  try: return dikt[key]
  except KeyError:
    try: value = default()  # Pythonic way - this is slightly faster than the ternary expression below!
    except: value = default
    # value = default() if callable(default) else default
    if set: dikt[key] = value
    return value


def dictGetSet(dikt, key, default):
  ''' dict.get() that computes and adds missing values.
      dikt: dictionary
      key:  key to get or set
      default: value or callable to compute value
      Returns existing value otherwise new (computed) value.
  >>> a = {}; b = a.get(0, 0); print((a, b))  # normal dict get
  ({}, 0)
  >>> a = {}; b = dictGetSet(a, 0, 0); print((a, b))  # improved dict get
  ({0: 0}, 0)
  >>> a = {}; b = dictGetSet(a, 0, lambda: 1); print((a, b))  # improved dict get
  ({0: 1}, 1)
  '''
  return dictGet(dikt, key, default, set = True)


def splitByPredicate(lizt, pred, transform = None):
  ''' Split lists by a (boolean) predicate.
      transform: optional transformation on resulting elements
      returns ([if-true], [if-false])
  >>> print(splitByPredicate([1,2,3,4,5], lambda e: e % 2 == 0))
  ([2, 4], [1, 3, 5])
  '''
  MATCH, NO_MATCH = 0, 1
  return reduce(lambda acc, nxt_: (
      lappend(acc[MATCH], nxt_ if transform is None else transform(nxt_)), acc[NO_MATCH])
    if pred(nxt_) else
      (acc[MATCH], lappend(acc[NO_MATCH], nxt_ if transform is None else transform(nxt_))),
    lizt, ([], []))


def caseCompareKey(c):
  ''' Python 3 key function for sorting, only used in debug output. '''
  if c == '': return 0
  if len(c) > 1: return ord(c[0].lower()) << 8 | caseCompareKey(c[1:])
  return ord(c.lower())


def constituentInPath(path, skip):
  if path.endswith(SLASH + skip):  return True  # also covers: if path == SLASH + skip: return True
  if SLASH + skip + SLASH in path: return True  # also covers: if path.startswith(SLASH + skip + SLASH): return True
  return False


def pathHasGlobalSkip(path, skips):
  ''' True if any path matches the global skip paths (regex for full, beginning, middle, end).
      Uses dynamic generation of regular expressions TODO path sanitization before re for security
  >>> pathHasGlobalSkip('/a', ['a'])
  True
  >>> pathHasGlobalSkip('/b', ['a'])
  False
  >>> pathHasGlobalSkip('/a/b/c', ['b'])
  True
  '''
  assert isinstance(path, str)
  assert isinstance(skips, list)
  return xany(lambda skip: constituentInPath(path, skip), skips)


def pathHasGlobalIgnore(path, ignores):
  ''' Check if last path constituent matches any global ignore pattern.
  >>> normalizer.setupCasematching(True)
  >>> pathHasGlobalIgnore('/a/b', ['b'])
  True
  >>> pathHasGlobalIgnore('/a/b', ['B'])
  False
  >>> normalizer.setupCasematching(False)
  >>> pathHasGlobalIgnore('/a/b', ['c'])
  False
  >>> pathHasGlobalIgnore('/a/b', ['C'])
  False
  >>> pathHasGlobalIgnore('', [''])
  True
  '''
  assert isinstance(path, str)
  assert isinstance(ignores, list)
  if not path: return '' in ignores  # check root ignore
  basename = path[path.rindex(SLASH) + 1:] if SLASH in path else path
  return xany(lambda ignore: normalizer.globmatch(basename, ignore), ignores)


def anyParentIsSkipped(path, paths):
  ''' True if any prefix path of path is marked as "skip", so that all children can be skipped, too.
  >>> anyParentIsSkipped('/a/b', {'/a': {'skip': ''}})
  True
  >>> anyParentIsSkipped('/a/b', {'/a/b': {'ignore': ''}})
  False
  '''
  assert isinstance(path, str)
  assert isinstance(paths, dict)
  def append(elem): nonlocal current; current += (SLASH + elem); return current  # append expression
  elements = path.split(SLASH)
  current = elements[0]
  if SKIP in paths.get(current, {}): return True
  return xany(lambda i: SKIP in paths.get(append(elements[i]), {}), range(1, len(elements)))  # test all parent paths


def splitTags(lizt):
  ''' Parse comma-separated arguments like tags.
  >>> print(splitTags([]))
  []
  >>> print(splitTags(["a,b"]))
  ['a', 'b']
  >>> print(splitTags(["ab"]))
  ['ab']
  >>> print(splitTags(["ab,"]))
  ['ab']
  '''
  assert isinstance(lizt, list)
  return [x for x in (y.strip() for y in reduce(lambda a, b: a + ([b] if COMB not in b else safeSplit(b)), lizt, [])) if x != ""]


def removeTagPrefixes(poss, negs):
  ''' Remove leading "inclusive" or "exclusive" +/- markers from tag lists.
  >>> print(removeTagPrefixes(["a"], []))
  (['a'], [])
  >>> print(removeTagPrefixes(["+a", "b"], ["-c", "d"]))
  (['a', 'b'], ['c', 'd'])
  '''
  return [p.lstrip('+') for p in poss], [n.lstrip('-') for n in negs]


if __name__ == '__main__': import doctest; doctest.testmod()
