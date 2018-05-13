"""
XuffApp

Ned Batchelder
http://www.nedbatchelder.com

20020202 - Created
20021124 - Separated into stellated.XuffApp
"""

import os, re, shutil, string, sys, time
from xml.dom import Node
from lxml import etree
from xml.sax import make_parser, handler, saxutils
import logging
import smartypants

import walk

_verbose = 0

class Timer:
    def __init__(self):
        self.start = time.clock()

    def show(self, activity):
        now = time.clock()
        print "Time: %s: %.2f sec" % (activity, now - self.start)
        self.start = now

class XuffError:
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return self.msg

def makedirs(name, mode=0777):
    """makedirs(path [, mode=0777]) -> None

    Super-mkdir; create a leaf directory and all intermediate ones.
    Works like mkdir, except that any intermediate path segment (not
    just the rightmost) will be created if it does not exist.  This is
    recursive.

    Copied from os.py and patched to allow 'foo\\.' as an arg.
    """
    if _verbose > 2: print "makedirs", name
    head, tail = os.path.split(name)
    if not tail:
        head, tail = os.path.split(head)
    if head and tail and not os.path.exists(head):
        makedirs(head, mode)
    if not os.path.exists(name):
        if _verbose > 1: print "mkdir", name
        os.mkdir(name, mode)
    else:
        if _verbose > 2: print "stat", name, os.stat(name)

def prepareForOutputFile(path):
    """
    Ensure all the dirs exist to be able to create a file, and
    remove the file if it exists to allow it to be created.
    """
    dirs = os.path.split(path)[0]
    if dirs:
        if not os.access(dirs, os.F_OK):
            makedirs(dirs)
    if os.access(path, os.F_OK):
        if _verbose > 1: print "rm", path
        os.remove(path)
    if _verbose > 0: print "writing", path

class MyXslt:

    class OneCache:
        def __init__(self):
            self.key = ''
            self.value = None

        def get(self, key):
            if key == self.key:
                return self.value
            else:
                return None

        def put(self, key, value):
            self.key = key
            self.value = value

    class ManyCache:
        def __init__(self):
            self.cache = {}

        def get(self, key):
            if key in self.cache:
                return self.cache[key]
            else:
                return None

        def put(self, key, value):
            self.cache[key] = value

    def __init__(self, styf):
        """Create an XSLT transformer based on the XSLT stylesheet at `styf` (a file path)."""
        self.xmlCache = self.OneCache()
        self.styf = styf
        self.xslt = etree.XSLT(etree.parse(self.styf))

    def transformFile(self, inf, outf, params=None, moreParams=None):
        """Transform file `inf` to `outf`.
        
        `inf` and `outf` are file paths.

        """

        #print "Transforming %s with %s to %s" % (inf, styf, outf)
        prepareForOutputFile(outf)

        xslt_params = {}
        if params:
            xslt_params.update(params)
            if moreParams:
                xslt_params.update(moreParams)

        try:
            xml = self.xmlCache.get(inf)
            if xml is None:
                xml = etree.parse(inf)
                self.xmlCache.put(inf, xml)

            out = str(self.xslt(xml, **xslt_params))
        except:
            import traceback
            traceback.print_exc()
            etype, evalue = sys.exc_info()[:2]
            raise XuffError("XSL error: %s: %s (%s %s)" % (etype, evalue, inf, self.styf))

        out_file = open(outf, "w")
        out_file.write(out)
        out_file.close()

def parse_xml(xmlfile):
    try:
        return etree.parse(xmlfile).getroot()
    except Exception, e:
        raise Exception("Couldn't parse %r: %s" % (xmlfile, e))

class TreeFileWalker(walk.DirWalker):
    """
    Our specialization of DirWalker
    """
    def __init__(self, dstf):
        walk.DirWalker.__init__(self)
        self.dstf = dstf

    def startDir(self, dirName, dirPath):
        dirPath = string.replace(dirPath, '\\', '/')
        print >> self.dstf, "<directory name='%s' path='%s'>" % (dirName, dirPath)

    def endDir(self, dirName, dirPath):
        print >> self.dstf, "</directory>"

    def file(self, fileName, path, patIndex):
        if patIndex == 0:
            path = string.replace(path, '\\', '/')
            print >> self.dstf, "<file name='%s' path='%s'>" % (fileName, path)
            # open the file
            f = open(path)
            l1 = f.readline().strip()
            # Only output the first line if it is not an XML declaration.
            #if not (l1.find("<?xml ") != -1 and l1.endswith("?>")):
            #    self.dstf.write(l1)
            if l1.find("<?xml ") != -1:
                l1 = l1[l1.find("?>")+2:]
            self.dstf.write(l1)
            for l in f.readlines():
                self.dstf.write(l)
            print >> self.dstf, "</file>"
        elif patIndex == 1:
            print >> self.dstf, "<file name='%s'/>" % fileName

