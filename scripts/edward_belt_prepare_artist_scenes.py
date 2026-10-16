"""Create separate blendshape and skin review scenes without touching artist Maya."""
import json
import os
from pathlib import Path
from maya import cmds
FOLDER=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001')
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid']
manifest=json.loads((FOLDER/'manifest.json').read_text())
master=FOLDER/'Edward_belt_all_candidates_TEST_v002.ma'
assert not master.exists()
cmds.evaluationManager(mode='off')
cmds.file(rename=str(master));cmds.file(save=True,type='mayaAscii',force=False,options='v=0;')
scenes={}
for label,keep,enum,notes in (
    ('BLENDSHAPE',('blendshape_only_shared','blendshape_only_separate'),
     'Original_PRX:Shared_BlendShape:Separate_BlendShapes',
     'Experimental FK pose targets. New combinations, IK and scale are not certified. Use beltVariant to compare the original.'),
    ('SKIN',('skin_only',),'Original_PRX:SkinClusters',
     'Experimental fitted LBS skinClusters, max eight nonzero weights per vertex. Use beltVariant to compare the original.'),
):
    cmds.file(str(master),open=True,force=True,prompt=False,executeScriptNodes=False)
    review=manifest['review']['control']
    # Remove only our earlier comparison visibility network, preserving every
    # original deformer and rig node in both review files.
    conditions=cmds.listConnections(review+'.beltVariant',s=False,d=True,type='condition') or []
    for mesh in list(manifest['joints'])+[m for v in manifest['variants'].values() for m in v['meshes'].values()]:
        plug=mesh+'.visibility'
        source=cmds.connectionInfo(plug,sfd=True)
        if source:cmds.disconnectAttr(source,plug)
        cmds.setAttr(plug,True)
    cmds.delete(conditions+[review])
    for kind,variant in manifest['variants'].items():
        if kind in keep:continue
        owned=list(variant['meshes'].values())+list(variant.get('skins',{}).values())+list(variant.get('blendshapes',{}).values())+variant.get('curves',[])
        owned+=[variant[n] for n in ('global_group','global_motion_node') if n in variant]
        owned=list(dict.fromkeys(n for n in owned if cmds.objExists(n)))
        if owned:cmds.delete(owned)
    review=cmds.createNode('transform',name='Edward_BeltBlendshape_Review')
    cmds.addAttr(review,ln='beltVariant',at='enum',en=enum,keyable=True)
    cmds.addAttr(review,ln='trialNotes',dt='string');cmds.setAttr(review+'.trialNotes',notes,type='string',lock=True)
    groups=[list(manifest['joints'])]+[list(manifest['variants'][k]['meshes'].values()) for k in keep]
    for index,meshes in enumerate(groups):
        node=cmds.createNode('condition',name='BeltReview_visibility_%d'%index)
        cmds.connectAttr(review+'.beltVariant',node+'.firstTerm');cmds.setAttr(node+'.secondTerm',index)
        cmds.setAttr(node+'.operation',0);cmds.setAttr(node+'.colorIfTrueR',1);cmds.setAttr(node+'.colorIfFalseR',0)
        for mesh in meshes:cmds.connectAttr(node+'.outColorR',mesh+'.visibility')
    for channel in ('translateX','translateY','translateZ','rotateX','rotateY','rotateZ','scaleX','scaleY','scaleZ','visibility'):
        cmds.setAttr(review+'.'+channel,lock=True,keyable=False,channelBox=False)
    cmds.setAttr(review+'.beltVariant',1)
    if label=='BLENDSHAPE':
        for s in ('L','R'):
            for limb in ('arm','leg'):cmds.setAttr(s+'_'+limb+'Settings_CTL.Ik_Fk',1)
    cmds.evaluationManager(mode='parallel');cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False)
    cmds.select(review,r=True)
    destination=FOLDER/('Edward_belts_'+label+'_COMPARE_v001.ma')
    assert not destination.exists()
    cmds.file(rename=str(destination));cmds.file(save=True,type='mayaAscii',force=False,options='v=0;')
    scenes[label]={'path':str(destination),'bytes':destination.stat().st_size,'review_control':review,
                   'attribute':'beltVariant','enum':enum,'default':1,'variants':list(keep),'notes':notes}
manifest['artist_comparison_scenes']=scenes
(FOLDER/'manifest.json').write_text(json.dumps(manifest,indent=2))
result=scenes
