"""Launch a separate owned interactive Maya for geometry-preserving trials."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001'
if (FOLDER / 'owned_maya.json').exists():
    if '--retry' not in sys.argv:
        raise ValueError('An owned trial was already launched; inspect it before retrying.')
    attempt=1
    while (FOLDER/('owned_maya.json.failed_attempt%02d'%attempt)).exists():attempt+=1
    for name in ('owned_maya.json','owned_maya_ready.json','owned_maya_startup.log','progress.json'):
        source = FOLDER / name
        if source.exists():
            destination = FOLDER / (name + '.failed_attempt%02d'%attempt)
            if destination.exists():
                raise ValueError('The failed trial archive already exists: ' + str(destination))
            source.rename(destination)
port = None
for candidate in (7202, 7212, 7222):
    with socket.socket() as probe:
        try:
            probe.bind(('127.0.0.1', candidate))
            port = candidate
            break
        except OSError:
            continue
if port is None:
    raise RuntimeError('No free owned trial command port.')
settings = {'root': str(ROOT), 'folder': str(FOLDER), 'port': port}
(FOLDER / 'launch_settings.json').write_text(json.dumps(settings, indent=2), encoding='utf-8')
startup = ROOT / 'scripts/edward_exact_trial_bootstrap.py'
code = 'import maya.utils; maya.utils.executeDeferred(lambda: __import__("runpy").run_path(%r))' % str(startup)
environment = os.environ.copy()
environment['MAYA_APP_DIR'] = str(ROOT / 'tmp/edward_exact_maya_preferences')
environment['MAYA_SKIP_USERSETUP_PY'] = '1'
log = (FOLDER / 'owned_maya_startup.log').open('w')
startup_info = subprocess.STARTUPINFO()
startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup_info.wShowWindow = 4  # SW_SHOWNOACTIVATE: separate trial, preserve artist focus.
process = subprocess.Popen([r'C:\Program Files\Autodesk\Maya2026\bin\maya.exe',
                            '-noAutoloadPlugins', '-command', 'python(' + json.dumps(code) + ')'],
                           stdout=log, stderr=subprocess.STDOUT, env=environment,
                           creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=startup_info)
settings['pid'] = process.pid
(FOLDER / 'owned_maya.json').write_text(json.dumps(settings, indent=2), encoding='utf-8')
print(json.dumps(settings))
