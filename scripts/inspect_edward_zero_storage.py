"""Inspect native sparse weight storage before/after zero-only cleanup."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/exact_optimization_20261015_v001'
sys.path[:0]=[str(ROOT/'autorig_tools'),str(ROOT/'autorig_tools/maya_tools/scripts')]
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
from maya_tools.scripts.tools import rig_exact_cleanup
for plugin in ('matrixNodes','quatNodes','lookdevKit','deformerEvaluator','bifrostGraph'):cmds.loadPlugin(plugin,quiet=True)
cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False);cmds.evaluationManager(mode='off')
cmds.file((FOLDER/'Edward_artist_baseline.mb').as_posix(),open=True,force=True,executeScriptNodes=False)
node='C_body_SKC_COPY_COPY'
def stats():
    indices=cmds.getAttr(node+'.matrix',multiIndices=True) or []
    rows=[]
    for vertex in (0,100,1000,3000,5000):
        weights=cmds.getAttr('%s.weightList[%d].weights'%(node,vertex),multiIndices=True) or []
        rows.append({'vertex':vertex,'stored_elements':len(weights),'maximum_index':max(weights) if weights else None})
    return {'matrix_elements':len(indices),'max_matrix_index':max(indices),'sample_storage':rows}
report={'before':stats()}
start=time.perf_counter();report['change']=rig_exact_cleanup.remove_exact_zero_influences([node],apply=True)
report['apply_seconds']=time.perf_counter()-start
report['after_removal']=stats()
fn=oma.MFnSkinCluster(om.MSelectionList().add(node).getDependNode(0))
path=om.MDagPath.getAPathTo(fn.getOutputGeometry()[0]);c=om.MFnSingleIndexedComponent()
component=c.create(om.MFn.kMeshVertComponent);c.setCompleteData(om.MFnMesh(path).numVertices)
before,count=fn.getWeights(path,component);before=np.asarray(before).copy()
report['min_positive_weight']=float(before[before>0].min())
if report['min_positive_weight']>1e-30:
    normalization=cmds.getAttr(node+'.normalizeWeights');cmds.setAttr(node+'.normalizeWeights',0)
    cmds.skinPercent(node,path.fullPathName(),pruneWeights=1e-30,normalize=False)
    cmds.setAttr(node+'.normalizeWeights',normalization)
    report['after_zero_storage_prune']=stats()
    after,count=fn.getWeights(path,component)
    report['retained_weights_exact']=bool(np.array_equal(before,np.asarray(after)))
(FOLDER/'zero_storage_inspection.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k!='change'},indent=2),flush=True)
sys.stdout.flush();sys.stderr.flush()
# Evidence is closed. Terminate only this disposable process to avoid the
# observed native Bifrost/Arnold teardown fault and recovery-file side effects.
ctypes.windll.kernel32.TerminateProcess(ctypes.windll.kernel32.GetCurrentProcess(),0)
