"""Cold-open a skirt delivery using Maya only, without project Python imports."""
import json
import math
import os
import sys
from pathlib import Path

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
ROOT = Path(__file__).resolve().parents[1]
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om

folder = ROOT/'maya_tools/assets/Nini/experiments/skirt_contact'
manifest = next(json.loads(p.read_text()) for p in sorted(folder.glob('final_delivery_v*.json'), reverse=True)
                if json.loads(p.read_text()).get('passed'))
version = Path(manifest['delivery']).stem.rsplit('_',1)[1]
reference = json.loads((folder/('portability_reference_'+version+'.json')).read_text())
target = folder/('native_portability_'+version+'.json')
assert not target.exists()
report = {'passed':False,'delivery':manifest['delivery'],'modes':{}}

def points(mesh):
    shapes = cmds.listRelatives(mesh,shapes=True,noIntermediate=True,type='mesh',fullPath=True)
    assert len(shapes)==1
    path = om.MSelectionList().add(shapes[0]).getDagPath(0)
    return [tuple(p)[:3] for p in om.MFnMesh(path).getPoints(om.MSpace.kWorld)]

try:
    cmds.file(manifest['delivery'],open=True,force=True)
    for evaluator in ('cache','deformer'):
        if evaluator in (cmds.evaluator(query=True) or []):
            cmds.evaluator(name=evaluator,enable=False)
    for mode in ('off','parallel'):
        cmds.evaluationManager(mode=mode)
        errors = {}
        for name,pose in reference['poses'].items():
            for side,delta in zip(('L','R'),pose):
                cmds.xform(side+'_ankleIk_CTL',ws=True,t=[a+b for a,b in zip(reference['rest'][side],delta)])
            errors[name] = max(math.dist(p,q) for m,expected in reference['snapshots'][name].items()
                               for p,q in zip(points(m),expected))
            assert errors[name] <= 1e-4,(mode,name,errors[name])
        report['modes'][mode] = errors
    imported = sorted(n for n in sys.modules if n.startswith('maya_tools'))
    report['project_python_imports'] = imported
    report['unknown_nodes'] = cmds.ls(type='unknown') or []
    report['script_nodes'] = cmds.ls(type='script') or []
    assert not imported and not report['unknown_nodes']
    report['passed'] = True
except BaseException:
    import traceback
    report['error'] = traceback.format_exc()
    raise
finally:
    target.write_text(json.dumps(report,indent=2),encoding='ascii')
    print('SKIRT_PORTABILITY='+json.dumps(report),flush=True)
