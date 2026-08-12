import contextlib
import hashlib
import json
import os
import subprocess as sp
import time
import traceback
import uuid
from urllib import parse as urlparse

from .hashing import b64encode, byteslike, strlike, b64sha256, hexdecode

from . import jutil
from . import listinit



class Auth(listinit.ListInit):
    def copy_instance(self, other, dpop=None):
        return self._init(other.data, dpop)

    def _init(self, f=None, dpop=None):
        self.dpop = dpop
        if isinstance(f, str):
            if os.path.exists(f):
                with open(f, 'r') as f:
                    self.data = json.load(f)
            else:
                try:
                    self.data = json.loads(f)
                except ValueError:
                    if f:
                        self.data = {'access_token': f}
                    else:
                        self.data = {}
        elif hasattr(f, 'read'):
            self.data = json.load(f)
        elif isinstance(f, Auth):
            self.data = f.data.copy()
        elif isinstance(f, dict):
            self.data = f.copy()
        elif f is None:
            self.data = {}
        else:
            raise ValueError('Bad value for Auth(): {}'.format(f))

        if self.dpop is None and 'DPoP' in self.data:
            self.dpop = DPoP(byteslike(self.data['DPoP']))

        try:
            # https://developers.google.com/identity/protocols/oauth2/web-server#exchange-authorization-code
            # "The type of token returned. This value is always Bearer, even when DPoP is used."
            self.auth = ' '.join([
                ('Bearer' if self.dpop is None else 'DPoP'),
                self.data['access_token'],
            ])
            if self.dpop:
                self.data['DPoP'] = strlike(self.dpop.private())
        except Exception:
            if self.data:
                traceback.print_exc()
            self.auth = ''
            self.dpop = None

        if self.data.get('expired') is None and self.data.get('expires_in', None) is not None:
            self.data['expired'] = time.time() + self.data.get('expires_in')
        return True

    def save(self, out):
        jutil.save(self.data, out)

    def __contains__(self, scope):
        return str(self.Scope(scope)) in self.data.get('scope', '')

    def update(self, info):
        """Update based on responses."""
        if self.dpop is not None:
            self.dpop.update(info)

    def revoked(self):
        self.auth = ''

    def __getitem__(self, k):
        return self.data[k]
    def get(self, k, default=None):
        return self.data.get(k, default)

    def __bool__(self):
        if self.data.get('expired'):
            if self.data['expired'] < time.time():
                return False
        return bool(self.auth)

    def __call__(self, headers, *args, **kwargs):
        """Add `Authorization` header or update from a response.

        Input is assumed to be a response if it has a "headers" attr.
        """
        if hasattr(headers, 'headers'):
            self.update(headers, *args, **kwargs)
        else:
            if self.auth:
                headers['Authorization'] = self.auth
                if self.dpop is not None:
                    self.dpop(headers, *args, **kwargs)
        return headers

    def __str__(self):
        return self.auth

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

