import json,os
from pathlib import Path
from maya import cmds
assert os.getpid()==23404
folder=Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/all_prx_bakes_20261016_v001')
folder.mkdir(parents=True,exist_ok=True)
target=folder/'Edward_artist_baseline.ma';assert not target.exists()
before={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),
        'frame':cmds.currentTime(q=True),'selection':cmds.ls(sl=True,long=True)}
cmds.file(str(target),exportAll=True,type='mayaAscii',force=False,preserveReferences=True,options='v=0;')
after={'scene':cmds.file(q=True,sn=True),'modified':cmds.file(q=True,modified=True),
       'frame':cmds.currentTime(q=True),'selection':cmds.ls(sl=True,long=True)}
result={'source':str(target),'bytes':target.stat().st_size,'before':before,'after':after}
assert before==after
(folder/'snapshot.json').write_text(json.dumps(result,indent=2))
