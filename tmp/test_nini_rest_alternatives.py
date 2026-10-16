import sys,json,math
from pathlib import Path
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
root=Path('C:/proyectos/auto-rig/autorig_tools');sys.path.insert(0,str(root))
from maya_tools.scripts.tools import dress_keepout_chains as tool
scene=root/'maya_tools/assets/Nini/scenes/Nini_dress_chains_v004.ma'
results=[]
poses=[((0,0,0),(0,0,0)),((0,15,18),(0,0,0)),((0,0,0),(0,15,18)),((0,14,15),(0,14,15)),((14,4,0),(-14,4,0)),((0,14,0),(0,0,0))]
for method in ('rebind','translation'):
    cmds.file(str(scene),open=True,force=True);cmds.evaluationManager(mode='off')
    data=json.loads(cmds.getAttr('NiniDress_Module_GRP.dressRigData'))
    if method=='rebind':
        for garment in data['garments']:
            sl=om.MSelectionList();sl.add(garment['skin']);fn=oma.MFnSkinCluster(sl.getDependNode(0))
            for path in fn.influenceObjects():
                if path.partialPathName() in data['joints']:
                    index=fn.indexForInfluenceObject(path)
                    cmds.setAttr(garment['skin']+'.bindPreMatrix[%s]'%index,*list(path.inclusiveMatrixInverse()),type='matrix')
    else:
        tool.compensate_rest_contacts(data)
        waist_inverse=om.MMatrix(cmds.getAttr(data['waist']+'.worldInverseMatrix[0]'))
        for joint in data['joints']:
            stem=joint.removesuffix('_JNT')
            local=om.MMatrix(cmds.getAttr(joint+'.worldMatrix[0]'))*waist_inverse
            follow=cmds.createNode('multMatrix',name=stem+'RestOrientation_MMT')
            cmds.setAttr(follow+'.matrixIn[0]',*list(local),type='matrix')
            cmds.connectAttr(data['waist']+'.worldMatrix[0]',follow+'.matrixIn[1]')
            dest=stem+'ParentSpace_MMT.matrixIn[0]';source=cmds.connectionInfo(dest,sourceFromDestination=True)
            blend=cmds.createNode('blendMatrix',name=stem+'TranslationOnly_BMT')
            cmds.connectAttr(follow+'.matrixSum',blend+'.inputMatrix')
            cmds.connectAttr(source,blend+'.target[0].targetMatrix')
            for comp in ('rotate','scale','shear'):cmds.setAttr(blend+'.target[0].'+comp+'Weight',0)
            cmds.disconnectAttr(source,dest);cmds.connectAttr(blend+'.outputMatrix',dest)
    rest={s:cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
    result={'method':method,'poses':[]}
    for i,pose in enumerate(poses):
        for s,delta in zip(('L','R'),pose):cmds.xform(s+'_ankleIk_CTL',ws=True,t=[a+b for a,b in zip(rest[s],delta)])
        contact=tool.signed_mesh_clearance('c_tunic_GEO',data['garments'][0]['region'],'c_body_GEO',surface_samples=True)
        result['poses'].append({'pose':i,'min_cm':contact['minimum_signed_clearance_cm'],'inside':contact['penetrating_vertices'],'uncertain':contact['uncertain_vertices']})
    results.append(result);print('ALTERNATIVE='+json.dumps(result),flush=True)
Path('C:/proyectos/auto-rig/tmp/nini_rest_alternatives.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
