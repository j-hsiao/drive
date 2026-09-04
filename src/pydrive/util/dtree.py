"""A tree structure of file nodes."""
import json
import logging
import os
import random
import sys

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
    LINK_TARGET = ['target']
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

    def getcwd(self):
        """Return the cwd of this DTree."""
        return self.cwd

    def normpath(self, path):
        """Normalize path to absolute."""
        if path is None or path == '.':
            return self.cwd
        elif path.startswith('@:'):
            return path
        return os.path.normpath(os.path.join(self.cwd, path))

    def ls(self, path='.', sort=True, alts=False):
        """Get a list of children or the node.

        path: path to ls.
        sort: sort children if `path` is a dir
        alts: Add alternatives (clashed names)
        """
        node = self.get(path)
        try:
            items = node[self.childrenkey].items()
        except KeyError:
            try:
                node = self.lut[self._link_target(node, self.lut)]
                items = node[self.childrenkey].items()
            except KeyError:
                return node
        if alts:
            alts = node.get(self.clashkey, {})
            nitems = []
            for k, v in items:
                namealts = alts.get(k)
                if namealts:
                    for altid in namealts:
                        nitems.append((k, altid))
                else:
                    nitems.append((k,v))
            items = nitems
            if sort:
                items.sort()
        elif sort:
            items = sorted(items)
        return [self.lut[childid] for name, childid in items]

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

    def get(self, path, default=None):
        """Same as _get but path can be unnormalized."""
        return self._get(self.normpath(path), default)
    def __getitem__(self, path):
        ret = self.get(path)
        if ret is None:
            raise KeyError(path)
        return ret

    def __call__(self, nodeid):
        """Get node via id."""
        return self.lut[nodeid]

    def walk(self, path='.', sort=True):
        """Walk through all descendents of the given path."""
        path = self.normpath(path)
        node = self._get(path)
        for res in self._walk(path, node, sort):
            yield res


    def isdir(self, nodeOrPath, link=True):
        """Check if node or path is a dir."""
        if isinstance(nodeOrPath, str):
            nodeOrPath = self[nodeOrPath]
        return self._isdir(nodeOrPath, link)
    def islink(self, nodeOrPath):
        """Check if path/node is a link."""
        if isinstance(nodeOrPath, str):
            nodeOrPath = self[nodeOrPath]
        return self._islink(nodeOrPath)
    def link_target(self, nodeOrPath, full=True):
        """Return target id of a link.

        Return the node id if not a link.
        """
        if isinstance(nodeOrPath, str):
            nodeOrPath = self[nodeOrPath]
        return self._link_target(nodeOrPath, self.lut, full)
    def real(self, pathOrNode):
        if isinstance(pathOrNode, str):
            pathOrNode = self.get(pathOrNode)
            if pathOrNode is None:
                return False
        return self._real(pathOrNode)

    def cd(self, path):
        """Change cwd."""
        normed = self.normpath(path)
        nd = self._get(normed)
        if nd is None:
            raise ValueError('{} does not exist or was not loaded.'.format(repr(path)))
        if self._isdir(nd):
            self.cwd = normed
            return
        raise ValueError('{} not a directory'.format(repr(path)))

    def makedirs(self, path):
        """Make dirs from non-normalized path."""
        return self._makedirs(self.normpath(path))
    def touch(self, path):
        """Touch a file by non-normalized path."""
        return self._touch(self.normpath(path))

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



    def _get_root(self, path):
        """Get the appropriate root dir node for this path.

        If it does not exist, then create it.
        The root is chosen as:
        1. if path starts with //, then the toplevel node.
        2. Otherwise, find the first root dir that:
           a. Has name in self.rootnames
           b. alphabetically first root.
        """
        node = self.lut[0]
        if path.startswith(sroot):
            return node
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
        return self._mkdir(node, '')

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

    def _get(self, path, default=None):
        """Return an item from normalized path.

        path: a normalized path via self.normpath.
            Each path component has some extra processing:
            @@* suppress @:id parsing and remove initial @.
            *]] suppress name[index] parsing and remove last ]
            @:id specifies an id explicitly.
            name[index] specifies an alternative (clashed name)

        Examples:
        component       meaning
        -----------------------
        something       name is 'something'
        @whatever       name is '@whatever'
        @:whatever      id is 'whatever'
        @@whatever      name is '@whatever'
        @@:whatever     name is '@:whatever'
        name[0]         0th alternative of name (same as 'name')
        name[1]         1st alternative of name.
        name[1]]        name is 'name[1]'
        @:name[0]       id is 'name[0]'
        @@:name[0]      0th alternative of '@:name'
        @@:name[0]]     name is '@:name[0]'
        """
        node = self._get_root(path)
        try:
            parts = list(filter(None, path.split(os.sep)))
            pidx = 0
            for pidx, item in enumerate(parts):
                node = self.lut[self._link_target(node, self.lut)]
                if item.startswith('@@'):
                    item = item[1:]
                elif item.startswith('@:'):
                    node = self.lut[item[2:]]
                    continue
                if item.endswith(']]'):
                    item = item[:-1]
                elif item.endswith(']'):
                    name, idx = item.rsplit('[', 1)
                    try:
                        idx = int(idx[:-1])
                    except ValueError:
                        pass
                    else:
                        if idx == 0:
                            item = name
                        else:
                            node = self.lut[node[self.clashkey][name][idx]]
                            continue
                node = self.lut[node[self.childrenkey][item]]
            return node
        except KeyError:
            pass
        except Exception:
            lg.exception('Error searching for %s', path)
        return default

    def _register(self, node):
        """Register a node.  Generate an id if missing. Return the node."""
        nid = node.get(self.idkey)
        if nid is None:
            nid = random.randint(0, sys.maxsize)
        for i in range(sys.maxsize):
            if self.lut.setdefault(nid, node) is node:
                node[self.idkey] = nid
                return node
            try:
                nid += 1
            except TypeError:
                raise ValueError('node with id {} already exists'.format(repr(nid)))
        raise ValueError('ID generation failed.')
    def _mkdir(self, parent, name, *args, **kwargs):
        """Create a dir node under parent with name and a generated id."""
        ndir = self.dirnode(name, *args, **kwargs)
        self._register(ndir)
        self._add_child(parent, ndir)
        return ndir
    def _touch(self, path):
        """Touch a file specified by normalized path."""
        dname, bname = os.path.split(path)
        dnode = self._get(dname)
        try:
           children = dnode[self.childrenkey]
        except KeyError:
           raise ValueError('{} is not a directory'.format(dname))
        ret = children.get(bname)
        if ret is None:
            ret = self._register(self.node(bname))
            self._add_child(dnode, ret)
        return ret
    def _makedirs(self, path):
        """Create directory + intermediates to normalized path.

        Return (target, created)
        """
        node = self._get_root(path)
        made = []
        for item in filter(None, path.split(os.sep)):
            try:
                children = node[self.childrenkey]
            except KeyError:
                raise ValueError('Not a directory.')
            try:
                cid = children[item]
            except KeyError:
                node = self._mkdir(node, item)
                made.append(node)
            else:
                try:
                    node = self.lut[cid]
                except KeyError:
                    node = self._mkdir(node, item, (self.idkey, cid))
        return node, made

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
    def _real(self, node):
        """Return whether the node is a real node or just a temporary place holder."""
        return isinstance(node.get(self.idkey), str)

    def _norm_clash(self, clashlist):
        """Return a normalized list of clashing ids.

        clashlist: list of ids of nodes with clashing paths.

        1. Remove duplicates
        2. Remove unregistered ids.
        3. Put the best representative at the beginning.
           a. real is better than not
           b. earlier in the list is better
        """
        s = set()
        out = []
        best = None
        real = False
        for cid in clashlist:
            if cid in s:
                continue
            s.add(cid)
            try:
                node = self.lut[cid]
            except KeyError:
                continue
            creal = self._real(node)
            if best is None or (creal and not real):
                real = creal
                best = len(out)
            out.append(cid)
        if out:
            pick = out[best]
            for i in range(best, 0, -1):
                out[i] = out[i-1]
            out[0] = pick
        return out

    def unneeded(self):
        """Return a list of unnecessary nodes.

        A node is unnecessary if it does not have a real descendant.
        """
        results = {}
        q = self.lut.items()
        ret = []
        while q:
            deferred = []
            for k, v in q:
                if self.real(v) or k == 0:
                    results[k] = True
                    continue
                children = v.get(self.childrenkey)
                if not children:
                    results[k] = False
                    ret.append(v)
                    continue
                for cname, cid in children.items():
                    need = results.get(cid)
                    if need is None:
                        deferred.append((k,v))
                        break
                    elif need:
                        results[k] = True
                        break
                else:
                    # all false, check clashkey
                    for name, clashids in v.get(self.clashkey, {}).items():
                        for clashid in clashids:
                            need = results.get(clashid)
                            if need is None:
                                deferred.append((k,v))
                                break
                            elif need:
                                results[k] = True
                                break
                        else:
                            continue
                        break
                    else:
                        results[k] = False
                        ret.append(v)
            q = deferred
        return ret

    def _isdir(self, node, link=True):
        """Check if node (dict) is a dir (or a link pointing to dir if `link`).

        node: the node to check
        link: Also return True for links to a dir.
        """
        if self._isdir_(node):
            return True
        if link:
            tgt = self._link_target(node, self.lut, True)
            try:
                return tgt != node[self.idkey] and self._isdir_(self.lut[tgt])
            except KeyError:
                return False
        return False
    def _isdir_(self, node):
        """Return whether a node is explicitly a dir."""
        return self.childrenkey in node

    def _islink(self, node):
        try:
            for k in self.LINK_TARGET:
                node = node[k]
            return True
        except Exception:
            return False

    def _link_target(self, node, lut, full=True):
        """Calculate the link target.

        full: fully follow links til non-link.
        If there is a link loop, then point to the first
        encountered member of the loop.
        ie: links a, b, and c
        a -> b, b -> c, c -> b, will return b's id.
        """
        pre = set()
        tgt = node[self.idkey]
        while 1:
            if tgt in pre:
                lg.warning('Loop of links detected: %s', tgt)
                return tgt
            pre.add(tgt)
            nid = tgt
            tgt = node
            for k in self.LINK_TARGET:
                tgt = tgt.get(k)
                if tgt is None:
                    return nid
            if full:
                node = lut.get(tgt)
                if node is None:
                    return tgt
            else:
                return tgt

    def _walk(self, path, node, sort=True):
        """Walk from a given node."""
        yield path, node
        items = node.get(self.childrenkey, {}).items()
        clashes = node.get(self.clashkey, {})
        if sort:
            items = sorted(items)
        for cname, cid in items:
            cpath = os.path.join(path, cname)
            cclash = clashes.get(cname, [cid])
            for idx, cid in enumerate(cclash):
                try:
                    child = self.lut[cid]
                except KeyError:
                    lg.error('Encountered nonexistent child %r of %r', cid, node)
                else:
                    for res in self._walk(
                        (cpath + '[{}]'.format(idx) if idx else cpath), child, sort):
                        yield res

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

