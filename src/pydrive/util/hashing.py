import base64
import hashlib
import codecs

def byteslike(data):
    if isinstance(data, str):
        return data.encode('utf-8')
    return data
def strlike(data, encoding='utf-8'):
    if isinstance(data, str):
        return data
    return codecs.decode(data, encoding, errors='replace')

def hexdecode(data):
    return base64.b16decode(byteslike(data), True)
def hexencode(data):
    return base64.b16encode(byteslike(data))

def b64encode(data, decode=None):
    """Urlsafe unpadded base 64 encoding.

    data: str or byteslike
    Return bytes
    """
    ret = base64.urlsafe_b64encode(byteslike(data)).rstrip(b'=')
    if decode:
        return ret.decode(decode, errors='replace')
    return ret

def b64decode(data, decode=None):
    """Urlsafe base64 decoding.

    data: str or byteslike
    return bytes
    """
    data = byteslike(data)
    rem = len(data) % 4
    extra = 4-rem
    if extra:
        b = bytearray(len(data) + extra)
        b[:len(data)] = data
        b[len(data):] = b'===='[:extra]
    else:
        b = data
    ret = base64.urlsafe_b64decode(b)
    if decode:
        return ret.decode(decode, errors='replace')
    return ret

def sha256(data):
    ret = hashlib.sha256(byteslike(data)).digest()
    return ret

def b64sha256(data, decode=None):
    return b64encode(sha256(data), decode=decode)
