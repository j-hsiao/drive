from pydrive.util import jutil
import os

d = jutil.JDir(os.path.join(os.path.dirname(__file__), '.jdir'))

jfile = d['hello']
print(jfile)
jfile['a'] = 1
jfile['b'] = 2
print(jfile)
jfile.save(indent=4)