class DPoP(object):
    __PRIVATE_COMMAND = [
        'openssl', 'ecparam', '-name', 'prime256v1', '-genkey', '-noout']
    __PUBLIC_COMMAND = ['openssl', 'ec', '-pubout']
    __COORD_COMMAND = ['openssl', 'ec', '-pubout', '-text', '-noout']
    __SIGN_COMMAND = ['openssl', 'dgst', '-sha256', '-binary', '-sign']

    def public(self):
        """Reteurn the public key."""
        if self._public is None:
            proc = sp.Popen(self.__PUBLIC_COMMAND, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
            self._public, err = proc.communicate(self._private)
            if proc.returncode:
                raise RuntimeError('Failed to calculate public key: {}'.format(strlike(err)))
        return self._public
    def private(self):
        """Reteurn the private key."""
        return self._private

    def __init__(self, private=None, auth=None):
        self._public = None
        if private is None:
            proc = sp.Popen(self.__PRIVATE_COMMAND, stdout=sp.PIPE, stderr=sp.PIPE)
            self._private, err = proc.communicate()
            if proc.returncode:
                raise RuntimeError('Failed to generate DPoP key: {}'.format(strlike(err)))
        else:
            if isinstance(private, str):
                with open(private, 'rb') as f:
                    self._private = f.read()
            else:
                self._private = private

        self._jwk = None
        self.__nonce = None
        self.__auth = auth

    def xy(self):
        """Return the x and y values as base64."""
        proc = sp.Popen(self.__COORD_COMMAND, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
        data, err = proc.communicate(self._private)
        if proc.returncode:
            raise ValueError('Failed to extract x and y from key: {}'.format(strlike(err)))
        hexnums = data.split(b'\npub:', 1)[-1].split(b'\nASN1 OID:', 1)[0]
        hexnums = hexnums.translate(bytes.maketrans(b'', b''), delete=b': \r\n\t')
        buf = hexdecode(hexnums)
        # https://stackoverflow.com/questions/29583211/get-x-and-y-components-from-ecc-public-key-in-pem-format-using-openssl
        # the first byte == 0x04 "indicates uncompressed form"
        #
        # https://www.rfc-editor.org/info/rfc5480/#section-2.2
        # uncompressed: 0x04
        # compressed: 0x02 or 0x03
        if buf[0] != 4:
            raise ValueError('Key x,y values are not in uncompressed format.')
        assert len(buf) == 65
        return b64encode(buf[1:33], 'utf-8'), b64encode(buf[-32:], 'utf-8')

    def jwk(self):
        """Return the jwk dict."""
        if self._jwk is None:
            x, y = self.xy()
            self._jwk = {
                'crv': 'P-256',
                'kty': 'EC',
                'x': x,
                'y': y,
            }
        return self._jwk

    def header(self):
        """Return jwt header"""
        return {
            'alg': 'ES256',
            'jwk': self.jwk(),
            'typ': 'dpop+jwt',
        }

    def jti(self, jti, auth):
        """Return an appropriate jti from jti and auth."""
        if jti is None:
            if auth is None:
                if self.__auth is None:
                    return uuid.uuid4().hex
                auth = self.__auth
                self.__auth = None
            return b64sha256(auth, 'ascii')
        return jti

    def payload(self, htu, jti=None, htm='POST', iat=None, auth=None, nonce=None):
        """Return jwt payload"""
        ret = {
            'jti': self.jti(jti, auth),
            'htm': htm.upper(),
            'htu': urlparse.urlsplit(htu)._replace(query='', fragment='').geturl(),
            'iat': int(time.time()) if iat is None else iat,
        }
        if nonce is not None:
            ret['nonce'] = nonce
        elif self.__nonce is not None:
            ret['nonce'] = self.__nonce
            self.__nonce = None
        return ret

    def __call__(self, headers, htu, **kwargs):
        headers['DPoP'] = self.jwt(htu, **kwargs)
        return headers

    def update(self, info):
        """Update internal state.

        Info can be:

        dictlike: headers
        dictlike info.headers: a response
        str: an auth code.
        """
        if isinstance(info, str):
            self.__auth = info
        else:
            self.__nonce = getattr(info, 'headers', info).get('DPoP-Nonce', None)

    def sign(self, data):
        """Sign a data with openssl utility.  Return signed data."""
        with contextlib.ExitStack() as stack:
            tmpname = uuid.uuid4().hex
            if os.environ.get('XDG_RUNTIME_DIR') is not None:
                tmpname = os.path.join(os.environ['XDG_RUNTIME_DIR'], tmpname)
            with open(tmpname, 'wb') as f:
                stack.callback(os.remove, tmpname)
                f.write(self._private)
            proc = sp.Popen(self.__SIGN_COMMAND + [tmpname], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
            signed, err = proc.communicate(byteslike(data))
            if proc.returncode:
                raise RuntimeError('Failed to sign data: {}'.format(strlike(err)))
            return signed

    def rawsig(self, data):
        """Parse a signature into concatenated R and S ints."""
        proc = sp.Popen(['openssl', 'asn1parse', '-inform', 'DER'], stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE)
        parsed, err = proc.communicate(byteslike(data))
        if proc.returncode:
            raise RuntimeError('Failed to parse signed data: {}'.format(strlike(err)))
        # proc = sp.Popen(['openssl', 'asn1parse', '-inform', 'DER', '-strparse', '2', '-out', '-'], stdin=sp.PIPE, stdout=sp.PIPE)
        # r, ignore = proc.communicate(data)
        # proc = sp.Popen(['openssl', 'asn1parse', '-inform', 'DER', '-strparse', '37', '-out', '-'], stdin=sp.PIPE, stdout=sp.PIPE)
        # s, ignore = proc.communicate(data)

        seq, rline, sline = parsed.splitlines()
        return hexdecode(
            rline.rsplit(b':', 1)[-1].strip()
            + sline.rsplit(b':', 1)[-1].strip())

    def jwt(self, htu, **kwargs):
        """Return a signed JWT as str."""
        header = b64encode(json.dumps(self.header(), separators=(',',':')))
        payload = b64encode(json.dumps(self.payload(htu, **kwargs), separators=(',',':')))
        raw = b'.'.join([header, payload])
        sig = self.rawsig(self.sign(raw))
        return strlike(b'.'.join([raw, b64encode(sig)]))
