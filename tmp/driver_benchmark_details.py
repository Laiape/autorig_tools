import json
from pathlib import Path
from maya import cmds
result={}
for n in ('cuerpo_base','cuerpo_base_poseCorrectives_BLS_driver','cabeza_high','EdwardWrinklesGraphShape','EdwardWrinkles_PrimaryWorld'):
    result[n]={'type':cmds.nodeType(n),'matrix':cmds.xform(n,q=True,matrix=True,worldSpace=True) if cmds.nodeType(n)=='transform' else None,'inputs':cmds.listConnections(n,s=True,d=False,c=True,p=True),'outputs':cmds.listConnections(n,s=False,d=True,c=True,p=True)}
result['body_targets']={a:cmds.getAttr('cuerpo_base_poseCorrectives_BLS.'+a,multiIndices=True) for a in ('weight','inputTarget')}
result['panels']={p:{'visible':cmds.control(p,q=True,visible=True),'camera':cmds.modelEditor(p,q=True,camera=True),'width':cmds.control(p,q=True,w=True),'height':cmds.control(p,q=True,h=True)} for p in cmds.getPanel(type='modelPanel')}
Path('C:/proyectos/auto-rig/tmp/driver_benchmark_details.json').write_text(json.dumps(result,indent=2,default=str))
