import json
from pathlib import Path
from maya import cmds
import sys
root=Path('C:/proyectos/auto-rig')
sys.path.insert(0,str(root/'autorig_tools'))
if not cmds.commandPort('localhost:7002',query=True):
    cmds.commandPort(name='localhost:7002',sourceType='python',echoOutput=True)
folder=root/'maya_tools/assets/Edward/experiments/driver_routing_20261015_v001'
inventory=json.loads((folder/'inventory.json').read_text())
cmds.evaluator(name='cache',enable=False)
cmds.evaluator(name='deformer',enable=False)
cmds.file((folder/'Edward_baseline.mb').as_posix(),open=True,force=True,prompt=False,executeScriptNodes=False)
cmds.currentTime(inventory['frame'])
cmds.select(inventory['selection'],replace=True)
cmds.file(rename=inventory['scene']);cmds.file(modified=inventory['modified'])
cmds.evaluationManager(mode='parallel')
(root/'tmp/edward_recovered.json').write_text(json.dumps({'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),'selection':cmds.ls(sl=True),'frame':cmds.currentTime(q=True)}))
