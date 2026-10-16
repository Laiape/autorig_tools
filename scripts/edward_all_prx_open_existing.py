"""Version the old belt review, then open the requested all-PRX comparison.

Only the two explicitly owned review windows are eligible. Artist Maya is not.
"""
import json
import os
from pathlib import Path
import traceback
from maya import cmds,mel
ROOT=Path(r'C:/proyectos/auto-rig')
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001'
OLD=ROOT/'maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001'
labels={7248:'BLENDSHAPE',55092:'SKIN'}
assert os.getpid() in labels, 'Only the owned comparison windows may be updated'
label=labels[os.getpid()]
manifest=json.loads((FOLDER/'manifest.json').read_text());record=manifest['scenes'][label]
current=Path(cmds.file(q=True,sn=True)).resolve()
assert current.parent==OLD.resolve() and current.name==('Edward_belts_'+label+'_COMPARE_v001.ma'), 'Do not replace another loaded scene'
backup=FOLDER/('Edward_belt_'+label+'_before_all_PRX_v001.ma');assert not backup.exists()
before={'scene':str(current),'modified':cmds.file(q=True,modified=True),'frame':cmds.currentTime(q=True),
        'selection':cmds.ls(sl=True,long=True)}
# Preserve the exact current artist review, including any keys/geometry edits.
cmds.file(str(backup),exportAll=True,type='mayaAscii',force=False,preserveReferences=True,options='v=0;')
assert cmds.file(q=True,modified=True)==before['modified']
controls={}
for node in cmds.ls('*_CTL',type='transform') or []:
    for attr in cmds.listAttr(node,keyable=True,scalar=True) or []:
        plug=node+'.'+attr
        if cmds.getAttr(plug,settable=True):
            value=cmds.getAttr(plug)
            if isinstance(value,(bool,int,float)):controls[plug]=value
backup_record={'pid':os.getpid(),'backup':str(backup),'bytes':backup.stat().st_size,'before':before,'free_control_values':controls}
(FOLDER/('previous_review_'+label+'.json')).write_text(json.dumps(backup_record,indent=2))
cmds.evaluationManager(mode='off');cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False)
cmds.file(record['path'],open=True,force=True,prompt=False,executeScriptNodes=False)
restored=[]
for plug,value in controls.items():
    if cmds.objExists(plug) and cmds.getAttr(plug,settable=True):
        cmds.setAttr(plug,value);restored.append(plug)
cmds.currentTime(before['frame'],edit=True)
cmds.evaluationManager(mode='parallel')
mel.eval('setNamedPanelLayout "Single Perspective View";')
cmds.modelEditor('modelPanel4',e=True,displayAppearance='smoothShaded',displayTextures=False,rendererName='vp2Renderer',shadows=False,grid=False)
cmds.select(list(record['outputs'].values()),r=True);cmds.viewFit('persp',fitFactor=.8,animate=False)
cmds.select(record['control'],r=True)
result={'success':True,'pid':os.getpid(),'label':label,'scene':cmds.file(q=True,sn=True),
        'backup':str(backup),'selector':cmds.getAttr(record['control']+'.'+record['attribute']),
        'output_count':len(record['outputs']),'visible_candidates':sum(bool(cmds.getAttr(m+'.visibility')) for m in record['outputs'].values()),
        'joints':len(cmds.ls(type='joint')),'restored_free_control_values':len(restored),
        'evaluation':cmds.evaluationManager(q=True,mode=True),'selection':cmds.ls(sl=True)}
(FOLDER/('artist_window_'+label+'_ready.json')).write_text(json.dumps(result,indent=2))
