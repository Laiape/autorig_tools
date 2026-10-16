import os
import sys
import json
from pathlib import Path
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
root = Path('C:/proyectos/auto-rig/autorig_tools')
sys.path[:0] = [str(root), str(root/'maya_tools/scripts')]
source = root/'maya_tools/assets/flower/flower_v01.ma'
cmds.file(str(source), open=True, force=True, executeScriptNodes=False)
report = {'source': str(source), 'roots': cmds.ls(assemblies=True, long=True), 'meshes': [],
          'history': {t: cmds.ls(type=t) for t in ['skinCluster', 'blendShape', 'expression', 'script', 'file', 'unknown']}}
for shape in cmds.ls(type='mesh', long=True, noIntermediate=True):
    sl = om.MSelectionList(); sl.add(shape)
    fn = om.MFnMesh(sl.getDagPath(0))
    pts = fn.getPoints(om.MSpace.kWorld)
    polycounts, indices = fn.getVertices()
    adjacency = [set() for _ in pts]
    cursor = 0
    for count in polycounts:
        face = list(indices[cursor:cursor+count]); cursor += count
        for index in face:
            adjacency[index].update(face)
    unseen = set(range(len(pts))); shells = []
    while unseen:
        todo = [unseen.pop()]; shell = set(todo)
        while todo:
            for index in adjacency[todo.pop()]:
                if index in unseen:
                    unseen.remove(index); shell.add(index); todo.append(index)
        shells.append(sorted(shell))
    def bounds(ids):
        return [min(pts[i][a] for i in ids) for a in range(3)]+[max(pts[i][a] for i in ids) for a in range(3)]
    report['meshes'].append({'shape': shape, 'vertices': len(pts), 'faces': fn.numPolygons,
       'bounds': bounds(range(len(pts))), 'shells': [{'count': len(s), 'bounds': bounds(s)} for s in shells],
       'shading': cmds.listConnections(shape, type='shadingEngine'),
       'history': cmds.listHistory(shape), 'transform': cmds.xform(cmds.listRelatives(shape, parent=True, fullPath=True)[0], q=True, matrix=True, worldSpace=True)})
folder = Path('C:/proyectos/auto-rig/tmp/flower_20261016')
(folder/'model_inventory.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
sys.stdout.flush(); os._exit(0)
