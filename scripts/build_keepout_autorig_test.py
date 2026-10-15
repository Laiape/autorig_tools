"""Create a skirt proxy with the production matrix IK/FK leg modules.

Run in mayapy. Guides and build cache belong only to this experiment; no
character's guides, build settings or normal biped cache are overwritten.
The saved scene has no animation keys so feet/PVs can be manipulated directly.
"""
import json
import math
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
DIRECTORY=ROOT/'maya_tools/assets/KeepOutSkirt/experiments'
os.environ.setdefault('MAYA_SKIP_USERSETUP_PY','1')


def guides():
    from maya_tools.scripts.tools import muscle_keepout_skirt as skirt
    result={}
    for side,x in (('L',8),('R',-8)):
        names=[side+'_'+part+'_JNT' for part in ('hip','knee','ankle','ball','toe')]
        points=[(x,106,0),(x,56,2),(x,8,0),(x,4,10),(x,4,18)]
        for i,(name,point) in enumerate(zip(names,points)):
            result[name]={'isJoint':True,'joint_matrix':skirt._matrix(point),
                          'parent':names[i-1] if i else None}
        result[names[0]]['children']=names[1:]
        for name,point in (('legSettings',(x*3,108,0)),('bankOut',(x+(3 if x>0 else -3),4,10)),
                           ('bankIn',(x-(3 if x>0 else -3),4,10)),('heel',(x,4,-5))):
            result[side+'_'+name+'_LOCShape']={'isJoint':False,'isLocator':True,
                                             'locator_position':skirt._matrix(point)}
    return {'KeepOutSkirt':result}


