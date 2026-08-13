import argparse
import os
import shlex
import sys
import textwrap
import traceback

from .multiplex import Multiplexed

class Command(object):
    def get_parser(self):
        p = argparse.ArgumentParser(add_help=False, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        p.set_defaults(func=self)
        return p

    def __call__(self, args):
        """Handle parsed args and return success True/False."""
        raise NotImplementedError

class Exit(Command):
    def __init__(self):
        self.parser = self.get_parser()
    def __call__(self, args):
        sys.exit()

def py_include_path(package, filename):
    """Calculate the python include dir to import filename."""
    if package:
        reps = len(package.split('.'))
    else:
        reps = 0
    dname = os.path.dirname(filename)
    return os.path.normpath(os.path.join(dname, *(['..'] * reps)))

class Commands(object):
    """Manage commands."""
    def __init__(self, *caches, **kwargs):
        """Initialize Commands.

        cache: dict(s) of cached values, list(s) of cache names (init to None)
               or str (same as list, but only 1 value).
        Cache will track the most recent non-None value for the
        given keys.

        kwargs: keyword arguments with values for the cache.
        """
        self.parser = p = argparse.ArgumentParser()
        self.parser.set_defaults(func=self.check)
        self.sub = p.add_subparsers()
        self.cache = {}
        self._noneinit = {}
        for cache in caches:
            if not cache:
                continue
            elif isinstance(cache, dict):
                self.cache.update(cache)
            elif isinstance(cache, str):
                self.cache[cache] = None
            else:
                try:
                    for _ in cache:
                        self.cache[_] = None
                except TypeError:
                    raise ValueError('Bad cache value {}'.format(cache))
        self.cache.update(kwargs)
        self(Exit)
        self._extraargs = []

    @staticmethod
    def check(args):
        print(args)
        return True

    def add_arguments(self, parser):
        """Add extra arguments to the parser.

        This allows the generic arguments to apply for the input parser,
        which is usually a subparser.  Without this call, then the generic
        arguments must be placed before the subparser command.
        """
        if isinstance(parser, type(self)):
            for args, kwargs, init in self._extraargs:
                parser.add_argument(*args, init=init, **kwargs)
        else:
            for args, kwargs, init in self._extraargs:
                parser.add_argument(*args, **kwargs)

    def add_argument(self, *args, **kwargs):
        """Add generic arguments for the toplevel parser.

        Extra kwarg "init" to initialize with type() if was parsed as None.
        """
        self._extraargs.append((args, kwargs, kwargs.pop('init', False)))
        ret = self.parser.add_argument(*args, **kwargs)
        if self._extraargs[-1][2]:
            self._noneinit[ret.dest] = ret.type
        return ret

    def __call__(self, *args, **kwargs):
        """Decorate or copy.

        If the first arg is callable, then assume decorator mode.  Call
        it with args/kwargs and create a subparser with parents=[result.parser].

        Otherwise, create a new instance of commands with extra cache values.
        """
        if args and callable(args[0]):
            inst = args[0](*args[1:], **kwargs)
            sub = self.sub.add_parser(
                args[0].__name__.lower(),
                parents=[inst.parser],
                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
            return args[0]
        elif args and isinstance(args[0], str) and len(args) == 1 and not kwargs:
            return self.handle(args[0])
        else:
            ret = type(self)(self.cache, *args, **kwargs)
            for name, p in self.sub.choices.items():
                ret.sub.add_parser(
                    name,
                    parents=[p],
                    add_help=False,
                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
            self.add_arguments(ret)
            return ret



    def bash_setup(self, package, filename=None, flags=(), command='drive'):
        """Return a bash script to create a "drive" command to access drive apis.

        package: the __package__ for the __main__.py  The package should be run as __main__
                 for the apis.
        filename: the filename of the __main__.py to find the directory to set PYTHONPATH
                  if applicable.
        flags: sequence of str flags or single str flag to actually run.
        """
        commandline = []
        if filename is not None:
            drivepath = py_include_path(package, filename)
            pypath = os.environ.get('PYTHONPATH', None)
            if pypath:
                pypath = os.pathsep.join([drivepath, pypath])
            else:
                pypath = drivepath
            commandline.append('PYTHONPATH=' + pypath)
        commandline.extend([sys.executable, '-m', package])
        if isinstance(flags, str):
            commandline.append(flags)
        else:
            commandline.extend(flags)
        script = textwrap.dedent(r'''
            {PYDRIVE_READ}
            {COMMANDNAME}() {{
                if ! declare -p __PYDRIVE_{COMMANDNAME}__ &>/dev/null
                then
                    if [[ "${{*}}" = exit ]]
                    then
                        echo "{COMMANDNAME}: drive not active."
                        return
                    fi
                    coproc __PYDRIVE_{COMMANDNAME}__ {{ {COMMANDLINE} ;}}
                fi
                local fds=("${{__PYDRIVE_{COMMANDNAME}__[@]}}")
                trap 'return' SIGPIPE
                trap 'trap - RETURN SIGPIPE' RETURN
                local result stream readcode
                printf '%q %s\n' "${{PWD}}" "${{*@Q}}" >&${{fds[1]}}
                while :;
                    pydrive_read ${{fds[0]}} stream result
                    readcode=$?
                    if ((!readcode))
                    then
                        if ((stream == 1))
                        then
                            [[ "${{*}}" = exit ]] && wait "${{__PYDRIVE_{COMMANDNAME}___PID}}"
                            result="${{result:-1}}"
                            break
                        else
                            printf '%s' "${{result}}"
                        fi
                    elif ((readcode > 128))
                    then
                        if read -t 0
                        then
                            read -r result
                            printf '%s\n' "${{result}}" >&${{fds[1]}}
                        fi
                    else
                        result=1
                        break
                    fi
                done
                [[ "${{*}}" = exit ]] && wait "${{__PYDRIVE_{COMMANDNAME}___PID}}"
                return "${{result}}"
            }}
            __{COMMANDNAME}_completer() {{
                COMPREPLY=()
                if ((${{COMP_CWORD}} == 1))
                then
                    local candidate
                    for candidate in {CHOICES}
                    do
                        if [[ "${{candidate}}" = "${{2}}"* ]]
                        then
                            COMPREPLY+=("${{candidate}}")
                        fi
                    done
                fi
            }}
            complete -F __{COMMANDNAME}_completer -o filenames -o default -o bashdefault {COMMANDNAME}
            ''')
        return script.format(
            CHOICES=shlex.join(self.sub.choices),
            COMMANDLINE=shlex.join(commandline),
            COMMANDNAME=command,
            PYDRIVE_READ=Multiplexed.SCRIPTS['bash'],
        )

    def main(self, package, filename=None):
        p = argparse.ArgumentParser()
        p.add_argument('-r', '--run', action='store_true')
        p.add_argument('-c', '--command', default='drive')
        args = p.parse_args()
        if args.run:
            self.run()
        else:
            shell = os.environ.get('SHELL', None)
            if shell is None:
                raise ValueError('Unknown shell')
            func = getattr(self, os.path.basename(shell) + '_setup', None)
            if func is None:
                raise RuntimeError('Shell {} is not supported.'.format(shell))
            else:
                print(func(package, filename, '-r', command=args.command))

    def run(self):
        """Read commands from stdin and output result to stdout."""
        out = sys.stdout
        try:
            multi = sys.stdout = Multiplexed(out)
            command = sys.stdin.readline()
            while command:
                try:
                    result = 0 if self.handle(command) else 1
                    with multi.stream(1):
                        print(result)
                except SystemExit:
                    with multi.stream(1):
                        print(0)
                    return
                except Exception:
                    traceback.print_exc()
                    with multi.stream(1):
                        print(1)
                command = sys.stdin.readline()
        finally:
            sys.stdout = out

    def handle(self, commandline):
        """Handle a commandline.  Return True/False successful or not."""
        parsed = shlex.split(commandline)
        if parsed and os.path.isdir(parsed[0]) and parsed[0].startswith('/'):
            os.chdir(parsed[0])
            parsed = parsed[1:]
        try:
            args = self.parser.parse_args(parsed)
        except SystemExit:
            return ('-h' in parsed) or ('--help' in parsed)
        for key, value in self.cache.items():
            argval = getattr(args, key, None)
            if argval is None:
                setattr(args, key, value)
        for k, tp in self._noneinit.items():
            if getattr(args, k, None) is None:
                setattr(args, k, tp())
        try:
            return args.func(args)
        finally:
            for key, value in self.cache.items():
                self.cache[key] = getattr(args, key, None)
