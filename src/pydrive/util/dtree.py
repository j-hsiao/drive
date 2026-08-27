"""A tree structure of file nodes."""
import json
import logging
import os

from . import jutil
from . import listinit

lg = logging.getLogger(__name__)

sroot = os.sep*2

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


    Nodes can generally be a file, dir, or link.
    file: a basic node.  Has id, name, parents
    dir: a file node but also has children and clash key
    link: a file node with a `LINK_TARGET` id.

    Basic keys:
    id: an identifying string, could be path, innode, etc.
    name: str, the name of the node
    parents: [parentids,...]
    children: dict[childname]: childid required for dirs
    clash: dict[childname]: [idlist], dir only, optional, child ids with same name.
    """
    LINK_TARGET = ('target')
    KEYS = ['id', 'name', 'children', 'parents', 'clash']
    def _init(self, initial=None, rootnames='', **kwargs):
        """Initialize DTree.

        initial: Dtree initializer.  Another Dtree to copy or a filepath.
        kwargs: *key
            * can be id, name, children, parents to customize the
            underlying datastructure.
        """
        if isinstance(rootnames, str):
            rootnames = [rootnames]
        self.rootnames = list(rootnames)
        if '' not in self.rootnames:
            self.rootnames.append('')
        self.copy_instance(None, **kwargs)
        if isinstance(initial, str):
            with open(os.path.expanduser(initial), 'r') as f:
                self.lut = json.load(f)
        elif hasattr(initial, 'read'):
            self.lut = json.load(f)
        else:
            self.lut = {0: self.dirnode('', (self.idkey, 0))}
            if initial:
                if isinstance(initial, dict):
                    if 0 in initial:
                        self.lut = initial
                    else:
                        self.update([initial])
                else:
                    self.update(initial)
        self.cwd = os.sep
        return True

    def update(self, files):
        """Update from sequence of file dicts containing parents key.

        files: list of file info (dict).  Each item should have keys:
            self.idkey and self.namekey are required.
            self.parentskey is optional.
        Each file will have parents/children key added as necessary.

        For convenience, update allows `childrenkey` to be a sequence of ids
        instead of a dict.
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
            if prev is not item:
                lg.info('merging %s, %s << %s', itemid, prev, item)
                self._merge(prev, item)
                if itemid in q:
                    continue
            q.append(itemid)
        for itemid in q:
            item = lut[itemid]
            lg.info('updating %s', item)
            name = item[namekey]
            try:
                parents = item[parentskey]
            except KeyError:
                self._add_child(lut[0], item)
            else:
                for parentid in parents:
                    try:
                        parnode = lut[parentid]
                    except KeyError:
                        parnode = lut[parentid] = self.dirnode('', (idkey, parentid))
                        self._add_child(lut[0], parnode)
                    self._add_child(parnode, item)
            children = item.get(childrenkey)
            if children is not None:
                if not isinstance(children, dict):
                    childids = children
                    item[childrenkey] = {}
                else:
                    childids = list(children.values())
                for childid in childids:
                    child = lut.get(childid)
                    if child is not None:
                        self._add_child(item, child)

    def _merge(self, old, new):
        """Merge new node data into old node.

        Break any relevant parent/child connections.
        """
        for k, v in new.items():
            try:
                pre = old[k]
            except KeyError:
                pass
            else:
                if v != pre:
                    if k == self.idkey:
                        raise ValueError('Should never be merging nodes with different id.')
                    elif k == self.namekey:
                        continue
                    lg.warning(
                        'Changing file value %s for %s: %s -> %s',
                        k, old[self.idkey], pre, v)
                    if k == self.parentskey:
                        for parentid in set(pre).difference(v):
                            parent = self.lut.get(parentid)
                            if parent is not None:
                                self._remove_child(parent, old)
                    elif k == self.childrenkey:
                        if isinstance(v, dict):
                            nchildids = set(v.values())
                        else:
                            nchildids = set(v)
                        ochildids = set(pre.values())
                        clash = old.get(self.clashkey)
                        if clash is not None:
                            ochildids.update(*clash.values())
                        for childid in ochildids.difference(nchildids):
                            child = self.lut.get(childid)
                            if child is not None:
                                self._remove_child(old, child)
            old[k] = v
        newname = new.get(self.namekey)
        if newname is None or old[self.namekey] == newname:
            return
        parents = old.get(self.parentskey)
        if parents is not None:
            parents = list(parents)
            for parentid in parents:
                parent = self.lut.get(parentid)
                if parent is None:
                    continue
                self._remove_child(parent, old)
            old[self.parentskey] = parents
        lg.warning('Changing file name for %s: %s -> %s', old[self.idkey], old[self.namekey], newname)
        old[self.namekey] = newname


    def copy_instance(self, initial, *args, **kwargs):
        """Shallow copy values from another dtree."""
        if initial is not None:
            for attr in ('lut', 'cwd', 'rootnames'):
                setattr(self, kwargs.get(attr, getattr(initial, attr)))
        for key in self.KEYS:
            keyname = key+'key'
            setattr(self, keyname, kwargs.get(keyname, key))

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
        if path.startswith('@') and not path.startswith('@@'):
            return path
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

    def find_root(self, path):
        """Find the root node to use for this path."""
        node = self.lut[0]
        if not path.startswith(sroot):
            children = node[self.childrenkey]
            for candidate in self.rootnames:
                try:
                    return self.lut[children[candidate]]
                except KeyError:
                    pass
            for k, v in sorted(children.items()):
                try:
                    return self.lut[v]
                except KeyError:
                    pass
        return node

    def get_(self, path, default=None):
        """Return an item from normalized path.

        path: a normalized path via self.normpath.
        A path component can also consist of special values:
            @id
            name[int-index]
        To start with a literal @, use @@
        To end with a literal ], end with ]]
        """
        node = self.find_root(path)
        try:
            for item in filter(None, path.split(os.sep)):
                try:
                    node = self.lut[self.link_target_(node, self.lut)]
                except KeyError:
                    return default
                if item.startswith('@'):
                    # TODO is it possible for id to start with an @ as well?
                    if item.startswith('@@'):
                        item = item[1:]
                    else:
                        try:
                            node = self.lut[item[1:]]
                        except KeyError:
                            return default
                        else:
                            continue
                if item.endswith(']')
                    if item.endswith(']]'):
                        item = item[:-1]
                    else:
                        name, idx = item.rsplit('[', 1)
                        try:
                            idx = int(idx[:-1])
                        except ValueError:
                            pass
                        else:
                            try:
                                node = self.lut[node[self.clashkey][name][idx]]
                            except (KeyError, IndexError, TypeError):
                                if idx == 0:
                                    item = name
                                else:
                                    return default
                            else:
                                continue
                try:
                    node = self.lut[node[self.childrenkey][item]]
                except KeyError:
                    return default
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

    def _add_child(self, parent, child):
        """Add connection from parent to child."""
        cid = child[self.idkey]
        pid = parent[self.idkey]
        cname = child[self.namekey]
        children = parent.setdefault(self.childrenkey, {})
        precid = children.setdefault(cname, cid)
        if precid != cid:
            lg.warning(
                'Multiple files with same name %s: %s vs %s',
                cname, precid, cid)
            clashes = parent.setdefault(self.clashkey, {})
            clashlist = clashes.setdefault(cname, [precid])
            if cid not in clashlist:
                clashlist.append(cid)
        parents = child.setdefault(self.parentskey, [])
        if pid not in parents:
            parents.append(pid)
            if pid != 0 and 0 in parents:
                self._remove_child(self.lut[0], child)

    def _remove_child(self, parent, child):
        """Disconnect child from parent."""
        cid = child[self.idkey]
        pid = parent[self.idkey]
        cname = child[self.namekey]
        children = parent.get(self.childrenkey)
        if children is not None:
            newchild = None
            precid = children.get(cname)
            clashes = parent.get(self.clashkey)
            if clashes is not None:
                cclashes = clashes.get(cname)
                if cclashes is not None:
                    if cid in cclashes:
                        cclashes.remove(cid)
                    if cclashes:
                        newchild = cclashes[0]
                    if len(cclashes) <= 1:
                        del clashes[cname]
            if precid != cid:
                newchild = precid
            if newchild is None:
                del children[cname]
            else:
                children[cname] = newchild
        parents = child.get(self.parentskey)
        if parents is not None and pid in parents:
            parents.remove(pid)
            if not parents:
                del child[self.parentskey]

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
        if link:
            tgt = node
            while 1:
                try:
                    for k in self.LINK_TARGET:
                        tgt = tgt[k]
                except KeyError:
                    return self.childrenkey in tgt
                try:
                    tgt = self.lut[tgt]
                except KeyError:
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
        while 1:
            tgt = node
            for k in self.LINK_TARGET:
                tgt = tgt.get(k)
                if tgt is None:
                    return node[self.idkey]
            if full:
                try:
                    node = self.lut[tgt]
                except KeyError:
                    return tgt
            else:
                return tgt

    def node(self, name, *args, **kwargs):
        """Create a node dict."""
        kwargs[self.namekey] = name
        for k, v in args:
            kwargs[k] = v
        return kwargs
    def dirnode(self, name, *args, **kwargs):
        """Create a dir node dict."""
        kwargs.setdefault(self.childrenkey , {})
        return self.node(name, *args, **kwargs)
