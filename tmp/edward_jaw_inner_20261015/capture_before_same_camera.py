import json,numpy as np
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
from maya_tools.scripts.tools import bifrost_wrinkles
WORK=Path(r'C:/proyectos/auto-rig/tmp/edward_jaw_inner_20261015/latest')
manifest=json.loads((WORK/'neutral_manifest.json').read_text())
def setweights(rec,weights):
    s=om.MSelectionList();s.add(rec['skin']);sf=oma.MFnSkinCluster(s.getDependNode(0));s=om.MSelectionList();s.add(rec['mesh']);p=s.getDagPath(0);p.extendToShape()
    cf=om.MFnSingleIndexedComponent();co=cf.create(om.MFn.kMeshVertComponent);cf.setCompleteData(len(weights))
    flags={a:cmds.getAttr(rec['skin']+'.'+a) for a in ('normalizeWeights','maintainMaxInfluences')}
    cmds.setAttr(rec['skin']+'.normalizeWeights',0);cmds.setAttr(rec['skin']+'.maintainMaxInfluences',False)
    sf.setWeights(p,co,om.MIntArray(range(weights.shape[1])),om.MDoubleArray(weights.ravel().tolist()),False)
    for a,v in flags.items():cmds.setAttr(rec['skin']+'.'+a,v)
def setmask(rec,mask):
    idx=4 if rec['mesh']=='cabeza_high' else 0
    p=rec['mesh']+'_poseCorrectives_BLS.inputTarget[0].inputTargetGroup[%d].targetWeights'%idx
    cmds.setAttr(p+'[0:%d]'%(len(mask)-1),*mask.tolist(),size=len(mask))
old=np.load(str(WORK/'preview_comparison.npz'))
try:
    with bifrost_wrinkles.primary_inputs_for_skin_export():
        for rec in manifest:
            setweights(rec,np.load(str(WORK/(rec['mesh']+'_neutral.npz')))['weights']);setmask(rec,old[rec['mesh']+'_oldmask'])
    cmds.refresh(force=True)
    result=cmds.playblast(completeFilename=str(WORK/'before_mouth.png'),format='image',compression='png',frame=cmds.currentTime(q=True),viewer=False,offScreen=True,showOrnaments=False,widthHeight=(1318,748),percent=100,forceOverwrite=True)
finally:
    with bifrost_wrinkles.primary_inputs_for_skin_export():
        for rec in manifest:
            plan=np.load(str(WORK/(rec['mesh']+'_weight_plan.npz')))
            setweights(rec,np.round(plan['weights'],8));setmask(rec,old[rec['mesh']+'_oldmask']*plan['jaw_target_mask'])
    cmds.refresh(force=True)
