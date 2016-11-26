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
Hint: Currently it's not possible to glob over folder names efficiently; trying to do so will need to walk all folders that are left in the filter process. TODO true?

## Command-line interface
The current main and only user interface is `tp.py`, a thin layer over the library's basic functions.
Here is a short description of valid programoptions and arguments:

* `--help`
  
  Shows user options, as does this section

* `--test [-v]`

  Runs unit tests from `tests.py`. If `-v` is specified, use verbose mode. TODO create global `-v` mode? Currently covered by `-1`

* `--version`

  Shows version string of code base

* `--init [-r rootfolder]`

  Create an empty configuration in the current folder (or the relative or absolute one specified by the -r option). TODO don't overwrite unless `--force` specified.
  The location of a configuration file `.tagsplorer.cfg` marks the root path for an entire indexed file tree. No other configuration files higher up the parent hierarchy will be considered.

`--update` or `-u`

  Update the file index by walking the entire folder tree from the root to child folders.
  This creates or updates the `.tagsplorer.idx` file with newly found contents.
  Since this file will be written over on every inde run, there is no need to track outdated items, perform memory management or garbage collections inside the index.

* `--search [[+]tag1[,tags2[,tags...]]] [[-]tag3[,tag4[,tags...]]] [-r rootfolder]` or `-s` or no option

  Perform a search (which is like as virtual folder listing).
  This is the main use case for the tagsplorer tools and accepts inclusive as well as exclusive search terms.
  There can be any number of arguments, which optionally can also be specified in a comma-separated way (after positives tags), or using the `-x` option.
  Note, however, that negative (exclusive) tag arguments must be specified after a comma, as the command line interface currently cannot distinguish between valid options and negative arguments. TODO

* `--exclude tag1[,tag2[,tags...]]` or `-x` or `-n`

  Specify exclusive tags when searching.
  TODO check if not accidentally still accepting +/-.
  TODO check if we can remove this option? only when -tag coincides with an option.
  TODO check if -y -n syntax is better than +/- or --x?

* `--tag [+][-]tag1[,[+][-]tag2[,tags...]] file[,file2[,files...]]` or `-t`

  Specifies a (set of) (inclusive or exlusive) tag(s) for the following file names, or glob patterns.
  This information is stored in the configuration file and is respected in the index upon next search and file tree walk.

* `--log level` or `-l`

  Specify detail level for printed messages.
  Note, however, that the program still prints to both stderr and stdout, depending on content.
  Also note, that the maximum log level displayed, is hard-coded into the source code (default: INFO - not printing DEBUG statements).

* `--set key=value`

  Sets a global configuration value.

* `--get key`

  Prints out a global configuration value.

* `--unset key`

  Removes a global configuration value. This usually switches back to the default logic or value.

* `--strict`

  Fail earlier. TODO explain and expand places to use this

* `--simulate`

  Don't write anything to the file system. TODO use `-n` for that (like rsync?)

* `--force` or `-f`

  Do things even against warning or in a potentially dangerous situation. TODO explain where and expand uses.

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
