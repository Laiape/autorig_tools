import json, os, sys
from pathlib import Path
from maya import cmds
from maya_tools.scripts.tools import bifrost_wrinkles as bw

WORK = Path(r'C:/proyectos/auto-rig/tmp/edward_wrinkles_20261015')
records = bw.export_setups()
(WORK / 'original_setups.json').write_text(json.dumps(records), encoding='utf-8')
result = {'pid': os.getpid(), 'scene': cmds.file(q=True, sn=True),
          'modified': cmds.file(q=True, modified=True), 'module': bw.__file__,
          'selection': cmds.ls(sl=True, long=True), 'frame': cmds.currentTime(q=True),
          'setups': [], 'controls': {}, 'blendshapes': []}
for rec in records:
    result['setups'].append({k:v for k,v in rec.items() if k not in ('patterns','rest','controls')})
    result['setups'][-1]['controls'] = [{k:v for k,v in f.items() if k != 'masks'} | {'regions': list(f['masks'])} for f in rec['controls']]
    result['setups'][-1]['patterns'] = {r: {'count': len(v), 'active':sum(abs(x)>1e-5 for x in v), 'min':min(v), 'max':max(v)} for r,v in rec['patterns'].items()}
for c in cmds.ls('*eyebrow*CTL','*lipCorner*CTL', 'C_nose*CTL', type='transform') or []:
    result['controls'][c] = {'translate': cmds.getAttr(c+'.translate'), 'rotate':cmds.getAttr(c+'.rotate'),
       'custom': {a: {'value':cmds.getAttr(c+'.'+a), 'incoming':cmds.listConnections(c+'.'+a,s=True,d=False,p=True)} for a in (cmds.listAttr(c,ud=True) or []) if cmds.getAttr(c+'.'+a,type=True) in ('double','float','long','enum','bool')}}
for n in cmds.ls(type='blendShape') or []:
    aliases=cmds.aliasAttr(n,q=True) or []
    if 'wrinkl' in n.lower() or any('wrinkl' in a.lower() or 'brow' in a.lower() for a in aliases):
        result['blendshapes'].append({'node':n,'aliases':aliases})
result['wrinkle_nodes'] = cmds.ls('*Wrinkl*','*wrinkl*')
