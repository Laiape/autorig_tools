"""LBS approximation plus a small bank of native orientation residual targets."""
import json,math
import numpy as np
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import proximity_bake as bake,pose_blendshapes as poses,orientation_correctives as orientation

@poses.undoable
def bake_with_residuals(start,end,step,controller,joint,reference,axis='X',max_influences=8,
                        error_limit=.1,extra_validation=None,color_error=True,keep_failed=False,pose_type='swing_twist'):
    if not math.isfinite(error_limit) or error_limit<=0:raise ValueError('Use a positive finite hybrid error limit.')
    selected=bake.selected_targets()
    if len(selected)!=1:raise ValueError('Select one source mesh for an orientation residual bank.')
    original_time=cmds.currentTime(q=True);initial_selection=cmds.ls(sl=True,long=True) or []
    result=None
    try:
        plain=bake.bake_selected(start,end,step,bind_frame=start,max_influences=max_influences)
        record=plain['records'][0];source=record['source'];destination=record['destination']
        cmds.currentTime(start)
        system=orientation.create_system(joint,reference,destination.rsplit('|',1)[-1]+'_residualOrientation',axis)
        bs=poses.create_blendshape(destination);targets=[]
        for frame in plain['frames']:
            if frame==start:continue
            cmds.currentTime(frame)
            expected=bake.points(source)
            cmds.setAttr(bs+'.envelope',0)
            actual=bake.points(destination)
            cmds.setAttr(bs+'.envelope',1)
            delta=expected-actual
            if float(np.linalg.norm(delta,axis=1).max())<1e-6:continue
            index,name=poses.add_target(destination,bs,controller,system,pose_type=pose_type)
            inverse=om.MMatrix(cmds.xform(destination,q=True,worldSpace=True,matrix=True)).inverse()
            for i,vector in enumerate(delta):
                if np.linalg.norm(vector)<1e-7:continue
                local=om.MVector(*vector)*inverse
                cmds.move(local.x,local.y,local.z,destination+'.vtx[%d]'%i,relative=True,objectSpace=True)
            poses.finish_edit();targets.append({'frame':frame,'index':index,'name':name})
        vertex_error=np.zeros(len(bake.points(source)));metrics=[]
        for frame in plain['frames']+plain['validation_frames']:
            cmds.currentTime(frame)
            error=np.linalg.norm(bake.points(destination)-bake.points(source),axis=1)
            vertex_error=np.maximum(vertex_error,error)
            metrics.append({'frame':frame,'set':'fit' if frame in plain['frames'] else 'held_out',
                'rms':float(np.sqrt(np.mean(error**2))),'max':float(error.max())})
        for case in extra_validation or []:
            cmds.currentTime(case.get('frame',start))
            with poses._temporary_values(case['values']):
                for plug,value in case['values'].items():cmds.setAttr(plug,value)
                error=np.linalg.norm(bake.points(destination)-bake.points(source),axis=1)
                vertex_error=np.maximum(vertex_error,error)
                metrics.append({'expression':case['name'],'set':'unseen_expression','rms':float(np.sqrt(np.mean(error**2))),'max':float(error.max())})
        maximum=max(m['max'] for m in metrics)
        result={'version':1,'source':source,'destination':destination,'skin':record['skin'],'blendShape':bs,
            'orientation_system':system,'targets':targets,'units':record['units'],'plain_worst_max':record['worst_max'],
            'plain_held_out_max':record['held_out_max'],'validation':metrics,'worst_max':maximum,
            'error_limit':error_limit,'quality_pass':maximum<=error_limit,'production_replacement':False,
            'acceptance':'Quality pass alone does not demonstrate a performance benefit. Compare cost before replacing the original.',
            'source_stack':[{'node':n,'type':cmds.nodeType(n)} for n,_ in bake.direct_deformers(source)],
            'destination_stack':[{'node':n,'type':cmds.nodeType(n)} for n,_ in bake.direct_deformers(bake.proximity_wrap.mesh_shape(destination))]}
        if color_error:bake.error_colors(destination,vertex_error,error_limit)
        metadata=cmds.createNode('network',name=bs+'_hybridValidation')
        poses._string(metadata,'hybridBakeValidation',json.dumps(result))
        poses._message(destination,metadata,'destination')
        result['metadata']=metadata
        if not result['quality_pass'] and not keep_failed:
            raise RuntimeError('Hybrid error %.6g exceeds limit %.6g %s; candidate rolled back.' % (maximum,error_limit,record['units']))
    finally:
        if poses.edit_session():poses.finish_edit(False)
        cmds.currentTime(original_time)
        cmds.select(initial_selection,replace=True) if initial_selection else cmds.select(clear=True)
    return result
