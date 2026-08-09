import contextlib
import sys
import json
import os
import uuid
import traceback

from .copyable import Copyable

def save(info, out, **kwargs):
    with contextlib.ExitStack() as stack:
        write = getattr(out, 'write')
        if write is None:
            dname = os.path.dirname(out)
            if not os.path.isdir(dname):
                try:
                    os.makedirs(dname)
                except Exception:
                    traceback.print_exc()
            out = stack.enter_context(open(out, 'w'))
        kwargs.setdefault('indent', 4)
        json.dump(info, out, **kwargs)
        out.write('\n')





class JFile(Copyable, dict):
    def _init(self, fname, data=None):
        self.__fname = os.path.expanduser(fname)
        if data is None:
            data = self._load(self.__fname)
        super(Copyable, self).__init__(data)

    def path(self):
        return self.__fname

    def _copy_instance(self, other, *args, **kwargs):
        """Copy from another JFile."""
        self.__fname = other.__fname
        super(Copyable, self).__init__(other)


    def __repr__(self):
        return 'JFile({},{})'.format(repr(self.__fname), super(JFile, self).__repr__())

    def update(self, *args, **kwargs):
        super(JFile, self).update(*args, **kwargs)
        return self

    def _load(self, fname):
        try:
            with open(fname, 'r') as f:
                return json.load(f)
        except Exception:
            traceback.print_exc()
            return {}

    def load(self):
        """Load data."""
        self.clear()
        self.update(self._load(self.__fname))

    def save(self, fname=None, **kwargs):
        """Save data."""
        if fname is None:
            fname = self.__fname
        try:
            save(self, fname, **kwargs)
        except Exception:
            print('Error saving jfile', repr(self), file=sys.stderr)
            traceback.print_exc()

    def delete(self):
        """Delete the file."""
        try:
            os.remove(self.__fname)
        except Exception:
            traceback.print_exc()

def load(s):
    try:
        with open(os.path.expanduser(s), 'r') as f:
            return json.load(f)
    except (ValueError, IOError):
        try:
            return json.loads(s)
        except ValueError:
            return {}

class JDir(object):
    """Dir of json files."""
    def __init__(self, dname):
        self.dname = dname

    def get(self, prefix='', ext='.json', rand='', overwrite=True):
        """Get a JFile in this JDir.

        prefix: name of file.
        ext: extension of the file.
        rand: str|bool, a random string to add, or whether to generate one.
        overwrite: overwrite an existing file, otherwise load it.
        """
        if rand and isinstance(rand, bool):
            rand = uuid.uuid4().hex
        fname = os.path.join(self.dname, ''.join([prefix, rand, ext]))
        return JFile(fname, (() if overwrite else None))

    def __getitem__(self, name):
        return self.get(name, overwrite=False)

    def find(self, info, name=('', '.json')):
        """Search for json with matching values.

        info: dict of values to search for
        name: str (prefix) or pair (prefix, suffix) to match filename.

        Don't really expect there to be too many of these files at any one time
        so just iterate through them and search one by one. no indexing etc.
        """
        try:
            if isinstance(name, str):
                name = (name, '.json')
            for item in os.listdir(self.dname):
                if name and not (item.startswith(name[0]) and item.endswith(name[1])):
                    continue
                try:
                    iname = os.path.join(self.dname, item)
                    with open(iname, 'r') as f:
                        data = json.load(f)
                    if all(data.get(k, self) == v for k, v in info.items()):
                        return JFile(iname, data)
                except Exception:
                    traceback.print_exc()
        except Exception:
            traceback.print_exc()
        return None
