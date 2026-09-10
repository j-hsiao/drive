"""Wrap text in ansi escaps to add color when printed to terminal."""
import base64
import re

RESET = '\x1b[0m'
FLAGS = dict(
    reset=0,
    bold=1,
    bright=1,
    dark=2,
    faint=2,
    italic=3,
    italics=3,
    under=4,
    underline=4,
    underlined=4,
    slowblink=5,
    fastblink=6,
    swap=7,
    hide=8,
    cross=9,
    crossed=9,
    font0=10,
    font1=11,
    font2=12,
    font3=13,
    font4=14,
    font5=15,
    font6=16,
    font7=17,
    font8=18,
    font9=19,
    fraktur=20,
    under2=21,
    normal=22,
    nitalic=23,
    nitalics=23,
    nunder=24,
    nblink=25,
    pspace=26,
    nreverse=27,
    reveal=28,
    ncross=29,
    ncrossed=29,

    black=30,
    red=31,
    green=32,
    yellow=33,
    blue=34,
    magenta=35,
    cyan=36,
    white=37,
    default=39,

    bblack=40,
    bred=41,
    bgreen=42,
    byellow=43,
    bblue=44,
    bmagenta=45,
    bcyan=46,
    bwhite=47,
    bdefault=49,

    nspace=50,
    framed=51,
    encircled=52,
    overlined=53,
    nframed=54,
    ncircled=54,
    noverlined=55,
    dunder=59,
    iunder=60,
    iunder2=61,
    iover=62,
    iover2=63,
    istress=64,
    nideo=65,
    sup=73,
    sub=74,
    nsu=75,

    brightblack=90,
    brightred=91,
    brightgreen=92,
    brightyellow=93,
    brightblue=94,
    brightmagenta=95,
    brightcyan=96,
    brightwhite=97,
    bbrightblack=100,
    bbrightred=101,
    bbrightgreen=102,
    bbrightyellow=103,
    bbrightblue=104,
    bbrightmagenta=105,
    bbrightcyan=106,
    bbrightwhite=107,
)

class LazyColor(object):
    def __init__(self, color, args, kwargs):
        self.info = color, args, kwargs
    def __str__(self):
        color, args, kwargs = self.info
        return color(*args, **kwargs)


class _Color(object):
    """Use __getattr__ to stack colors.

    Attrs should match FLAGS keys.
    rgb/brgb can be used to specify a color explicitly using rgb.
    Or use (b)rgbRRGGBB where RRGGBB are hex values for each component.
    ex. rgbff0000 for red 255.

    example usage:
        _Color().brightgreen.bred('abc', 123, sep='-')
        will have brightgreen as text with red as bg
        where text is 'abc-123'
    """
    # https://en.wikipedia.org/wiki/ANSI_escape_code
    # "semicolon separated list of codes"
    def __init__(self, pre='', post=RESET):
        self._pre = pre
        self._post = post

    def _addcodes(self, *args):
        """Return string with added codes."""
        if self._pre:
            parts = [self._pre]
        else:
            parts = []
        parts.extend(args)
        return ';'.join(map(str, parts))
    def rgb(self, r, g, b):
        return _Color(self._add(38, 2, r, g, b), self._post)
    def brgb(self, r, g, b):
        return _Color(self._add(48,2,r,g,b), self._post)
    def urgb(self, r, g, b):
        return _Color(self._add(58,2,r,g,b), self._post)

    def __getattr__(self, attr):
        """Get a new _Color instance with specified color."""
        try:
            code = FLAGS[attr]
        except KeyError:
            if attr.startswith('rgb'):
                ncode = self._addcodes(38, 2, *base64.b16decode(attr[3:], True))
            elif attr.startswith('brgb'):
                ncode = self._addcodes(48, 2, *base64.b16decode(attr[4:], True))
            elif attr.startswith('urgb'):
                ncode = self._addcodes(58, 2, *base64.b16decode(attr[4:], True))
            else:
                raise AttributeError(attr)
        else:
            ncode = self._addcodes(code)
        ret = _Color(ncode, self._post)
        setattr(self, attr, ret)
        return ret

    def lazy(self, *args, **kwargs):
        """Lazy evaluation useful for example, in a log message.

        Return a LazyColor.  The colored text is only calculated when
        __str__ is called.  When used in a log message, the message
        is only formatted if it is actually logged.
        """
        return LazyColor(self, args, kwargs)
    def __getitem__(self, tup):
        """Lazy, but no kwargs, args must be tuple."""
        return LazyColor(self, tup, {})

    def __call__(self, *args, **kwargs):
        """Format arguments with color.

        Convert each argument to str and join with "sep" kwarg.
        Surround the result with ansi escape codes for color.
        """
        b = []
        if args:
            if self._pre:
                b = ['\x1b[', self._pre, 'm']
            sep = kwargs.get('sep', ' ')
            it = map(str, args)
            b.append(next(it))
            for item in it:
                b.append(sep)
                b.append(item)
        b.append(self._post)
        return ''.join(b)

    def __repr__(self):
        return repr('{}{{}}{}'.format(self._pre, self._post)).join(('Color(', ')'))

color = _Color()
ansiregex = re.compile('\x1b' r'\[[0-9:;<=>?]*' r'[!"#$%&()*+,-./' "'" r']*' r'[@A-Z[\\\]^_`a-z{|}~]')
class _plain(object):
    def __init__(self, txt=None):
        self.txt = txt
    def __str__(self):
        return ansiregex.sub('', str(self.txt))
    def __getitem__(self, txt):
        """Lazy stripping ansi codes."""
        return _plain(txt)
    def __call__(self, txt):
        """Return txt without ansi codes."""
        return ansiregex.sub('', txt)
plain = _plain()
