import copy, json, os
from pathlib import Path
from maya import cmds
from maya_tools.scripts.tools import bifrost_wrinkles as bw, rig_performance as rp

ROOT=Path(r'C:/proyectos/auto-rig')
WORK=ROOT/'tmp/edward_wrinkles_20261015'
assert os.getpid()==42096
assert cmds.file(q=True,sn=True).endswith('/Edward_working_v003.mb')
backup=WORK/'Before_Edward_FourWrinkles.mb'
if backup.exists():
    raise RuntimeError('The backup already exists.')
cmds.file(str(backup),exportAll=True,type='mayaBinary',preserveReferences=True,force=False)
records=bw.export_setups()
record=next(r for r in records if r['prefix']=='EdwardWrinkles')
original=copy.deepcopy(record)
details=rp.export_detail_modes()
(WORK/'original_detail_modes.json').write_text(json.dumps(details,indent=2))
removed=[]
for region in ('Eyes','Chin'):
    record['patterns'][region]=[0.0]*record['vertices']
    record['settings'][region]=0.0
fields=[]
for field in record['controls']:
    for region in ('Eyes','Chin'):
        field['masks'].pop(region,None)
    if field['masks']:
        fields.append(field)
    else:
        removed.append(field['controller'])
record['controls']=fields
assert record['patterns']['Forehead']==original['patterns']['Forehead']
assert record['patterns']['Cheeks']==original['patterns']['Cheeks']
assert record['patterns']['Nose']==original['patterns']['Nose']
assert record['rest']==original['rest']
cmds.undoInfo(openChunk=True,chunkName='Edward four wrinkle expressions')
try:
    built=bw.import_setups([record],replace_existing=True)[0]
    rp.restore_detail_modes(details)
    for c in removed:
        for a in ('wrinkleDepth','wrinkleValue'):
            p=c+'.'+a
            if cmds.objExists(p) and not cmds.listConnections(p,s=True,d=True):
                cmds.deleteAttr(p)
    # Disabled legacy regions stay in the portable schema, outside artist channels.
    for region in ('Eyes','Chin'):
        cmds.setAttr(built['settings']+'.'+region,keyable=False,channelBox=False,lock=True)
finally:
    cmds.undoInfo(closeChunk=True)
updated=bw.export_setups()
(WORK/'updated_setups.json').write_text(json.dumps(updated),encoding='utf-8')
result={'backup':str(backup),'active_regions':['Forehead (brow up and in)','Nose (brow down)','Cheeks (smile)'],
 'removed_regions':['Eyes','Chin'],'remaining_local_controls':len(record['controls']),
 'removed_controls':[c.rsplit('|',1)[-1] for c in removed],
 'regional_vertices':len(built['regional_support']['active'])}
