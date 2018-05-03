from __future__ import print_function
import sys
if sys.executable.endswith("pythonw.exe"):
    sys.stdout = sys.stdout = None
from datetime import datetime

def display(msg):
    try:
	sys.stdout.write('['+datetime.today().strftime('%y-%m-%d %H:%M:%S')+'] - ' + msg + '\n')
	sys.stdout.flush()
    except:
	pass
    
