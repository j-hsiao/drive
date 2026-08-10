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
        target = getattr(args, args.item)
        if args.show:
            print(target)
        if args.out is not None:
            if args.out:
                out = args.out[0]
            else:
                # TODO the name
                opened, out = dsearch.open('', 'w')
                if not opened:
                    raise OSError('Failed to open save target.')
            target.save(out)
        return True
