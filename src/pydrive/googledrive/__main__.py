import argparse

import requests

from .googledrive import api
from . import (
    login,
    logout,
    create,
)


if __name__ == '__main__':
    api(session=requests.Session()).main(__package__, __file__)
