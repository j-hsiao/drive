import json
import os
import logging
import sys
import pprint

from pydrive.util import dtree

dummyflat = [
    dict(name='hello', parents=['1'], id='2'),
    dict(name='goodbye', parents=['1'], id='3'),

    dict(name='hello', parents=['2'], id='4'),
    dict(name='goodbye', parents=['2'], id='5'),

    dict(name='shortcut', id='6', mimeType='shortcut'),
    dict(name='standalone', id='6'),
    dict(name='notclobbered', id='6', extra='whatever'),

    dict(name='shortcut', id='7', mimeType='shortcut', parents=['5']),
    dict(name='standalone', id='7'),
    dict(name='notclobbered', id='7', extra='whatever'),
]
roots, dangle = dtree.DTree().parse_parents(dummyflat)
expect = [{
    'id': '1', 'name': '',
    'children': {
        'goodbye': {'id': '3', 'name': 'goodbye', 'parents': ['1']},
        'hello': {
            'id': '2', 'name': 'hello', 'parents': ['1'],
            'children': {
                'goodbye': {
                    'id': '5', 'name': 'goodbye', 'parents': ['2'],
                    'children': {
                        'shortcut': {
                            '_id': '7', 'id': '7', 'mimeType': 'shortcut',
                            'name': 'shortcut', 'parents': ['5'],
                            '': {
                                'extra': 'whatever',
                                'id': '7',
                                'name': 'standalone'
                            },
                        },
                    },
                },
                'hello': {'id': '4', 'name': 'hello', 'parents': ['2']},
            },
        },
    },
}]
assert roots == expect
assert dangle == {'6': dict(name='standalone', id='6', extra='whatever')}

def normed(l):
    if isinstance(l, str):
        return os.path.normpath(l)
    return [os.path.normpath(_) for _ in l]

tree = dtree.DTree()
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
