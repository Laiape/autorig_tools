import json, os, socket, sys, traceback
from pathlib import Path
ROOT = Path(r'C:/proyectos/auto-rig')
WORK = ROOT / 'tmp/edward_wrap_bake_20261015'
sys.path.insert(0, str(ROOT / 'autorig_tools/maya_tools/scripts'))
sys.path.insert(0, str(ROOT / 'maya_tools/scripts'))
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
cmds.evaluator(name='cache', enable=False)
cmds.evaluationManager(mode='off')
scene = ROOT / 'autorig_tools/maya_tools/assets/Edward/scenes/Edward_working_v002.mb'
cmds.file(str(scene), open=True, force=True, prompt=False, executeScriptNodes=False)
namespace = globals()
sock = socket.socket()
sock.bind(('127.0.0.1', 9878))
sock.listen(1)
(WORK / 'ready.json').write_text(json.dumps({'scene':str(scene), 'pid':os.getpid()}))
print('EDWARD_HOST_READY', flush=True)
while True:
    conn, _ = sock.accept()
    with conn:
        buf = b''
        while b'\n' not in buf:
            chunk = conn.recv(65536)
            if not chunk: break
            buf += chunk
        if not buf.strip(): continue
        request = json.loads(buf)
        try:
            if request.get('stop'):
                conn.sendall(b'{"stopped":true}\n')
                os._exit(0)
            namespace['result'] = None
            exec(compile(Path(request['script']).read_text(encoding='utf-8'), request['script'], 'exec'), namespace)
            reply = {'result':namespace.get('result')}
        except BaseException:
            reply = {'error':traceback.format_exc()}
        if request.get('receipt'):
            Path(request['receipt']).write_text(json.dumps(reply, indent=2, default=str), encoding='utf-8')
        conn.sendall((json.dumps(reply, default=str)+'\n').encode())
