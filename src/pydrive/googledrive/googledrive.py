import argparse
import os

import requests

from pydrive.util.command import Commands, Command as _Command
from pydrive.util.auth import Auth
from pydrive.util import jutil


api = Commands(['auth', 'app'])
api.add_argument('-a', '--auth', type=Auth, help='saved auth file', nargs='?')
api.add_argument('--app', type=jutil.JFile, help='registered app jsonfile', nargs='?')

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
