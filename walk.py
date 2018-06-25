"""
Directory walking, adapted from ASPN Cookbook.
"""
from __future__ import print_function

import fnmatch
import os
import string

class DirWalker:
    def __init__(self):
        self.patterns = []
        
    def startDir(self, dirName, dirPath):
        """Overridable for starting a directory"""
        pass

    def endDir(self, dirName, dirPath):
        """Overridable for ending a directory"""
        pass

    def file(self, fileName, path, patIndex):
        """Overridable for a file"""
        pass

    def setPattern(self, pattern, index):
        while index >= len(self.patterns):
            self.patterns.append([])
        self.patterns[index] = string.split(pattern)
        
    def walkdir(self, dname, dfull):
        # must have at least root folder
        try:
            names = os.listdir(dfull)
        except os.error:
            return

        self.startDir(dname, dfull)
        
        # check each file
        for fname in names:
            fullname = os.path.normpath(os.path.join(dfull, fname))

            # grab if it matches our pattern and entry type
            if os.path.isfile(fullname):
                bHandled = 0
                for iPat in range(len(self.patterns)):
                    patList = self.patterns[iPat]
                    for pat in patList:
                        if fnmatch.fnmatch(fname, pat):
                            self.file(fname, fullname, iPat)
                            bHandled = 1
                            break
                    if bHandled:
                        break

            # recursively scan other folders
            if os.path.isdir(fullname) and not os.path.islink(fullname):
                if fname[0] != '.':
                    self.walkdir(fname, fullname)

        self.endDir(dname, dfull)

    def walk(self, start, dname, dfull):
        olddir = os.getcwd()
        os.chdir(start)
        self.walkdir(dname, dfull)
        os.chdir(olddir)

if __name__ == '__main__':
    # test code
    class TestIt(DirWalker):
        def startDir(self, dirName, dirPath):
            print("startDir", dirName, dirPath)

        def endDir(self, dirName, dirPath):
            print("endDir", dirName, dirPath)

        def file(self, fileName, fullName, patIndex):
            print("file", fileName, fullName, patIndex)
            
    print('\nExample1:')
    walker = TestIt()
    walker.setPattern('*', 0)
    walker.walk('.', '.')

    print('\nExample 2:')
    walker = TestIt()
    walker.setPattern('*.py', 0)
    walker.setPattern('*.xml', 1)
    walker.walk('.', '.')
