import json
import os
import logging
import sys
import pprint

from pydrive.util import dtree

dummyflat = [
    dict(name='hello', parents=['1'], id='2', children={}),
    dict(name='goodbye', parents=['1'], id='3'),

    dict(name='hello', parents=['2'], id='4'),
    dict(name='goodbye', parents=['2'], id='5', children={}),

    dict(name='standalone', id='6'),
    dict(name='notclobbered', id='6', extra='whatever'),
    dict(name='shortcut', id='7', mimeType='shortcut', target='6'),

    dict(name='shortcut', id='9', mimeType='shortcut', parents=['5'], target='8'),
    dict(name='standalone', id='8'),
    dict(name='notclobbered', id='8', extra='whatever'),
]
tree = dtree.DTree()
roots = tree.update_parents(dummyflat)
assert roots == ['1']
assert tree(0) is tree('1')

n1 = tree(0)
n2 = tree.child_(n1, 'hello', lut)
n3 = tree.child_(n1, 'goodbye', lut)
n4 = tree.child_(n2, 'hello', lut)
n5 = tree.child_(n2, 'goodbye', lut)
n9 = tree.child_(n5, 'shortcut', lut)

assert set('123456789').issubset(lut)
assert n1 is lut['1']
assert n2 is lut['2']
assert n3 is lut['3']
assert n1['children'] == dict(hello='2', goodbye='3')
assert n4 is lut['4']
assert n5 is lut['5']
assert n2['children'] == dict(hello='4', goodbye='5')
assert n9 is lut['9']
assert n5['children'] == dict(shortcut='9')

def normed(l):
    if isinstance(l, str):
        return os.path.normpath(l)
    return [os.path.normpath(_) for _ in l]

tree = dtree.DTree()
assert tree['/'] is tree.root
assert tree['//'] is tree.root['children']['']
assert list(name for name, info in tree.walk('/')) == []
assert list(name for name, info in tree.walk()) == []

assert tree.get('/a/b') is None
assert tree.makedirs('/a/b') == (tree.dirnode('b'), normed(['/a', '/a/b']))
# /
#   a/
#     b/

assert tree.isdir('/a/b')
assert tree.isdir('/a')
assert tree.isdir('/a/')
assert tree.isdir('/')

assert tree.isdir('a')
assert tree.isdir('a/b')

assert tree.makedirs('/a/b/c') == (tree.dirnode('c'), normed(['/a/b/c/']))
tree.cd('a/b/')
assert tree.makedirs('/a/b/d') == (tree.dirnode('d'), normed(['/a/b/d/']))

# /
#   a/
#*    b/
#       c/
#       d/

assert not tree.isdir(tree.touch('x'))
assert not tree.isdir(tree.touch('../y'))
assert not tree.isdir(tree.touch('z'))

# /
#   a/
#*    b/
#       c/
#       d/
#       x
#       z
#     y

assert tree.cwd == normed('/a/b')
assert tree.normpath('../y') == '/a/y'

assert set([_['name'] for _ in tree.ls()]) == set('cdxz')
assert set([_['name'] for _ in tree.ls('..')]) == set('by')

tree.update(dict(children={k:dict(name=k) for k in 'efg'}), '.')
# /
#   a/
#*    b/
#       c/
#       d/
#       x
#       z
#       e
#       f
#       g
#     y
assert set(tree['.']['children']) == set('cdxzefg')
assert not tree.isdir('e')
assert not tree.isdir('f')
assert not tree.isdir('g')

assert [name for name, node in tree.walk('/')] == [
    '/a/',
    '/a/b/',
    '/a/b/c/',
    '/a/b/d/',
    '/a/b/e',
    '/a/b/f',
    '/a/b/g',
    '/a/b/x',
    '/a/b/z',
    '/a/y',
]

assert [name for name, node in tree.walk()] == [
    '/a/b/c/',
    '/a/b/d/',
    '/a/b/e',
    '/a/b/f',
    '/a/b/g',
    '/a/b/x',
    '/a/b/z',
]

tree.touch('//shareditem')
tree.makedirs('//sharedir/item')
assert [name for name, node in tree.walk('/')] == [
    '//sharedir/',
    '//sharedir/item/',
    '//shareditem',
    '/a/',
    '/a/b/',
    '/a/b/c/',
    '/a/b/d/',
    '/a/b/e',
    '/a/b/f',
    '/a/b/g',
    '/a/b/x',
    '/a/b/z',
    '/a/y',
]
