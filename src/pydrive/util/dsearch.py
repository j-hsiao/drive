"""Search specific directoriesdirectories."""
import glob
import os

class DSearch(object):
    def __init__(self, targets=('~/.config/pydrive', '~')):
        self.targets = [os.path.expanduser(os.path.normpath(item)) for item in targets]

    def open(self, name, mode, cwd=None):
        """Return (created, fileobj).

        If not existing, then prioritize the 1st choice in self.targets.
        """
        fname = self.find(name, cwd)
        if fname:
            return True, open(fname, mode)
        else:
            target = os.path.join(self.targets[0], name)
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
            extra: str|list, extra path(s) to search.  If there is overlap with
                   self.targets, then the paths will be searched multiple times.
            first: bool, return the first matching path.
        """
        if not globpats:
            globpats = ('*',)
        ret = []
        extra = kwargs.get('extra', ())
        if isinstance(extra, str):
            extra = [extra]
        extra = [os.path.expanduser(os.path.normpath(_)) for _ in extra]
        first = kwargs.get('first', False)
        for globpat in globpats:
            globpat = os.path.expanduser(os.path.normpath(globpat))
            if globpat.startswith(os.sep):
                ret.extend(glob.glob(globpat))
                if first and ret:
                    return ret[0]
            else:
                for dlist in [extra, self.targets]:
                    for target in dlist:
                        print('checking target', target)
                        ret.extend(glob.glob(os.path.join(target, globpat)))
                        if first and ret:
                            return ret[0]
        if first and not ret:
            return None
        return ret
