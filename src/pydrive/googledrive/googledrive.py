import argparse
import os

import requests

from pydrive.util.command import Commands, Command as _Command
from pydrive.util.auth import Auth as Auth_
from pydrive.util import jutil
from pydrive.util.dsearch import DSearch
from pydrive.util.dtree import DTree as DTree_

dsearch = DSearch(
    [
        '~/.config/pydrive/googledrive',
        '~/.googledrive',
        '~',
    ]
)

class AppInfo(jutil.JFile):
    initfuncs = ['_init_none'] + jutil.JFile.initfuncs

    def _init_none(self, appjson=None, data=None):
        if appjson is None:
            appjson = dsearch('*app*.json', first=True)
            if appjson is None:
                raise ValueError('No app info found.')
        self._init(appjson, data)
        if not self:
            raise ValueError('No app info.')
        return True

class Auth(Auth_):
    initfuncs = ['_init_None'] + Auth_.initfuncs
    def _init_None(self, f, *args, **kwargs):
        if f is None:
            return self._init(
                dsearch('*auth*.json', first=True),
                *args, **kwargs)
        return False

class DTree(DTree_):
    initfuncs = ['_init_None'] + DTree_.initfuncs
    def _init_None(self, initial=None, *args, **kwargs):
        if initial is None:
            return self._init(
                dsearch('*dtree*.json', first=True),
                *args, **kwargs)
        return False


api = Commands(['auth', 'app', 'dtree'])
api.add_argument('-a', '--auth', type=Auth, help='saved auth file', nargs='?')
api.add_argument(
    '--app', type=AppInfo, default={},
    help='registered app jsonfile', nargs='?')
api.add_argument(
    '--dtree', help='',
    default=DTree(),
    type=DTree,
)

class Command(_Command):
    @staticmethod
    def session(args):
        return getattr(args, 'session', requests)


def interruptdir():
    candidates = []
    if os.environ.get('GOOGLEDRIVE_INTERRUPTED', None):
        candidates.append(os.environ.get['GOOGLEDRIVE_INTERRUPTED'])
    if os.environ.get('HOME', None):
        candidates.append(os.path.join(os.environ['HOME'], '.googledrive_interrupted'))
    candidates.append('.googledrive_interrupted')
    for candidate in candidates:
        if os.path.isdir(candidate):
            return candidate
    try:
        os.makedirs(candidates[0])
    except Exception:
        print(candidates)
        traceback.print_exc()
        return '.'
    else:
        return candidates[0]