def replace_body_proxy(data,cap,motion,end_matrix,leg_material):
    from maya import cmds
    from maya.api import OpenMaya as om, OpenMayaAnim as oma
    from maya_tools.scripts.tools import muscle_keepout_skirt as skirt
    name=cap['shape'].replace('ColliderShape','Body')
    base=skirt._node('joint',name+'Start_JNT',data['prefix']+'joints_GRP')
    end=skirt._node('joint',name+'End_JNT',data['prefix']+'joints_GRP')
    for joint in (base,end):
        cmds.setAttr(joint+'.inheritsTransform',False)
        cmds.setAttr(joint+'.segmentScaleCompensate',False)
    cmds.connectAttr(motion+'.worldMatrix[0]',base+'.offsetParentMatrix')
    blend=skirt._node('blendMatrix',name+'End_BMT')
    cmds.connectAttr(motion+'.worldMatrix[0]',blend+'.inputMatrix')
    cmds.connectAttr(end_matrix,blend+'.target[0].targetMatrix')
    for part in ('rotate','scale','shear'): cmds.setAttr(blend+'.target[0].'+part+'Weight',0)
    cmds.connectAttr(blend+'.outputMatrix',end+'.offsetParentMatrix')
    mesh=skirt._capsule_mesh(name+'_GEO',cap['radius'],cap['length'],
                             data['prefix']+'geometry_GRP',leg_material)
    cmds.xform(mesh,worldSpace=True,matrix=cmds.getAttr(motion+'.worldMatrix[0]'))
    skin=cmds.skinCluster([base,end],mesh,toSelectedBones=True,maximumInfluences=1,
                          normalizeWeights=1,name=name+'_SKC')[0]
    selection=om.MSelectionList(); selection.add(mesh)
    path=selection.getDagPath(0);path.extendToShape()
    vertices=om.MFnMesh(path).numVertices
    component=om.MFnSingleIndexedComponent()
    obj=component.create(om.MFn.kMeshVertComponent);component.addElements(range(vertices))
    selection=om.MSelectionList();selection.add(skin)
    fn=oma.MFnSkinCluster(selection.getDependNode(0))
    weights=om.MDoubleArray([value for i in range(vertices)
                            for value in ((1,0) if i<vertices//2 else (0,1))])
    fn.setWeights(path,obj,om.MIntArray([0,1]),weights,False)
    cmds.polySoftEdge(mesh,angle=180,constructionHistory=False)
    return mesh


def build():
    from maya import cmds
    from maya.api import OpenMaya as om
    from maya_tools.scripts.biped.autorig import leg_module_custom
    from maya_tools.scripts.utils import data_manager,guides_manager
    from maya_tools.scripts.tools import muscle_keepout_skirt as skirt
    if not cmds.about(batch=True): raise RuntimeError('Run this builder in mayapy.')
    cmds.optionVar(stringValue=('currentAssetRigName','Edward'))
    for plugin in ('matrixNodes','lookdevKit','MayaMuscle'):
        if not cmds.pluginInfo(plugin,query=True,loaded=True): cmds.loadPlugin(plugin,quiet=True)
    data=skirt.build_demo(animate=False)
    data['global']=cmds.rename(data['global'],'C_masterwalk_CTL')
    data['waist']=cmds.rename(data['waist'],'C_localHip_CTL')
    # Longer production-leg proportions need a wider margin between samples.
    cmds.setAttr(data['waist']+'.collisionMargin',3.3)
    global_scale=skirt._attribute(data['global'],'globalScale',1,.001)
    for axis in 'XYZ': cmds.connectAttr(global_scale,data['global']+'.scale'+axis)
    modules=skirt._node('transform','modules_GRP',data['prefix']+'technical_GRP')
    skeleton=skirt._node('transform','skel_GRP',data['prefix']+'technical_GRP')
    cmds.setAttr(skeleton+'.visibility',False)
    cache={'basic_structure':{'modules_GRP':modules,'skel_GRP':skeleton,
                              'masterwalk_ctl':data['global']},
           'spine_module':{'local_hip_ctl':data['waist']}}
    class SceneCache:
        def get_data(self,module,key): return cache.get(module,{}).get(key)
        def append_data(self,module,values): cache.setdefault(module,{}).update(values)
    guide_data=guides()
    guide_path=DIRECTORY/'KeepOutSkirt_autorig.guides'
    guide_path.write_text(json.dumps(guide_data,indent=2),encoding='utf-8')
    rigs={}
    with patch.object(data_manager,'DataExportBiped',SceneCache), \
         patch.object(guides_manager,'_load_guides_file',lambda character:(str(guide_path),guide_data)):
        for side in ('L','R'):
            rig=leg_module_custom.LegModule()
            rig.make(side,skinning_jnts=5)
            rigs[side]=rig
            print('PRODUCTION_LEG_BUILT='+side,flush=True)
    (DIRECTORY/'KeepOutSkirt_autorig.cache').write_text(json.dumps(cache,indent=2),encoding='utf-8')
    old_legs=data['legs']
    data['legs']={}
    for side,rig in rigs.items():
        data['legs'][side]={'thigh':rig.fk_controllers[0],'knee':rig.fk_controllers[1],
                            'ik':rig.ik_controllers[0],'pv':rig.pv_ctl,'settings':rig.settings_ctl,
                            'root_ik':rig.root_ik_ctl}
        for index,label in ((0,'thigh'),(1,'calf')):
            cap=next(cap for cap in data['capsules'] if cap['shape']==data['prefix']+side+'_'+label+'ColliderShape')
            start=rig.blend_matrices[index][0]+'.outputMatrix'
            endpoint=rig.blend_matrices[index+1][0]+'.outputMatrix'
            motion=skirt._follow(data['prefix']+side+'_'+label+'Motion_GRP',(0,0,0),start,
                                   data['prefix']+'technical_GRP')
            correction=om.MTransformationMatrix()
            correction.setRotation(om.MEulerRotation(0,0,math.pi/2*(1 if side=='L' else -1)))
            skirt._set_matrix(motion.replace('_GRP','_MMT')+'.matrixIn[0]',list(correction.asMatrix()))
            cap['driver']=motion
            distance=skirt._node('distanceBetween',data['prefix']+side+'_'+label+'Length_DST')
            cmds.connectAttr(start,distance+'.inMatrix1');cmds.connectAttr(endpoint,distance+'.inMatrix2')
            normalize=skirt._node('multiplyDivide',data['prefix']+side+'_'+label+'Length_MDV')
            cmds.setAttr(normalize+'.operation',2)
            cmds.connectAttr(distance+'.distance',normalize+'.input1X')
            cmds.connectAttr(global_scale,normalize+'.input2X')
            cmds.connectAttr(normalize+'.outputX',cap['shape']+'.length')
            cap['length']=cmds.getAttr(cap['shape']+'.length')
            holder=data['prefix']+side+'_'+label+'Collider_MMT'
            cmds.connectAttr(motion+'.worldMatrix[0]',holder+'.matrixIn[1]',force=True)
            old_proxy=data['prefix']+side+'_'+label+'Proxy_GRP'
            cmds.delete(old_proxy)
            replace_body_proxy(data,cap,motion,endpoint,data['prefix']+'legs_SG')
        cmds.delete(data['prefix']+side+'_thigh_GRP',data['prefix']+side+'_knee_GRP')
        # Retain the production controls; tuck construction/bendy handles away.
        for ctl in cmds.ls(side+'_leg*Bendy_CTL',type='transform'):
            for shape in cmds.listRelatives(ctl,shapes=True) or []: cmds.setAttr(shape+'.visibility',False)
        for shape in cmds.listRelatives(rig.ik_controllers[0],shapes=True) or []:
            cmds.setAttr(shape+'.overrideEnabled',True)
            cmds.setAttr(shape+'.overrideRGBColors',True)
            cmds.setAttr(shape+'.overrideColorRGB',*( (.15,.6,1) if side=='L' else (1,.25,.2)),type='double3')
        # A simple foot proxy follows the blended ankle, so IK/FK both work.
        foot_group=skirt._follow(side+'_footProxy_GRP',(0,0,0),rig.blend_matrices[2][0]+'.outputMatrix',
                                  data['prefix']+'geometry_GRP')
        foot=cmds.polyCube(name=side+'_footProxy_GEO',width=12,height=6,depth=9,constructionHistory=False)[0]
        cmds.parent(foot,foot_group,relative=True)
        cmds.sets(foot,edit=True,forceElement=data['prefix']+'legs_SG')
    data['autorig_module']='maya_tools.scripts.biped.autorig.leg_module_custom.LegModule.make'
    cmds.setAttr(data['root']+'.demoData',json.dumps(data),type='string')
    cmds.setAttr(data['root']+'.rigNotes','Production matrix IK/FK legs, five skin joints per segment. '
                 'Move L_ankleIk_CTL / R_ankleIk_CTL and the legPv controls. '
                 'L_legSettings_CTL / R_legSettings_CTL: Ik_Fk (0 IK / 1 FK). '
                 'C_localHip_CTL: waist and collisionEnable / collisionBlend / collisionMargin. '
                 'No animation keys; neutral pose ready for manual tests.',type='string')
    skirt.smooth_skin_weights(data)
    return data,rigs


def main():
    import maya.standalone
    maya.standalone.initialize(name='python')
    from maya import cmds
    from maya_tools.scripts.tools import muscle_keepout_skirt as skirt
    DIRECTORY.mkdir(parents=True,exist_ok=True)
    data,rigs=build()
    rest={side:cmds.xform(rig.ik_controllers[0],query=True,worldSpace=True,translation=True)
          for side,rig in rigs.items()}
    frames=[1,25,49,73,97]
    poses=[((0,0,0),(0,0,0)),((0,30,32),(0,0,0)),((0,0,0),(0,30,32)),
           ((0,28,32),(0,28,32)),((18,5,0),(-18,5,0))]
    for frame,pose in zip(frames,poses):
        for side,delta in zip(('L','R'),pose):
            ctl=rigs[side].ik_controllers[0]
            cmds.xform(ctl,worldSpace=True,translation=[p+d for p,d in zip(rest[side],delta)])
            cmds.setKeyframe(ctl,attribute=['translateX','translateY','translateZ'],time=frame)
    cmds.currentTime(1)
    report=skirt.validate_demo(data,frames=frames,repeats=1)
    report.pop('scheduling_graph',None)
    report['autorig_module']=data['autorig_module']
    report['ik_handles']=cmds.ls(type='ikHandle') or []
    # Remove only the test animation, and restore the neutral IK feet.
    curves=cmds.ls(type='animCurve') or []
    if curves: cmds.delete(curves)
    for side,rig in rigs.items(): cmds.xform(rig.ik_controllers[0],worldSpace=True,translation=rest[side])
    cmds.currentTime(1);cmds.evaluationManager(mode='parallel')
    cmds.playbackOptions(minTime=1,maxTime=120,animationStartTime=1,animationEndTime=120)
    report['saved_animation_curves']=cmds.ls(type='animCurve') or []
    version=1
    while (DIRECTORY/'KeepOutSkirt_autorig_v{:03d}.ma'.format(version)).exists(): version+=1
    scene=DIRECTORY/'KeepOutSkirt_autorig_v{:03d}.ma'.format(version)
    report['scene']=str(scene)
    report_path=DIRECTORY/'autorig_evaluation_report_v{:03d}.json'.format(version)
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    cmds.select(rigs['L'].ik_controllers[0])
    cmds.file(rename=str(scene));cmds.file(save=True,type='mayaAscii')
    print('AUTORIG_RESULT='+json.dumps({k:v for k,v in report.items() if k not in ('muscle_scheduling','cycle_clusters')}),flush=True)
    maya.standalone.uninitialize()
    if not report['passed']: raise SystemExit(2)


if __name__=='__main__': main()
