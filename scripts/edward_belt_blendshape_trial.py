"""Owned, opt-in Edward belt target experiment; never used by CREATE RIG.

Run with mayapy --host FOLDER, then send JSON script requests to localhost:9880.
The owned host loads a frozen native snapshot and never accesses artist Maya.
"""
import json
import os
from pathlib import Path
import socket
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001'


def host(source=None):
    sys.path[:0] = [str(ROOT/'autorig_tools'), str(ROOT/'autorig_tools/maya_tools/scripts'), str(ROOT/'scripts')]
    import maya.standalone
    maya.standalone.initialize(name='python')
    from maya import cmds
    cmds.evaluationManager(mode='off')
    cmds.evaluator(name='cache', enable=False)
    for plugin in ('matrixNodes','quatNodes','lookdevKit','deformerEvaluator','bifrostGraph'):
        try:
            cmds.loadPlugin(plugin, quiet=True)
        except Exception:
            pass
    cmds.evaluator(name='deformer',enable=False)
    cmds.file(str(source or FOLDER/'Edward_artist_baseline.ma'),open=True,force=True,prompt=False,executeScriptNodes=False)
    namespace = dict(globals(), cmds=cmds)
    with socket.socket() as server:
        server.bind(('127.0.0.1',9880))
        server.listen(1)
        (FOLDER/'owned_ready.json').write_text(json.dumps({'pid':os.getpid(),'port':9880,'scene':cmds.file(q=True,sn=True)}))
        while True:
            connection, _ = server.accept()
            with connection:
                data = b''
                while b'\n' not in data:
                    chunk=connection.recv(65536)
                    if not chunk:break
                    data+=chunk
                request=json.loads(data)
                if request.get('stop'):
                    os._exit(0)
                try:
                    namespace['result']=None
                    namespace['TRIAL_ARGUMENTS']=request.get('arguments',{})
                    exec(compile(Path(request['script']).read_text(),request['script'],'exec'),namespace)
                    response={'success':True,'result':namespace.get('result')}
                except BaseException:
                    response={'success':False,'traceback':traceback.format_exc()}
                Path(request['receipt']).write_text(json.dumps(response,indent=2,default=str))
                connection.sendall(b'done\n')


def dispatch(script,receipt,arguments=None):
    destination=Path(receipt).resolve()
    assert not destination.exists(), 'Receipt exists'
    with socket.create_connection(('127.0.0.1',9880),timeout=5) as connection:
        connection.settimeout(7200)
        connection.sendall((json.dumps({'script':str(Path(script).resolve()),'receipt':str(destination),
                                      'arguments':arguments or {}})+'\n').encode())
        connection.recv(100)
    return json.loads(destination.read_text())


if __name__=='__main__':
    if sys.argv[1]=='--host':
        host()
    elif sys.argv[1]=='--launch':
        import subprocess
        environment=os.environ.copy()
        environment['MAYA_APP_DIR']=str(ROOT/'tmp/edward_belt_blendshape_maya_preferences')
        environment['MAYA_SKIP_USERSETUP_PY']='1'
        log=(FOLDER/'owned_startup.log').open('x')
        process=subprocess.Popen([r'C:\Program Files\Autodesk\Maya2026\bin\mayapy.exe',__file__,'--host'],
                                 stdout=log,stderr=subprocess.STDOUT,env=environment,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        (FOLDER/'owned_launch.json').write_text(json.dumps({'pid':process.pid,'port':9880}))
        print(process.pid)
    else:
        print(json.dumps(dispatch(sys.argv[1],sys.argv[2],json.loads(sys.argv[3]) if len(sys.argv)>3 else {}),indent=2))
