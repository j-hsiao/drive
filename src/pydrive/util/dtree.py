"""A tree structure of file nodes."""
import json
import logging
import os
import uuid

from . import jutil
from . import listinit

lg = logging.getLogger(__name__)

class DTree(listinit.ListInit):
    """Maintain a local structure of dirs/items.

    A lookup table of id to dict representing a node in the tree.
    Special keys can be customized via __init__ kwargs.
        idkey: node id, like an innode
        namekey: name of node.
        parentskey: list of parent ids
        childrenkey: dict[name] = id

    The lut also has special id int 0. This is a node that acts as parent
    for all (potential) roots.
    There might or might not be an explicit (main) root.
    roots don't have parents and are represented as '//rootname'.
    """
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
        if isinstance(initial, str):
            with open(os.path.expanduser(initial), 'r') as f:
                self.lut = json.load(f)
        elif hasattr(initial, 'read'):
            self.lut = json.load(f)
        else:
            self.lut = {0: self.dirnode(''), '': self.dirnode('')}
            self.lut[0][self.childrenkey][''] = ''
        self.cwd = os.sep
        return True

    def update(self, files):
        """Update from sequence of file dicts containing parents key.

        files: list of file info (dict).  Each item should have keys:
            self.idkey and self.namekey are required.
            self.parentskey is optional.

        Each file will have parents/children key added as necessary.
        """
        lut = self.lut
        idkey = self.idkey
        namekey = self.namekey
        childrenkey = self.childrenkey
        parentskey = self.parentskey
        q = []
        for item in files:
            item = item.copy()
            itemid = item[idkey]
            if not isinstance(itemid, str):
                item[idkey] = itemid = str(itemid)
            prev = lut.setdefault(itemid, item)
            if self.isdir_(prev, False):
                prev.setdefault(childrenkey, {})
            if prev is not item:
                self.merge(prev, item)
            else:
                q.append(prev)
        for item in q:
            itemid = item[idkey]
            name = item[namekey]
            try:
                parents = item[parentskey]
            except KeyError:
                self._link_child(lut[0], item)
            else:
                for parentid in parents:
                    try:
                        parnode = lut[parentid]
                    except KeyError:
                        parnode = lut[parentid] = self.dirnode('')
                        parnode[idkey] = parentid
                        self._link_child(lut[0], parnode)
                    self._link_child(parnode, item)
            children = item.get(childrenkey)
            if children is not None:
                for childid in children.values():
                    child = lut[childid]
                    if child is not None:
                        self._link_child(item, child)
        if '' in lut[0][childrenkey]:
            lut[''] = lut[lut[0][childrenkey]['']]
        return roots

    def copy_instance(self, initial, *args, **kwargs):
        """Shallow copy values from another dtree."""
        for attr in ('lut', 'cwd', 'idkey', 'namekey', 'childrenkey', 'parentskey'):
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
        node = self.lut[0]
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
            lg.exception('Error searching for %s', path)
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

    def child(self, node, childname):
        return self.child_(node, childname, self.lut)
    def child_(self, node, childname, lut):
        return lut[node[self.childrenkey][childname]]


    def _link_child(self, parent, child):
        cid = child[self.idkey]
        pid = parent[self.idkey]
        cname = child[self.namekey]
        children = parent[self.childrenkey]
        if children.setdefault(cname, cid) != cid:
            lg.warning(
                'Multiple files with same name %s: %s vs %s',
                cname, children[cname], cid)
            children['_'.join([cname, uuid.uuid4().hex])] = cid

        parents = child.setdefaults(self.parentskey, [])
        if pid not in parents:
            parents.append(pid)


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
        for k, v in new.items():
            if k == self.childrenkey:
                try:
                    children = old[self.childrenkey]
                except KeyError:
                    lg.warning('Merge target is not dirlike: %s vs %s', old, new)
                    old[k] = v
                else:
                    for ck, cv in v.items():
                        if children.setdefault(ck, cv) is not cv and children[ck] != cv:
                            lg.warning('Merged child %s of %s, ids are different: %s vs %s', ck, old[self.namekey], children[ck], cv)
                            children['_'.join([ck, uuid.uuid4().hex])] = cv
            else:
                try:
                    pre = old[k]
                except KeyError:
                    pass
                else:
                    if v != pre:
                        lg.warning('Changing file value %s: %s -> %s', k, pre, v)
                old[k] = v
