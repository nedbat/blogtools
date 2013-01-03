"""
Filename globbing utility.
"""

import os
import fnmatch
import re

__all__ = ["glob"]

def glob(pathname, deep=0):
    """
    Return a list of paths matching a pathname pattern.

    The pattern may contain simple shell-style wildcards a la fnmatch.

    """
    result = []
    if not hasMagic(pathname):
        if os.path.exists(pathname):
            result = [pathname]
    else:
        dirname, basename = os.path.split(pathname)

        if not dirname:
            result = globInDir(os.curdir, basename)
        else:
            if hasMagic(dirname):
                dirs = glob(dirname, deep)
            else:
                dirs = [dirname]

            if not hasMagic(basename):
                for dirname in dirs:
                    if basename or os.path.isdir(dirname):
                        name = os.path.join(dirname, basename)
                        if os.path.exists(name):
                            result.append(name)
            else:
                for dirname in dirs:
                    sublist = globInDir(dirname, basename)
                    for name in sublist:
                        result.append(os.path.join(dirname, name))

    return result

def globInDir(dirname, pattern):
    try:
        names = os.listdir(dirname or os.curdir)
    except os.error:
        return []
    return fnmatch.filter(names,pattern)


magicCheck = re.compile('[*?[]')

def hasMagic(s):
    return magicCheck.search(s) is not None
