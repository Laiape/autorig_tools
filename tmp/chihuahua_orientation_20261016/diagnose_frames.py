import json
from pathlib import Path
import maya.cmds as cmds
base=Path('C:/proyectos/auto-rig/tmp/chihuahua_orientation_20261016')
guides=json.loads((base/'exported.json').read_text())['result']['joint_matrices']
rows=[]
for node in cmds.ls('*_CTL',type='transform')+cmds.ls('*Skinning_JNT',type='joint'):
 source=node.replace('Skinning_JNT','_JNT').replace('Fk_CTL','_JNT').replace('eyeDirect_CTL','eye_JNT').replace('_CTL','_JNT')
 if source in guides and ('Fk_CTL' in node or 'Skinning_JNT' in node or any(token in node for token in ('eyeDirect','ear'))):
  actual=cmds.xform(node,q=True,ws=True,m=True)
  rows.append({'node':node,'source':source,'error':max(abs(a-b) for a,b in zip(actual,guides[source]))})
result=sorted(rows,key=lambda row:row['error'],reverse=True)[:12]
