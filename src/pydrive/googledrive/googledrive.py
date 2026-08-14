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
        '.',
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
    def _init_None(self, f=None, *args, **kwargs):
        if f is None:
            return self._init(
                dsearch('*auth*.json', first=True),
                *args, **kwargs)
        return False

    class Scope(object):
        BASE = 'https://www.googleapis.com/auth/'
        def __init__(self, scope):
            self.scope = getattr(scope, 'scope', None)
            if self.scope is None:
                if not scope.startswith(self.BASE):
                    scope = self.BASE + scope
                self.scope = scope

        def __str__(self):
            return self.scope

        def __repr__(self):
            return self.scope[len(self.BASE):]

        def __eq__(self, other):
            if isinstance(other, Scope):
                return self.scope == other.scope
            elif isinstance(other, str):
                return other == self.scope or other == repr(self)
            else:
                return False

        @classmethod
        def join(cls, scopes):
            return ' '.join([str(cls(scope)) for scope in scopes])
    SCOPES = [
        'drive',
        'drive.readonly',
        'drive.metadata',
        'drive.metadata.readonly',
        'drive.file',
        'drive.appdata',
        'drive.apps.readonly',
        'drive.meet.readonly',
        'drive.photos.readonly',
        'drive.scripts',
    ]


class DTree(DTree_):
    initfuncs = ['_init_None'] + DTree_.initfuncs
    def _init_None(self, initial=None, *args, **kwargs):
        if initial is None:
            return self._init(
                dsearch('*dtree*.json', first=True),
                *args, **kwargs)
        return False


api = Commands(['auth', 'app', 'dtree'])
api.add_argument(
    '--auth', type=Auth, nargs='?',
    help='Saved auth file. Omit arg to search for default.', init=True)
api.add_argument(
    '--app', type=AppInfo, nargs='?', init=True,
    help='Registered app file.  Omit arg to search for default.')
api.add_argument(
    '--dtree', type=DTree, nargs='?', init=True,
    help='Saved dtree file. Omit arg to search for default.')

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
