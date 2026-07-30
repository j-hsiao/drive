import os
import json

class DTree(object):
    """Maintain a local structure of dirs/items."""
    def __init__(self, initial=None, rootid='root', folder_mimes=['application/vnd.google-apps.folder']):
        self.folder_mimes = folder_mimes
        self.root = {'children': {}, 'id': rootid}
        self.items = {}
        self.cwd = '/'
        if initial is not None:
            if isinstance(initial, str):
                try:
                    with open(initial, 'r') as f:
                        self.root = json.load(f)
                except Exception:
                    pass
            elif isinstance(initial, DTree):
                self.root = initial.root
                self.items = initial.items
                self.cwd = initial.cwd
                self.folder_mimes = initial.folder_mimes

    def normpath(self, path):
        """Normalize path to absolute.

        Converts to using / regardless of os.sep.
        """
        if path is None:
            return self.cwd
        path = os.path.normpath(path)
        if os.sep != '/':
            path = path.replace('\\', '/')
        if path.startswith(os.sep):
        return os.path.normpath(os.path.join(self.cwd, path))

    def cd(self, path):
        """Change cwd."""
        self.cwd = self.normpath(path)

    def get_(self, path, make=False):
        """Return an item from normalized path.

        make: node and intermediates if not found.
              Otherwise, return None if not found.
        """
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
        return self.get_(self.normpath(pathOrId), make)

    def __getitem__(self, pathOrId):
        """Get node by id."""
        return self.items[pathOrId]

    def isdir_(self, node):
        """Check of node (dict) is a dir."""
        return ('children' in node) or (node.get('mimeType', '') in self.folder_mimes)

    def isdir(self, nodeOrPath):
        """Check if node or path is a dir."""
        if isinstance(node, str):
            node = self.get(node)
        return self.isdir_(node)

    def update(self, fobjs, parent='/'):
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

    def walk(self, path='.', sort=True):
        """Walk through all descendents of the given path."""
        q = [(path, self.get(path))]
        while q:
            name, node = q.pop()
            if self.isdir_(node):
                name += os.sep
                yield name, node
                children = node.get('children', {})
                if sort:
                    children = list(children.items())
                    children.sort(key=(lambda x: x[0]), reverse=True)
                else:
                    children = children.items()
                for cname, child in children:
                    q.append((name + cname, child))
            else:
                yield name, node
