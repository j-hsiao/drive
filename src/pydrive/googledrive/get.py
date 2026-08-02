"""Get data.

"""
import os
from urllib import parse as urlparse
from pydrive.util.response import Response

from .googledrive import api, Command

from .urls import FILE_URL

@api
class LS(Command):
    def __init__(self):
        self.parser = p = self.get_parser()
        p.add_argument('name', help='target to ls', nargs='?', default='.')
        p.add_argument('-c', '--corpora', default='user', choices=('user', 'domain', 'drive', 'allDrives'))
        p.add_argument('--all', action='store_true', help='include items from all drives')
        p.add_argument('-t', '--trash', action='store_true', help='include trashed items')
        p.add_argument('--fields', default='id,name,mimeType')
        p.add_argument('-v', '--verbose', action='store_true')
        p.add_argument('-l', '--longform', action='store_true', help='prints extra fields for the file.')
        p.add_argument('-f', '--force', action='store_true', help='force an api call instead of using cached data.')
        p.add_argument(
            '-o', '--order', nargs='*', default=['folder', 'name'],
            choices=(
                'createdTime', 'folder', 'modifiedByMeTime', 'modifiedTime',
                'name', 'name_natural', 'quotaBytesUsed', 'recency',
                'sharedWithMeTime', 'starred', 'viewedByMeTime', 'desc'
            ),
            help='List of items to order by'
        )
        api.add_extra(p)

    @staticmethod
    def parse_order(order):
        items = []
        for item in order:
            if item == 'desc':
                item[-1] = item[-1] + ' desc'
            else:
                items.append(item)
        return ','.join(items)

    def _get(self, args, query, pageToken=None):
        if pageToken:
            query = query + [('nextPageToken', pageToken)]
        if args.verbose:
            for k,v in query:
                print(k, v)
        url = '?'.join([FILE_URL, urlparse.urlencode(query)])
        if args.verbose:
            print('GET', url)
        response = self.session(args).get(
            url, headers=args.auth({}, url, htm='get')
        )
        args.auth(response)
        return response


    def _get_api(self, nodeid, args):
        if not args.auth:
            print('Not logged in.')
            return False
        qstr = ["'{}' in parents".format(nodeid.replace("'", r'\'').replace('\\', r'\\'))]
        if not args.trash:
            qstr.append('trashed = false')

        query = [
            ('corpora', args.corpora),
            ('q', ' and '.join(qstr)),
            ('fields', 'files({}),nextPageToken,kind,incompleteSearch'.format(args.fields)),
            ('orderBy', self.parse_order(args.order)),
        ]
        if args.all:
            query.append(('includeItemsFromAllDrives', 'true'))

        nextpage = None
        files = []
        while 1:
            response = self._get(args, query, nextpage)
            if args.verbose:
                print(Response(response))
            if 200 <= response.status_code < 300:
                result = response.json()
                files.extend(result['files'])
                if result.get('kind', 'drive#fileList') != 'drive#fileList':
                    print('WARNING: response "kind" is unexpected:', result['kind'])
                nextpage = result.get('nextPageToken', None)
                if not result['incompleteSearch'] or nextpage is None:
                    for f in files:
                        name = f.get('name', 'unkown')
                        if f.get('mimeType', '') == 'application/vnd.google-apps.folder':
                            name = '\x1b[0m\x1b01;34m{}\x1b[0m/'.format(name)
                        print(name)
                        if args.longform:
                            fmt = '    {{:{}}}: {{}}'.format(max(map(len, f)))
                            for k, v in f.items():
                                if k != 'name':
                                    print(fmt.format(k, v))
                    return True
            else:
                if not args.verbose:
                    print(Response(response))
                print(response.headers)
                return False

    def display_node(self, node):
        pass


    def __call__(self, args):
        if not args.force:
            node = args.dtree.get(args.name)
            if node is not None:
                self.display_node(node)
                return True
        name = os.sep
        for item in args.dtree.normpath(args.name).split(os.sep):
