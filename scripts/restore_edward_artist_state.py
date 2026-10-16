"""Restore the protected artist snapshot after all experiments, without saving it."""
import json
from pathlib import Path
from maya import cmds, mel
ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'maya_tools/assets/Edward/experiments/full_audit_20261015_v001'
snapshot=FOLDER.parent/'driver_routing_20261015_v001/Edward_baseline.mb'
inventory=json.loads((snapshot.parent/'inventory.json').read_text())
cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False)
cmds.file(snapshot.as_posix(),open=True,force=True,prompt=False,executeScriptNodes=False)
cmds.evaluationManager(mode='parallel')
cmds.evaluator(name='cache',enable=False);cmds.evaluator(name='deformer',enable=False)
cmds.currentTime(inventory['frame'])
mel.eval('setNamedPanelLayout "Single Perspective View";')
cmds.select(inventory['selection'],replace=True)
cmds.refresh(force=True)
routes=[]
for n,p in inventory['prx'].items():
    for index,driver in p['drivers'].items():
        for attr in ('driverGeometry','driverBindGeometry'):
            plug=n+'.drivers['+index+'].'+attr
            routes.append({'plug':plug,'expected':driver[attr],'actual':cmds.connectionInfo(plug,sourceFromDestination=True)})
head='cabeza_high_Shape.inMesh'
expected=inventory['mesh']['cabeza_high']['shapes']['|Edward|geo_GRP|FINAL|cabeza_geo|cabeza_high|cabeza_high_Shape']['input']
routes.append({'plug':head,'expected':expected,'actual':cmds.connectionInfo(head,sourceFromDestination=True)})
if any(r['actual']!=r['expected'] for r in routes):raise RuntimeError('Artist routing did not restore')
if cmds.ls('rigBenchmarkTemporaryCurve*'):raise RuntimeError('Temporary animation survived snapshot restoration')
cmds.file(rename=inventory['scene']);cmds.file(modified=inventory['modified'])
result={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),
        'frame':cmds.currentTime(q=True),'selection':cmds.ls(sl=True,long=True),
        'evaluation':'Parallel CPU; cache OFF, GPU deformer OFF, conservative mode after collar quality comparison',
        'wrinkle_final_source':cmds.connectionInfo(head,sourceFromDestination=True),
        'all_original_prx_and_head_routes_match':True,'temporary_animation_remaining':False,
        'original_file_overwritten':False,'snapshot':str(snapshot)}
(FOLDER/'artist_state_restored.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
