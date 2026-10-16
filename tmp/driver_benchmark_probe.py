import json, os
from pathlib import Path
from maya import cmds
from maya_tools.scripts.tools import rig_benchmark as rb, pose_blendshapes as pb
result = {
 'pid': os.getpid(), 'scene': cmds.file(q=True, sn=True),
 'modified': cmds.file(q=True, modified=True), 'batch': cmds.about(batch=True),
 'modules': [rb.__file__, pb.__file__], 'mode': cmds.evaluationManager(q=True,mode=True),
 'prx': cmds.ls(type='proximityWrap'),
 'meshes': [n for n in cmds.ls(type='transform') if any(s in n.lower() for s in ('driver','cintur','belt','wrinkle','cabeza'))],
 'blendShapes': cmds.ls(type='blendShape'),
}
Path('C:/proyectos/auto-rig/tmp/driver_benchmark_probe.json').write_text(json.dumps(result,indent=2))
