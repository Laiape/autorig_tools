"""Native eyelid contact, manual rotation and scene persistence regression."""
import ast
import math
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om
import numpy as np
from test_spine_chest_stretch import create_controller

SOURCE = Path(__file__).resolve().parents[2] / 'biped/autorig/eyelid_module.py'


def build(side='L', surface=False, source=SOURCE, eye_frame=None, radii=(2,2,2), samples=7):
    cmds.file(new=True, force=True)
    if ':' in side:
        cmds.namespace(add=side.rsplit(':', 1)[0])
    sys.path.insert(0, str(SOURCE.parents[4]))
    from maya_tools.scripts.utils import matrix_manager
    names = {'local', 'create_curves', 'curve_cvs_into_guides', 'create_controllers',
             'constraints_callback', 'local_constraints_callback', 'create_blink_setup',
             'create_eye_surface', 'skinning_joints', 'getClosestParamToPosition'}
    sign = 1 if side == 'L' else -1
    if eye_frame is None:
        eye_frame = list(om.MMatrix.kIdentity)
        eye_frame[12:15] = [sign*4,10,0]
    frame = om.MMatrix(eye_frame)

    def guides(guide_export, parent):
        upper = 'Upper' in guide_export
        points = []
        fractions = (0, .08, .23, .44, .63, .81, 1) if samples==7 else [i/(samples-1) for i in range(samples)]
        for t in fractions:
            x = radii[0]*(-.75 + 1.5*t)
            y = radii[1]*((.4 if upper else -.3)*math.sin(math.pi*t) + .15*x/radii[0])
            z = radii[2]*math.sqrt(max(0,1-(x/radii[0])**2-(y/radii[1])**2))
            p = om.MPoint(sign*x,y,z)*frame
            points.append((p.x,p.y,p.z))
        curve = cmds.curve(d=1, p=points, n=guide_export.replace('Shape', ''))
        return cmds.parent(curve, parent)[0]

    scope = dict(cmds=cmds, om=om, math=math, matrix_manager=matrix_manager,
                 curve_tool=SimpleNamespace(create_controller=create_controller,
                                            lock_attributes=lambda *args: None),
                 guides_manager=SimpleNamespace(get_guides=guides))
    tree = ast.parse(source.read_text(encoding='utf-8'))
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), scope)
    eye = type('EyeFixture', (), {n: scope[n] for n in names})()
    eye.side, eye.surface = side, surface
    eye.module_trn = cmds.createNode('transform', n='module')
    eye.curves_grp = cmds.createNode('transform', n='curves', p=eye.module_trn)
    eye.local_jnts_grp = cmds.createNode('transform', n='locals', p=eye.module_trn)
    eye.skeleton_grp = cmds.createNode('transform', n='skeleton')
    eye.controllers_grp = cmds.createNode('transform', n='controllers')
    eye.extra_controllers_grp = cmds.createNode('transform', n='extras', p=eye.controllers_grp)
    eye.eye_direct_ctl = cmds.createNode('transform', n=side+'_eyeDirect_CTL')
    for attr, default in (('Upper_Blink', 0), ('Lower_Blink', 0), ('Blink_Height', .2)):
        cmds.addAttr(eye.eye_direct_ctl, ln=attr, at='double', dv=default, k=True)
    guide = cmds.createNode('transform')
    cmds.xform(guide,ws=True,m=eye_frame)
    eye.eye_guide_matrix = cmds.getAttr(guide+'.worldMatrix[0]')
    cmds.delete(guide)
    eye.create_curves()
    eye.curve_cvs_into_guides()
    eye.create_controllers()
    eye.create_blink_setup()
    if surface:
        eye.create_eye_surface()
    eye.skinning_joints()
    return eye


def curve_points(curve):
    selection = om.MSelectionList()
    selection.add(curve)
    path = selection.getDagPath(0)
    path.extendToShape()
    fn = om.MFnNurbsCurve(path)
    start, end = fn.knotDomain
    return np.array([list(fn.getPointAtParam(start+(end-start)*i/32, om.MSpace.kWorld))[:3]
                     for i in range(33)])


def sample(eye):
    return np.array([curve_points(eye.eyelid_up_curve_rebuild),
                     curve_points(eye.eyelid_down_curve_rebuild)])