class XslTreeWalker(walk.DirWalker):
    """
    Specialization of DirWalker for transforming trees of files.
    """
    def __init__(self, styf, dstpath, userXslParams):
        walk.DirWalker.__init__(self)
        self.myxslt = MyXslt(styf)
        self.dstpath = os.path.abspath(dstpath)
        self.userXslParams = userXslParams

    def forceExtension(self, ext):
        self.ext = ext

    def file(self, fileName, path, patIndex):
        dpath = path
        if self.ext:
            dpath = dpath[:string.rfind(dpath, '.')] + self.ext
        moreParams = {
            'path':     '"' + string.replace(path, '\\', '/') + '"',
            'dpath':    '"' + string.replace(dpath, '\\', '/') + '"'
            }
        dpath = os.path.join(self.dstpath, dpath)
        self.myxslt.transformFile(path, dpath, self.userXslParams, moreParams)

class CopyFilesWalker(walk.DirWalker):
    """
    Specialization of DirWalker for copying trees of files.
    """
    def __init__(self, dstpath):
        walk.DirWalker.__init__(self)
        self.dstpath = os.path.abspath(dstpath)

    def file(self, fileName, path, patIndex):
        dpath = os.path.join(self.dstpath, path)
        prepareForOutputFile(dpath)
        shutil.copyfile(path, dpath)

class FileSplitter(handler.ContentHandler):
    def __init__(self, dst='.'):
        self.xmlgen = None
        self.dirStack = [dst]

    def startElement(self, name, attrs):
        if name == 'directory':
            self.dirStack.append(os.path.join(self.dirStack[-1], attrs['name']))
        elif name == 'file':
            fpath = os.path.join(self.dirStack[-1], attrs['name'])
            prepareForOutputFile(fpath)
            self.outf = open(fpath, 'w')
            self.outf.write('<?xml version="1.0" encoding="utf-8"?>')
            self.xmlgen = saxutils.XMLGenerator(self.outf, 'utf-8')
        else:
            self.xmlgen.startElement(name, attrs)

    def endElement(self, name):
        if name == 'directory':
            self.dirStack = self.dirStack[:-1]
        elif name == 'file':
            self.xmlgen = None
            self.outf.flush()
            self.outf.close()
        else:
            self.xmlgen.endElement(name)

    def characters(self, content):
        if self.xmlgen:
            self.xmlgen.characters(content)
        elif content.strip() != '':
            print "Orphaned chars:", content

from XsltExtensions import *

##
##  The XuffApp
##

