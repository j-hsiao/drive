import os
import subprocess
import sys
import time
import webbrowser

def rm_try_dups():
    _tryorder = getattr(webbrowser, '_tryorder', [])
    for idx in range(len(_tryorder)-1, -1, -1):
        if _tryorder[idx] in _tryorder[:idx]:
            del _tryorder[idx]

try:
    webbrowser.get('xdg-open')
except Exception:
    pass
else:
    class XDGOpen(webbrowser.GenericBrowser):
        """Replace xdg-open browser if applicable.

        webbrowser uses webbrowser.BackgroundBrowser.
        However, background browser only checks whether the process
        started (only catches "command not found").  However, xdg-open
        searches for browsers and fails if none are found.  Thus, even
        if no browser exist, webbrowser will report success.  Thus,
        replace the normal xdg-open browser
        """
        def ignore(self,*args):
            pass
        def open(self, url, new=0, autoraise=True):

            cmdline = [self.name] + [arg.replace("%s", url)
                                     for arg in self.args]

            getattr(sys, 'audit', self.ignore)("webbrowser.open", url)
            getattr(self, '_check_url', self.ignore)(url)
            try:
                if sys.platform[:3] == 'win':
                    p = subprocess.Popen(cmdline)
                    return (p.poll() is None)
                else:
                    if sys.version_info.major >= 3:
                        p = subprocess.Popen(cmdline, close_fds=True,
                                             start_new_session=True)
                        return (not p.wait(2))
                    else:
                        setsid = getattr(os, 'setsid', None)
                        if not setsid:
                            setsid = getattr(os, 'setpgrp', None)
                        p = subprocess.Popen(cmdline, close_fds=True, preexec_fn=setsid)
                        period = 0.1
                        for i in range(max(1, int(2 / period))):
                            if p.poll() is not None:
                                break
                            time.sleep(period)
                        return not p.returncode
            except OSError:
                return False
    webbrowser.register('xdg-open', None, XDGOpen("xdg-open"))
rm_try_dups()
