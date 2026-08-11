import logging
lg = logging.getLogger(__name__)

class ListInit(object):
    """Class with list of functions to run for initialization.

    Each function returns whether initialization is copmlete.
    Functions are stored in initfuncs
    """
    initfuncs = [
        '_init_selftype',
        '_init',
    ]

    def __init__(self, *args, **kwargs):
        for item in self.initfuncs:
            try:
                if getattr(self, item)(*args, **kwargs):
                    return
            except Exception:
                lg.exception('Error during ListInit initialization.')
        else:
            raise ValueError('ListInit failed to init from {}, {}'.format(args, kwargs))

    def _init_selftype(self, other, *args, **kwargs):
        if isinstance(other, type(self)):
            self.copy_instance(other, *args, **kwargs)
            return True
        return False

    def _init(self, *args, **kwargs):
        super(ListInit, self).__init__(*args, **kwargs)
        return True
    def copy_instance(self, *args, **kwargs):
        raise NotImplementedError