def run():
    maya.standalone.initialize(name='python')
    cmds.loadPlugin('matrixNodes', quiet=True)
    cmds.loadPlugin('lookdevKit', quiet=True)
    try:
        baseline = os.environ.get('AUTORIG_EYELID_BASELINE')
        if baseline:
            from maya_tools.scripts.tools import eyelid_contact
            for side in ('L', 'R', 'character:L'):
                eye = build(side.rsplit(':', 1)[-1], True, Path(baseline))
                if ':' in side:
                    with tempfile.TemporaryDirectory() as folder:
                        path = str(Path(folder)/'legacy.ma')
                        cmds.file(rename=path)
                        cmds.file(save=True, type='mayaAscii', force=True)
                        cmds.file(new=True, force=True)
                        cmds.file(path, i=True, namespace='character')
                    for key in ('eye_direct_ctl', 'eyelid_up_curve_rebuild', 'eyelid_down_curve_rebuild'):
                        setattr(eye, key, 'character:'+getattr(eye, key))
                cmds.undoInfo(state=True)
                original = sample(eye)
                cmds.select(side+'_eyelidUp_CTL')
                selection = cmds.ls(sl=True)
                assert eyelid_contact.upgrade([eye.eye_direct_ctl]) == [side]
                assert cmds.ls(sl=True) == selection
                assert np.allclose(sample(eye), original, atol=1e-6, rtol=0)
                assert not eyelid_contact.upgrade([eye.eye_direct_ctl])
                cmds.undo()
                assert not cmds.objExists(side+'_upperContactAmount_CLP')
                assert np.allclose(sample(eye), original, atol=1e-6, rtol=0)
                eyelid_contact.upgrade([eye.eye_direct_ctl])
                for attr in ('Upper_Blink', 'Lower_Blink'):
                    cmds.setAttr(eye.eye_direct_ctl+'.'+attr, 1)
                closed = sample(eye)
                assert np.max(abs(closed[0]-closed[1])) < 1e-5
        for side in ('L', 'R'):
            for surface in (False, True):
                eye = build(side, surface)
                rest = sample(eye)
                for ctl in eye.controllers:
                    for axis in 'XYZ':
                        cmds.setAttr(ctl+'.rotate'+axis, 20)
                        assert np.max(abs(sample(eye)-rest)) > .001, (ctl, axis)
                        cmds.setAttr(ctl+'.rotate'+axis, 0)
                cmds.setAttr(side+'_eyelidUp_CTL.rotate', 15, -12, 20)
                cmds.setAttr(side+'_eyelidDown_CTL.rotate', -8, 7, -15)
                cmds.setAttr(side+'_eyelidInUp_CTL.translateY', .2)
                posed = sample(eye)
                assert np.max(np.abs(rest-posed)) > .01
                for mode in ('off', 'serial', 'parallel'):
                    cmds.evaluationManager(mode=mode)
                    for height in (0, .2, .5, 1, .5, 0):
                        cmds.setAttr(eye.eye_direct_ctl+'.Blink_Height', height)
                        for amount in (0, .25, .75, 1, .75, .25, 0, -.5):
                            for attr in ('Upper_Blink', 'Lower_Blink'):
                                cmds.setAttr(eye.eye_direct_ctl+'.'+attr, amount)
                            actual = sample(eye)
                            common = curve_points(eye.blink_ref_curve)
                            expected = (1-amount)*posed + amount*common
                            assert np.allclose(actual, expected, atol=1e-5, rtol=0), np.max(abs(actual-expected))
                            if amount == 1:
                                assert np.max(abs(actual[0]-actual[1])) < 1e-5
                                upper = np.array([cmds.xform(side+'_upperEyelid0%dSkinning_JNT'%i, q=True, ws=True, t=True) for i in range(7)])
                                lower = np.array([cmds.xform(side+'_downEyelid0%dSkinning_JNT'%i, q=True, ws=True, t=True) for i in range(7)])
                                assert np.max(abs(upper-lower)) < 1e-4, ('joint contact', side, surface, height, np.max(abs(upper-lower)))
                for attr in ('Upper_Blink', 'Lower_Blink'):
                    cmds.setAttr(eye.eye_direct_ctl+'.'+attr, 0)
                open_pose = sample(eye)
                cmds.setAttr(eye.eye_direct_ctl+'.Upper_Blink', 1)
                upper_only = sample(eye)
                assert np.allclose(upper_only[1], open_pose[1], atol=1e-6, rtol=0)
                assert np.max(abs(upper_only[0]-open_pose[0])) > .01
                cmds.setAttr(eye.eye_direct_ctl+'.Upper_Blink', 0)
                ctl = side+'_upperEyelid03_CTL'
                joint = side+'_upperEyelid03Skinning_JNT'
                base = np.array(cmds.getAttr(joint+'.worldMatrix[0]')).reshape(4, 4)
                for axis in 'XYZ':
                    cmds.setAttr(ctl+'.rotate'+axis, 25)
                    actual = np.array(cmds.getAttr(joint+'.worldMatrix[0]')).reshape(4, 4)
                    assert np.max(abs(actual[:3,:3]-base[:3,:3])) > .1, axis
                    assert np.allclose(actual[3], base[3], atol=1e-6, rtol=0)
                    cmds.setAttr(ctl+'.rotate'+axis, 0)
                assert not (cmds.cycleCheck(all=True, list=True) or [])
                expected = sample(eye)
                with tempfile.TemporaryDirectory() as folder:
                    path = str(Path(folder)/'eyelid.ma')
                    cmds.file(rename=path)
                    cmds.file(save=True, type='mayaAscii', force=True)
                    cmds.file(path, open=True, force=True)
                    assert np.allclose(sample(eye), expected, atol=1e-6, rtol=0)
        print('PASS: L/R contact with posed controls, negative/open/partial/full blink, all heights, XYZ detail rotations, DG/serial/parallel and native reopen')
    finally:
        maya.standalone.uninitialize()


if __name__ == '__main__':
    run()
