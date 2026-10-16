import numpy as np
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
from tools import proximity_wrap as pw, proximity_bake as pb
from collections import Counter
def safe(fn):
    try: return fn()
    except Exception as e: return {'error':str(e)}
meshes=[]
for shape in cmds.ls(type='mesh',noIntermediate=True,long=True) or []:
    stack=pw.direct_deformers(shape,('skinCluster','proximityWrap','wrap','blendShape','deltaMush','ffd'))
    meshes.append({'shape':shape,'vertices':cmds.polyEvaluate(shape,vertex=True),'stack':[(n,cmds.nodeType(n)) for n,_ in stack]})
wraps=[]
for typ in ('proximityWrap','wrap'):
    for w in cmds.ls(type=typ) or []:
        wraps.append({'name':w,'type':typ,'geometry':cmds.deformer(w,q=True,g=True), 'connections':cmds.listConnections(w,s=True,d=False,p=True),'envelope':cmds.getAttr(w+'.envelope')})
controls=[]
for t in cmds.ls('*CTL',type='transform') or []:
    vals={}
    for a in cmds.listAttr(t,keyable=True) or []:
        p=t+'.'+a
        vals[a]={'v':safe(lambda:cmds.getAttr(p)),'settable':safe(lambda:cmds.getAttr(p,settable=True)),'in':cmds.listConnections(p,s=True,d=False,p=True) or []}
    controls.append({'node':t,'attrs':vals})
bs=[]
for b in cmds.ls(type='blendShape') or []:
    bs.append({'node':b,'geometry':cmds.deformer(b,q=True,g=True),'envelope':cmds.getAttr(b+'.envelope'),'aliases':cmds.aliasAttr(b,q=True),'weights':[(i,cmds.getAttr(b+'.weight[%s]'%i),cmds.listConnections(b+'.weight[%s]'%i,s=True,d=False,p=True)) for i in cmds.getAttr(b+'.weight',multiIndices=True) or []]})
result={'scene':cmds.file(q=True,sn=True),'units':cmds.currentUnit(q=True,linear=True),'frame':cmds.currentTime(q=True),'meshes':meshes,'wraps':wraps,'controls':controls,'blendshapes':bs,'unknown':cmds.ls(type='unknown'),'scripts_path':pb.__file__,'node_types':dict(Counter(cmds.nodeType(n) for n in cmds.ls()))}
(WORK/'inventory.json').write_text(json.dumps(result,indent=2,default=str))
result={'scene':result['scene'],'wraps':wraps,'wrapped_meshes':[m for m in meshes if any(t in ('wrap','proximityWrap') for _,t in m['stack'])],'blendshapes':bs,'controls':len(controls),'unknown':result['unknown']}
