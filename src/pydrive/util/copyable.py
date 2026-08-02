class Copyable(object):
    def __init__(self, *args, **kwargs):
        if args and isinstance(args[0], type(self)):
            self._copy_instance(*args, **kwargs)
        else:
            self._init(*args, **kwargs)
    def _init(self, *args, **kwargs):
        super(Copyable, self).__init__(*args, **kwargs)
    def _copy_instance(self, *args, **kwargs):
        raise NotImplementedError
