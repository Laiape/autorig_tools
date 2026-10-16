"""Native Edward-guide jaw fixture without asset cache writes or control drawings."""
import ast
import json
import math
import os
from pathlib import Path
import runpy
from types import SimpleNamespace

from maya import cmds
from maya.api import OpenMaya as om

SCRIPTS = Path(__file__).resolve().parents[3]
SOURCE = SCRIPTS / 'biped/autorig/jaw_module_nurbs.py'
DATA = json.loads(Path(__file__).with_name('edward_lip_guides.json').read_text())


def build(source=SOURCE):
    cmds.file(new=True, force=True)
    cmds.evaluationManager(mode='off')
    for plugin in ('matrixNodes', 'lookdevKit'):
        cmds.loadPlugin(plugin, quiet=True)

    def controller(name, parent=None, **unused):
        group = cmds.createNode('transform', name=name + '_GRP', parent=parent)
        offset = cmds.createNode('transform', name=name + '_OFF', parent=group)
        return [group, offset], cmds.createNode('transform', name=name + '_CTL', parent=offset)

    def lock(node, attrs):
        for attr in attrs:
            cmds.setAttr(node + '.' + attr, lock=True, keyable=False)

    def guides(name, parent=None):
        if name == 'C_jaw_JNT':
            node = cmds.createNode('joint', name=name)
            cmds.xform(node, ws=True, t=DATA['jaw_position'])
            return [node]
        key = name.removesuffix('Shape')
        data = DATA['geometry'][key]
        points = om.MPointArray([om.MPoint(*p) for p in data['cvs']])
        if data['type'] == 'curve':
            obj = om.MFnNurbsCurve().create(points, om.MDoubleArray(data['knots']),
                                           data['degree'], data['form'], False, True)
        else:
            obj = om.MFnNurbsSurface().create(
                points, om.MDoubleArray(data['knotsU']), om.MDoubleArray(data['knotsV']),
                data['degreeU'], data['degreeV'], data['formU'], data['formV'], True)
        node = cmds.rename(om.MFnDagNode(obj).fullPathName(), key)
        if parent:
            cmds.parent(node, parent)
        return node

    tree = ast.parse((SCRIPTS / 'utils/matrix_manager.py').read_text(encoding='utf-8'))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef)
                 and n.name == 'getClosestParamsToPositionSurface']
    matrices = {'cmds': cmds, 'om': om}
    exec(compile(ast.Module(body=functions, type_ignores=[]), '<matrix>', 'exec'), matrices)
    scope = dict(cmds=cmds, om=om, math=math, os=os,
                 guide_frames=SimpleNamespace(enabled=lambda: False),
                 curve_tool=SimpleNamespace(create_controller=controller, lock_attributes=lock),
                 guides_manager=SimpleNamespace(get_guides=guides),
                 data_manager=SimpleNamespace(DataExportBiped=lambda: SimpleNamespace(append_data=lambda *a: None)),
                 matrix_manager=SimpleNamespace(getClosestParamsToPositionSurface=matrices['getClosestParamsToPositionSurface']),
                 organize_module_nurbs=runpy.run_path(str(SCRIPTS / 'utils/module_nurbs.py'))['organize_module_nurbs'])
    tree = ast.parse(Path(source).read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(source), 'exec'), scope)
    jaw = scope['JawModule'].__new__(scope['JawModule'])
    for field in ('modules', 'skel_grp', 'masterwalk_ctl', 'face_ctl', 'head_ctl'):
        setattr(jaw, field, cmds.createNode('transform', name=field))
    jaw.face_controls_parent = jaw.face_ctl
    jaw.make('C')
    return jaw
