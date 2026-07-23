from pydrive.util import dtree

tree = dtree.DTree()


assert list(name for name, info in tree.walk()) == ['/']

assert tree.get('/a/b') is None
assert isinstance(tree.get('/a/b', True), dict)

assert not tree.isdir('/a/b')
assert tree.isdir('/a')
assert tree.isdir('/a/')
assert tree.isdir('/')

tree.update([dict(name=name) for name in 'abc'], '/a')

assert list(name for name, info in tree.walk()) == ['/', '/a/', '/a/a', '/a/b', '/a/c']
