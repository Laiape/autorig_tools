import json, os, subprocess
from pathlib import Path
base = Path('C:/proyectos/auto-rig/tmp/chihuahua_shapes_20261016')
env = dict(os.environ, MAYA_APP_DIR='C:/proyectos/auto-rig/tmp/chihuahua_orientation_20261016/gui_preferences', MAYA_SKIP_USERSETUP_PY='1')
code = "exec(compile(open('C:/proyectos/auto-rig/tmp/chihuahua_shapes_20261016/bootstrap.py').read(), 'bootstrap.py', 'exec'))"
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = subprocess.SW_HIDE
with (base/'startup.log').open('w') as log:
    process = subprocess.Popen(['C:/Program Files/Autodesk/Maya2026/bin/maya.exe', '-command', 'python('+json.dumps(code)+')'], env=env, startupinfo=startup, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
(base/'pid.txt').write_text(str(process.pid))
print(process.pid)
