"""Isolated Maya host for the requested skin-only SKC export."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import edward_belt_blendshape_trial as bridge

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/skin_only_delivery_20261016_v001'
bridge.FOLDER = FOLDER

if __name__ == '__main__':
    if sys.argv[1] == '--host':
        bridge.host(FOLDER / 'Edward_artist_before_skin_only.ma')
    elif sys.argv[1] == '--launch':
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 9880))
        environment = os.environ.copy()
        environment['MAYA_APP_DIR'] = str(ROOT / 'tmp/edward_skin_only_preferences')
        environment['MAYA_SKIP_USERSETUP_PY'] = '1'
        environment['OPENBLAS_NUM_THREADS'] = '2'
        environment['OMP_NUM_THREADS'] = '2'
        with (FOLDER / 'owned_startup.log').open('x') as log:
            process = subprocess.Popen([r'C:\Program Files\Autodesk\Maya2026\bin\mayapy.exe',
                                        __file__, '--host'], stdout=log,
                                       stderr=subprocess.STDOUT, env=environment,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
        data = {'pid': process.pid, 'port': 9880}
        (FOLDER / 'owned_launch.json').write_text(json.dumps(data))
        print(json.dumps(data))
    else:
        print(json.dumps(bridge.dispatch(sys.argv[1], sys.argv[2],
              json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}), indent=2))
