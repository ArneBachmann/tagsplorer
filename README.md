Linux: [![Build Status](https://travis-ci.org/ArneBachmann/tagsplorer.svg?branch=master)](https://travis-ci.org/ArneBachmann/tagsplorer) Windows: [![Build status](https://ci.appveyor.com/api/projects/status/46axk9bixn4ab0d5/branch/master?svg=true)](https://ci.appveyor.com/project/ArneBachmann/tagsplorer/branch/master)  Test coverage: [![Coverage Status](https://coveralls.io/repos/github/ArneBachmann/tagsplorer/badge.svg?branch=master)](https://coveralls.io/github/ArneBachmann/tagsplorer?branch=master)

# tagsPlorer
A quick and resource-efficient OS-independent tagging filetree extension tool and library written in Python, working with both Python versions 2 and 3.

Each folder name of the indexed file tree is implicitly treated as a tag name, and additional tags can be set or excluded on singular files or file glob patterns. Contents of other folders in the file tree can virtually be mapped into others.
The entire system is fully backwards-compatible with the common file tree metaphor present in most file systems.

## Initial example
If you happen to manage your data in a tree-like manner, as supported by most all currently used file systems, your data may look like that:

 /personal/money/tax/2016
 /personal/money/tax/2017
 /personal/money/invoice/2016
 /personal/money/invoice/2017
 /personal/travel/2011/hawaii
 /personal/travel/2011/new york
 /work/projects/archive
 /work/projects/current/communication

This is just an example, but gives you the general idea. In each folder, you have files of varying types like office documents, media, or other.
tagsPlorer allows you to create virtual "views" over your file by asking for "all Word documents from 2016", or "all money-related spreadsheets files from 2017" etc.:

`tp.py .docx 2016` or `tp.py money 2017 .xlsx`

## Problem statement
Nowadays most operating systems and window managers still adhere to the "tree of files" metaphor, or try to employ some kind of integrated search engine to find and access existing files.
Both approaches have strong drawbacks that could be solved by tagging files individually, and only when needed.

### Problems with file trees
Each file belongs to only one parent folder, which practically prohibits a file to be found under more than one category. This can be solved locally by using soft or hard links, if the OS supports them, or storing the same file several times in different folders. In that case, however, you either loose OS-independence, compatibility with version control systems becomes clunky and error-prone, or you have lots of duplication that again leads to human errors.

### Problems with search engines
There are (semantic) search engines that continuously crawl and oversee your file system, guessing and suggesting what you might want to access next. Here the problem lies in the system overhead and loss of control - you don't know if you are presented the right file versions, and if you search for the right terms, plus you loose oversight of your file system structure.

## Solution: tagsPlorer to the rescue!
TagsPlorer uses a simple concept which enables you to continue using simple and compatible file trees, keep all your data under version control of your choice, allows you to put files or entire folders into more than one (virtual) category, and still benefit from little manual maintenance or additional setup. The benefit will increase even more with graphical tools using this library and with tight integration into your OS of choice.

# Usage
Hint: Currently it's not possible to glob over folder names efficiently; trying to do so will need to walk all folders that are left in the filter process or will have no effect when preselection picks up a set of potential folder matches before.

## Command-line interface
The current main and only user interface is `tp.py`, a thin yet convenient layerover the library's basic functions.
Here is a short description of valid program options and arguments:

* `--help`

  Shows user options, same as detailed in this section

* `--version`

  Shows tagsPlorer code base version string

* `--init [-r rootfolder]`

  Create an empty configuration in the current (or the relative or absolute one specified by the -r option) folder.
  The location of a configuration file `.tagsplorer.cfg` marks the root path for an entire indexed file tree. No other configuration files higher up the parent hierarchy will be considered. This allows for nested sub-indices, which is however not recommended (similar to not nesting version control system checkouts)

`--update` or `-u`

  Update the file index by walking the entire folder tree from the root down to leaf folders.
  This creates or updates the `.tagsplorer.idx` index file with updated contents to match the current state of the files regarding the configuration specified.
  As this file will be written over on every index run, there is no need to track outdated items, perform memory management or garbage collections inside the index, which simplifies the entire software model and mental model.

* `--search [[+]tag1[,tags2[,tags...]]] [[-]tag3[,tag4[,tags...]]] [-r rootfolder]` or `-s` or no option switch plus search terms appended

  Perform a search (which corresponds to a "virtual folder" listing).
  This is the main usage for tagsPlorer tools and accepts inclusive as well as exclusive search terms.
  There can be any number of arguments, which optionally can also be specified in a comma-separated way (after one initial positives tag), or using the `-x` option with optional comma-separated further exclusive terms.
  Note, however, that the command line interface cannot distinguish between valid option switches (like -r <root>) and negative tag arguments (like -r to exclude all files tagged with "r"). Therefore, negative (exclusive) tag arguments must be specified after either a double-dash `--` or after a comma of a positive (inclusive) term.

* `--exclude tag[,tag2[,tags...]]` or `-x`

  Specify tags to exclude explicity when searching (not listing any files or folders that match these tags).

* `--tag [+][-]tag[,[+][-]tag2[,tags...]] file[,file2[,files...]]` or `-t`

  Action that defines a (set of) (inclusive or exclusive) tag(s) for the following file name(s) or glob pattern(s).
  This information is stored in the configuration file and is respected in the index upon next search (-s) or file tree walk (-u).

* `--untag` [+][-]tag[,tag2[,tags...]] file[,file2[,files...]] or `--del`

  Specifies a (set of) (inclusive or exclusive) tag(s) to be removed for the following file name(s) or glob pattern(s).
  The tagging information stored in the configuration file is updated accordingly.
  Removing a positive yet undefined tag does not automatically invert it into an exclusive mark. Removal works solely on a pattern basis in the configuration file, and never on actual files currently found or matched by existing file or glob pattern(s).

* `--log level` or `-l` with level one value out of 0,1,2

  Specify the detail level for printed messages.
  Note, however, that the program still prints to both stderr and stdout, depending on the content to log (currently, only search results got to stdout, while all log messages go to stderr). TODO check outputs of --dir and add/tag results etc.
  Also note, that the maximum log level displayed is hard-coded into the source code (default: INFO - not printing DEBUG statements).

* `--set key=value`

  Sets a global configuration value. Currently supported values are: `case_sensitive` (true/false)

* `--get key`

  Prints out a global configuration value.

* `--unset key`

  Removes a global configuration value. This usually switches back to the default logic or value.

* `--relaxed`

  Be more lenient when adding tags (allow to define tags even for missing files, or for globs that don't match any file at the time of definition).

* `--simulate` or `-n`

  Don't write anything to the file system. TODO check if true in all places

* `--force` or `-f`

  Do things even against warning or in potentially dangerous situations: Currently covered are a) Creating a new index root file, and b) adding tag file patterns already covered by globs for that tag.

* `--dirs`

  List only matching folders instead matchng files in matching folders, plus allows glob matching on folder names (but only for the already reduced set of paths of remaining non-glob tags, or from all paths if none found at all).

# Architecture and program semantics
## Search algorithm
In general, what the program does is simple boolean set operations. The index maps tags to folders, with the risk of false positives (it's an over-specified, optimistic index, linking folders with both inclusive or exclusive manual tag settings and tags mapped from other folders, plus file extension information).
After determination of potential folders in a first search step, the found folders' contents are filtered by potential further tags and inclusive or exclusive file name patterns. This step always operates on the actual currently encountered files, not on any indexed and potentially outdated state, to ensure correctness of output filtered data.


## Configuration file
Using the tagsPlorer's `-i` option, we can create an empty configuration file which also serves as the marker for the file tree's root (just like the existence of version control systems' `.svn` or `.git` folders mark their respective root folders).
Usually, all access to the configuration file should be performed through the `tp.py` command line interface or directly through the `lib.py` library functions.
The configuration file follows mainly the format and structure of Windows' INI-file, but without any interpolation or substitution logic (not using Python's built-in `ConfigParser`, to enable multiple keys).
The first line contains a timestamp to ensure that the matching index file `tagsplorer.idx` file is not outdated.

For each section, including the root section `[]`, any number of occurences of the following options may be added.
The root section additionally allows for global configuration options that can be set and queried by the `--set`, `--unset` and `--get` command line switches.
The following list describes all potential settings:

* `tag=name;includes;excludes`

  Defines a tag `name` for the file name(s) specified in `includes` string, excluding those specified in the `excludes` string. `name` should differ from the current folder name, to give a sensible added value. TODO add check plus force option.
  `includes` and `excludes` are comma-separated lists of file names and file globs.
  The order of evaluation during search is always left-to-right; there is no deeper semantics prohibiting the user to add e.g. file names or stricter globs that are already included in other looser glob patterns (inclusive or exclusive) but warnings may be issued.

* `from=path`

  Virtually maps the provided folder `path`'s contents into the (current) specified folder, including all its specified tags, observing respective include and exclude constraints on its files during search.
  There is not recursive `from` mapping; only one level of mapping is considered (and that's a good thing!).

* `ignore=`

  Advises the file indexer to not index this folder's contents, but continue traversal into its sub-folders. The current folder's name (tag) is ignored for all sub-folders' files indexing (they won't get this parent folder's tag).

* `skip=`

  Advises the file indexer to not index this folder's contents and don't recurse into its sub-folders, effectively skipping the entire folder tree.

* `alias=name`

   TODO: Implement it.

In addition, it's possible to specify global settings under the root configuration section `[]`, usually updated by the `--set` and `--unset` command line options:

* `global=key=value`

  This defines a global configuration variable `key` with the contents of `value`, which is either a string or boolean toggle.
  The following values are currently allowed:

  * *`case_sensitive`*

      This key is either `true` or `false` or undefined.
      If undefined, the current operating system determines, if character case is used for file name indexing and searching (Windows defaults to false, other operating systems may default to true).

* `ignored=dirname`

  Similar to single folders' `ignore` configuration, this defines a global folder (directory) name to ignore and to not index; per `ignored` configuration entry only one folder is specified.

* `skipd=dirname`

  Similar to `skip` this defines a global folder name to skip and not recurse into.

## Tagging semantics
TODO What happens if a file with a tag gets mapped into the current folder, where the same tag excludes that file? Or the other way around?
This currently cannot happen, as all folders are processed individually and then get merged into a single view, with duplicates being removed. There is no real link to the originating folder for the folder list, as we have the concept of virtual (tag) folders in a unified view.

## Design decisions regarding linking on the file system level
If files are hard-linked between different locations in the file tree and are submitted to the version control system, they won't be linked when checking out at different locations, and modifying one instance will result on several linked copies being modified on the original file system when updated. This leads to all kinds of irritating errors or VCS conflicts.

1. Option: tagsPlorer has to intercept update/checkout and re-establish file links according to its metadata (configuration). This is hard to guarantee.
2. Option: Add ignore details to the used VCS (.gitignore or SVN ignore list) for all linked (or rather mapped) files. The danger here is of course to ignore files that later could be added manually, and not being able to distinguish between automatically ignored files, and those that the user wants to ignore on purpose.
3. Option: As by the current design the snapshot `*.idx` file is not persisted in VCS (TODO add ignore automatically), all links can be recreated on first file tree walk (as option 1), even if linked files were earlier submitted as separate files, the folder walk would re-establish the link (potentially asking the user to confirm linking forcing to choose one master version, of issueing a warning for diverging file contents).

## Other design decisions
* The implementation of the simple switch for `case_sensitive` raised quite a lot of semantic questions. For one, should file extensions be treated differently from file names? Is there a benefit of ignoring case for extensions, but not for the actual names? Probably not. Secondly, if we store data case-normalized in the index, we lose the relationship to the actual writings of the indexed folder names, which might cause problems. This would only occur on a case_sensitive file system with `case_sensitive` set to `false`. As a conclusion, we might need to separate storage of tag dirs from other tags or file extensions, or modify search operation to case-normalize instead of doing this in the index, which would slow down the program. Current conclusion: Tough, would need mapping from case-normalized to actual naming on filesystem, or lower() comparisons all over the place :-( to be delayed

* Although semantically better suited, in many places we don't use `not a.startswith(b)`, rather the shorter (and faster) `a[0] != b`, but we must ensure a length > 0.

* Program output is written to stdout for further processing by other tools, all logging on stderr.

* Globbing on tags or folders is not intended to work, because the index is made for quick checks. It does nevertheless work when no matching folders were found (due to glob patterns being not represented in the index) and traversing the entire folder tree. A second option is to use the `--dirs` option. TODO add tests, because still unsure if all working fine

* For the "skip folder" logic, we *could* have used a semantics of "index the folder, but don't recurse into its sub-folders". However, we prefer marking and skipping each sub-folder to ignore individually, because it's more flexible; implementation complexity has not been compared, but could be similar.

* Different implementations and replacements for the built-in configuration parser have been tested; there is, however, no version that both a) allows reading values for duplicate keys, and b) is fully interoperable between Python 2 and 3. The alternative of using JSON may be considered, but is potentially harder to edit by humans and requires profiling to make a decision.

* The index itself is designed to be both low on memory consumption and fast to load from the file system. After profiling storing it compressed vs. not compressed, the level 2 zlib approach delivered optimal results on both resource restricted and modern office computers, and offers only minimally worse compacted file size compared even to bz2 compression level 9, while almost being as fast to unpickle as pure uncompressed data (which again was faster than any bz2 level).



# Development

## Git and Github workflows
The master branch should always run fine and contain the latest stable version (release). Currently we are pre-V1.0 therefore everything is still happening either on master or on other branches without announcement.
Development activities are merged on the develop branch, and only merged to master for a release.

# Known issues

* It's possible to commit file names into Subversion, that aren't allowed to checkout on Windows, e.g. `file.`. Since this is no problem that tagsPlorer can solve, we ignore this potential problem. In the code, the only difference was whether to check for the DOT from first to last character, or only from first to second last.

* ...
