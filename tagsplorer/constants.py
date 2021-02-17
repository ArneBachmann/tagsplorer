''' tagsPlorer library  (C) 2016-2021  Arne Bachmann  https://github.com/ArneBachmann/tagsplorer '''

import os, re, sys


# Constants
MAJOR_VERSION = 0
APPNAME = "tagsPlorer"  # or something clunky like "virtdirview"
RIGHTS  = 0o760  # for creating new index folders (usually exist already)
CONFIG  = ".tagsplorer.cfg"  # main user-edited configuration file
INDEX   = ".tagsplorer.idx"  # index         file (re-built on every manual or detected file system change)
SKPFILE = ".tagsplorer.skp"  # skip   marker file (could equally be configured in configuration instead)
IGNFILE = ".tagsplorer.ign"  # ignore marker file (could equally be configured in configuration instead)
IGNORE, SKIP, TAG, FROM, SKIPD, IGNORED, GLOBAL = "ignore", "skip", "tag", "from", "skipd", "ignored", "global"  # allowed config file options
NL, COMB, SEPA, SLASH, DOT, ALL, ST_MTIME, ST_SIZE = "\n", ",", ";", "/", os.extsep, "*", 8, 6  # often-used constants
TOKENIZER = re.compile(r"[\s\-_\.!\?#,]+")  # tokenize file names as additional tags
PICKLE_PROTOCOL = 4  # (Python V3.4+) for pypy3 compatibility
SKIPDS   = [".git", ".svn", "$RECYCLE.BIN", "System Volume Information"]
IGNOREDS = []

ON_WINDOWS = sys.platform == 'win32'
