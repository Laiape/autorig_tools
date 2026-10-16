"""Freeze current Edward inputs and launch one isolated interactive A/B host."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = ROOT / 'autorig_tools'
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/custom_solvers_20261016_v001'
FOLDER.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('freeze_package', ACTIVE / 'maya_tools/scripts/tools/rig_package.py')
package = importlib.util.module_from_spec(spec); spec.loader.exec_module(package)
suffixes = {'models': '.ma', 'guides': '.guides', 'curves': '.curves',
            'build': '.build', 'skin_clusters': '.skc', 'wrinkles': '.wrinkles.json'}
selected = {c: max((ACTIVE / 'maya_tools/assets/Edward' / c).glob('*' + ext), key=lambda p: p.name)
            for c, ext in suffixes.items()}
frozen = FOLDER / 'frozen'
manifest = package.create(ACTIVE, 'Edward', frozen, selected_files=selected)
correctives = ACTIVE / 'maya_tools/assets/Edward/corrective_blendshapes'
for source in correctives.glob('*.json'):
    target = frozen / source.relative_to(ACTIVE); target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    manifest['files'][source.relative_to(ACTIVE).as_posix()] = {'sha256': package.digest(target), 'bytes': target.stat().st_size}
(frozen / 'manifest.json').write_text(json.dumps(manifest, indent=2))
package.verify(frozen)
work = FOLDER / 'work'
shutil.copytree(frozen, work)
settings = {'root': str(ROOT), 'folder': str(FOLDER), 'runtime': str(work), 'port': 7392,
            'inputs': {c: {'path': str(p), 'sha256': package.digest(p)} for c, p in selected.items()},
            'frozen_manifest_sha256': package.digest(frozen / 'manifest.json')}
with socket.socket() as probe:
    probe.bind(('127.0.0.1', settings['port']))
environment = os.environ.copy()
environment.update(MAYA_APP_DIR=str(FOLDER / 'preferences'), MAYA_SKIP_USERSETUP_PY='1',
                   EDWARD_SOLVER_SETTINGS=str(FOLDER / 'launch.json'),
                   AUTORIG_BUILD_CACHE_DIR=str(FOLDER / 'build_cache'),
                   AUTORIG_MODEL_CACHE_DIR=str(FOLDER / 'model_cache'),
                   OPENBLAS_NUM_THREADS='2', OMP_NUM_THREADS='2')
code = 'import maya.utils;maya.utils.executeDeferred(lambda:__import__("runpy").run_path(%r))' % str(ROOT / 'scripts/edward_solver_trial_bootstrap.py')
with (FOLDER / 'startup.log').open('x') as log:
    process = subprocess.Popen([r'C:\Program Files\Autodesk\Maya2026\bin\maya.exe',
                                '-noAutoloadPlugins', '-command', 'python(' + json.dumps(code) + ')'],
                               env=environment, stdout=log, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW)
settings['pid'] = process.pid
(FOLDER / 'launch.json').write_text(json.dumps(settings, indent=2))
print(json.dumps({'pid': process.pid, 'port': settings['port'], 'inputs': {c: p.name for c, p in selected.items()}}, indent=2))
