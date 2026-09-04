import json
import os
import logging
import sys
import pprint

logging.basicConfig(
    level=getattr(logging, os.environ.get('LOGLEVEL', 'WARNING').upper(), logging.WARNING),
    stream=sys.stderr
)
lg = logging.getLogger(__name__)

from pydrive.util import dtree

def norm(l):
    if isinstance(l, str):
        return os.path.normpath(l)
    return [os.path.normpath(_) for _ in l]


def test_normal_update():
    # //
    #   new
    #   shortcut1 -> //new
    #   /
    #     a/
    #       c/
    #         new2
    #       d/
    #         shortcut2 -> /a/c/new2
    #     b
    dummypar = [
        dict(name='a', parents=['1'], id='2'),
        dict(name='b', parents=['1'], id='3'),

        dict(name='c', parents=['2'], id='4'),
        dict(name='d', parents=['2'], id='5'),

        dict(name='orig', id='6'),
        dict(name='new', id='6', extra='whatever'),
        dict(name='shortcut1', id='7', target='6'),

        dict(name='shortcut2', id='9', parents=['5'], target='8'),
        dict(name='orig2', id='8', parents=['4']),
        dict(name='new2', id='8', extra='whatever'),
    ]

    dummychi = [
        dict(name='', id='1', children=['2', '3']),
        dict(name='a', id='2', children=['4', '5']),
        dict(name='b', id='3'),

        dict(name='c', id='4', children=['8']),
        dict(name='d', id='5', children=['9']),

        dict(name='orig', id='6'),
        dict(name='new', id='6', extra='whatever'),
        dict(name='shortcut1', id='7', target='6'),

        dict(name='shortcut2', id='9', target='8'),
        dict(name='orig2', id='8'),
        dict(name='new2', id='8', extra='whatever'),
    ]

    keys = dict(childrenkey='children', parentskey='parents', idkey='id')

    tree = dtree.DTree(**keys)
    tree.update(dummypar)
    lg.info('parent tree\n%s', pprint.pformat(tree.lut))
    assert tree(0)['children'] == {'': '1', 'new': '6', 'shortcut1': '7'}
    assert tree('1')['children'] == dict(a='2', b='3')
    assert tree('2')['children'] == dict(c='4', d='5')
    assert 'children' not in tree('3')
    assert tree('4')['children'] == dict(new2='8')
    assert tree('5')['children'] == dict(shortcut2='9')
    assert 'children' not in tree('6')
    assert 'children' not in tree('7')
    assert 'children' not in tree('8')
    assert 'children' not in tree('9')
    for i in range(1, 10):
        assert tree(str(i)) is tree['@:{}'.format(i)]
        assert tree(str(i)) is tree['/a/c/@:{}'.format(i)]

    assert tree('1') is tree['//[0]']
    assert tree('1') is tree['/']
    assert tree('2') is tree['//[0]/a']
    assert tree('2') is tree['/a']
    assert tree('2') is tree['a']
    assert tree('3') is tree['//[0]/b']
    assert tree('3') is tree['/b']
    assert tree('3') is tree['b']
    assert tree('4') is tree['//[0]/a/c']
    assert tree('4') is tree['/a/c']
    assert tree('4') is tree['a/c']
    assert tree('5') is tree['//[0]/a/d']
    assert tree('5') is tree['/a/d']
    assert tree('5') is tree['a/d']
    assert tree('6') is tree['//new']
    assert tree('6') is tree['//new[0]']
    assert tree('7') is tree['//shortcut1']
    assert tree('7') is tree['//shortcut1[0]']
    assert tree('8') is tree['//[0]/a/c/new2']
    assert tree('8') is tree['/a/c/new2']
    assert tree('8') is tree['a/c/new2']
    assert tree('9') is tree['/a/d/shortcut2']
    assert tree('9') is tree['//[0]/a/d/shortcut2']

    assert tree.link_target('//shortcut1') == tree['//new']['id']
    assert tree.link_target('/a/d/shortcut2') == tree['/a/c/new2']['id']

    ntree = dtree.DTree(**keys)
    ntree.update(dummychi)
    lg.info('child tree\n%s', pprint.pformat(ntree.lut))
    assert ntree.lut == tree.lut

    assert tree.ls('/') == [tree['/a'], tree['/b/']]
    assert tree.ls('/a') == [tree['/a/c'], tree['/a/d']]
    assert tree.ls('/a/c') == [tree['/a/c/new2']]
    assert tree.ls('//new') is tree['//new']
    assert tree.ls('//shortcut1') is tree['//new']
    assert tree.ls('/a/c/new2') is tree['/a/c/new2']
    assert tree.ls('/a/d/shortcut2') is tree['/a/c/new2']


    # rename
    tree.update([dict(name='changed again', id='8')])
    assert tree(0)['children'] == {'': '1', 'new': '6', 'shortcut1': '7'}
    assert tree('1')['children'] == dict(a='2', b='3')
    assert tree('2')['children'] == dict(c='4', d='5')
    assert 'children' not in tree('3')
    assert tree('4')['children'] == {'changed again': '8'}
    assert tree('5')['children'] == dict(shortcut2='9')
    assert 'children' not in tree('6')
    assert 'children' not in tree('7')
    assert 'children' not in tree('8')
    assert 'children' not in tree('9')

