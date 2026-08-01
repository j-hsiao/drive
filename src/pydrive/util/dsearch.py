"""Search directories
"""
import glob
import os

class DSearch(object):
    def __init__(self, targets=('~/.config/pydrive', '~')):
        self.targets = [os.path.expanduser(item) for item in targets]

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

    def glob(self, globpat='*', cwd=None):
        """Iterate globs for target directories.

        cwd: also search cwd.
        """
        ret = []
        if cwd:
            ret.extend(glob.glob(os.path.join(cwd, globpat)))
        if not globpat.startswith(os.sep):
            for target in self.targets:
                ret.extend(glob.glob(os.path.join(target, globpat)))
        return ret

    def find(self, name, cwd=None):
        """Return path for name.

        Search through target directories for a matching name.
        """
        if cwd:
            candidate = os.path.join(cwd, name)
            if os.path.exists(candidate):
                return candidate
        for target in self.targets:
            candidate = os.path.join(target, name)
            if os.path.exists(candidate):
                return candidate
