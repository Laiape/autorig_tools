import json,runpy,time
from pathlib import Path
from maya import cmds
WORK=Path(r'C:/proyectos/auto-rig/tmp/edward_jaw_inner_20261015')
camera={}
for a in ['translateX','translateY','translateZ','rotateX','rotateY','rotateZ','focalLength','nearClipPlane','farClipPlane','centerOfInterest']:
    try:camera[a]=cmds.getAttr('persp.'+a)
    except:pass
pose=json.loads((WORK/'original_pose.json').read_text())
backup=WORK/('Before_Open_Latest_%s.mb'%time.strftime('%H%M%S'))
cmds.file(str(backup),exportAll=True,type='mayaBinary',preserveReferences=True,force=False)
(WORK/'live_reference.json').write_text(json.dumps({'scene':cmds.file(q=True,sn=True),'backup':str(backup),'camera':camera,'pose':pose},indent=2))
cmds.file(r'C:/proyectos/auto-rig/maya_tools/assets/Edward/scenes/Edward_working_v003.mb',open=True,force=True,prompt=False,executeScriptNodes=False)
for p,v in pose.items():
    if cmds.objExists(p) and cmds.getAttr(p,settable=True):cmds.setAttr(p,v)
for a,v in camera.items():
    try:cmds.setAttr('persp.'+a,v)
    except:pass
result={'scene':cmds.file(q=True,sn=True),'wraps':len(cmds.ls(type='proximityWrap') or []),'backup':str(backup)}
