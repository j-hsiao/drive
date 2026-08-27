from . import color
import traceback
def run(globs, prefix='test_'):
    for k, v in list(globs.items()):
        if k.startswith(prefix):
            try:
                v()
            except Exception:
                traceback.print_exc()
                print(k[len(prefix):], ':', color.wrap('fail', 'red'))
            else:
                print(k[len(prefix):], ':', color.wrap('pass', 'brightgreen'))
