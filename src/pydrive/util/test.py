from . import color
def run(globs, prefix='test_'):
    for k, v in list(globs.items()):
        if not k.startswith(prefix):
            continue
        try:
            v()
        except Exception:
            print(k[len(prefix):], ':', color.wrap('fail', 'red'))
            raise
        else:
            print(k[len(prefix):], ':', color.wrap('pass', 'brightgreen'))
