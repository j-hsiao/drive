"""A tree structure of file nodes."""
import os
import json
from . import jutil
from . import listinit

class DTree(listinit.ListInit):
    """Maintain a local structure of dirs/items."""
    @staticmethod
    def parse_flat(files, parkey='parents', idkey='id', namekey='name'):
        """Parse files into a tree structure.

        files: list of file info (dict)
        parkey: key into each file for (list of) parent(s)
        idkey: Key to identifying info in parents key.
        namekey: key for name of the the file.
        """
        lut = {}
        roots = []
        for item in files:
            lut[item[idkey]] = item.copy()
            if parkey not in item:
                roots.append(lut[item[idkey]])
        for item in list(lut.values()):
            try:
                parents = item[parkey]
            except KeyError:
                pass
            if isinstance(parents, str):
                parents = [parents]
            name = item[namekey]
            for parent in parents:
                try:
                    node = lut[parent]
                except KeyError:
                    node = lut[parent] = {'children': {}, idkey: parent, namekey: ''}
                    roots.append(node)
                try:
                    children = node['children']
                except KeyError:
                    children = node['children'] = {}
                children[item[namekey]] = item
        return roots

    def copy_instance(self, initial, *args, **kwargs):
        # should this be deep copy?
        for attr in ('root', 'items', 'cwd', 'folder_mimes'):
            setattr(self, kwargs.get(attr, getattr(initial, attr)))

    def _init(self, initial=None, rootid='root', folder_mimes=['application/vnd.google-apps.folder'], **kwargs):
        """Initialize DTree.

        initial: Dtree initializer.  Another Dtree to copy or a filepath."""
        self.folder_mimes = folder_mimes
        if isinstance(initial, str):
            try:
                with open(initial, 'r') as f:
                    self.root = json.load(f)
            except Exception:
                pass
        elif hasattr(initial, 'read'):
            self.root = json.load(f)
        else:
            self.root = {'children': {}, 'id': rootid}
        self.cwd = os.sep
        return True

    def save(self, out, **kwargs):
        """Save to out."""
        jutil.save(self.root, out, **kwargs)

    def __repr__(self):
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

    def get_(self, path, default=None, make=False):
        """Return an item from normalized path.

        path: a normalized path via self.normpath.
        make: node and intermediates if not found.
              Otherwise, return None if not found.
        """
        node = self.root
        for item in filter(None, path.split(os.sep)):
            try:
                children = node['children']
            except KeyError:
                if not make:
                    return default
                children = node['children'] = {}
            try:
                node = children[item]
            except KeyError:
                if not make:
                    return default
                node = children[item] = {}
        return node
    def get(self, path, default=None, make=False):
        """Same as get_ but normalize path first."""
        return self.get_(self.normpath(path), default, make)
    def __getitem__(self, path):
        ret = self.get(path)
        if ret is None:
            raise KeyError(path)
        return ret

    def isdir_(self, node):
        """Check if node (dict) is a dir."""
        return ('children' in node) or (node.get('mimeType') in self.folder_mimes)
    def isdir(self, nodeOrPath):
        """Check if node or path is a dir."""
        if isinstance(nodeOrPath, str):
            nodeOrPath = self[nodeOrPath]
        return self.isdir_(nodeOrPath)

    def update(self, fobjs, parent=None):
        """Update entries under parent.

        fobjs: sequence of dicts.
               'name' is required.
        """
        parent = self.get(parent, make=True)
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
