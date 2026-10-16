"""Bounded owned GUI trial of model UI scripts and legacy XGen preview."""
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time
import traceback
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'autorig_tools'), str(ROOT/'autorig_tools/maya_tools/scripts')]
FOLDER = Path(os.environ['AUTORIG_CHIHUAHUA_TRIAL_FOLDER'])
from maya import cmds, mel
from maya.api import OpenMaya as om
from maya_tools.scripts.utils import model_cache
source = ROOT/'autorig_tools/maya_tools/assets/chihuahua/models/chihuahua_v001.ma'
binary = model_cache._cache_record(source)['binary']
report = {'samples': [], 'binary': str(binary), 'pid': os.getpid()}
def checkpoint(phase):
    report['phase'] = phase
    (FOLDER/'progress.json').write_text(json.dumps(report, indent=2))

def geometry():
    output = {}
    for name in cmds.ls(type='mesh', long=True):
        selection=om.MSelectionList(); selection.add(name)
        fn=om.MFnMesh(selection.getDagPath(0))
        values=[v for p in fn.getPoints(om.MSpace.kWorld) for v in (p.x,p.y,p.z)]
        output[name]=hashlib.sha256(struct.pack('<%sd' % len(values), *values)).hexdigest()
    return output

try:
    cmds.evaluationManager(mode='off')
    checkpoint('warmup_open')
    cmds.file(str(binary), open=True, force=True, executeScriptNodes=False)
    mel.eval('setNamedPanelLayout "Single Perspective View";')
    cmds.modelEditor('modelPanel4', edit=True, displayAppearance='smoothShaded', rendererName='vp2Renderer')
    checkpoint('warmup_redraw')
    cmds.refresh(force=True)
    report['meshes'] = {n: {'vertices': cmds.polyEvaluate(n, vertex=True),
                            'smooth': cmds.getAttr(n+'.displaySmoothMesh')} for n in cmds.ls(type='mesh', long=True)}
    report['groom_visibility'] = cmds.getAttr('xgen.visibility')
    report['expression_connections'] = cmds.listConnections('xgmRefreshPreview', connections=True, plugs=True)
    reference=geometry()
    for index, mode in enumerate(('full','no_scripts','no_preview','no_preview','no_scripts','full','full','no_scripts','no_preview')):
        checkpoint('%s_%s_prepare' % (index,mode))
        cmds.file(new=True, force=True, executeScriptNodes=False)
        checkpoint('%s_%s_open' % (index,mode))
        start=time.perf_counter()
        cmds.file(str(binary), open=True, force=True, executeScriptNodes=mode!='no_scripts')
        opened=time.perf_counter()
        if mode=='no_preview':
            cmds.setAttr('xgmRefreshPreview.nodeState',1)
        checkpoint('%s_%s_redraw' % (index,mode))
        drawstart=time.perf_counter()
        cmds.refresh(force=True)
        drawn=time.perf_counter()
        report['samples'].append({'mode':mode,'open_seconds':opened-start,
                                  'redraw_seconds':drawn-drawstart,'geometry_matches':geometry()==reference})
        checkpoint('%s_%s_complete' % (index,mode))
    checkpoint('complete')
    (FOLDER/'result.json').write_text(json.dumps(report,indent=2))
except BaseException:
    (FOLDER/'failure.txt').write_text(traceback.format_exc())
finally:
    cmds.quit(force=True)
