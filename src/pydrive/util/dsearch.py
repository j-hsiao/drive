"""Search specific directoriesdirectories."""
import glob
import os

class DSearch(object):
    def __init__(self, targets=('.', '~/.config/pydrive', '~')):
        self.dirs = [os.path.expanduser(os.path.normpath(item)) for item in targets]

    def open(self, name, mode):
        """Return (created, fileobj).

        If not existing, then prioritize the 1st choice in self.dirs.
        """
        fname = self(name, first=True)
        if fname:
            return True, open(fname, mode)
        else:
            target = os.path.join(self.dirs[0], name)
            dname = os.path.dirname(target)
            if not os.path.isdir(dname):
                try:
                    os.makedirs(dname)
                except Exception:
                    pass
            if 'w' not in mode and 'a' not in mode:
                mode = 'w' + mode.replace('r', '+')
            return False, open(fname, mode)

    def __call__(self, *globpats, **kwargs):
        """Return glob matches in target directories

        kwargs:
            dirs: str|list, dirs to search. Default to self.dirs.
            first: bool, return the first matching path or None.
        """
        if not globpats:
            globpats = ('*',)
        ret = []
        dirs = kwargs.get('dirs', None)
        if dirs is None:
            dirs = self.dirs
        else:
            if isinstance(dirs, str):
                dirs = [dirs]
            dirs = [os.path.expanduser(os.path.normpath(_)) for _ in dirs]
        first = kwargs.get('first', False)
        for globpat in globpats:
            globpat = os.path.expanduser(os.path.normpath(globpat))
            if globpat.startswith(os.sep):
                ret.extend(glob.glob(globpat))
                if first and ret:
                    return ret[0]
            else:
                for target in dirs:
                    ret.extend(glob.glob(os.path.join(target, globpat)))
                    if first and ret:
                        return ret[0]
        if first and not ret:
            return None
        return ret
