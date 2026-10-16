"""Save separate all-garment BS/SKC review files with the original PRX toggle."""
import json
import os
from pathlib import Path
from maya import cmds
from tools import proximity_wrap as pw
FOLDER=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001')
assert os.getpid()==json.loads((FOLDER/'owned_launch.json').read_text())['pid']
manifest=json.loads((FOLDER/'manifest.json').read_text())
master=FOLDER/'Edward_all_PRX_candidates_TEST_v001.ma';assert not master.exists()
cmds.evaluationManager(mode='off');cmds.file(rename=str(master));cmds.file(save=True,type='mayaAscii',force=False,options='v=0;')
scenes={}
for label in ('BLENDSHAPE','SKIN'):
    cmds.file(str(master),open=True,force=True,prompt=False,executeScriptNodes=False)
    if label=='BLENDSHAPE':
        remove=[record['mesh'] for record in manifest['skin'].values()]+[record['skin'] for record in manifest['skin'].values()]
        records=manifest['blendshape']['outputs']
    else:
        remove=[manifest['blendshape'][key] for key in ('node','group','matrix')]+manifest['blendshape']['curves']
        records=manifest['skin']
    cmds.delete(list(dict.fromkeys(n for n in remove if cmds.objExists(n))))
    review=cmds.createNode('transform',name='Edward_PRX_Review')
    cmds.addAttr(review,ln='deformationVariant',at='enum',en='Original_PRX:'+('Shared_BlendShape' if label=='BLENDSHAPE' else 'SkinClusters'),keyable=True)
    cmds.addAttr(review,ln='comparisonScope',dt='string')
    cmds.setAttr(review+'.comparisonScope','All 23 PRX outputs; experimental approximation. Use deformationVariant for the original.',type='string',lock=True)
    for index in (0,1):
        condition=cmds.createNode('condition',name='AllPRXReview_visibility_%d'%index)
        cmds.connectAttr(review+'.deformationVariant',condition+'.firstTerm');cmds.setAttr(condition+'.secondTerm',index)
        cmds.setAttr(condition+'.operation',0);cmds.setAttr(condition+'.colorIfTrueR',1);cmds.setAttr(condition+'.colorIfFalseR',0)
        for wrap,item in manifest['items'].items():
            mesh=item['source'] if index==0 else records[wrap]['mesh']
            cmds.connectAttr(condition+'.outColorR',mesh+'.visibility',force=True)
    for a in ('translateX','translateY','translateZ','rotateX','rotateY','rotateZ','scaleX','scaleY','scaleZ','visibility'):
        cmds.setAttr(review+'.'+a,lock=True,keyable=False,channelBox=False)
    cmds.setAttr(review+'.deformationVariant',1)
    for side in ('L','R'):
        for limb in ('arm','leg'):cmds.setAttr(side+'_'+limb+'Settings_CTL.Ik_Fk',1)
    histories={wrap:cmds.ls(cmds.listHistory(r['mesh']) or [],type='proximityWrap') or [] for wrap,r in records.items()}
    assert not any(histories.values())
    assert len(cmds.ls(type='joint'))==852
    cmds.evaluationManager(mode='parallel');cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False)
    cmds.select(review,r=True)
    destination=FOLDER/('Edward_all_PRX_'+label+'_COMPARE_v001.ma');assert not destination.exists()
    cmds.file(rename=str(destination));cmds.file(save=True,type='mayaAscii',force=False,options='v=0;')
    scenes[label]={'path':str(destination),'bytes':destination.stat().st_size,'control':review,'attribute':'deformationVariant',
                   'outputs':{w:r['mesh'] for w,r in records.items()},'candidate_prx_history':histories,'joints':852,'default':1}
manifest['scenes']=scenes;manifest['master_scene']=str(master)
(FOLDER/'manifest.json').write_text(json.dumps(manifest,indent=2))
result={k:{a:v for a,v in s.items() if a not in ('outputs','candidate_prx_history')} for k,s in scenes.items()}
