# tagsplorer
A quick and resource-efficient OS-independent tagging filetree extension tool and library written in Python, working with both Python versions 2 and 3.

## Problem statement
Nowadays most operating systems and window managers still adhere to the "tree of files" metaphor, or try to employ some kind of integrated search engine to find and access existing files.
Both approaches have strong drawbacks that could be solved by tagging files individually, and only when needed.

### Problems with file trees
Each file belongs to only one parent folder, which practically prohibits a file to be found under more than one category. This can be solved locally by using soft or hard links, if the OS supports them, or storing the same file several times in different folders. In that case, however, you either loose OS-independence, compatibility with version control systems becomes clunky and error-prone, or you have lots of duplication that again leads to human errors.

### Problems with search engines
There are (semantic) intelligent search engines that continuously crawl and oversee your file system, guessing and suggesting what you might want to access next. Here the problem lies in the system overhead and loss of control - you don't know if you are presented the right file versions, and if you search for the right terms.

## Solution: tagsplorer to the rescue!
Tagsplorer uses a simple concept which enables you to continue using simple and compatible file trees, keep all your data under version control of your choice, allows you to put files or entire folders into more than one (virtual) category, and still benefit from little manual maintenance or additional setup.

# Usage
Currently it's not possible to glob over folder names efficiently; trying to do so will need to walk all folders that are left in the filter process. TODO true?

# Architecture and program semantics
## Configuration file
Using the tagsplorer's `-i` option, we can create an empty configuration file which also serves as the marker for the file tree's root (just like the `.svn` or `.git` folders).
Usually, all access to the configuration file should be performed through the `tp.py` command line interface or the `lib.py` library functions. For quick initialization, however, it may be benefitial to add some options manually.
The file generally follows the Windows ini-file structure, but without any higher substitution logic.
The first line contains a timestamp to ensure that the index's `*.dmp` file is not outdated.

For each section, including the root section `[]`, any number of occurencens of the following options may be added.
The following list describes all potential settings:

* `tag=tagname;includes;excludes`
 
  Defines a tag `tagname` for the file names specified in `includes`, except those specified in `excludes`. `tagname` should differ from the current folder name, to give a sensible added value.
  `includes` and `excludes` are comma-separated lists of file names and file globs.

* `from=path`

  Virtually maps the provided folder `path`'s contents into the current folder, including all its specified tags, observing respective include and exclude constraints.
  There is not recursive mapping; only one level of mapping is available.

* `ignore=`

  Advises the file indexer to not index this folder's contents, but continue traversal in its sub-folders. The current folder's name (tag) is ignored for all sub-folders' files indexing.

* `skip=`

  Advises the file indexer to not index this folder's contents and don't recurse into sub-folders.

* `alias=name`

   TODO: Implement it.
   Specify an alternative folder name (tag) under which to find this folder's contents.
   The advantage would be that this works also in folder-only mode. TODO explain difference and usage scenarios (overspecific).

In addition, it's possible to specify global settings under the root configuration section `[]`:

* `global=key=value`

  This defines a global configuration variable `key` with the contents of `value`, which is either a string or boolean toggle.
  The following values are currently allowed:

  * `case_sensitive`

    This key is either `true` or `false` or undefined.
    If undefined, the operating system determines, if case is used for file name indexing and searching (Windows false, other OS true).

* `ignored=dirname`

  Similar to `ignore` this defines a global folder name to ignore and not index.
  TODO glob? several per line?

* `skipd=dirname`

  Similar to `skip` this defines a global folder name to skip and not recurse into.

## Tagging semantics
TODO What happens if a file with a tag gets mapped into the current folder, where the same tag excludes that file? Or the other way around?
This currently cannot happen, as all folders are processed individually and then get merged into a single view.

TODO define semantics of globs vs. single files

## Design decisions regarding linking on the file system level
If files are hard-linked between different locations in the file tree and are submitted to the version control system, they won't be linked when checking out at different locations, and modifying one instance will result on several linked copies being modified on the original file system when updated. This leads to all kinds of irritating errors or VCS conflicts.

1. Option: tagsplorer has to intercept update/checkout and re-establish file links according to its metadata (configuration). This is hard to guarantee.
2. Option: Add ignore details to the used VCS (.gitignore or SVN ignore list) for all linked (or rather mapped) files. The danger here is of course to ignore files that later could be added manually, and not being able to distinguish between automatically ignored files, and those that the user wants to ignore on purpose.
3. Option: As by the current design the snapshot `*.dmp` file is not persisted in VCS (TODO add ignore automatically), all links can be recreated on first file tree walk (as option 1), even if linked files were earlier submitted as separate files, the folder walk would re-establish the link (potentially asking the user to confirm linking forcing to choose one master version, of issueing a warning for diverging file contents).
