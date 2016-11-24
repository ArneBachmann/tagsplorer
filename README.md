# tagsplorer
A quick and resource-efficient OS-independent tagging filetree extension tool and library

Nowadays most operating systems and window managers still adhere to the "tree of files" metaphor, or try to employ some kind of integrated search engine to find and access existing files.
Both approaches have strong drawbacks that could be solved by tagging files individually, and only when needed.

## Problems with file trees
Each file belongs to only one parent folder, which practically prohibits a file to belong to more than one category. This can be solved locally by using soft or hard links, if the OS supports them. In that case, however, you loose OS-independence and working with version control systems becomes clunky and error-prone.

## Problems with search engines
There are semantic intelligent search engines that continuously crawl and oversee your file system, guessing what you might want to access. Here the problem lies in the system overhead and loss of control - you don't know if you are shown everything and if it's the right files and versions.

## tagsplorer to the rescue
Tagsplorer uses a simple concept which enables you to continue using simple and compatible file trees, keep all your data under version control of your choice, allow to put your files, files by glob pattern, or entire folders into more than category, and still benefit from little manual maintenance or additional setup.
