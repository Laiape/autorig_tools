"""Measure the imported scalp's point animation data separately from rig modules."""
import hashlib
import json
from pathlib import Path
from maya import cmds
from maya.api import OpenMaya as om, OpenMayaAnim as oma

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/full_audit_20261015_v001'
catalog=json.loads((FOLDER/'catalog.json').read_text())
curves=[n for n,r in catalog['nodes'].items() if r['type']=='animCurveTL']
destinations={e[1] for e in catalog['edges'] if e[0] in set(curves)}
if destinations!={'scalp_cabello_Shape'}:raise RuntimeError('Unexpected TL ownership: '+str(destinations))
keys=[]
for n in curves:
    sl=om.MSelectionList();sl.add(n);keys.append(oma.MFnAnimCurve(sl.getDependNode(0)).numKeys)
path=FOLDER/'storage_payloads/scalp_point_animation_curves.mb'
selection=cmds.ls(sl=True,long=True) or []
try:
    cmds.evaluator(name='deformer',enable=False)
    cmds.select(curves,replace=True,noExpand=True)
    cmds.file(path.as_posix(),exportSelectedStrict=True,type='mayaBinary',force=True)
finally:
    cmds.select(selection,replace=True) if selection else cmds.select(clear=True)
result={'curves':len(curves),'shape':'scalp_cabello_Shape','vertices':1817,
        'keys_total':sum(keys),'keys_per_curve_min':min(keys),'keys_per_curve_max':max(keys),
        'input_connections':cmds.listConnections(curves,source=True,destination=False,plugs=True) or [],
        'shape_consumers':cmds.listConnections('scalp_cabello_Shape',source=False,destination=True,plugs=True) or [],
        'bytes':path.stat().st_size,'file':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'meaning':'Native strict payload for imported per-point scalp curves. Separate from baked polygon geometry and from module SDK curves; not process RAM.'}
(FOLDER/'scalp_payload.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
