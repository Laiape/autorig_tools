"""Run with mayapy: sockets share eyelid Fleshy without double transforms."""
import ast
import math
import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('MAYA_SKIP_USERSETUP_PY', '1')
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om
from test_spine_chest_stretch import create_controller


def close(actual, expected):
    assert all(math.isclose(a, b, abs_tol=1e-5) for a, b in zip(actual, expected)), (list(actual), list(expected))


def run():
    maya.standalone.initialize(name='python')
    try:
        source = Path(__file__).resolve().parents[2] / 'biped/autorig/eyelid_module.py'
        names = {'sockets', 'socket_fleshy_setup'}
        functions = [n for n in ast.walk(ast.parse(source.read_text(encoding='utf-8')))
                     if isinstance(n, ast.FunctionDef) and n.name in names]
        scope = {'cmds': cmds, 'om': om,
                 'curve_tool': SimpleNamespace(create_controller=create_controller)}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), scope)
        Module = type('TestEye', (), {name: scope[name] for name in names})
        for side, sign in [('L', 1), ('R', -1)]:
            cmds.file(new=True, force=True)
            module = Module()
            module.side = side
            module.module_trn = cmds.createNode('transform')
            module.controllers_grp = cmds.createNode('transform')
            module.skeleton_grp = cmds.createNode('transform')
            module.face_ctl = cmds.createNode('transform')
            cmds.addAttr(module.face_ctl, ln='Sockets', at='long', dv=2)
            module.head_guide_matrix = list(om.MMatrix())
            eye_frame = om.MTransformationMatrix()
            eye_frame.setTranslation(om.MVector(sign * 3, 20, 2), om.MSpace.kWorld)
            eye_frame.setRotation(om.MEulerRotation(.1, sign * .2, -.05))
            module.eye_guide_matrix = list(eye_frame.asMatrix())
            eye = cmds.createNode('transform', n=side+'_eyeDirect_CTL')
            cmds.addAttr(eye, ln='Fleshy', at='double', dv=0)
            cmds.addAttr(eye, ln='Fleshy_Corners', at='double', dv=.5)
            for corner in (False, True):
                cm = cmds.createNode('composeMatrix', n=side+'_fleshy'+('Corners' if corner else '')+'_CM')
                mul = cmds.createNode('multiplyDivide')
                cmds.connectAttr(eye+'.rotate', mul+'.input1')
                for axis in 'XYZ':
                    if corner:
                        weight = cmds.createNode('multiplyDivide')
                        cmds.connectAttr(eye+'.Fleshy', weight+'.input1X')
                        cmds.connectAttr(eye+'.Fleshy_Corners', weight+'.input2X')
                        cmds.connectAttr(weight+'.outputX', mul+'.input2'+axis)
                    else:
                        cmds.connectAttr(eye+'.Fleshy', mul+'.input2'+axis)
                cmds.connectAttr(mul+'.output', cm+'.inputRotate')
            brow = cmds.createNode('transform', n=side+'_eyebrowMain_CTL')
            scope['data_manager'] = SimpleNamespace(DataExportBiped=lambda: SimpleNamespace(get_data=lambda *args: brow))
            offsets = {'upperSocket':(0,2,3), 'lowerSocket':(0,-2,3),
                       'inSocket':(-sign*2,0,3), 'outSocket':(sign*2,0,3),
                       'upInSocket':(-sign,1,3), 'upOutSocket':(sign,1,3),
                       'downInSocket':(-sign,-1,3), 'downOutSocket':(sign,-1,3)}
            positions = {name: om.MPoint(*p) * eye_frame.asMatrix() for name,p in offsets.items()}
            def guides(name=None, guide_export=None, **kwargs):
                name = guide_export or name
                if name.endswith('CRVShape'):
                    return None
                joint = cmds.createNode('joint', n=name)
                cmds.xform(joint, ws=True, t=list(positions[name[len(side)+1:-4]])[:3])
                return joint
            scope['guides_manager'] = SimpleNamespace(get_guides=guides)
            module.sockets()
            primaries = ['upperSocket','lowerSocket','inSocket','outSocket']
            pairs = {'upInSocket':('upperSocket','inSocket'), 'upOutSocket':('upperSocket','outSocket'),
                     'downInSocket':('lowerSocket','inSocket'), 'downOutSocket':('lowerSocket','outSocket')}
            def position(name):
                return cmds.xform(side+'_'+name+'Skinning_JNT', q=True, ws=True, t=True)
            for name in positions:
                close(position(name), list(positions[name])[:3])
            for mode in ['off', 'parallel']:
                cmds.evaluationManager(mode=mode)
                for weight in [0, .5, 1]:
                    cmds.setAttr(eye+'.Fleshy', weight)
                    cmds.setAttr(eye+'.rotate', 30,-25,15)
                    expected = {}
                    for name in primaries:
                        factor = weight * (.5 if name in ('inSocket','outSocket') else 1)
                        rotation = om.MEulerRotation(*(math.radians(v*factor) for v in (30,-25,15))).asMatrix()
                        delta = eye_frame.asMatrix().inverse() * rotation * eye_frame.asMatrix()
                        expected[name] = delta
                        close(position(name), list(positions[name] * delta)[:3])
                    for name, parents in pairs.items():
                        points = [positions[name] * expected[p] for p in parents]
                        close(position(name), [(a+b)*.5 for a,b in zip(points[0],points[1])][:3])
            cmds.setAttr(eye+'.Fleshy', 0)
            cmds.setAttr(brow+'.Auto_Socket', 1)
            cmds.setAttr(brow+'.translateY', 1.25)
            upper = position('upperSocket')
            close(upper, [positions['upperSocket'].x, positions['upperSocket'].y+1.25, positions['upperSocket'].z])
            cmds.setAttr(side+'_lowerSocket_CTL.translateY', -.75)
            close(position('lowerSocket'), [positions['lowerSocket'].x, positions['lowerSocket'].y-.75, positions['lowerSocket'].z])
            assert not (cmds.cycleCheck(all=True, list=True) or [])
        print('PASS: L/R sockets orbit with Fleshy 0/.5/1, corner attenuation, secondary interpolation, manual controls, Auto_Socket; DG/parallel; no cycles')
    finally:
        maya.standalone.uninitialize()


if __name__ == '__main__':
    run()

