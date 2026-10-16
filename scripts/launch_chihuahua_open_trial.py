"""Launch an owned hidden interactive Maya for model-open measurements."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT/'tmp/chihuahua_open_20261016_v001'
FOLDER.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env['MAYA_APP_DIR'] = str(FOLDER/'preferences')
env['MAYA_SKIP_USERSETUP_PY'] = '1'
script = (ROOT/'scripts/chihuahua_open_trial.py').as_posix()
code = "import maya.utils; maya.utils.executeDeferred(lambda: __import__('runpy').run_path(%r, run_name='__main__'))" % script
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 0
with (FOLDER/'startup.log').open('x') as log:
    process = subprocess.Popen([r'C:\Program Files\Autodesk\Maya2026\bin\maya.exe', '-noAutoloadPlugins',
                                '-command', 'python('+json.dumps(code)+');'], env=env, stdout=log,
                               stderr=subprocess.STDOUT, startupinfo=startup, creationflags=subprocess.CREATE_NO_WINDOW)
(FOLDER/'launch.json').write_text(json.dumps({'pid': process.pid}))
print(process.pid)
