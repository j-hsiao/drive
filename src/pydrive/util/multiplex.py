import contextlib
import io
import sys
import textwrap

@contextlib.contextmanager
def _stream_context(self, stream, flush=True):
    """Change stream in this context.

    Also flush after context ends.
    """
    try:
        buf = self.bufs[stream]
    except KeyError:
        buf = self.bufs[stream] = io.StringIO()
    original = self._stream
    try:
        self.buf = buf
        self._stream = stream
        yield self
    finally:
        if flush:
            self.flush()
        self._stream = original
        self.buf = self.bufs[original]

class Multiplexed(object):
    """Multiplexing output to stdout.

    write: "default" stream
    write2: write to 2nd stream.

    Data is prefixed with a small header:
    plain text:
    [0|1] [numbytes]
    bytes

    Using plaintext header is ?more shell friendly?, more easily used with stdout.
    """

    SCRIPTS = {
        'bash': textwrap.dedent('''
            pydrive_read() # fd *stream *out [timeout]
            {
                local length
                local timeout="${4:+-t ${4}}"
                read ${timeout} -u "${1}" -r "${2}" length && LANG=C IFS= read -u "${1}" -r -d '' -N "${length}" "${3}"
            }
            '''),
    }

    def __init__(self, out, encoding=None):
        self.encoding = getattr(out, 'encoding', 'utf-8')
        self.out = getattr(out, 'buffer', out)
        self._stream = 0
        self.bufs = {self._stream: io.StringIO()}
        self.buf = self.bufs[self._stream]

    # so must have a separate one.
    def stream(self, stream, flush=True):
        """Change stream in this context.

        Also flush after context ends.
        """
        return _stream_context(self, stream, flush)

    def write(self, data):
        buf = self.buf
        ret = buf.write(data)
        if data.endswith('\n') or buf.tell() > io.DEFAULT_BUFFER_SIZE:
            self.flush()
        return ret

    def flush(self):
        buf = self.buf
        if not buf.tell():
            return
        stream = self._stream
        data = buf.getvalue()
        buf.truncate(0)
        buf.seek(0)
        encoded = data.encode(self.encoding)
        self.out.write(
            '{} {}\n'.format(str(stream), len(encoded)).encode(self.encoding))
        self.out.write(encoded)
        self.out.flush()
