"""Opt-in owned host for all-PRX bake comparison scenes; never a build step."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import edward_belt_blendshape_trial as bridge
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001'
bridge.FOLDER=FOLDER
if __name__=='__main__':
    if sys.argv[1]=='--host':bridge.host()
    elif sys.argv[1]=='--launch':
        with socket.socket() as probe:probe.bind(('127.0.0.1',9880))
        environment=os.environ.copy()
        environment['MAYA_APP_DIR']=str(ROOT/'tmp/edward_all_prx_maya_preferences')
        environment['MAYA_SKIP_USERSETUP_PY']='1'
        environment['OPENBLAS_NUM_THREADS']='2';environment['OMP_NUM_THREADS']='2'
        log=(FOLDER/'owned_startup.log').open('x')
        process=subprocess.Popen([r'C:\Program Files\Autodesk\Maya2026\bin\mayapy.exe',__file__,'--host'],
                                 stdout=log,stderr=subprocess.STDOUT,env=environment,creationflags=subprocess.CREATE_NO_WINDOW)
        (FOLDER/'owned_launch.json').write_text(json.dumps({'pid':process.pid,'port':9880}))
        print(process.pid)
    else:
        response=bridge.dispatch(sys.argv[1],sys.argv[2],json.loads(sys.argv[3]) if len(sys.argv)>3 else {})
        print(json.dumps(response,indent=2))
