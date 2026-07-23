"""Wrap text in ansi escaps to add color when printed to terminal."""
import base64

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
    swap=7,
    cross=9,
    crossed=9,
    medium=22,
    normal=22,
    hide=8,
    reveal=28,

    black=30,
    red=31,
    green=32,
    yellow=33,
    blue=34,
    magenta=35,
    cyan=36,
    white=37,
    default=39,

    brightblack=90,
    brightred=91,
    brightgreen=92,
    brightyellow=93,
    brightblue=94,
    brightmagenta=95,
    brightcyan=96,
    brightwhite=97,

    bblack=40,
    bred=41,
    bgreen=42,
    byellow=43,
    bblue=44,
    bmagenta=45,
    bcyan=46,
    bwhite=47,
    bdefault=49,

    bbrightblack=100,
    bbrightred=101,
    bbrightgreen=102,
    bbrightyellow=103,
    bbrightblue=104,
    bbrightmagenta=105,
    bbrightcyan=106,
    bbrightwhite=107,
)
FLAGS = {k:str(v) for k,v in FLAGS.items()}

def wrap(text, flags='', end=RESET, reset=True):
    """Wrap text in color.

    text: the text to wrap
    end: end sequence, set to '' to not reset afterwards.
    reset: bool, if True, then reset before the flags.

    flags: a string of white-space-delimited flags:
        text:
            [bright]black
            [bright]red
            [bright]green
            [bright]yellow
            [bright]blue
            [bright]magenta
            [bright]cyan
            [bright]white
            default
            #RRGGBB (hex)
        background:
            same as text color names but prefix with a b, ex: bblue
            ##RRGGBB background rgb in hex (2 #s)
        modifiers:
            bold/bright
            normal/medium
            faint/dark
            italic/italics ?On some terminals this just swaps fg/bg?
            under/underline/underlined
            swap
            cross/crossed
            hide
            reveal
        reset

        NOTE: bright modifier affects foreground, to use the bright versions
        in background, use the concatenated bright version of the color instead.
        ex: bright blue background: bbrightblue
    """
    parts = []
    if flags:
        parts.append('\x1b[')
        pre = '0;' if reset else ''
        for flag in flags.split():
            parts.append(pre)
            if flag.startswith('#'):
                bg, color = flag.rsplit('#', 1)
                if bg:
                    parts.append('48;2')
                else:
                    parts.append('38;2')
                for num in base64.b16decode(color, True):
                    parts.append(';')
                    parts.append(str(num))
            else:
                parts.append(FLAGS[flag.lower()])
            pre = ';'
        parts.append('m')
    parts.append(text)
    parts.append(end)
    return ''.join(parts)
