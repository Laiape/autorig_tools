"""Native constant-point cleanup retains shape, animation and excluded data."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'maya_tools/scripts')]
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.tools import rig_exact_cleanup as cleanup


def points(shape):
    return [tuple(p) for p in om.MFnMesh(om.MSelectionList().add(shape).getDagPath(0)).getPoints()]


class ExactCleanupTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True,force=True)
        mesh=cmds.polyCube(name='scalp')[0]
        self.shape=cmds.listRelatives(mesh,shapes=True,fullPath=True)[0]
        self.curve=cmds.createNode('animCurveTL')
        cmds.setKeyframe(self.curve,time=1,value=.25)
        self.destination=self.shape+'.pnts[0].pntx'
        cmds.connectAttr(self.curve+'.output',self.destination)
        self.before=points(self.shape)

    def test_exact_shape_idempotence_and_native_reopen(self):
        plan=cleanup.bake_static_point_curves([self.shape])
        self.assertEqual(plan['count'],1)
        self.assertTrue(cmds.objExists(self.curve))
        result=cleanup.bake_static_point_curves([self.shape],apply=True)
        self.assertTrue(result['applied'])
        self.assertFalse(cmds.objExists(self.curve))
        for frame in (1,10,-20):
            cmds.currentTime(frame)
            self.assertEqual(points(self.shape),self.before)
        self.assertEqual(cleanup.bake_static_point_curves([self.shape],apply=True)['count'],0)
        with tempfile.TemporaryDirectory() as directory:
            path=str(Path(directory)/'cleanup.mb')
            cmds.file(rename=path);cmds.file(save=True,type='mayaBinary')
            cmds.file(path,open=True,force=True)
            self.assertEqual(points(self.shape),self.before)

    def test_time_driven_curve_is_retained(self):
        cmds.connectAttr('time1.outTime',self.curve+'.input')
        self.assertEqual(cleanup.bake_static_point_curves([self.shape],apply=True)['count'],0)
        self.assertTrue(cmds.objExists(self.curve))

    def test_other_consumers_and_other_mesh_are_retained(self):
        other=cmds.polyCube(name='other')[0]
        cmds.connectAttr(self.curve+'.output',other+'.translateX')
        self.assertEqual(cleanup.bake_static_point_curves([self.shape],apply=True)['count'],0)
        self.assertEqual(cleanup.bake_static_point_curves([other],apply=True)['count'],0)

    def test_multiple_keys_are_retained(self):
        cmds.setKeyframe(self.curve,time=2,value=.5)
        self.assertEqual(cleanup.bake_static_point_curves([self.shape],apply=True)['count'],0)

    def test_failure_undo_restores_connection_and_shape(self):
        with mock.patch.object(cmds,'delete',side_effect=RuntimeError('Injected cleanup failure')):
            with self.assertRaisesRegex(RuntimeError,'Injected cleanup failure'):
                cleanup.bake_static_point_curves([self.shape],apply=True)
        self.assertTrue(cmds.isConnected(self.curve+'.output',self.destination))
        self.assertEqual(points(self.shape),self.before)

    def test_authored_metadata_and_locked_point_curves_are_retained(self):
        cmds.addAttr(self.curve,longName='artistNote',dataType='string')
        self.assertEqual(cleanup.bake_static_point_curves([self.shape],apply=True)['count'],0)
        cmds.deleteAttr(self.curve+'.artistNote')
        cmds.lockNode(self.curve,lock=True)
        self.assertEqual(cleanup.bake_static_point_curves([self.shape],apply=True)['count'],0)
        self.assertTrue(cmds.isConnected(self.curve+'.output',self.destination))
        cmds.lockNode(self.curve,lock=False)

    def test_exact_zero_skin_columns_preserve_tiny_positive_weights(self):
        from maya.api import OpenMayaAnim as oma
        import numpy as np
        cmds.select(clear=True)
        joints=[cmds.joint(name='influence%d'%i,position=(i,0,0)) for i in range(3)]
        skin=cmds.skinCluster(joints,self.shape,toSelectedBones=True,maximumInfluences=3)[0]
        fn=oma.MFnSkinCluster(om.MSelectionList().add(skin).getDependNode(0))
        path=om.MSelectionList().add(self.shape).getDagPath(0)
        c=om.MFnSingleIndexedComponent();component=c.create(om.MFn.kMeshVertComponent);c.setCompleteData(8)
        cmds.setAttr(skin+'.normalizeWeights',0)
        data=np.tile([1.-1e-12,1e-12,0.],(8,1))
        fn.setWeights(path,component,om.MIntArray([0,1,2]),om.MDoubleArray(data.ravel().tolist()),False)
        cmds.setAttr(skin+'.normalizeWeights',2)
        before=points(self.shape)
        report=cleanup.remove_exact_zero_influences([skin],apply=True)
        self.assertEqual(report['removed_count'],1)
        self.assertEqual(len(cmds.skinCluster(skin,query=True,influence=True)),2)
        self.assertEqual(points(self.shape),before)
        self.assertEqual(cmds.getAttr(skin+'.normalizeWeights'),2)
        self.assertEqual(cleanup.remove_exact_zero_influences([skin],apply=True)['removed_count'],0)

    def test_identical_lip_math_preserves_matrix_and_coupled_target_weights(self):
        source=cmds.createNode('transform',name='corner')
        nodes=[cmds.createNode('multMatrix',name='C_lipCorner%dFrame_MMX'%i) for i in (1,2)]
        targets=[]
        for node in nodes:
            cmds.setAttr(node+'.matrixIn[0]',*([1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.,0.,0.,0.,0.,1.]),type='matrix')
            cmds.connectAttr(source+'.worldMatrix[0]',node+'.matrixIn[1]')
            target=cmds.createNode('blendMatrix')
            cmds.connectAttr(node+'.matrixSum',target+'.target[0].targetMatrix')
            for attr in ('translateWeight','rotateWeight','scaleWeight','shearWeight'):
                cmds.setAttr(target+'.target[0].'+attr,.3)
            targets.append(target)
        before=[cmds.getAttr(node+'.outputMatrix') for node in targets]
        report=cleanup.share_identical_lip_math()
        self.assertEqual(len(report['removed']),1)
        for node,expected in zip(targets,before):
            self.assertEqual(cmds.getAttr(node+'.outputMatrix'),expected)
            self.assertEqual(cmds.getAttr(node+'.target[0].translateWeight'),.3)
        self.assertFalse(cleanup.share_identical_lip_math()['removed'])


result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExactCleanupTests))
assert result.wasSuccessful(),'Exact point cleanup failed'
