"""A tree structure of file nodes."""
import json
import logging
import os

from . import jutil
from . import listinit

lg = logging.getLogger(__name__)

class DTree(listinit.ListInit):
    """Maintain a local structure of dirs/items."""
    def _init(self, initial=None, rootid='root', **kwargs):
        """Initialize DTree.

        initial: Dtree initializer.  Another Dtree to copy or a filepath."""
        if isinstance(initial, str):
            try:
                with open(initial, 'r') as f:
                    self.root = json.load(f)
            except Exception:
                pass
        elif hasattr(initial, 'read'):
            self.root = json.load(f)
        elif initial:
            self.root = initial
        else:
            self.root = {'children': {}, 'id': rootid}
        self.cwd = os.sep
        return True

    def parse_parents(self, files, idkey='id', namekey='name', parkey='parents', truid=None):
        """Parse files into a tree structure.

        files: list of file info (dict).  Each itme should have keys:
            idkey: required, Key to identifying info in parents key.
            namekey: required, key for name of the the file.
            parkey: optional, key into each file for list of parent(s)
            truid: truid key for shortcuts
        """
        q = []
        lut = {}
        dangle = {}
        links = []
        if not truid:
            truid = '_' + idkey
        for item in files:
            item = item.copy()
            itemid = item[idkey]
            q.append(item)
            if self.isdir_(item):
                item.setdefault('children', {})
            if self.islink_(item):
                links.append(item)
            else:
                prev = lut.setdefault(itemid, item)
                if prev is not item:
                    lg.warning('Item already exists: %s vs %s', prev, item)
                    for k, v in item.items():
                        prev.setdefault(k, v)
                if parkey not in prev:
                    dangle[itemid] = prev
        for link in links:
            targetid = self.link_target_(link)
            try:
                link[''] = lut[targetid]
            except KeyError:
                lg.error('Link %s has no target.', link[idkey])
            else:
                link[truid] = link[idkey]
                link[idkey] = targetid
        roots = []
        for item in q:
            try:
                parents = item[parkey]
            except KeyError:
                parents = []
            if isinstance(parents, str):
                parents = [parents]
            name = item[namekey]
            for parent in parents:
                try:
                    pnode = lut[parent]
                except KeyError:
                    pnode = lut[parent] = {
                        'children': {}, idkey: parent, namekey: ''
                    }
                    roots.append(pnode)
                if self.islink_(pnode):
                    lg.warning('parent is a link')
                try:
                    children = pnode['children']
                except KeyError:
                    children = pnode['children'] = {}
                children[name] = item
                dangle.pop(item[idkey], None)
        for link in links:
            try:
                children = link['']['children']
            except KeyError:
                continue
            link['children'] = children
        return roots, dangle

    def copy_instance(self, initial, *args, **kwargs):
        # should this be deep copy?
        for attr in ('root', 'items', 'cwd'):
            setattr(self, kwargs.get(attr, getattr(initial, attr)))

    def save(self, out, **kwargs):
        """Save to out."""
        jutil.save(self.root, out, **kwargs)

    def __repr__(self):
        if self.cwd == os.sep:
            parts = ['* ', os.sep]
        else:
            parts = ['  ', os.sep]
        if self.root.get('name'):
            parts.extend([' (', self.root['name'], ')'])
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
            # parts.append([' (', node['id'], ')'])
        return ''.join(parts)

    def getcwd(self):
        return self.cwd

    def normpath(self, path):
        """Normalize path to absolute."""
        if path is None or path == '.':
            return self.cwd
        return os.path.normpath(os.path.join(self.cwd, path))

    def cd(self, path):
        """Change cwd."""
        path = self.normpath(path)
        if self.isdir(path):
            self.cwd = path
            return
        raise ValueError('path is not a dir or is not loaded.')
    def ls(self, path='.'):
        node = self.get(path)
        try:
            return list(node['children'].values())
        except KeyError:
            return node


    def get_(self, path, default=None):
        """Return an item from normalized path.

        path: a normalized path via self.normpath.
        """
        node = self.root
        for item in filter(None, path.split(os.sep)):
            try:
                node = node['children'][item]
            except KeyError:
                return default
        return node
    def get(self, path, default=None):
        """Same as get_ but normalize path first."""
        return self.get_(self.normpath(path), default)
    def __getitem__(self, path):
        ret = self.get(path)
        if ret is None:
            raise KeyError(path)
        return ret


    def makedirs_(self, path):
        node = self.root
        made = []
        parts = list(filter(None, path.split(os.sep)))
        for depth, item in enumerate(parts):
            try:
                children = node['children']
            except KeyError:
                raise ValueError('Not a directory.')
            try:
                node = children[item]
            except KeyError:
                node = children[item] = self.dirnode(item)
                made.append(os.path.join(os.sep, *parts[:depth+1]))
        return node, made
    def makedirs(self, path):
        return self.makedirs_(self.normpath(path))
    def touch_(self, path):
        dname, bname = os.path.split(path)
        node, made = self.makedirs_(dname)
        ret = node['children'][bname] = self.node(bname)
        return ret
    def touch(self, path):
        return self.touch_(self.normpath(path))

    def update_(self, path, node):
        """Update an entry.

        path: the path to the entry
        node: the info to update
        """
        orig = self.get_(path)
        if orig is None:
            dname, bname = os.path.split(path)
            node, made = self.makedirs_(dname)
            for k, v in self.node(bname).items():
                node.setdefault(k, v)
            node['children'] = node
            return node
        else:
            raise NotImplementedError
            # walk and update...
            # todo

    def update(self, path, node):
        return self.update_(self.normpath(path), node)

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

    def isdir(self, nodeOrPath):
        """Check if node or path is a dir."""
        if isinstance(nodeOrPath, str):
            nodeOrPath = self[nodeOrPath]
        return self.isdir_(nodeOrPath)

    def islink(self, nodeOrPath):
        if isinstance(nodeOrPath, str):
            nodeOrPath = self[nodeOrPath]
        return self.islink_(nodeOrPath)
    def link_target(self, nodeOrPath):
        if isinstance(nodeOrPath, str):
            nodeOrPath = self[nodeOrPath]
        return self.link_target_(nodeOrPath)

    # ========================
    # implementation specific:
    # ========================
    def isdir_(self, node):
        """Check if node (dict) is a dir."""
        return (
            'children' in node
            or (self.islink_(node) and self.isdir_(node.get('', {})))
        )
    def islink_(self, node):
        return (
            '' in node
            or ('_id' in node and node.get('id') != node['_id'])
            or 'shortcut' in node.get('mimeType', '').lower()
        )
    def link_target_(self, node):
        return node.get('id')

    def node(self, name, **kwargs):
        kwargs['name'] = name
        return kwargs
    def dirnode(self, name, **kwargs):
        kwargs['name'] = name
        kwargs.setdefault('children', {})
        return kwargs

