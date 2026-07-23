import base64
import uuid
import hashlib

class PKCE(object):
    """Generate PKCE challenge and verifier."""
    def __init__(self, method='S256'):
        if isinstance(method, bool):
            method = 'S256'
        self.code_challenge_method = method
        if method is None:
            return
        verifier = base64.urlsafe_b64encode(uuid.uuid4().hex.encode()).rstrip(b'=')
        self.code_verifier = verifier.decode()
        if method == 'S256':
            self.code_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(verifier).digest()).rstrip(b'=').decode()
        elif method == 'plain':
            self.code_challenge = self.code_verifier
        else:
            raise ValueError('Invalid PKCE method {}'.format(method))


    def challenge(self, item):
        """Add `code_challenge` and `code_challenge_method` to `item`.

        item: dict or list of pairs.
        """
        if self.code_challenge_method is None:
            return
        if isinstance(item, dict):
            item['code_challenge'] = self.code_challenge
            item['code_challenge_method'] = self.code_challenge_method
        elif isinstance(item, list):
            item.extend([
                ('code_challenge', self.code_challenge),
                ('code_challenge_method', self.code_challenge_method),
            ])
        else:
            raise ValueError('Can only add challenge to dict or list.')

    def verify(self, item):
        """Add `code_verifier` to `item`.

        item: dict or list of pairs.
        """
        if self.code_challenge_method is None:
            return
        if isinstance(item, dict):
            item['code_verifier'] = self.code_verifier
        elif isinstance(item, list):
            item.extend([
                ('code_verifier', self.code_verifier),
            ])
        else:
            raise ValueError('Can only add challenge to dict or list.')

