Linux: [![Build Status](https://travis-ci.com/ArneBachmann/tagsplorer.svg?branch=master)](https://travis-ci.com/ArneBachmann/tagsplorer) Windows: [![Build status](https://ci.appveyor.com/api/projects/status/46axk9bixn4ab0d5/branch/main?svg=true)](https://ci.appveyor.com/project/ArneBachmann/tagsplorer/branch/main)  Test coverage: [![Coverage Status](https://coveralls.io/repos/github/ArneBachmann/tagsplorer/badge.svg)](https://coveralls.io/github/ArneBachmann/tagsplorer)


# tagsPlorer
A quick and resource-efficient OS-independent tagging folder tree extension tool and library written in Python.
*tagsPlorer* is licensed under the [Mozilla Public License version 2.0](https://www.mozilla.org/en-US/MPL/2.0/), which can also be found in the [`LICENSE`](LICENSE) file.

Each folder name of the indexed file tree is implicitly treated as a tag name, and additional tags can be set or excluded on singular files or file glob patterns.
Contents of other folders in the file tree can virtually be mapped into the tree.
The entire system is fully backwards-compatible with the common file tree metaphor present in most file systems.


## Initial example
If you happen to manage your data in a tree-like manner, as most often the case in most any contemporary file system, your data may look similar like that:

```
/personal/money/tax/2016
/personal/money/tax/2017
/personal/money/invoice/2016
/personal/money/invoice/2017
/personal/travel/2011/hawaii
/personal/travel/2011/new york
/work/projects/archive
/work/projects/current/communication
```

This is just an example, but gives you the general idea.
In each folder, you have files of varying types like office documents, media, or others.
*tagsPlorer* allows you to create virtual "views" over your files allowing your to ask for "all Word documents from 2016" via `tp .docx 2016`, or "all money-related spreadsheets files from 2017" via `tp money 2017 .xlsx`.


## Problem statement
Nowadays most operating systems and file system browsers still adhere to the *tree of files* metaphor, or try to employ some kind of integrated search engine to find and access existing files.
Both approaches have noticeable drawbacks that could be solved by adding a thin optional tagging layer.

### Problems with file trees
Each file belongs to exactly one parent folder, which practically prohibits a file to be found under more than one category, one exception being Windows 7's libraries, which are virtual views over several folders.

This can be solved locally by using soft or hard links, if the operating system and file system support them, or storing the same file several times in different folders.
In that case, however, you either lose independence from the operating system, and/or compatibility with version control systems becomes clunky and error-prone, or you have lots of duplication that might lead to human errors and increased storage demands.

### Problems with search engines
Some desktop systems come with (sometimes even semantic) search engines that continuously crawl and index your files, plus guess and suggest what you might want to access next.
Here the problem lies in the system overhead and loss of control - you don't know if you are presented the relevant file (or version of tit) and if the search terms are correct, and you lose oversight of your actual underlying file system structure.


## One solution: tagsPlorer to the rescue!
*tagsPlorer* uses a simple concept which enables you to
- continue using simple and compatible file trees and the standard load/save file dialogs,
- keep all your data under version control of your choice,
- allows you to put files or entire folders into more than one (virtual) category,

and still benefit from only little manual maintenance or additional setup.
The benefit will increase even more with graphical tools using this library and with tighter integration into the OS or desktop system of your choice.


## History
The author has been attempting to write similar utilities several times in the past, namely `taggify`, `tagtree`, and `tagtree2`.
This is his latest take at this persistent problem of convenient semi-sewmantic data archiving and retrieval by using space-efficient ahead-of-time indexing.
There are similarities to the Linux `find` and `grep` utilites, which are performant but crawl the entire folder tree on every search, and don't support virtual folder mapping.
There exist other projects with similar goals, e.g. [TMSU](https://github.com/oniony/TMSU).


## Usage
*Hint:* Currently it's not possible to glob over folder names efficiently; trying to do so requires *tagsPlorer* to walk all folders that are left after an initial preselection process, or will have no effect when preselection picks up a set of potential folder matches before that step.


## Command-line interface
Try running *tagsPlorer* with the [PyPy](http://pypy.org) Python 3 distribution.

The current only user interface is the console script `tp` (or `python3 -m tagsplorer.tp`, a thin yet streamlined layer over the library's basic functions.
*Glob patterns* support using `*` and `?` to match any character sequence or single character, but not character lists and ranges like `[abc]` or `[a-z]`; also make sure to quote the globs correctly for your shell.

Here is a short description of valid program options and arguments:

- `--init [--root <rootfolder>]` or `-i [-r <rootfolder>]`

  Create an empty configuration in the current (or specified) folder.

  The location of the configuration file `.tagsplorer.cfg` marks the root path for an entire indexed file tree.
  No files higher up the parent hierarchy will be considered.
  This - in theory - allows for nested sub-indices, (not recommended, though).

  Creating the root configuration will not start indexing the folder tree.
  Use the `--update` command or a search command to trigger that.

`--update` or `-U`

  Update the file index by walking the entire folder tree from the root down to leaf folders.
  This creates or updates (in fact replaces) the index in `.tagsplorer.idx` with the file system state respecting the current configuration.
  As this file will be written over on every index run, there is no need to track outdated items or perform memory management in the index.
  This simplifies the entire software model.

- `[--search|-s] [[+]tags1a[,tags1b[,tags1c...]] [[+]tags2a[,...]]] [[-]tags3a[,tags3b[,tags3c...]]]` or *no* command switch plus search terms appended

  Perform a search with inclusive (`+`) and exclusive (`-`) search terms.

  This is the main operation for *tagsPlorer* and accepts search terms like tags, folder names, file names, file extensions, or glob patterns.

  Multiple terms can be specified by either repeating the `-s` or `-x` commands, by using commas between arguments, or by noting down terms directly with preceding `+` or `-`.

  Do not provide more than one inclusive or exclusive file extension, as it would always return or exlude zero matches.

  Note, however, that the command line interface cannot distinguish between valid option switches (like `-r <root>` or `--root <root>`) and exclusive tags (like `-r` to exclude all files tagged with "r").

  Alternatively, exclusive tags must either be specified with an additional dash in front (`--r` or `---root`) or after a comma of a inclusive term. TODO check if all these are true

- `--exclude tag[,tag2[,tags...]]` or `-x`

  Specify tags to exclude explicity when searching (not listing any files or folders that match these tags).

- `--tag | -t [+|-]tag1[,[+|-]tag2[,tags...]] [path/][[+|-]glob[,[+|-]glob2[,globs...]] [[path2/][+|-]glob[...]`

  Action that defines one or more inclusive or exclusive tags for the given (or current) path under the specified glob patterns.
  This information is stored in the configuration file `.tagsplorer.cfg` and is respected during index creation and search upon next file tree walk.

  Given glob patterns are treated as conjunctive (logical and, reducing the set of matches).
  To specify alternative disjunctive patterns, run the tag command several times with different patterns (logical or, enlarging the set of matches).

  Historically this command added one or more inclusive or exclusive tags to a glob pattern in a folder.
  As of now, this command assigns a tag to one or more conjunctions of inclusive and exclusive glob patterns in a folder.
  This design change is more technical but more useful.

- `--untag | -u [+|-]tag[,[+|-]tag2[,tags...]] [path/][+|-]glob[,[+|-]glob2[,globs...]] [[path2/][+|-]glob[...]`

  Action that removes one or more inclusive or exclusive tags for the given (or current) path under the specified glob patterns.

  Removing an inclusive yet undefined tag does not automatically invert it into an exclusive mark.

  Removal works solely on a pattern basis in the configuration file, and never on actual files currently matched by existing glob patterns.

- `--set <key>=<value>`

  Sets a global configuration parameter.

  Currently supported keys are:

  - `case_sensitive`      (on/off, default is true if not on Windows)
  - `reduce_storage` (on/off, default is false)

  Assuming the existence of a filder /folder/File:

  | `case_sensitive` | `reduce_storage` | Windows | Linux | Find `File` | Find `file` | Find `FILE` |
  | ---------------- | ---------------- | ------- | ----- | ----------- | ----------- | ----------- |
  | yes              | no               | yes     | no    | yes         | no          | no          |
  | yes              | no               | no      | yes   | yes         | no          | no          |
  | yes              | yes              | yes     | no    | yes         | no          | no          |
  | yes              | yes              | no      | yes   | yes         | no          | no          |
  | no               | no               | yes     | no    | yes         | yes         | yes         |
  | no               | no               | no      | yes   | yes         | yes         | yes         |
  | no               | yes              | yes     | no    | yes         | yes         | yes         |
  | no               | yes              | no      | yes   | yes         | yes         | yes         |



- `--get <key>`

  Prints out the value of a global configuration parameter.

- `--unset <key>`

  Removes a global configuration parameter. This switches back to the default value.

- `--simulate` or `-n`

  Don't write anything to the file system. TODO check if true in all places

- `--force` or `-f`

    Perform actions despite warnings or in potentially dangerous situations. This currently covers:

    - write over an index root file (removing all settings)
    - adding tag file patterns already covered by globs for that tag

- `--dirs`

  List only matching folders instead of all files in matching folders, plus allows glob matching on folder names.

  Glob matching works only on already the tag-filtered folder list, not necessarily on all indexed folders.

- `--verbose` or `-v` | `--debug` or `-V`

  Specify the detail level for printed messages.
  `-v` increases the log level to `INFO`
  `-V` increases the log level to `DEBUG`

- `--stdout`

  Write log to STDOUT instead of STDERR.
  This allows piping for certain situations (e.g. continuous integration or legacy products).

- `--help`

  Shows user options, which are described in more detail in this section

- `--version`

  Shows *tagsPlorer* code base version string and copyright notice


## Architecture and program semantics

### Search algorithm
In general, what the program does is simple boolean set operations.
The indexer maps tags (which include file and folder name (constituents), user-specified tags, and file extensions) to folders, with the risk of false positives (it's an over-generic, optimistic index that links folders with both inclusive or exclusive manual tags plus tags mapped from other folders, plus file extension information).
After determination of potential folders in a first search step, their contained file names are filtered by potential further tags and inclusive or exclusive file name patterns.
This step always operates on the actual currently encountered files, not on any indexed and potentially outdated state, to ensure correctness of output filtered data.
If a mapped folder is excluded by a negative tag, its contents can still be found by the name of the positive tags of the mapping. TODO check if true.


## Configuration file
Using the *tagsPlorer*'s `-i` option, we can create an empty configuration file which also serves as the marker for the file tree's root (just like the existence of version control systems' `.svn` or `.git` folders).
Usually all access to the configuration file should be performed through the `tp` command or directly via `tagsplorer/lib.py` library functions.
The configuration file follows mainly the format and structure of Windows' INI-file, but without any interpolation nor substitution (avoiding Python's built-in `ConfigParser` to enable multiple keys).
The first line contains a timestamp to ensure that the matching index file `tagsplorer.idx` file is not outdated.

The root section contains global configuration options that can be set and queried by the `--set`, `--unset`, `--get` and `--clear` commands.

Each section points to a path, including the root section `[]`, and specifies any number of occurences of the following options:

-   `tag=<name>;<includes>;<excludes>`

    Defines a tag `name` for the file name(s) specified in `includes` string, excluding those specified in the `excludes` string.
    `name` must differ from the current folder name, to give sensible added value. TODO add check plus force option.

    `includes` and `excludes` are comma-separated lists of file names and file globs.
    This allows powerful distinctions inside a single folder.

    The order of evaluation during search is always left-to-right; there is no deeper semantics prohibiting the user to add e.g. file names or stricter globs that are already included in other wider-scope glob patterns (inclusive or exclusive).

-   `from=<path>`

    Virtually map `path`'s contents into the (current) section's folder, including all its specified tags, observing respective include and exclude constraints on its files during search.
    There is no recursive `from` mapping; only one level of mapping is considered (and that's a good thing).

    It's possible to map a skipped folder into another folder, to suppress indexing its original folder name, but find all contents under the name it is mapped to.

    `<path>` is either a repository root-relative path starting with a slash like `/sub1/sub2` or a folder-relative path like `../super1` or `sub1`.

-   `ignore=`

    Advises the file indexer to not index this folder's contents, but continue traversal into its sub-folders.
    The folder's name (current section) is ignored as a tag for all sub-folders' indexing (they won't inherit this parent folder's tag TODO and name constituents, which are not yet implemented).

-   `skip=`

    Advises the file indexer to not index this folder's contents and not recurse into its sub-folders, effectively skipping the entire folder tree.

-   `rename=<name1>[,<name2>[,<names...>]]`

     Replace this folder's name with another one, effectively renaming it.
     TODO: Implement it.

Global settings are stored under the root section `[]`:

-   `global=<key>=<value>`

    This sets the global configuration variable `key` with the contents of `value`, which is either a string or boolean toggle.
    The following values are currently allowed:

    -   *`case_sensitive`*

        This key is either `true` or `false` and defaults to `true` on Linux-y operating systems and to `false` on Windows.
        The setting determines if search is case-sensitive.

        If set to `false`, search terms `a` and `A` will match both file names `a` and `A`; if set to `true`, `a` finds only `a` and `A` finds only `A`.

        Even if set to `true`, users may override the search behavior by using the command-line option `--ignore-case` or `-c`.

    -   *`reduce_storage`*

        This key is either `true` or `false` and defaults to `false`, if undefined.
        This setting determines if the indexer minimizes file name storage by keeping only one case version per entry.
        By default, *tagsPlorer* stores both true-case and case-normalized file names in the index.

        Setting `reduce_storage` to `true` deactivates storage of case-normalized file names.

-   *`ignored=dirname`*
    Define a global folder glob to ignore, but continue indexing its child folders.
    The glob is not a full path and only applied to the folder base name.

-   `skipd=dirname`

    Define a global folder glob that is skipped and not recursed into.
    The glob is not a full path and only applied to the folder base name.

## Marking folders

Individual folders can be marked as being ignored or to skip indexing all their children.
This can be done in three different ways:

1. Place a marker file `.tagsplorer.ign` or `.tagsplorer.skp` into the folder. Please note, that the filename is case-sensitive for all platforms.
2. Manually create a configuration setting inside the index configuration file `.tagsplorer.cfg` under the key `[/<path>]`: `ignore=` or `skip=`
3. Manually create a global configuration setting inside the index configuration file `.tagsplorer.cfg` under the root key `[]`: `ignored=<glob>` or `skipd=<glob>`


## Internal storage format
The indexer class contains the following data structures:

- `tagdirs`: array-of-strings containing all encountered folder names during file system walk.
  Duplicates are not removed (to retain folder-parent relations).
  May contain case-normalized versions of folder names as well, or even only those (depending on internal configuration settings and operating system run on).

    In a second indexing step, `tagdirs` is augmented with further non-folder tags defined in the configuration file or stemming from file extension information (see `tags` below).

- `tagdir2parent`: array-of-integers containing indexes of each `tagdirs` entry to its parent folder entry (in `tagdirs`).
  Each entry corresponds to one entry in the `tagdirs` structure; both data could equally have been represented as an array-of-pair-of-string-and-integer (equivalent to `zip(tagdirs, tagdir2parents`)).
- `tagdir2paths`: integer-dict-to-list-of-integers, mapping `tagdirs` indexes to lists of `tagdirs` indexes of the leaf folder name for all folders carrying that folder name.
  After indexing, this is converted into an array-of-lists-of-integer instead with index position corresponding to `tagdirs` positions.
  During indexing `tagdir2paths` makes use of default dictionary semantics for convenience.

There are two further intermediate data structures used during indexing:

- `tags`: array-of-strings containing all manually set tag names and file extensions, which gets mapped into the `tagdirs` structure after walking
- `tag2paths`: dict-from-integer-to-list-of-integer, mapping `tags` indexes to lists of `tagdirs` indexes of the leaf folder name for all folders carrying that tag.


## Tagging semantics
TODO What happens if a file with a tag gets mapped into the current folder, where the same tag excludes that file?
Or the other way around?
This currently cannot happen, as all folders are processed individually and then get merged into a single view, with duplicates being removed.
There is no real link to the originating folder for the folder list, as we have the concept of virtual (tag) folders in a unified view.


## Design decisions regarding linking on the file system level
If files are hard-linked between different locations in the file tree and are submitted to the version control system, they won't be linked when checking out at different locations, and modifying one instance will result on several linked copies being modified on the original file system when updated.
This leads to all kinds of irritating errors or VCS conflicts.

1. Option: *tagsPlorer* has to intercept *update*/*checkout* and re-establish file links according to its metadata (configuration).
This is hard to guarantee and communicate.
2. Option: Add ignore details to the used VCS (.gitignore or SVN ignore list) for all linked (or rather mapped) files.
The danger here is of course to ignore files that later could be added manually, and not being able to distinguish between automatically ignored files, and those that the user wants to ignore on purpose.
3. Option: As by the current design the snapshot `*.idx` file is not persisted to the VCS (TODO add ignore markers automatically), all links can be recreated on first file tree walk (as option 1), even if linked files were earlier submitted as separate files, the folder walk would re-establish the link (potentially asking the user to confirm linking forcing to choose one master version, of issueing a warning for diverging file contents).


## Other design decisions
- Configuration and index synchronisation

    - Most operations only modify the configuration file, updating its integrated timestamp, deferring crawling to the next operation

    - Only search operations require an up-to-date index.
      If a time skew between the configuration file's timestamp and the copy of the configuration file inside the index is detected, the index and all timestamps is updated by re-indexing all files.

- The implementation of the simple switch for `case_sensitive` raised quite a lot of semantic questions.
For one, should file extensions be treated differently from file names, and is there a benefit of ignoring case for extensions, but not for the actual names?
Probably not.
Secondly, if we store data case-normalized in the index, we lose the relationship to the actual writings of the indexed folder names, which might cause problems.
This would only occur on a case_sensitive file system with `case_sensitive` set to `false`.
As a conclusion, we might need to separate storage of tag dirs from other tags or file extensions, or modify search operation to case-normalize instead of doing this in the index, which would slow down the program.
Current conclusion: Tough, would need mapping from case-normalized to actual naming on filesystem, or lower() comparisons all over the place TODO :-( to be delayed

- Although semantically better suited, in many places we don't use `not a.startswith(b)`, but rather the shorter (and faster) `a[0] != b`, but we must of course ensure that `len(a) > 0` and `len(b) == 1`.

- Program output is written to stdout for further processing by other tools, all logging goes to stderr.

- Globbing on tags or folders is originally not intended to work, because the index is made for quick checks only.
It does nevertheless work in a situation when no matching folders were found (due to glob patterns being not represented in the index) and traversing the entire folder tree.
An alternative is to use the `--dirs` option. TODO add tests, because still unsure if all that is working fine

- For the "skip folder" logic, we *could* have used a semantics of "index the folder, but don't recurse into its sub-folders".
We prefer, however, marking and skipping each sub-folder to ignore individually, because it's more flexible; implementation complexity has not been compared, but could be similar.

- Different implementations and replacements for the built-in configuration parser have been tested; there is, however, no version that allows reading values for duplicate keys. TODO Python2 support was dropped, re-evaluate.
Using JSON as an alternative may be considered, but is potentially harder to edit by humans and diff by version control systems, thus requires profiling to make a decision.
Since configuration files may be persisted by users, this is also a breaking change which would require a migration path.

- The index itself is designed to be both low on memory consumption and fast to load from the file system, to the expense of higher CPU processing to recombine folder names into paths once printed out.
After profiling whether to store the index either compressed vs. uncompressed, the level `2` zlib approach delivered optimal results on both resource restricted and modern office computers, and offers only minimally larger compacted file size compared even to `bz2` compression level `9`, while almost being as fast to unpickle as pure uncompressed data (which again was faster than any `bz2` level).
Since speed is more important than storage size, even considering more effective compression methods like `lzma` weren't even considered.


## Development

### Git and Github workflows ##
The master branch should always run fine and contain the latest stable version (release). Currently we are still nefore V1.0 therefore everything is still happening either on master or on other branches without announcement.
Development activities are merged on the develop branch, and only merged to master for a release, which is then tagged.
If any releases are build in the future (e.g. for pip or conda installation), they would only be build from commits that pass all tests on e.g. *Travis CI* or *AppVeyor*.


## Known issues

- It's possible to commit file names into Subversion from operating systems like Linux, that aren't valid on Windows file systems, e.g. the filename `file.` with a trailing dot.
Since this is no problem that *tagsPlorer* can solve, we do not handle it in the code.
The only decision to make in that regard was whether to check for the DOT from first to last character, or only from first to second last (or even second to second last to avoid "hidden by convention" files to be indexed as extensions), which can be seen as premature optimization and unnecessary.


## TODOs
- are configured tags always case-sensitive? in many places (like tagging yes), in other places (like index+search) no, searching always depends on the config setting, and stored tags are treated exactly like user-specified tags, so no need to distinguish there!
- search for extension = 0 folder matches. why extensions not in folder index?
- case sensitive: what does it mean during index run vs. during search run?
    - search terms
    - folder names (index) vs. file system
- TODO Add option to avoid indexing all hidden dot-files (start check at second character) at the expense of having to use `?` glob to find them
- Moving the config file to create a different root requires adapting tag paths inside
