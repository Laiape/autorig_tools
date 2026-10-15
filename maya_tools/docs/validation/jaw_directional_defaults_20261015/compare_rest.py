"""Maya batch comparison of unchanged poses before/after signed corner defaults."""
import hashlib
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path.cwd()
OUT = ROOT / '.git/jaw_directional_rest.json'
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path[:0] = [str(ROOT), str(ROOT/'maya_tools/scripts'), str(ROOT/'maya_tools/scripts/tools/tests')]
from PySide6 import QtWidgets
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
import numpy as np
from fixtures.jaw_scene import build, SOURCE

cases = [({}, 'neutral')] + [({'C_jaw_CTL.rx': a}, 'jaw_'+str(a)) for a in (5,10,20,30)]
cases += [({'C_jaw_CTL.rx':20,'C_'+p+'Lip_CTL.ty':v},p+str(v))
          for p in ('upper','lower') for v in (-1,1)]
cases += [({'C_jaw_CTL.rx':20,'C_jaw_CTL.stickyLips':v},'sticky_'+str(v)) for v in (.5,1)]
cases += [({'C_mainMouth_CTL.tx':1,'C_mainMouth_CTL.ry':14},'mouth'),
          ({'head_ctl.tx':3,'head_ctl.rz':19},'head')]
report = dict(success=False, baseline_ref='2a3fad8', maya_version=cmds.about(version=True),
              source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
              purpose='Independent default-pose comparison only. Signed corner poses intentionally change and are tested separately. CPU geometry and world matrices, no viewport or timing claim.')

def sample_cases(read, poses):
    defaults={p:cmds.getAttr(p) for case,_ in poses for p in case}
    result={}
    for case,name in poses:
        for p,v in case.items():cmds.setAttr(p,v)
        result[name]=read()
        for p in case:cmds.setAttr(p,defaults[p])
    return result

def error(before, after):
    return max(float(np.abs(a-b).max()) for k in before for a,b in zip(before[k],after[k]))

with tempfile.TemporaryDirectory(prefix='jaw_signed_rest_') as private:
    old=Path(private)/'jaw_before.py'
    old.write_bytes(subprocess.check_output(['git','show','2a3fad8:maya_tools/scripts/biped/autorig/jaw_module_nurbs.py'],cwd=ROOT))
    baseline=None
    inventory=[]
    for source in (old,SOURCE):
        build(source)
        nodes=sorted(cmds.ls('*Lip*_JNT',type='joint')+cmds.ls('*Lip*_GRP','*lipCorner_GRP','*lipCorner_OFF',type='transform'))
        inventory.append(len(cmds.ls()))
        posed=sample_cases(lambda:[np.array([cmds.xform(n,q=True,ws=True,matrix=True) for n in nodes])],cases)
        if baseline is None:baseline=posed
        else:report['fixture_matrix_error']=error(baseline,posed)
    report['fixture_cases']=len(cases)
    report['fixture_matrix_count']=len(nodes)
    report['fixture_nodes_before_after']=inventory
    assert report['fixture_matrix_error']<1e-6, report
    print('REST_FIXTURE',report['fixture_matrix_error'],flush=True)

    active=old
    class SourceFinder(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path,target=None):
            if fullname=='maya_tools.scripts.biped.autorig.jaw_module_nurbs':
                return importlib.util.spec_from_file_location(fullname,str(active))
    finder=SourceFinder()
    sys.meta_path.insert(0,finder)
    from maya_tools.scripts.utils import create_rig
    from maya_tools.scripts.framework import context
    context.service().set_asset('Edward')
    cmds.optionVar(stringValue=('currentAssetRigName','Edward'))
    os.environ['AUTORIG_BUILD_CACHE_DIR']=str(Path(private)/'cache')
    baseline=None
    full_cases=[p for p in cases if p[1]!='head']
    meshes=('cabeza_high','cabeza_low','cuerpo_base')
    try:
        for active in (old,SOURCE):
            create_rig.AutoRig().build()
            cmds.evaluationManager(mode='off')
            fns=[]
            for mesh in meshes:
                shape=cmds.listRelatives(mesh,shapes=True,noIntermediate=True,fullPath=True)[0]
                fns.append(om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0)))
            def read():return [np.array([[p.x,p.y,p.z] for p in fn.getPoints(om.MSpace.kWorld)]) for fn in fns]
            posed=sample_cases(read,full_cases)
            if baseline is None:baseline=posed
            else:report['edward_geometry_error']=error(baseline,posed)
        assert report['edward_geometry_error']<1e-6,report
        report['edward_cases']=len(full_cases)
        report['edward_vertices']={mesh:fn.numVertices for mesh,fn in zip(meshes,fns)}
        report['success']=True
    finally:
        sys.meta_path.remove(finder)
        OUT.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('PASS unchanged default rest against 2a3fad8',json.dumps(report),flush=True)
