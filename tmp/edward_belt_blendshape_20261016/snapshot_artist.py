from pathlib import Path
import json, os
from maya import cmds
assert os.getpid() == 23404
folder = Path(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/experiments/belt_blendshape_20261016_v001')
folder.mkdir(parents=True, exist_ok=True)
destination = folder / 'Edward_artist_baseline.ma'
assert not destination.exists()
before = {'scene':cmds.file(q=True,sn=True), 'modified':cmds.file(q=True,modified=True),
          'selection':cmds.ls(sl=True,long=True), 'frame':cmds.currentTime(q=True)}
cmds.file(str(destination), exportAll=True, type='mayaAscii', force=False, preserveReferences=True, options='v=0;')
after = {'scene':cmds.file(q=True,sn=True), 'modified':cmds.file(q=True,modified=True),
         'selection':cmds.ls(sl=True,long=True), 'frame':cmds.currentTime(q=True)}
result={'snapshot':str(destination),'bytes':destination.stat().st_size,'before':before,'after':after}
(folder/'snapshot.json').write_text(json.dumps(result,indent=2))
