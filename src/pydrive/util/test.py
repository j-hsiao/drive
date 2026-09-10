from .color import color
red = color.brightred
green = color.brightgreen
bold = color.bold
def run(globs, prefix='test_'):
    head = 'Running test:'
    headlen = len(head)+1
    for k, v in list(globs.items()):
        if not k.startswith(prefix):
            continue
        print(bold('='*(len(k)+headlen)))
        print(head, bold(k))
        try:
            v()
        except Exception:
            print(k[len(prefix):], ':', red('fail'))
            raise
        else:
            print(k[len(prefix):], ':', green('pass'))
