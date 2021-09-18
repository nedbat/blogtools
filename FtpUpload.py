"""
FtpUpload

Upload files via FTP based on their content changing.

Ned Batchelder
http://www.nedbatchelder.com
"""

import ftplib, pickle, sys, hashlib, os, string
import logging

from path import Path

__version__ = '1.0a'
__all__ = ['FtpUpload']

class Tracer:
    def __init__(self, name, fout):
        self.myname = name
        self.fout = fout

    def __getattr__(self, name):
        return lambda *a, **k: self.fout.write("%s.%s(%s, %s)\n" % (self.myname, name, a, k))

def path_parts(filepath):
    if not filepath:
        return []
    return filepath.split(os.sep)

def list_startswith(l1, l2):
    return l1[:len(l2)] == l2


class EzFtp:
    """
    A simplified interface to ftplib.

    Lets you use full pathnames, with server-side
    directory management handled automatically.
    """
    def __init__(self, ftp):
        self.ftp = ftp
        self.serverDir = ''

    def setRoot(self, dir):
        """
        Set the remote directory that we'll call the root.
        """
        self.ftp.cwd(dir)

    def cd(self, dir, create=True):
        """
        Change the directory on the server, if need be.
        If create is true, directories are created if necessary to get to the full path.
        Returns true if the directory is changed.
        """
        if dir != self.serverDir:
            # Move up to the common root.
            dir_parts = path_parts(dir)
            server_dir_parts = path_parts(self.serverDir)
            while not list_startswith(dir_parts, server_dir_parts):
                logging.info("ftpcd ..")
                self.ftp.cwd("..")
                server_dir_parts.pop()
            # Move down to the right directory
            for d in dir_parts[len(server_dir_parts):]:
                if d:
                    try:
                        logging.info("ftpcd %s" % d)
                        self.ftp.cwd(d)
                    except:
                        if create:
                            logging.info("ftpmkdir %s" % d)
                            self.ftp.mkd(d)
                            self.ftp.cwd(d)
                        else:
                            return False
                    server_dir_parts.append(d)
            self.serverDir = os.sep.join(server_dir_parts)
        return True

    def putasc(self, this, that):
        """
        Put a text file to the server.
        """
        thatDir, thatFile = os.path.split(that)
        self.cd(thatDir)
        with open(this, "rb") as f:
            logging.info("ftpstorasc %s" % that)
            self.ftp.storlines("STOR "+thatFile, f)

    def putbin(self, this, that):
        """
        Put a binary file to the server.
        """
        thatDir, thatFile = os.path.split(that)
        self.cd(thatDir)
        with open(this, "rb") as f:
            logging.info("ftpstorbin %s" % that)
            self.ftp.storbinary("STOR "+thatFile, f)

    def delete(self, that):
        """
        Delete a file on the server.
        """
        thatDir, thatFile = os.path.split(that)
        if self.cd(thatDir, create=False):
            logging.info("ftpdel %s" % that)
            try:
                self.ftp.delete(thatFile)
            except:
                pass

    def quit(self):
        """
        Quit.
        """
        self.ftp.quit()