class XuffApp:
    XuffNamespaceUri = 'http://www.stellated.com/xuff'

    def __init__(self):
        self.userXslParams = {}
        self.timing = 0

    def main(self, argv):
        """
        The main entry point of the xuff application.
        """
        import getopt

        def usage():
            print "xuff [-t] [-v[v]] xuff-files ..."

        # Parse arguments.
        try:
            opts, args = getopt.getopt(argv[1:], "tv")
        except getopt.GetoptError:
            usage()
            return

        for o, a in opts:
            if o == '-v':
                global _verbose
                _verbose += 1
            elif o == '-t':
                self.timing += 1
            else:
                usage()
                return

        # Construct our log.
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s", "%H:%M:%S"))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)

        # Init our XSLT extensions.
        def wrapit(fn):
            """ lxml extensions have a first dummy arg that Pyana extensions don't.  Adapt.
            """
            def inside(dummy, *args):
                try:
                    return fn(*args)
                except Exception, e:
                    print "Error in XSLT extension: %s" % e
                    raise
            return inside

        ns = etree.FunctionNamespace(self.XuffNamespaceUri)
        ns['endswith'] = wrapit(endswith)
        ns['makeuri'] = wrapit(makeuri)
        ns['urlquote'] = wrapit(urlquote)
        ns['phpquote'] = wrapit(phpquote)
        ns['now'] = wrapit(now8601)
        ns['w3cdtf'] = wrapit(w3cdtf)
        ns['idfromtext'] = wrapit(idfromtext)
        ns['slugfromtext'] = wrapit(slugfromtext)
        ns['lexcode'] = wrapit(lexcode)
        ns['imgwidth'] = wrapit(imgwidth)
        ns['imgheight'] = wrapit(imgheight)
        ns['smartypants'] = wrapit(smartypants.smartypants)

        # Execute all the files.
        #try:
        for a in args:
            self.processFile(a)
        #except XuffError, msg:
        #    print "*** %s" % msg

    def isXuffElement(self, e):
        """Determines whether `e` is a Xuff element."""
        return (
            isinstance(e.tag, str) and
            e.nsmap[e.prefix] == self.XuffNamespaceUri
            )

    def local_name(self, e):
        """For an element `e`, returns the non-namespace part of the tag name."""
        return e.tag.split('}')[-1]
        
    def processFile(self, fname):
        """
        Process a single xuff file
        """
        xml = parse_xml(fname)
        for e in xml:
            if self.isXuffElement(e):
                handler = None
                try:
                    handler = getattr(self, 'handle_' + self.local_name(e))
                except AttributeError:
                    self.error("Didn't understand %s instruction" % (e.tag))

                if handler:
                    global _verbose
                    doVerbose = self.getAttr(e, 'verbose', 'unchanged')
                    oldVerbose = _verbose
                    if doVerbose != 'unchanged':
                        _verbose = doVerbose.lower() in ['1', 'true', 't', 'on', 'yes', 'y']
                    timer = Timer()
                    handler(e)
                    if self.timing:
                        timer.show("<%10s>" % e.tag)
                    _verbose = oldVerbose

    def error(self, str):
        """
        Raise an error.
        """
        raise XuffError(str)

    def attrError(self, e, attrName):
        """
        The element must have the attribute.
        """
        self.error("<%s> must have %s=" % (e.tag, attrName))

    def getAttr(self, e, attrName, defValue=None):
        """
        Get an attribute from an element.
        """
        return e.get(attrName) or defValue or self.attrError(e, attrName)

    def getAttrNullOk(self, e, attrName):
        """
        Get an attribute from an element.
        """
        return e.get(attrName) or ""

    def addXslParam(self, dParams, e):
        """
        Save away an XSLT param from a <param> element.
        """
        name = self.getAttr(e, 'name')
        value = self.getAttr(e, 'value')
        dParams[name] = '"' + value + '"'

    def handle_ignore(self, e):
        """
        Completely ignore this element.
        """
        pass

    def handle_message(self, e):
        """
        Write a message.
        """
        txt = self.getAttr(e, 'text')
        print txt

    def handle_treefile(self, e):
        """
        Write a model of a tree as an XML file.
        """
        out = self.getAttr(e, 'out', 'tree.xml')

        prepareForOutputFile(out)
        outf = open(out, 'w')

        print >> outf, "<?xml version='1.0'?>"
        print >> outf, "<tree>"

        if e.get('src'):
            # The element itself is the file spec.
            self.doFilesForTreeFile(e, outf)
        else:
            # Each <files> subelement is a file spec.
            for e2 in e:
                if self.isXuffElement(e2):
                    if self.local_name(e2) == 'files':
                        self.doFilesForTreeFile(e2, outf)
                    else:
                        self.error("Didn't understand %s element" % (e2.tag))

        print >> outf, "</tree>"

    def doFilesForTreeFile(self, e, outf):
        src = self.getAttr(e, 'src')
        inc = self.getAttrNullOk(e, 'include')
        mnt = self.getAttrNullOk(e, 'mention')

        if (not inc) and (not mnt):
            mnt = '*'

        walker = TreeFileWalker(outf)

        walker.setPattern(inc, 0)
        walker.setPattern(mnt, 1)
        walker.walk(src, '.', '.')

    def handle_copy(self, e):
        """
        Copy one file.
        """
        inf = self.getAttr(e, 'in')
        outf = self.getAttr(e, 'out')
        self.copyfile(inf, outf)
        
    def copyfile(self, src, dst):
        prepareForOutputFile(dst)
        shutil.copyfile(src, dst)

    def handle_copytree(self, e):
        """
        Copy files from one directory to another.
        """
        kw = {}
        kw['src'] = self.getAttr(e, 'src', '.')
        kw['dst'] = self.getAttr(e, 'dst')
        kw['include'] = self.getAttr(e, 'include', '*.*')
        self.copytree(**kw)
        
    def copytree(self, dst, src='.', include='*.*'):
        walker = CopyFilesWalker(dst)
        walker.setPattern(include, 0)
        walker.walk(src, '.', '.')

    def handle_xsl(self, e):
        """
        Transform a single file.
        """
        styf = self.getAttr(e, 'style')
        inf = self.getAttr(e, 'in')
        outf = self.getAttr(e, 'out')

        # Each <param> subelement is a stylesheet param.
        dLocalParams = {}
        for e2 in e:
            if self.isXuffElement(e2):
                if self.local_name(e2) == 'param':
                    self.addXslParam(dLocalParams, e2)
                else:
                    self.error("Didn't understand <xsl> %s element" % (e2.tag))

        myxslt = MyXslt(os.path.abspath(styf))
        myxslt.transformFile(inf, outf, self.userXslParams, dLocalParams)

    def handle_xsltree(self, e):
        """
        Transform a tree of files.
        """
        styf = self.getAttr(e, 'style')
        src = self.getAttr(e, 'src', '.')
        dst = self.getAttr(e, 'dst', '.')
        inc = self.getAttr(e, 'include', '*')
        ext = self.getAttrNullOk(e, 'outext')

        walker = XslTreeWalker(os.path.abspath(styf), dst, self.userXslParams)
        walker.setPattern(inc, 0)
        if ext:
            walker.forceExtension(ext)
        walker.walk(src, '.', '.')

    def handle_splitfile(self, e):
        """
        Parse an XML file, and write the files it says to.
        """
        inf = self.getAttr(e, 'in')
        dst = self.getAttr(e, 'dst', '.')

        parser = make_parser()
        parser.setContentHandler(FileSplitter(dst))
        parser.parse(inf)

    def handle_param(self, e):
        """
        Set a parameter for future XSL transforms.
        """
        self.addXslParam(self.userXslParams, e)

    def handle_del(self, e):
        """
        Remove a file.
        """
        dst = self.getAttr(e, 'dst')
        if os.access(dst, os.F_OK):
            if _verbose > 0: print "del", dst
            os.remove(dst)

    def handle_rmdir(self, e):
        """
        Remove a directory.
        """
        dst = self.getAttr(e, 'dst')
        if os.access(dst, os.F_OK):
            if _verbose > 0: print "rmdir", dst
            shutil.rmtree(dst)

    def handle_xuff(self, e):
        """
        Call another xuff script.
        """
        xuff = self.getAttr(e, 'file')
        if _verbose > 0: print "xuffing", xuff
        self.processFile(xuff)

    def handle_upload(self, e):
        """
        FTP stuff up to the server.
        """
        kw = {}
        kw['host'] = self.getAttr(e, 'host')
        kw['user'] = self.getAttr(e, 'user')
        kw['password'] = self.getAttr(e, 'password')
        kw['hostdir'] = self.getAttrNullOk(e, 'hostdir')
        kw['src'] = self.getAttr(e, 'src', '.')
        kw['text'] = self.getAttr(e, 'text')
        kw['binary'] = self.getAttr(e, 'binary')
        kw['md5file'] = self.getAttrNullOk(e, 'md5')

        self.upload(**kw)
        
    def upload(self, host, user, password, hostdir, src, text, binary, md5file):
        import stellated.FtpUpload as FtpUpload
        import socket

        fu = FtpUpload.FtpUpload()
        if md5file:
            fu.setMd5File(md5file)
        fu.setHost(host, user, password)
        try:
            fu.upload(hostdir=hostdir, text=text, binary=binary, src=src)
            fu.deleteOldFiles()
        except Exception, msg:
            print "Error:", msg
        fu.finish()

    def handle_httpping(self, e):
        """
        Get an HTTP url, and ignore the results.
        """

        import httplib
        import urllib

        host = self.getAttr(e, 'host')
        url = self.getAttr(e, 'url')
        args = ''

        for e2 in e:
            if self.isXuffElement(e2):
                if self.local_name(e2) == 'param':
                    if args:
                        args += '&'
                    args += urllib.urlencode({e2.get('name'): e2.get('value')})
                else:
                    self.error("Didn't understand %s element" % (e2.tag))

        if args:
            url += '?' + args

        if _verbose: print 'ping host:', host
        if _verbose: print 'ping url:', url

        conn = httplib.HTTPConnection(host)
        conn.request("GET", url)
        r = conn.getresponse()
        if r.status in [200,302]:
            d = r.read()
            if _verbose:
                print 'ping returned:'
                print d
        else:
            print "HTTP ping status:", r.status, r.reason
        conn.close()

    def handle_xmlrpc(self, e):
        """
        Make an XML-RPC call.
        """
        url = self.getAttr(e, 'url')
        object = self.getAttr(e, 'object')
        method = self.getAttr(e, 'method')

        args = []

        for e2 in e:
            if self.isXuffElement(e2):
                if self.local_name(e2) == 'param':
                    args.append(e2.get('value'))
                else:
                    self.error("Didn't understand %s element" % (e2.tag))
        self.xmlrpc(url, object, method, args)
        
    def xmlrpc(self, url, object, method, args):
        import xmlrpclib

        remoteServer = xmlrpclib.Server(url)
        remoteObject = getattr(remoteServer, object)
        remoteMethod = getattr(remoteObject, method)
        if _verbose:
            print 'xml-rpc: %s %s.%s%s' % (url, object, method, args)
        dReturn = remoteMethod(*args)
        print dReturn['message']

if __name__ == '__main__':
    xuff = XuffApp()
    xuff.main(sys.argv)
