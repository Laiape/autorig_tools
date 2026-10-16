"""Save a reversible native review scene, with the original PRX selected."""
import json
import os
from pathlib import Path
from maya import cmds
from tools import proximity_wrap as pw
FOLDER=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001')
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid'], 'Use the owned trial process'
manifest=json.loads((FOLDER/'manifest.json').read_text())
destination=FOLDER/'Edward_belt_blendshape_TEST_v001.ma'
assert not destination.exists(), 'Never overwrite a review scene'
review=cmds.createNode('transform',name='Edward_BeltBlendshape_Review')
cmds.addAttr(review,ln='beltVariant',at='enum',en='Original_PRX:Shared_BlendShape:Separate_BlendShapes:SkinPlusShared_BS:SkinPlusSeparate_BS',keyable=True)
cmds.addAttr(review,ln='trialVerdict',dt='string')
cmds.setAttr(review+'.trialVerdict','EXPERIMENTAL: captured poses pass; held-out deformation fails. Keep original PRX for production.',type='string',lock=True)
groups=[list(manifest['joints'])]+[list(manifest['variants'][k]['meshes'].values()) for k in ('blendshape_only_shared','blendshape_only_separate','shared','separate')]
visibility=[]
for index,meshes in enumerate(groups):
    node=cmds.createNode('condition',name='EdwardBeltReview_visibility_%d'%index)
    cmds.connectAttr(review+'.beltVariant',node+'.firstTerm')
    cmds.setAttr(node+'.secondTerm',index);cmds.setAttr(node+'.operation',0)
    cmds.setAttr(node+'.colorIfTrueR',1);cmds.setAttr(node+'.colorIfFalseR',0)
    for mesh in meshes:
        visibility.append({'mesh':mesh,'value':cmds.getAttr(mesh+'.visibility'),
                           'source':cmds.connectionInfo(mesh+'.visibility',sfd=True)})
        cmds.connectAttr(node+'.outColorR',mesh+'.visibility',force=True)
for channel in ('translateX','translateY','translateZ','rotateX','rotateY','rotateZ','scaleX','scaleY','scaleZ','visibility'):
    cmds.setAttr(review+'.'+channel,lock=True,keyable=False,channelBox=False)
history={kind:{b:{'proximity_wraps':cmds.ls(cmds.listHistory(mesh) or [],type='proximityWrap') or [],
                 'skins':cmds.ls(cmds.listHistory(mesh) or [],type='skinCluster') or [],
                 'blendshapes':cmds.ls(cmds.listHistory(mesh) or [],type='blendShape') or []}
               for b,mesh in variant['meshes'].items()} for kind,variant in manifest['variants'].items()}
assert not any(info['proximity_wraps'] for meshes in history.values() for info in meshes.values())
manifest['review']={'scene':str(destination),'control':review,'attribute':'beltVariant','default':0,
                    'enum':'Original_PRX:Shared_BlendShape:Separate_BlendShapes:SkinPlusShared_BS:SkinPlusSeparate_BS',
                    'original_visibility':visibility,'candidate_history':history,'approved':False}
cmds.evaluationManager(mode='parallel');cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False)
cmds.select(review,r=True)
cmds.file(rename=str(destination))
cmds.file(save=True,type='mayaAscii',force=False,options='v=0;')
manifest['review']['bytes']=destination.stat().st_size
(FOLDER/'manifest.json').write_text(json.dumps(manifest,indent=2))
result=manifest['review']
