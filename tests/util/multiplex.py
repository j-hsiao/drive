from pydrive.util.multiplex import Multiplexed
import sys
import io
import subprocess as sp
import time

p = sp.Popen(['bash'], stdin=sp.PIPE)
ptext = io.TextIOWrapper(p.stdin)
ptext.write(Multiplexed.SCRIPTS['bash'])



ptext.write('''
run() {
    type pydrive_read
    while pydrive_read 0 stream result 1; ((!(ss=$?)))
    do
        echo "stream ${stream}:"
        printf '  %s' "${result}"
    done
    echo finished $? $ss
    if ((ss > 128)); then echo timed out
    else echo eof; fi
}
run
''')
ptext.flush()

out = Multiplexed(ptext)
print('hello world!', file=out)
print('goodbye world!', file=out)
print('multi\nline', file=out)
with out.stream(1):
    print('hello world!', file=out)
    print('goodbye world!', file=out)
    print('multi\nline', file=out)
    print('not ending in newline', file=out, end='')
print('back to stream original', file=out)
ptext.flush()
# time.sleep(2)
ptext.close()
p.wait()
