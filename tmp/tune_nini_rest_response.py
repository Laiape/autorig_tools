import sys,json,math
from pathlib import Path
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
root=Path('C:/proyectos/auto-rig/autorig_tools');sys.path.insert(0,str(root))
from maya_tools.scripts.tools import dress_keepout_chains as tool
cmds.file(str(root/'maya_tools/assets/Nini/scenes/Nini_dress_chains_v004.ma'),open=True,force=True)
cmds.evaluationManager(mode='off')
data=json.loads(cmds.getAttr('NiniDress_Module_GRP.dressRigData'))
records=tool.compensate_rest_contacts(data)
gains=[]
for record in records:
    clamp=record['clamp'];destinations=cmds.listConnections(clamp+'.outputR',source=False,destination=True,plugs=True) or []
    node=cmds.createNode('multDoubleLinear',name=record['station']+'RestResponse_MDL')
    cmds.connectAttr(clamp+'.outputR',node+'.input1')
    for destination in destinations:
        cmds.disconnectAttr(clamp+'.outputR',destination);cmds.connectAttr(node+'.output',destination)
    gains.append(node)
rest={s:cmds.xform(s+'_ankleIk_CTL',q=True,ws=True,t=True) for s in ('L','R')}
poses=[((0,0,0),(0,0,0)),((0,15,18),(0,0,0)),((0,0,0),(0,15,18)),((0,14,15),(0,14,15)),((14,4,0),(-14,4,0)),((0,14,0),(0,0,0))]
result=[]
for gain in (1.02,1.05,1.1,1.15,1.25):
    for node in gains:cmds.setAttr(node+'.input2',gain)
    current={'gain':gain,'poses':[]}
    for i,pose in enumerate(poses):
        for s,delta in zip(('L','R'),pose):cmds.xform(s+'_ankleIk_CTL',ws=True,t=[a+b for a,b in zip(rest[s],delta)])
        contact=tool.signed_mesh_clearance('c_tunic_GEO',data['garments'][0]['region'],'c_body_GEO',surface_samples=True)
        current['poses'].append({'pose':i,'minimum_cm':contact['minimum_signed_clearance_cm'],'inside':contact['penetrating_vertices'],'uncertain':contact['uncertain_vertices']})
    current['passed']=all(not p['inside'] and not p['uncertain'] for p in current['poses'])
    result.append(current);print('GAIN_RESULT='+json.dumps(current),flush=True)
    if current['passed']:break
Path('C:/proyectos/auto-rig/tmp/nini_rest_response_tuning.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
