"""Replace stdin with a socket to allow polling "stdin" on windows.

Continually reads from the original stdin and feeds to one end of a socket.
sys.stdin is replaced with the other end.

NOTE: by experiment, interactive python does not use the current sys.stdin as input.
Therefore, only replace stdin if not interactive.

Modules are singletons so this replacement will only ever happen once.
"""
import platform

if platform.system() == 'Windows':
    import threading
    import socket
    import sys
    if sys.flags.interactive:
        print('Interactive mode detected, NOT replacing stdin with a socket.', file=sys.sdterr)
    else:
        r, w = socket.socketpair()
        r.shutdown(socket.SOCK_WR)
        w.shutdown(socket.SOCK_RD)
        def feedstdin(original, sock):
            raw = getattr(original, 'buffer', original)
            method = getattr(raw, 'read1', raw.read)
            while 1:
                try:
                    data = method()
                    sock.sendall(data)
                except Exception:
                    pass
        t = threading.Thread(target=feedstdin, args=[sys.stdin, w])
        t.daemon = True
        t.start()
        sys.stdin = r.makefile('r')
