"""Launch an owned hidden interactive Maya for model-open measurements."""
import json
import os
from pathlib import Path
import subprocess
import argparse

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--operation', choices=('open', 'import'), default='open')
parser.add_argument('--folder', default=str(ROOT/'tmp/chihuahua_open_20261016_v001'))
parser.add_argument('--baseline')
parser.add_argument('--candidate')
parser.add_argument('--script', default=str(ROOT/'scripts/chihuahua_open_trial.py'))
options = parser.parse_args()
FOLDER = Path(options.folder).resolve()
FOLDER.mkdir(parents=True, exist_ok=True)
env = os.environ.copy()
env['MAYA_APP_DIR'] = str(FOLDER/'preferences')
env['MAYA_SKIP_USERSETUP_PY'] = '1'
env['AUTORIG_CHIHUAHUA_TRIAL_FOLDER'] = str(FOLDER)
env['AUTORIG_CHIHUAHUA_TRIAL_OPERATION'] = options.operation
if options.baseline:
    env['AUTORIG_CHIHUAHUA_TRIAL_BASELINE'] = str(Path(options.baseline).resolve())
if options.candidate:
    env['AUTORIG_CHIHUAHUA_TRIAL_CANDIDATE'] = str(Path(options.candidate).resolve())
script = Path(options.script).resolve().as_posix()
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
