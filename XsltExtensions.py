##
##  XSLT extension functions.
##

import os
import re
import time
import urllib.parse

from PIL import Image

def endswith(text, s):
    return int(bool(text.endswith(s)))

def makeuri(base, u, dpath):
    if ':' in u:
        # Full URI: don't touch.
        uri = u
    else:
        # Relative.  Base+u, but make sure a slash separates them.
        if u.startswith('#'):
            u = dpath + u
        uri = base
        if not base.endswith('/') and not u.startswith('/'):
            uri += '/'
        uri += u
        # Don't link to index.html pages.
        if uri.endswith('/index.html'):
            uri = uri.removesuffix('/index.html')
    return uri

def urlquote(u):
    return urllib.parse.quote(urllib.parse.unquote(u.encode('utf-8')))

def phpquote(u):
    return u.replace('"', r'\"').replace("'", r"\'")

def now8601():
    return time.strftime("%Y%m%dT%H%M%S")

def w3cdtf(s8601):
    sTime = time.strftime("%Y-%m-%dT%H:%M:%S", time.strptime(s8601, "%Y%m%dT%H%M%S"))
    if time.daylight:
        zsecs = time.altzone
    else:
        zsecs = time.timezone
    if zsecs < 0:
        zchar = '+'
        zsecs = -zsecs
    else:
        zchar = '-'
    zmins = zsecs/60
    zhours = zmins/60
    zmins = zmins % 60
    return "%s%s%02d:%02d" % (sTime, zchar, zhours, zmins)

def idfromtext(s):
    s = urllib.parse.quote(s.strip().replace(' ', '_').encode('utf-8'))
    return s.replace('%', '_')

def slugfromtext(txt):
    slug = txt.encode('ascii', 'ignore').decode('ascii').replace(' ', '_').lower()
    slug = re.sub(r'[^\w _]', '', slug)
    slug = re.sub(r'_+', r'_', slug).strip('_')
    if not slug:
        slug = urllib.parse.quote(txt.strip().replace(' ', '_').encode('utf-8'))
        slug = slug.replace('%', '_')
    return slug

idfromtext = slugfromtext

def lexcode(code, lang, number=False):
    import pygments, pygments.lexers, pygments.formatters
    # Because we are omitting the <pre> wrapper, we need spaces to become &nbsp;.
    import pygments.formatters.html as pfh
    pfh._escape_html_table.update({ord(' '): u'&#xA0;'})

    class CodeHtmlFormatter(pygments.formatters.HtmlFormatter):

        def wrap(self, source):
            return self._wrap_code(source)

        def _wrap_code(self, source):
            # yield 0, '<pre>'
            for i, t in source:
                if i == 1:
                    # it's a line of formatted code
                    t += '<br>'
                yield i, t
            # yield 0, '</pre>'

    aliases = {
        "cs": "c#",
        "htaccess": "apacheconf",
        "ps": "postscript",
        "m3u": "text",  # Don't know if this will ever be supported...
        }
    lang = lang.lower()
    lang = aliases.get(lang, lang)
    lexer = pygments.lexers.get_lexer_by_name(lang, stripall=True)
    formatter = CodeHtmlFormatter(linenos='inline' if number else False, cssclass="source")
    result = pygments.highlight(code, lexer, formatter)
    return result


def markdown(text):
    import markdown2
    return markdown2.markdown(text)


imgsizecache = {}
curdir = os.getcwd()
# Yuk! Hard-coded path!
imgpath = [ curdir, os.path.join(curdir, 'public') ]

def getImageSize(s):
    if s.startswith('http://') or s.startswith('file://'):
        return
    if s.startswith('//'):
        # Turn "//domain.com/path/to/file" into "path/to/file"
        s = s.split('/', maxsplit=3)[3]
    if s not in imgsizecache:
        img = None
        for p in imgpath:
            try:
                spath = os.path.join(p, s)
                img = Image.open(spath)
                #print("opened %r" % s)
                break
            except IOError as msg:
                pass
        if img:
            imgsizecache[s] = img.size
        else:
            print("Couldn't open image %s" % s)
    if s in imgsizecache:
        return imgsizecache[s]

def imgwidth(s, scale=None):
    return img_dimension(0, s, scale)

def imgheight(s, scale=None):
    return img_dimension(1, s, scale)

def img_dimension(which, s, scale=None):
    scale = scale or 1.0
    size = getImageSize(s)
    if size:
        return str(int(size[which]*float(scale)))
    else:
        return ''
