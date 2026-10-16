import os
import subprocess
from pathlib import Path
folder = Path(__file__).resolve().parent
env = dict(os.environ, MAYA_SKIP_USERSETUP_PY='1')
command = 'python("import maya.utils; maya.utils.executeDeferred(lambda: __import__(\'runpy\').run_path(\'%s\'))");' % (folder/'gui_bootstrap.py').as_posix()
proc = subprocess.Popen(['C:/Program Files/Autodesk/Maya2026/bin/maya.exe', '-noAutoloadPlugins',
                         '-log', str(folder/'maya_gui.log'), '-command', command], env=env)
print(proc.pid)
