import contextlib
import logging

from .googledrive import api, Command, dcache, dconfig
from pydrive.util import jutil

lg = logging.getLogger(__name__)

@api
class State(Command):
    SEARCH = {
        'app': dconfig
    }
    def __init__(self):
        self.parser = p = self.get_parser()
        p.add_argument('info', choices=['app', 'auth', 'dtree'], nargs='*')
        p.add_argument('-s', '--show', action='store_true')
        p.add_argument(
            '-o', '--out', nargs='?', default=Ellipsis,
            help='output base prefix or dir/path if explicit (first path component is "", ., or ..)')
        p.add_argument('-f', '--force', action='store_true')
        p.add_argument('-r', '--repr', help='show repr instead.', action='store_true')
        p.add_argument('-i', '--indent', type=int)
        api.add_arguments(p)

    def __call__(self, args):
        if not args.info:
            args.info = ['auth', 'dtree']
        for info in args.info:
            target = getattr(args, info)
            if args.show or args.out is None:
                print('valid:', bool(target))
                with jutil.indent(args.indent):
                    if args.repr:
                        print(repr(target))
                    else:
                        print(target)
            if args.out is not Ellipsis:
                with contextlib.ExitStack() as stack:
                    if args.out:
                        normed = os.path.normcase(args.out)
                        if normed.split(os.sep, 1)[0] in '..':
                            if len(args.info)>1:
                                out = os.path.join(args.out, info + '.json')
                            else:
                                out = args.out
                            lg.info('save %s to: %s', info, out)
                        else:
                            out = ('_'+info).join(os.path.splitext(args.out))
                            if not out.endswith('.json'):
                                out += '.json'
                            out = stack.enter_context(self.SEARCH.get(
                                info, dcache).open(out, 'w', force=args.force)[1])
                            lg.info('save %s to: %s', info, out.name)
                    else:
                        search = self.SEARCH.get(info, dcache)
                        out = stack.enter_context(search.open(
                            info + '.json', 'w', force=args.force)[1])
                        lg.info('save %s to: %s', info, out.name)
                    target.save(out)
        return True
