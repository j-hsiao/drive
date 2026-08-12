"""Google oauth2 access tokens."""
import argparse
import contextlib
import functools
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import platform
import selectors
import sys
from urllib import parse as urlparse
import uuid
import webbrowser
import tkinter as tk

from pydrive.util.auth import Auth, DPoP
from pydrive.util import command
from pydrive.util.pkce import PKCE
from pydrive.util import winsockstdin
from pydrive.util.response import Response
from pydrive.util import webbrowserpatch
from .googledrive import api, Command

from .urls import TOKEN_URL, AUTH_URL


class LocalAuthServer(HTTPServer):
    class HandlerClass(BaseHTTPRequestHandler):
        def __init__(self, q, *args, **kwargs):
            self.__q = q
            super(LocalAuthServer.HandlerClass, self).__init__(*args, **kwargs)

        def do_GET(self):
            path = urlparse.urlsplit(self.path)
            qs = urlparse.parse_qsl(path.query)
            self.__q.append(path.query)
            for name, val in qs:
                if name == 'code':
                    self.send_response(200)
                    self.send_header('Connection', 'close')
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'Authorization Successful! You can close this tab.')
                    return
                elif name == 'error':
                    self.send_error(401, None, 'authorization failed: {}'.format(path.query))
                    return
            self.send_error(400, None, 'no recognized querystrings: {}'.format(self.path))
    def __init__(self, address=('localhost', 0)):
        self.__queryq = []
        super(LocalAuthServer, self).__init__(address, functools.partial(self.HandlerClass, self.__queryq))

    def port(self):
        return self.socket.getsockname()[1]

    def qs(self):
        try:
            return self.__queryq[0]
        except IndexError:
            return ''

@api
class Login(Command):
    def __init__(self):
        self.parser = p = self.get_parser()
        p.add_argument('-o', '--offline', action='store_true')
        p.add_argument('-r', '--refresh', action='store_true')
        p.add_argument('-v', '--verbose', action='store_true')
        p.add_argument('--no-gui', action='store_false', dest='gui')
        p.add_argument('-d', '--dpop', help='use dpop', nargs='*')
        p.add_argument(
            '-s', '--scopes', nargs='*', choices=Auth.SCOPES,
            default=['drive.file', 'drive.metadata.readonly'],
            help='required scope(s)')
        p.add_argument(
            '--no-incremental', dest='incremental', action='store_false',
            help='Do not include previously granted scopes.')
        api.add_arguments(p)

    def _get_qs(self, appdata, query, verbose, gui):
        with contextlib.ExitStack() as stack:
            server = stack.enter_context(LocalAuthServer())
            query['redirect_uri'] = 'http://localhost:{}'.format(server.port())
            url = '?'.join([
                appdata.get('auth_uri', AUTH_URL),
                urlparse.urlencode(query)])
            print('If browser fails, copy url, authorize, and paste redirected url:')
            print(url)
            print('redirected url: ', end='', flush=True)
            if gui:
                r = tk.Tk()
                r.call('clipboard', 'clear')
                r.call('clipboard', 'append', url)
                button = tk.Button(r, text='Copy login url.', command='clipboard clear; clipboard append {{{}}}'.format(url))
                button.grid(row=0, column=0)
                r.update()
                r.iconify()
                stack.callback(r.destroy)
                webbrowser.open(url)
            sel = stack.enter_context(selectors.DefaultSelector())
            sel.register(server, selectors.EVENT_READ)
            stack.callback(sel.unregister, server)
            sel.register(sys.stdin, selectors.EVENT_READ)
            stack.callback(sel.unregister, sys.stdin)
            while 1:
                if gui:
                    r.update()
                for key, mask in sel.select(.1):
                    if verbose:
                        print('selected!:', key, key.fileobj)
                    if key.fileobj is server:
                        server.handle_request()
                        if verbose:
                            print('query string from localhost:', server.qs())
                        return server.qs()
                    else:
                        if verbose:
                            print('reading a line...')
                        inp = sys.stdin.readline().rstrip()
                        if verbose:
                            print('Got stdin response:', inp)
                        result = urlparse.urlsplit(inp).query
                        if verbose:
                            print('result from stdin', result)
                        return result

    def __call__(self, args):
        if args.auth and not args.refresh:
            print('Already logged in.')
            return True
        if not args.app:
            print('App info missing.')
            return False

        pkce = PKCE()
        for apptype, settings in args.app.items():
            print('application type:', apptype)
            req = [
                ('client_id', settings['client_id']),
                ('client_secret', settings['client_secret']),
            ]
            if args.refresh:
                req.append(('grant_type', 'refresh_token'))
                req.append(('refresh_token', args.auth['refresh_token']))
            else:
                q = {
                    'client_id': settings['client_id'],
                    'response_type': 'code',
                    'scope': Auth.Scope.join(args.scopes),
                    'state': uuid.uuid4().hex,
                }
                if args.incremental:
                    q['include_granted_scopes'] = 'true'
                pkce.challenge(q)
                if args.offline:
                    req.append(('access_type', 'offline'))
                rawqs = self._get_qs(settings, q, args.verbose, args.gui)
                req.extend([
                    ('grant_type', 'authorization_code'),
                    ('redirect_uri', q['redirect_uri']),
                ])
                if not rawqs:
                    print('No query string detected.')
                    return False
                pkce.verify(req)
                for name, val in urlparse.parse_qsl(rawqs):
                    if name == 'code':
                        req.append((name, val))
                    elif name == 'state':
                        if val != q['state']:
                            print('State does not match!')
                            print('  original:', q['state'])
                            print('  current :', val)
                            return False
                if req[-1][0] != 'code':
                    print('authorization code not found.')
                    return False
            headers = {}
            # TODO: I still can't seem to get this dpop thing to work.
            # Even if I use a library to create the dpop jwt, it still fails.
            dpop = None
            token_url = settings.get('token_uri', TOKEN_URL)
            if args.dpop is not None:
                dpop = DPoP(private=(args.dpop[0] if args.dpop else None))
                dpop(headers, token_url, auth=req[-1][1])
                if args.verbose:
                    print('dpop public key:', dpop.public())
            if args.verbose:
                print('target url:', token_url)
                print('body', req)
                print('headers', headers)
            response = self.session(args).post(
                token_url, data=req, headers=headers)
            if 200 <= response.status_code < 300:
                if args.verbose:
                    print(Response(response))
                else:
                    try:
                        j = response.json()
                        if 'access_token' in j:
                            j['access_token'] = '***'
                        if 'refresh_token' in j:
                            j['refresh_token'] = '***'
                        print(response, ':', json.dumps(j, indent=4))
                    except Exception:
                        print(response, 'expected json but got...', response.content)
                args.auth = Auth(response.json(), dpop)
                args.auth.update(response)
                return True
            print(Response(response))
            print(response.headers)
            return False
