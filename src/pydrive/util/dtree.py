import os

class DTree(object):
    """Maintain a local structure of dirs/items."""
    def __init__(self, folder_mimes=['application/vnd.google-apps.folder']):
        self.folder_mimes = folder_mimes
        self.root = {'children': {}}
        self.items = {}
        self.cwd = '/'

    def get(self, path, make=False):
        if path.startswith('/'):
            node = self.root
            for item in filter(None, os.path.normpath(path).lstrip(os.sep).split(os.sep)):
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
        else:
            return self.items.get(path, None)

    def isdir(self, node):
        if isinstance(node, str):
            node = self.get(node)
        return ('children' in node) or (node.get('mimeType', '') in self.folder_mimes)

    def update(self, fobjs, parent='/'):
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

    def walk(self, sort=True):
        q = [('', self.root)]
        while q:
            name, node = q.pop()
            children = node.get('children', None)
            if children is None:
                if node.get('mimeType', None) in self.folder_mimes:
                    children = {}
            if children is None:
                yield name, node
            else:
                name += os.sep
                yield name, node
                if sort:
                    children = list(children.items())
                    children.sort(key=(lambda x: x[0]), reverse=True)
                else:
                    children = children.items()
                for cname, child in children:
                    q.append((name + cname, child))
