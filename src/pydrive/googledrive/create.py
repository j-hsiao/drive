"""Various file creation methods.

docs seem a bit messy...
https://developers.google.com/workspace/drive/api/guides/manage-uploads
https://developers.google.com/workspace/drive/api/reference/rest/v3/files/create
https://developers.google.com/workspace/drive/api/guides/folder

Verified, having filename as path/to/name does NOT put name under that path
but instead just creates a file with name containing slashes...

TODO:
    making a file under a folder
    can i just use path/to/file/destination
    or do i have to walk through get some folder id, then use that?
"""
import contextlib
import io
import json
import mimetypes
import os
import uuid
import traceback


from .googledrive import api, Command, interruptdir
from pydrive.util.response import Response
from pydrive.util import jutil
from .urls import FILE_URL, UPLOAD_URL

SHORTCUT = 'application/vnd.google-apps.shortcut'
FOLDER = 'application/vnd.google-apps.folder'

def metadata(name, mime=None, **kwargs):
    """Guess the file metadata.

    Useful metadata:
        name,
        mimeType,
        parents,
    """
    kwargs['name'] = name
    if mime:
        kwargs['mimeType'] = mime
    return kwargs


@api
class Touch(Command):
    def __init__(self):
        self.parser = p = self.get_parser()
        api.add_extra(p)
        p.add_argument('name', help='name of file to create.')
        p.add_argument('-m', '--mime', help='mime type to use.')

    def __call__(self, args):
        if not args.auth:
            print('Not logged in')
            return False
        response = self.session(args).post(
            FILE_URL, headers=args.auth({}, FILE_URL),
            json=metadata(args.name, args.mime)
        )
        args.auth(response)
        print(Response(response))
        return 200 <= response.status_code < 300

@api
class MkDir(Command):
    def __init__(self):
        self.parser = p = self.get_parser()
        api.add_extra(p)
        p.add_argument('dname', help='name of dir to name', nargs='+')
        p.add_argument('-p', help='make intermediate parent directories too.')

    def __call__(self, args):
        if not args.auth:
            print('Not logged in')
            return False
        response = self.session(args).post(
            FILE_URL, headers=args.auth({}, FILE_URL),
            json=metadata(args.name, 'application/vnd.google-apps.folder')
        )
        args.auth(response)
        print(Response(response))
        return 200 <= response.status_code < 300

@api
class Upload(Command):
    def __init__(self):
        self.parser = p = self.get_parser()
        api.add_extra(p)
        p.add_argument('name', help='name of file to upload.')
        p.add_argument('out', help='target output name, default to basename of `name`', nargs='?')
        p.add_argument('-m', '--mime', help='mime type to use.')
        p.add_argument('-s', '--simple', action='store_true', help='simple upload with metadata')
        p.add_argument('--uri', help='the resumable uri.')
        # Apparently most servers do not support request compression
        # because could do a gzip bomb or something??
        # self.parser.add_argument('-c', '--compression', type=int, help='compression level', default=0)

    def __call__(self, args):
        if not args.auth:
            print('Not logged in')
            return False
        if not args.out:
            args.out = os.path.basename(args.name)
        if not args.mime:
            args.mime, encoding = mimetypes.guess_type(args.name)
        if args.simple:
            return self.multi(args)
        else:
            return self.resumeable(args)

    def multi(self, args):
        """Upload with multipart (metadata + contents)."""
        with open(args.name, 'rb') as f:
            url = UPLOAD_URL + '?uploadType=multipart'
            response = self.session(args).post(
                url, headers=args.auth({}, url),
                files=(
                    ('Metadata', ('mtadata.json', metadata(args.out, args.mime), 'application/json')),
                    ('Media', (args.out, f, args.mime)),
                ),
            )
        args.auth(response)
        print(Response(response))
        return 200 <= response.status_code < 300

    def resumeable(self, args):
        """Resumeable upload."""
        with open(args.name, 'rb') as ifile:
            try:
                fstats = os.stat(ifile.fileno())
                size = fstats.st_size
                inode = fstats.st_ino
            except Exception:
                size = None
                inode = None
            resumeinfo = None
            if not args.uri:
                headers = {'X-Upload-Content-Length': str(size)}
                if args.mime:
                    headers['X-Upload-Content-Type'] = args.mime
                finfo = dict(name=args.name, dst=args.out, mime=args.mime, size=size, inode=inode)
                jdir = jutil.JDir(interruptdir())
                resumeinfo = jdir.find(finfo, 'upload_')
                if resumeinfo is None:
                    url = UPLOAD_URL + '?uploadType=resumable',
                    response = self.session(args).post(
                        url, headers=args.auth(headers, url),
                        json=metadata(args.out, args.mime),
                    )
                    args.auth(response)
                    if not (200 <= response.status_code < 300):
                        print(Response(response))
                        return False
                    args.uri = response.headers['Location']
                    print('Resumable uri:', args.uri)

                    response = self.session(args).put(args.uri, data=ifile)
                    print(Response(response))
                    if 200 <= response.status_code < 300:
                        return True
                    else:
                        try:
                            jdir.get('upload_', rand=True).update(finfo).save(indent=4)
                        except Exception:
                            traceback.print_exc()
                        return False
                else:
                    args.uri = resumeinfo['uri']
            # check status
            response = self.session(args).put(
                args.uri,
                headers=args.auth(
                    {'Content-Range': '*/{}'.format('*' if size is None else size)},
                    args.uri, htm='put'),
            )
            args.auth(response)
            print(Response(response))
            if 200 <= response.status_code < 300:
                if resumeinfo is not None:
                    resumeinfo.remove()
                return True
            if 400 <= response.status_code < 500:
                if resumeinfo is not None:
                    resumeinfo.remove()
                print('Cannot resume upload of', args.name)
                return False
            if response.status_code != 308:
                print('Unhandled response')
                return False
            rng = response.headers.get('range', None)
            if rng is None:
                start = 0
            else:
                unit, ranges = rng.split('=', 1)
                parts = ranges.split(',')
                if len(parts) > 1:
                    print('multiple ranges not implemented', rng)
                    return False
                start, stop = parts[0].split('-')
                if start.strip():
                    start = int(start)
                else:
                    start = 0
                if stop.strip():
                    stop = int(stop)
                else:
                    stop = size
                print('resuming from:', start, stop)
                if start != 0:
                    print('WARNING: progress does not start at 0...')
                start = stop+1
            ifile.seek(start)
            response = self.session(args).put(
                args.uri, data=ifile,
                headers=args.auth({
                    'Content-Range': '{}-{}'.format(start, '' if size is None else size-1)
                }, args.uri, htm='put'),
            )
            args.auth(response)
            print(Response(response))
            return 200 <= response.status_code < 300
