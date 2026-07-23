import jwt
import json

def verify(tok):
    header = jwt.get_unverified_header(tok)
    print('header')
    print(json.dumps(header, indent=4))
    alg = jwt.algorithms.get_default_algorithms()[header['alg']]
    key = alg.from_jwk(header['jwk'])
    print(key)

    decoded = jwt.decode(tok, key, algorithms=[header['alg']])
    print(json.dumps(decoded, indent=4))
