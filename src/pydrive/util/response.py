import json

def jformat(response):
    decode = response.content.decode('utf-8', errors='replace')
    try:
        asjson = json.loads(decode)
    except ValueError:
        return decode
    else:
        return json.dumps(asjson, indent=4)


class Response(object):
    """Wrap a response with a new __str__ method."""
    def __init__(self, response):
        self.__response = response

    def __getattr__(self, name):
        return getattr(self.__response, name)

    def __str__(self):
        return ': '.join([str(self.__response), jformat(self.__response)])
