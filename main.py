"""
This file is only a pointer. Do not use it as the app entrypoint.

In PyCharm:
  1. Run setup_pycharm.py  (install packages)
  2. Run run.py            (start NETRIX)

Browser: http://127.0.0.1:5000
"""
import runpy
import sys

print('NETRIX: starting via run.py ...')
print('(If packages are missing, run setup_pycharm.py first.)')
try:
    runpy.run_path('run.py', run_name='__main__')
except ModuleNotFoundError as e:
    print('Missing package:', e)
    print('Fix: right-click setup_pycharm.py → Run')
    sys.exit(1)
