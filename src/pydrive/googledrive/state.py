import contextlib

from .googledrive import api, Command, dcache, dconfig
from pydrive.util import jutil

@api
class State(Command):
    SEARCH = {
        'app': dconfig
    }
    def __init__(self):
        self.parser = p = self.get_parser()
        p.add_argument('info', choices=['app', 'auth', 'dtree'])
        p.add_argument('-s', '--show', action='store_true')
        p.add_argument('-o', '--out', help='save to an output location', nargs='*')
        p.add_argument('-f', '--force', action='store_true')
        p.add_argument('-r', '--repr', help='show repr instead.', action='store_true')
        p.add_argument('-i', '--indent', type=int)
        api.add_arguments(p)

    def __call__(self, args):
        target = getattr(args, args.info)
        if args.show or args.out is None:
            print('valid:', bool(target))
            with jutil.indent(args.indent):
                if args.repr:
                    print(repr(target))
                else:
                    print(target)
        if args.out is not None:
            with contextlib.ExitStack() as stack:
                if args.out:
                    out = args.out[0]
                else:
                    search = self.SEARCH.get(args.info, dcache)
                    out = stack.enter_context(search.open(
                        args.info + '.json', 'w', force=args.force)[1])
                name = getattr(out, 'name', None)
                if name:
                    print('saving to', repr(name))
                target.save(out)
        return True