def test_clashing_update():
    nodes = [
        dict(id='2', parents=['1'], name='a'),
        dict(id='3', parents=['1'], name='a'),
        dict(id='4', parents=['2'], name='b'),
        dict(id='5', parents=['2'], name='b'),
    ]
    tree = dtree.DTree(nodes)
    assert tree(0)['children'] == {'': '1'}
    assert tree('1')['children'] == dict(a='2')
    assert tree('1')['clash'] == dict(a=['2', '3'])
    assert tree('2')['children'] == dict(b='4')
    assert tree('2')['clash'] == dict(b=['4', '5'])

    tree._remove_child(tree('1'), tree('2'))

    assert tree(0)['children'] == {'': '1'}
    assert tree('1')['children'] == dict(a='3')
    assert not tree('1').get('clash')
    assert tree('2')['children'] == dict(b='4')
    assert tree('2')['clash'] == dict(b=['4', '5'])

    tree._remove_child(tree('2'), tree('5'))

    assert tree(0)['children'] == {'': '1'}
    assert tree('1')['children'] == dict(a='3')
    assert not tree('1').get('clash')
    assert tree('2')['children'] == dict(b='4')
    assert not tree('2')['clash']

def test_linkloop():
    nodes = [
        dict(id='2', parents=['1'], name='a', target='3'),
        dict(id='3', parents=['1'], name='b', target='2'),
        dict(id='4', parents=['1'], name='c', target='2'),
    ]
    tree = dtree.DTree(nodes)
    assert tree['/a']['target'] == '3'
    assert tree['/a']['id'] == '2'
    assert tree['/b']['target'] == '2'
    assert tree['/b']['id'] == '3'
    assert tree['/b']['target'] == '2'
    assert tree['/c']['id'] == '4'

    assert not tree.isdir('/a')
    assert not tree.isdir('/b')
    assert not tree.isdir('/c')

    assert tree.link_target('/a', full=False) == '3'
    assert tree.link_target('/b', full=False) == '2'
    assert tree.link_target('/c', full=False) == '2'

    assert tree.link_target('/a', full=True) == '2'
    assert tree.link_target('/b', full=True) == '3'
    assert tree.link_target('/c', full=True) == '2'


def test_tmpnodes():
    nodes = [dict(id='2', name='something')]
    tree = dtree.DTree()
    assert len(tree.unneeded()) == 0
    result, made = tree.makedirs('/a/b')
    print(tree.lut)
    tree['/']
    tree['/a']
    tree['/a/b']



# tree = dtree.DTree()
# assert tree['/'] is tree.root
# assert tree['//'] is tree.root['children']['']
# assert list(name for name, info in tree.walk('/')) == []
# assert list(name for name, info in tree.walk()) == []

# assert tree.get('/a/b') is None
# assert tree.makedirs('/a/b') == (tree.dirnode('b'), norm(['/a', '/a/b']))
# # /
# #   a/
# #     b/

# assert tree.isdir('/a/b')
# assert tree.isdir('/a')
# assert tree.isdir('/a/')
# assert tree.isdir('/')

# assert tree.isdir('a')
# assert tree.isdir('a/b')

# assert tree.makedirs('/a/b/c') == (tree.dirnode('c'), norm(['/a/b/c/']))
# tree.cd('a/b/')
# assert tree.makedirs('/a/b/d') == (tree.dirnode('d'), norm(['/a/b/d/']))

# # /
# #   a/
# #*    b/
# #       c/
# #       d/

# assert not tree.isdir(tree.touch('x'))
# assert not tree.isdir(tree.touch('../y'))
# assert not tree.isdir(tree.touch('z'))

# # /
# #   a/
# #*    b/
# #       c/
# #       d/
# #       x
# #       z
# #     y

# assert tree.cwd == norm('/a/b')
# assert tree.normpath('../y') == '/a/y'

# assert set([_['name'] for _ in tree.ls()]) == set('cdxz')
# assert set([_['name'] for _ in tree.ls('..')]) == set('by')

# tree.update(dict(children={k:dict(name=k) for k in 'efg'}), '.')
# # /
# #   a/
# #*    b/
# #       c/
# #       d/
# #       x
# #       z
# #       e
# #       f
# #       g
# #     y
# assert set(tree['.']['children']) == set('cdxzefg')
# assert not tree.isdir('e')
# assert not tree.isdir('f')
# assert not tree.isdir('g')

# assert [name for name, node in tree.walk('/')] == [
#     '/a/',
#     '/a/b/',
#     '/a/b/c/',
#     '/a/b/d/',
#     '/a/b/e',
#     '/a/b/f',
#     '/a/b/g',
#     '/a/b/x',
#     '/a/b/z',
#     '/a/y',
# ]

# assert [name for name, node in tree.walk()] == [
#     '/a/b/c/',
#     '/a/b/d/',
#     '/a/b/e',
#     '/a/b/f',
#     '/a/b/g',
#     '/a/b/x',
#     '/a/b/z',
# ]

# tree.touch('//shareditem')
# tree.makedirs('//sharedir/item')
# assert [name for name, node in tree.walk('/')] == [
#     '//sharedir/',
#     '//sharedir/item/',
#     '//shareditem',
#     '/a/',
#     '/a/b/',
#     '/a/b/c/',
#     '/a/b/d/',
#     '/a/b/e',
#     '/a/b/f',
#     '/a/b/g',
#     '/a/b/x',
#     '/a/b/z',
#     '/a/y',
# ]

if __name__ == '__main__':
    from pydrive.util import test
    test.run(globals())
