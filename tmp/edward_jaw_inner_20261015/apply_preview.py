import json,hashlib,numpy as np
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
from maya_tools.scripts.tools import bifrost_wrinkles
WORK=Path(r'C:/proyectos/auto-rig/tmp/edward_jaw_inner_20261015/latest')
manifest=json.loads((WORK/'neutral_manifest.json').read_text())
def path(mesh):
    s=om.MSelectionList();s.add(mesh);p=s.getDagPath(0)
    if p.node().hasFn(om.MFn.kTransform):p.extendToShape()
    return p
def points(mesh):return np.asarray(om.MFnMesh(path(mesh)).getPoints(om.MSpace.kWorld))[:,:3].copy()
def image(name):
    cmds.refresh(force=True)
    return cmds.playblast(completeFilename=str(WORK/(name+'.png')),format='image',compression='png',frame=cmds.currentTime(q=True),viewer=False,offScreen=True,showOrnaments=False,widthHeight=(1318,748),percent=100,forceOverwrite=True)
image('before_preview')
before={m['mesh']:points(m['mesh']) for m in manifest}
old_masks={};reports=[]
cmds.undoInfo(openChunk=True,chunkName='Edward_Jaw_InnerLip_Smoothing')
try:
    with bifrost_wrinkles.primary_inputs_for_skin_export():
        for rec in manifest:
            mesh=rec['mesh'];skin=rec['skin'];plan=np.load(str(WORK/(mesh+'_weight_plan.npz')))
            s=om.MSelectionList();s.add(skin);fn=oma.MFnSkinCluster(s.getDependNode(0));dag=path(mesh)
            cf=om.MFnSingleIndexedComponent();co=cf.create(om.MFn.kMeshVertComponent);cf.setCompleteData(om.MFnMesh(dag).numVertices)
            raw,n=fn.getWeights(dag,co);old=np.asarray(raw).reshape(-1,n).copy()
            expected=np.load(str(WORK/(mesh+'_neutral.npz')))['weights']
            if np.max(abs(old-expected))>1e-9:raise RuntimeError('Skin changed since snapshot '+skin)
            weights=np.round(plan['weights'],8)
            flags={a:cmds.getAttr(skin+'.'+a) for a in ('normalizeWeights','maintainMaxInfluences')}
            cmds.setAttr(skin+'.normalizeWeights',0);cmds.setAttr(skin+'.maintainMaxInfluences',False)
            try:fn.setWeights(dag,co,om.MIntArray(range(n)),om.MDoubleArray(weights.ravel().tolist()),False)
            finally:
                for a,v in flags.items():cmds.setAttr(skin+'.'+a,v)
            bs=mesh+'_poseCorrectives_BLS';index=4 if mesh=='cabeza_high' else 0
            g=bs+'.inputTarget[0].inputTargetGroup[%d]'%index
            ids=cmds.getAttr(g+'.targetWeights',mi=True) or []
            oldmask=np.ones(len(weights))
            for i in ids:oldmask[i]=cmds.getAttr(g+'.targetWeights[%d]'%i)
            old_masks[mesh]=oldmask
            newmask=oldmask*plan['jaw_target_mask']
            cmds.setAttr(g+'.targetWeights[0:%d]'%(len(weights)-1),*newmask.tolist(),size=len(weights))
            reports.append({'mesh':mesh,'skin':skin,'edited_weights':int(plan['changed'].sum()),'jaw_mask_edited':int((abs(newmask-oldmask)>1e-7).sum()),'lip_sculpt_deltas_untouched':True})
    after={m['mesh']:points(m['mesh']) for m in manifest}
    np.savez_compressed(str(WORK/'preview_comparison.npz'),**{m+'_'+k:pts for k,d in [('before',before),('after',after)] for m,pts in d.items()},**{m+'_oldmask':v for m,v in old_masks.items()})
    for r in reports:
        d=np.linalg.norm(after[r['mesh']]-before[r['mesh']],axis=1);r['max_pose_change_cm']=float(d.max())
    image('after_preview')
    cmds.file(modified=True)
finally:cmds.undoInfo(closeChunk=True)
(WORK/'preview_results.json').write_text(json.dumps(reports,indent=2))
result=reports
