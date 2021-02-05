''' tagsPlorer library  (C) 2016-2021  Arne Bachmann  https://github.com/ArneBachmann/tagsplorer '''

import os, re, sys


# Compute
with open(os.path.join(os.path.dirname(__file__), 'VERSION'), encoding = 'utf-8') as fd: VERSION = fd.read()
ON_WINDOWS = sys.platform == 'win32'


# Constants
MAJOR_VERSION = 0
APPNAME = "tagsPlorer"  # or something clunky like "virtdirview"
APPSTR  = APPNAME + " version %s  (C) 2016-2021  Arne Bachmann" % VERSION
RIGHTS  = 0o760  # for creating new index folders (usually exist already)
CONFIG  = ".tagsplorer.cfg"  # main user-edited configuration file
INDEX   = ".tagsplorer.idx"  # index         file (re-built on every manual or detected file system change)
SKPFILE = ".tagsplorer.skp"  # skip   marker file (could equally be configured in configuration instead)
IGNFILE = ".tagsplorer.ign"  # ignore marker file (could equally be configured in configuration instead)
IGNORE, SKIP, TAG, FROM, SKIPD, IGNORED, GLOBAL = "ignore", "skip", "tag", "from", "skipd", "ignored", "global"  # allowed config file options
COMB, SEPA, SLASH, DOT, ALL, ST_MTIME, ST_SIZE = ",", ";", "/", os.extsep, "*", 8, 6  # often-used constants
TOKENIZER = re.compile(r"[\s\-_\.]+")  # tokenize file names as additional tags WARN may return empty string
REGEX_SANITIZE = re.compile(r"([\.\[\]\(\)\^\$\+\*\?\{\}])")  # all special regex characters to escape
PICKLE_PROTOCOL = 4  # (Python V3.4+) for pypy3 compatibility
SKIPDS = ["$RECYCLE.BIN", "System Volume Information"]
IGNOREDS = []
