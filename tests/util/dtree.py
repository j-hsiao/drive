import os

from pydrive.util import dtree

def normed(l):
    if isinstance(l, str):
        return os.path.normpath(l)
    return [os.path.normpath(_) for _ in l]

tree = dtree.DTree()
assert list(name for name, info in tree.walk('/')) == []
assert list(name for name, info in tree.walk()) == []

assert tree.get('/a/b') is None
assert isinstance(tree.get('/a/b', True), dict)
# /
#   a/
#     b

assert not tree.isdir('/a/b')
assert tree.isdir('/a')
assert tree.isdir('/a/')
assert tree.isdir('/')

assert tree.isdir('a')
assert not tree.isdir('a/b')

tree.update([dict(name=name) for name in 'abc'], '/a')
# /
#   a/
#     a/
#     b/
#     c/

assert normed(list(name for name, info in tree.walk())) == normed(['/a/', '/a/a', '/a/b', '/a/c'])

tree.cd('a')
assert tree.cwd == normed('/a')

assert normed(list(name for name, info in tree.walk())) == normed(['/a/a', '/a/b', '/a/c'])

assert str(tree) == '''  /
*   a/
      a
      b
      c'''
