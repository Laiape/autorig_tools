"""Account for stored mesh originals, XGen data and material networks separately."""
import hashlib
import json
from pathlib import Path
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/full_audit_20261015_v001'
catalog=json.loads((FOLDER/'catalog.json').read_text())
cmds.file((FOLDER.parent/'driver_routing_20261015_v001/Edward_baseline.mb').as_posix(),open=True,force=True,prompt=False,executeScriptNodes=False)
cmds.evaluationManager(mode='off')
mesh_shapes=[m['path'] for m in catalog['meshes']]
mesh_parents=[p for s in mesh_shapes for p in cmds.listRelatives(s,parent=True,fullPath=True) or []]
shader_types={'lambert','standardSurface','openPBRSurface','particleCloud','shadingEngine','materialInfo','aiStandardSurface','aiStandardHair','file','place2dTexture','bump2d'}
groups=[('stored_polygon_meshes',list(set(mesh_shapes+mesh_parents))),
        ('xgen_nodes',[n for n,r in catalog['nodes'].items() if r['type'] in {'xgmSplineBase','xgmSplineDescription'}]),
        ('materials_and_file_nodes',[n for n,r in catalog['nodes'].items() if r['type'] in shader_types])]
rows=[]
for label,names in groups:
    cmds.select(names,replace=True,noExpand=True)
    path=FOLDER/'storage_payloads'/(label+'.mb')
    cmds.file(path.as_posix(),exportSelectedStrict=True,type='mayaBinary',force=True)
    rows.append(dict(label=label,nodes=len(names),bytes=path.stat().st_size,file=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
(FOLDER/'model_storage_extra.json').write_text(json.dumps({'payloads':rows,'meaning':'Stored native payloads, distinct from evaluated baked model; strict export omits external dependencies, not additive to other exports or RAM.'},indent=2),encoding='utf-8')
print('EXTRA_MODEL_STORAGE_COMPLETE',flush=True)
