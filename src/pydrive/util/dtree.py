"""A tree structure of file nodes."""
import json
import logging
import os

from . import jutil
from . import listinit

lg = logging.getLogger(__name__)

class DTree(listinit.ListInit):
    """Maintain a local structure of dirs/items."""
    LINK_TARGET = ('target')
    def _init(self, initial=None, **kwargs):
        """Initialize DTree.

        initial: Dtree initializer.  Another Dtree to copy or a filepath.
        kwargs: *key
            * can be id, name, children, parents to customize the
            underlying datastructure.
        """
        for key in ['id', 'name', 'children', 'parents']:
            setattr(self, key+'key', kwargs.get(key+'key', key))
        self.lut = {'': self.dirnode('')}
        if isinstance(initial, str):
            with open(os.path.expanduser(initial), 'r') as f:
                self.lut = json.load(f)
        elif hasattr(initial, 'read'):
            self.lut = json.load(f)
        elif initial:
            self.lut[''].update(initial)
        self.root = self.lut['']
        shares = self.root.setdefault(self.childrenkey, {}).setdefault('', self.dirnode(''))
        shares.setdefault(self.idkey, '')
        self.cwd = os.sep
        return True

    def parse_parents(self, files):
        """Parse files into a tree structure.

        files: list of file info (dict).  Each itme should have keys:
            self.idkey and self.namekey are required.
            self.parentskey is optional.

        Return roots, dangle, lut
        lut: dict of id: node.
        roots: list of root nodes.  These are nodes that were referred
               to as parents but not in `files`.
        dangle: list of nodes in `files` without any parents.
        """
        q = []
        lut = {}
        dangle = set()
        for item in files:
            item = item.copy()
            itemid = item[self.idkey]
            q.append(item)
            if self.isdir_(item):
                item.setdefault(self.childrenkey, {})
            prev = lut.setdefault(itemid, item)
            if prev is not item:
                lg.warning('Item already exists: %s vs %s', prev, item)
                for k, v in item.items():
                    prev.setdefault(k, v)
            if self.parentskey not in item:
                dangle.add(itemid)
        roots = []
        for item in q:
            try:
                parents = item[self.parentskey]
            except KeyError:
                continue
            name = item[self.namekey]
            for parent in parents:
                try:
                    pnode = lut[parent]
                except KeyError:
                    pnode = lut[parent] = {self.childrenkey: {}, self.idkey: parent}
                    roots.append(parent)
                if self.islink_(pnode):
                    lg.warning('parent is a link')
                try:
                    children = pnode[self.childrenkey]
                except KeyError:
                    children = pnode[self.childrenkey] = {}
                if children.setdefault(name, item) is not item:
                    lg.warning(
                        'Multiple children with the same name: %s vs %s',
                        children[name], item)
        return lut, roots, dangle

    def copy_instance(self, initial, *args, **kwargs):
        """Shallow copy values from another dtree."""
        for attr in ('lut', 'root', 'cwd', 'idkey', 'namekey', 'childrenkey', 'parentskey'):
            setattr(self, kwargs.get(attr, getattr(initial, attr)))

    def save(self, out, **kwargs):
        """Save to out."""
        jutil.save(self.lut, out, **kwargs)

    def __str__(self):
        if self.cwd == os.sep:
            parts = ['* ', os.sep]
        else:
            parts = ['  ', os.sep]
        if self.root.get(self.namekey):
            parts.extend([' (', self.root[self.namekey], ')'])
        special = os.sep*2
        for name, node in self.walk('/'):
            parts.append('\n')
            if name.rstrip(os.sep) == self.cwd:
                parts.append('* ')
            else:
                parts.append('  ')
            if name.startswith(special):
                parts.append(special)
            split = name.strip(os.sep).split(os.sep)
            for _ in range(len(split)):
                parts.append('  ')
            parts.append(split[-1])
            if name.endswith(os.sep):
                parts.append(os.sep)
        return ''.join(parts)

    def getcwd(self):
        """Return the cwd of this DTree."""
        return self.cwd

    def normpath(self, path):
        """Normalize path to absolute."""
        if path is None or path == '.':
            return self.cwd
        return os.path.normpath(os.path.join(self.cwd, path))

    def cd(self, path):
        """Change cwd."""
        normed = self.normpath(path)
        nd = self.get_(normed)
        if nd is None:
            raise ValueError('{} does not exist or was not loaded.'.format(repr(path)))
        if self.isdir_(nd):
            self.cwd = normed
            return
        raise ValueError('{} not a directory'.format(repr(path)))
    def ls(self, path='.', sort=True):
        """Get a list of children or the node."""
        node = self.get(path)
        try:
            items = node[self.childrenkey].items()
        except KeyError:
            tgt = self.link_target_(node, self.lut)
            if tgt == node[self.idkey]:
                return node
            try:
                items = self.lut[tgt]
            except KeyError:
                raise OSError('link target does not exist.')
            else:
                try:
                    items = items[self.childrenkey].items()
                except KeyError:
                    return items
        if sort:
            items = sorted(items)
        return [child for name, child in items if name]

    def path(self, node):
        """Calculate the path of this node."""
        parts = []
        namekey = self.namekey
        name = node.get(namekey)
        while name is not None:
            parts.append(name)
            try:
                node = self.lut[node[self.parentskey][0]]
            except KeyError:
                break
            name = node.get(self.namekey)
        if name:
            parts.extend(('', ''))
        return os.sep.join(reversed(parts))

    def get_(self, path, default=None):
        """Return an item from normalized path.

        path: a normalized path via self.normpath.
        """
        node = self.root
        try:
            for item in path.split(os.sep)[1+path.endswith(os.sep):]:
                try:
                    node = node[self.childrenkey][item]
                except KeyError:
                    tgt = self.link_target_(node, self.lut)
                    if tgt == node[self.idkey]:
                        return default
                    else:
                        node = self.lut[tgt][self.childrenkey][item]
            return node
        except Exception:
            return default
    def get(self, path, default=None):
        """Same as get_ but path can be unnormalized."""
        return self.get_(self.normpath(path), default)
    def __call__(self, nodeid):
        """Get node via id."""
        return self.lut[nodeid]
    def __getitem__(self, path):
        ret = self.get(path)
        if ret is None:
            raise KeyError(path)
        return ret

    def makedirs_(self, path):
        """Create directory + intermediates to normalized path.

        Return (target, created)
        """
        node = self.root
        made = []
        parts = path.split(os.sep)[1+path.endswith(os.sep):]
        for depth, item in enumerate(parts):
            try:
                children = node[self.childrenkey]
            except KeyError:
                raise ValueError('Not a directory.')
            try:
                node = children[item]
            except KeyError:
                node = children[item] = self.dirnode(item)
                made.append(os.path.join(os.sep, *parts[:depth+1]))
        return node, made
    def makedirs(self, path):
        """Make dirs from non-normalized path."""
        return self.makedirs_(self.normpath(path))
    def touch_(self, path):
        """Touch a file specified by normalized path."""
        dname, bname = os.path.split(path)
        dnode = self.get_(dname)
        return dnode[self.childrenkey].setdefault(bname, self.node(bname))
    def touch(self, path):
        """Touch a file by non-normalized path."""
        return self.touch_(self.normpath(path))

    def update_(self, node, path=None, id=None):
        """Update an entry.

        path: the path to the entry
        node: the info to update
        """
        if id is None:
            orig = self.get_(path)
            if orig is None:
                dname, bname = os.path.split(path)
                dnode, made = self.makedirs_(dname)
                if self.isdir_(node):
                    orig = self.dirnode(node[self.namekey])
                else:
                    orig = self.node(node[self.namekey])
                dnode[self.childrenkey][node[self.namekey]] = orig
        else:
            orig = self.lut[id]
        self.merge(orig, node)
    def update(self, node, path=None, id=None):
        return self.update_(node, self.normpath(path), id)

    def walk(self, path='.', sort=True, _node=None):
        """Walk through all descendents of the given path."""
        if _node is None:
            path = self.normpath(path)
            _node = self.get_(path)
        else:
            if self.isdir_(_node):
                if path.endswith(os.sep):
                    if not _node[self.childrenkey]:
                        return
                else:
                    yield path + os.sep, _node
            else:
                yield path, _node
                return
        items = _node.get(self.childrenkey, {}).items()
        if sort:
            items = sorted(items)
        for cname, cnode in items:
            if cname:
                cpath = os.path.join(path, cname)
            else:
                cpath = path + os.sep
            for res in self.walk(cpath, sort=sort, _node=cnode):
                yield res

    def isdir(self, nodeOrPath, link=True):
        """Check if node or path is a dir."""
        if isinstance(nodeOrPath, str):
            nodeOrPath = self[nodeOrPath]
        return self.isdir_(nodeOrPath, link)

    def islink(self, nodeOrPath):
        if isinstance(nodeOrPath, str):
            nodeOrPath = self[nodeOrPath]
        return self.islink_(nodeOrPath)
    def link_target(self, nodeOrPath, full=True):
        """Return target id."""
        if isinstance(nodeOrPath, str):
            nodeOrPath = self[nodeOrPath]
        return self.link_target_(nodeOrPath, self.lut, full)

    # ========================
    # implementation specific:
    # ========================
    def isdir_(self, node, link=True):
        """Check if node (dict) is a dir.

        node: the node to check
        link: follow links.
        """
        if self.childrenkey in node:
            return True
        if link and self.islink_(node):
            node = self.lut.get(self.link_target_(node, self.lut))
            if node is None:
                return False
            return self.isdir_(node, False)
        return False

    def islink_(self, node):
        try:
            for k in self.LINK_TARGET:
                node = node[k]
            return True
        except Exception:
            return False

    def link_target_(self, node, lut, full=True):
        """Calculate the link target.

        full: fully follow links til non-link.
        """
        try:
            tgt = node
            for k in self.LINK_TARGET:
                tgt = tgt[k]
        except KeyError:
            return node[self.idkey]
        if full:
            tnode = lut.get(tgt)
            if tnode is None:
                return tgt
            return self.link_target_(tnode, lut, full)
        else:
            return tgt

    def node(self, name, **kwargs):
        kwargs[self.namekey] = name
        return kwargs
    def dirnode(self, name, **kwargs):
        kwargs.setdefault(self.childrenkey , {})
        return self.node(name, **kwargs)

    def merge(self, old, new):
        """Merge file info dict new into old."""
        # TODO update self.lut
        for k, v in new.items():
            if k == self.childrenkey:
                try:
                    children = old[self.childrenkey]
                except KeyError:
                    raise ValueError('Merging dir node into a non-dir node.')
                for cname, cnode in new[self.childrenkey].items():
                    onode = children.get(cname)
                    if onode is None:
                        if self.isdir_(cnode, False):
                            onode = children[cname] = self.dirnode(cname)
                        else:
                            onode = children[cname] = self.node(cname)
                    self.merge(onode, cnode)
                for cname, cnode in new[self.childrenkey].items():
                    children[cname] = self.lut[cnode[self.idkey]]
            else:
                if k in old:
                    if v != old[k]:
                        lg.warning('Changing file value %s: %s -> %s', k, old[k], v)
                        old[k] = v
                else:
                    old[k] = v
                if k == self.idkey:
                    self.lut[v] = old
