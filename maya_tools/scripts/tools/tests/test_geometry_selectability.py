"""Native Locked/Selectable/Off regression for the shared builder display graph."""
import ast
from pathlib import Path
import tempfile

import maya.standalone
import maya.cmds as cmds

maya.standalone.initialize(name='python')
source_path = Path(__file__).resolve().parents[2] / 'utils/basic_structure.py'
source = ast.parse(source_path.read_text(encoding='utf-8'))
build = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'create_basic_structure')
start = next(i for i,node in enumerate(build.body) if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == 'ref_cond' for target in node.targets))
end = next(i for i,node in enumerate(build.body) if isinstance(node, ast.Assign)
           and any(isinstance(target, ast.Name) and target.id == 'pb_rev' for target in node.targets))
graph = compile(ast.Module(body=build.body[start:end], type_ignores=[]), str(source_path), 'exec')


def get_or_create(kind, name):
    return name if cmds.objExists(name) else cmds.createNode(kind, name=name)


def safe_connect(source, target):
    if not cmds.isConnected(source, target):
        cmds.connectAttr(source, target, force=True)


cmds.file(new=True, force=True)
settings = cmds.createNode('transform', name='C_settings_CTL')
cmds.addAttr(settings, longName='geoDisplay', attributeType='enum', enumName='Locked:Selectable:Off')
geo = cmds.createNode('transform', name='geo_GRP')
cmds.polyCube(name='character_mesh', constructionHistory=False)
cmds.parent('character_mesh', geo)
scope = dict(cmds=cmds, settings_ctl=settings, geo_grp=geo,
             get_or_create=get_or_create, safe_connect=safe_connect)
for repeat in range(2):
    previous_count = len(cmds.ls())
    exec(graph, scope)
    if repeat:
        assert len(cmds.ls()) == previous_count
    for mode in ('off', 'serial', 'parallel'):
        cmds.evaluationManager(mode=mode)
        for setting, display, visible in ((0, 2, True), (1, 0, True), (2, 0, False), (1, 0, True)):
            cmds.setAttr(settings + '.geoDisplay', setting)
            assert cmds.getAttr(geo + '.overrideDisplayType') == display, (repeat, mode, setting)
            assert cmds.getAttr(geo + '.visibility') == visible, (repeat, mode, setting)
with tempfile.TemporaryDirectory() as folder:
    path = str(Path(folder) / 'selectable.mb')
    cmds.file(rename=path)
    cmds.file(save=True, type='mayaBinary', force=True)
    cmds.file(path, open=True, force=True)
    assert cmds.getAttr('geo_GRP.overrideDisplayType') == 0
    assert cmds.getAttr('geo_GRP.visibility')
    cmds.file(new=True, force=True)
print('PASS: Locked/Selectable/Off, rebuild idempotence, DG/Serial/Parallel, native reopen')
