from .color import color
red = color.brightred
green = color.brightgreen
def run(globs, prefix='test_'):
    for k, v in list(globs.items()):
        if not k.startswith(prefix):
            continue
        try:
            v()
        except Exception:
            print(k[len(prefix):], ':', red('fail'))
            raise
        else:
            print(k[len(prefix):], ':', green('pass'))
