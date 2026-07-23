import json
import os
from urllib import parse as urlparse

from pydrive.util.response import Response
from pydrive.util.auth import Auth
from .googledrive import api, Command


@api
class Logout(Command):
    def __init__(self):
        self.parser = p = self.get_parser()
        p.add_argument('auth', nargs='?', help='auth json or access token.', type=Auth)

    def __call__(self, args):
        auth = args.auth
        if not auth:
            print('Not logged in.')
            return True
        response = self.session(args).post(
            'https://oauth2.googleapis.com/revoke?'
            + urlparse.urlencode([('token', auth['access_token'])]))
        print(Response(response))
        auth.revoked()
        return 200 <= response.status_code < 300
