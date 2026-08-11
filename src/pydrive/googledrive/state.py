import contextlib
from .googledrive import api, Command, dsearch

@api
class State(Command):
    def __init__(self):
        self.parser = p = self.get_parser()
        p.add_argument('info', choices=['app', 'auth', 'dtree'])
        p.add_argument('-s', '--show', action='store_true')
        p.add_argument('-o', '--out', help='save to an output location', nargs='*')
        api.add_extra(p)

    def __call__(self, args):
        target = getattr(args, args.info)
        if args.show:
            print(target)
        if args.out is not None:
            with contextlib.ExitStack() as stack:
                if args.out:
                    out = args.out[0]
                else:
                    opened, out = dsearch.open(args.info + '.json', 'w')
                    if not opened:
                        raise OSError('Failed to open save target.')
                    stack.enter_context(out)
                target.save(out)
        return True
