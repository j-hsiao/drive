import os
import json
from . import jutil
from . import listinit

class DTree(listinit.ListInit):
    """Maintain a local structure of dirs/items."""
    def copy_instance(self, initial, *args, **kwargs):
        self.root = kwargs.get('root', initial.root)
        self.items = kwargs.get('items', initial.items)
        self.cwd = kwargs.get('cwd', initial.cwd)
        self.folder_mimes = kwargs.get('folder_mimes', initial.folder_mimes)

    def _init(self, initial=None, rootid='root', folder_mimes=['application/vnd.google-apps.folder']):
        self.folder_mimes = folder_mimes
        self.root = {'children': {}, 'id': rootid}
        self.items = {}
        self.cwd = os.sep
        for name, node in self.walk('/'):
            self.items[node['id']] = node
            self.items[name] = node
        if isinstance(initial, str):
            try:
                with open(initial, 'r') as f:
                    self.root = json.load(f)
            except Exception:
                pass
        return True

    def save(self, out, **kwargs):
        jutil.save(self.root, out, **kwargs)

    def __str__(self):
        if self.cwd == os.sep:
            parts = ['* ', os.sep]
        else:
            parts = ['  ', os.sep]

        for name, node in self.walk('/'):
            parts.append('\n')
            if name.rstrip(os.sep) == self.cwd:
                parts.append('* ')
            else:
                parts.append('  ')
            split = name.strip(os.sep).split(os.sep)
            for _ in range(len(split)):
                parts.append('  ')
            parts.append(split[-1])
            if name.endswith(os.sep):
                parts.append(os.sep)
        return ''.join(parts)

    def getcwd(self):
        return self.cwd

    def normpath(self, path):
        """Normalize path to absolute."""
        if path is None or path == '.':
            return self.cwd
        path = os.path.normpath(path)
        if path.startswith(os.sep):
            return path
        return os.path.join(self.cwd, path)

    def cd(self, path):
        """Change cwd."""
        path = self.normpath(path)
        if self.isdir(path):
            self.cwd = path
            return
        raise ValueError('path is not a dir or is not loaded.')

    def get_(self, path, make=False):
        """Return an item from normalized path.

        make: node and intermediates if not found.
              Otherwise, return None if not found.
        """
        try:
            return self.items[path]
        except KeyError:
            pass
        node = self.root
        for item in filter(None, self.normpath(path).split(os.sep)):
            try:
                children = node['children']
            except KeyError:
                if not make:
                    return None
                children = node['children'] = {}
            try:
                node = children[item]
            except KeyError:
                if not make:
                    return None
                node = children[item] = {}
        return node
    def get(self, path, make=False):
        """Same as get_ but normalize path first."""
        return self.get_(self.normpath(path), make)
    def __getitem__(self, pathOrId):
        """Get node by id."""
        ret = self.get(pathOrId)
        if ret is None:
            raise KeyError(str(pathOrId))
        return ret

    def isdir_(self, node):
        """Check of node (dict) is a dir."""
        return ('children' in node) or (node.get('mimeType', '') in self.folder_mimes)

    def isdir(self, nodeOrPath):
        """Check if node or path is a dir."""
        if isinstance(nodeOrPath, str):
            nodeOrPath = self.get(nodeOrPath)
        return self.isdir_(nodeOrPath)

    def update(self, fobjs, parent=None):
        """Update entries under parent.

        fobjs: sequence of dicts.
               'name' is required.
               'id' is expected.
        """
        parent = self.get(parent, True)
        children = parent.setdefault('children', {})
        for item in fobjs:
            name = item['name']
            try:
                child = children[name]
            except KeyError:
                child = children[name] = item
            else:
                child.update(item)
            try:
                childid = item['id']
            except KeyError:
                pass
            else:
                self.items[childid] = child

    def walk(self, path='.', sort=True, _node=None):
        """Walk through all descendents of the given path."""
        if _node is None:
            path = self.normpath(path)
            _node = self.get_(path)
        else:
            if self.isdir_(_node):
                yield path + os.sep, _node
            else:
                yield path, _node
        items = _node.get('children', {}).items()
        if sort:
            items = sorted(items)
        for cname, cnode in items:
            for res in self.walk(os.path.join(path, cname), sort=sort, _node=cnode):
                yield res