class FtpUpload:
    """
    Provides intelligent FTP uploading of files, using MD5 hashes to track
    which files have to be uploaded.  Each upload is recorded in a local
    file so that the next upload can skip the file if its contents haven't
    changed.  File timestamps are ignored, allowing regenerated files to
    be properly uploaded only if their contents have changed.

    Call `setHost` and `setMd5File` to establish the settings for a session,
    then `upload` for each set of files to upload.  If you want to have
    removed local files automatically delete the remote files, call
    `deleteOldFiles` once, then `finish` to perform the closing bookkeeping.

    ::

        fu = FtpUpload()
        fu.setHost('ftp.myhost.com', 'myusername', 'password')
        fu.setMd5File('myhost.md5')
        fu.upload(
            hostdir='www', src='.',
            text='*.html *.css', binary='*.gif *.jpg'
        )
        # more upload() calls can go here..
        fu.deleteOldFiles()
        fu.finish()

    """

    def __init__(self):
        self.ftp = None
        self.ezftp = None
        self.md5file = None
        self.md5DictIn = {}
        self.md5DictOut = {}
        self.md5DictUp = {}

    def setHost(self, host, username, password):
        """
        Set the host, the username and password.
        """
        assert not self.ftp
        self.ftp = ftplib.FTP(host, username, password)
        self.ftp.set_pasv(1)
        #self.ftp.set_debuglevel(2)

        # 2.7.8 added a maxline of 8192, which is not long enough.
        self.ftp.maxline = 100000

    def setMd5File(self, md5file):
        """
        Assign a filename to use for the MD5 tracking.
        """
        self.md5file = md5file
        if self.md5file:
            try:
                with open(self.md5file, "r") as inf:
                    first = inf.read(1)
                    inf.seek(0)
                    if first == "(":
                        # Old pickle
                        self.md5DictIn = pickle.load(inf)
                    else:
                        for line in inf:
                            line = line.rstrip()
                            if not line:
                                continue
                            md5hash, filename = line.split(' ', 1)
                            self.md5DictIn[filename] = md5hash
                self.md5DictUp.update(self.md5DictIn)
            except IOError:
                self.md5DictIn = {}

    def upload(self,
               hostdir='.',
               text='*.*',
               binary='',
               src='.',
               only=None,
               skip=None,
               ):
        """
        Upload a set of files.
        Source files are found in the directory named by `src`
        (and its subdirectories recursively).  The files are uploaded
        to the directory named by `hostdir` on the remote host.
        Files that match one of the space-separated patterns in `text`
        are uploaded as text files, those that match the patterns in
        `binary` are uploaded as binary files.

        `only` is an fnmatch pattern to limit the files we consider.
        `skip` is an fnmatch pattern to skip certain files.

        This method can be called a number of times to upload different
        sets of files to or from different directories within the same
        FtpUpload session.
        """

        if not self.ezftp:
            if not self.ftp:
                self.ftp = Tracer('ftp', sys.stdout)
            self.ezftp = EzFtp(self.ftp)

        if hostdir != '.':
            self.ezftp.setRoot(hostdir)

        # patdict is a dict of fnmatch patterns to ftp function.
        patdict = {}
        for pat in text.split():
            patdict[pat] = self.ezftp.putasc
        for pat in binary.split():
            patdict[pat] = self.ezftp.putbin

        nchanged = 0

        # Walk the tree, putting files to the ezftp.
        srcpath = Path(src)
        for thispath in sorted(srcpath.walkfiles()):
            if only:
                if not thispath.fnmatch(only):
                    continue
            if skip:
                if thispath.fnmatch(skip):
                    continue

            # Find the pattern the file matches, if any, and get the ftp
            # function to use from the map.
            for pat in patdict.keys():
                if thispath.fnmatch(pat):
                    ftpfn = patdict[pat]
                    break
            else:
                # It's not a file type we grok, skip it.
                continue

            thatpath = srcpath.relpathto(thispath)
            thatpathstr = str(thatpath)
            # Compute this file's MD5 fingerprint
            m = hashlib.md5()
            with open(thispath, "rb") as f:
                m.update(f.read())
            thisMd5 = m.hexdigest()

            # What was the last MD5 fingerprint?
            thatMd5 = self.md5DictIn.get(thatpathstr, '')

            # Remember the new fingerprint.
            self.md5DictOut[thatpathstr] = thisMd5
            self.md5DictUp[thatpathstr] = thisMd5

            # If the current file is different, then put it to the server.
            if thisMd5 != thatMd5:
                ftpfn(thispath, thatpath)

                nchanged += 1
                if nchanged % 30 == 0:
                    self.writeMd5()

    def deleteOldFiles(self):
        """
        Delete any remote files that we have uploaded previously but
        that weren't considered in this FtpUpload session.  This doesn't
        touch files that exist on the remote host but were never uploaded
        by this module.
        """

        # Files in md5DictIn but not in md5DictOut must have been removed.
        for this in self.md5DictIn:
            if this not in self.md5DictOut:
                self.ezftp.delete(this)
                del self.md5DictUp[this]

    def finish(self):
        """
        Do our final bookkeeping.
        """
        # Done with ftp'ing.
        self.ezftp.quit()

        self.writeMd5()

    def writeMd5(self):
        # Write the md5 control file out for next time.
        if self.md5file:
            with open(self.md5file, "w") as outf:
                for filename, md5hash in sorted(self.md5DictUp.items()):
                    outf.write("{} {}\n".format(md5hash, filename))
