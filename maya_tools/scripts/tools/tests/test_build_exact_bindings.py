"""Native Maya: initial optimized binds retain exact deformation and tiny weights."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import numpy as np
os.environ['MAYA_SKIP_USERSETUP_PY']='1'
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'maya_tools/scripts')]
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om,OpenMayaAnim as oma
from maya_tools.scripts.tools.skin_manager_api import SkinManager
from maya_tools.scripts.tools import rig_exact_cleanup


class NewBindTests(unittest.TestCase):
    def setUp(self):
        cmds.file(new=True,force=True)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.target=str(Path(self.temp.name)/'weights.skc')
        self.joints=[]
        for i in range(3):
            cmds.select(clear=True);self.joints.append(cmds.joint(name='joint%d'%i,position=(i,0,0)))
        self.mesh=cmds.polyCube(name='mesh')[0]
        self.skin=cmds.skinCluster(self.joints,self.mesh,toSelectedBones=True,skinMethod=2,name='testSkin')[0]
        self.shape=cmds.listRelatives(self.mesh,shapes=True,noIntermediate=True,fullPath=True)[0]
        self.path=om.MSelectionList().add(self.shape).getDagPath(0)
        component=om.MFnSingleIndexedComponent();self.comp=component.create(om.MFn.kMeshVertComponent);component.setCompleteData(8)
        self.weights=np.tile([1.-1e-12,0.,1e-12],(8,1))
        cmds.setAttr(self.skin+'.normalizeWeights',0)
        self.fn().setWeights(self.path,self.comp,om.MIntArray([0,1,2]),om.MDoubleArray(self.weights.ravel().tolist()),False)
        self.fn().setBlendWeights(self.path,self.comp,om.MDoubleArray([0.,.2,.5,1.]*2))
        self.mask=np.asarray(self.fn().getBlendWeights(self.path,self.comp)).copy()
        self.manager=SkinManager.__new__(SkinManager)
        self.manager.k_skin_attrs=['skinningMethod','normalizeWeights','maxInfluences','maintainMaxInfluences']
        self.manager.tolerance=1e-5
        cmds.select(self.mesh);self.manager.export_skins(self.target)
        self.data=json.loads(Path(self.target).read_text())

    def fn(self):return oma.MFnSkinCluster(om.MSelectionList().add(self.skin).getDependNode(0))

    def recreate(self,optimized=True,zero=False,driven=False):
        if zero:
            for key,rows in self.data.items():
                if not key.startswith('__'):rows[0]['sparse_weights']={}
        self.data={k:v for k,v in self.data.items() if not k.startswith('__')}
        if driven:
            self.data['__scene_deformers__']={'nodes':[{'name':self.skin,'type':'skinCluster','connections':[
                {'source':'driver.output','destination':self.skin+'.weightList[0].weights[1]'}]}]}
        Path(self.target).write_text(json.dumps(self.data))
        cmds.delete(self.mesh,constructionHistory=True)
        self.manager.import_skins(self.target,import_method='index',import_wrinkles=False,optimize_new_bindings=optimized)

    def test_initial_bind_omits_only_exact_zero_without_native_removal(self):
        command=cmds.skinCluster
        with mock.patch.object(cmds,'skinCluster',wraps=command) as calls:
            self.recreate()
        self.assertFalse(any('removeInfluence' in call.kwargs for call in calls.call_args_list))
        names=[p.partialPathName() for p in self.fn().influenceObjects()]
        self.assertEqual(names,[self.joints[0],self.joints[2]])
        actual=np.asarray(self.fn().getWeights(self.path,self.comp)[0]).reshape((8,2))
        self.assertTrue(np.array_equal(actual,self.weights[:,[0,2]]))
        self.assertTrue(np.array_equal(np.asarray(self.fn().getBlendWeights(self.path,self.comp)),self.mask))
        self.assertEqual(self.manager._import_optimization_report[0]['after'],2)

    def test_existing_skin_replacement_keeps_its_bindings(self):
        self.manager.import_skins(self.target,replace_existing=True,import_wrinkles=False,optimize_new_bindings=True)
        self.assertEqual(len(self.fn().influenceObjects()),3)
        self.assertEqual(self.manager._import_optimization_report,[])

    def test_opt_out_and_empty_weights_keep_original_binding_contract(self):
        self.recreate(optimized=False)
        self.assertEqual(len(self.fn().influenceObjects()),3)
        self.recreate(zero=True)
        self.assertEqual(len(self.fn().influenceObjects()),3)

    def test_driven_weight_record_disables_static_filter(self):
        self.recreate(driven=True)
        self.assertEqual(len(self.fn().influenceObjects()),3)

    def test_scoped_math_does_not_touch_preexisting_or_empty_selection(self):
        source=cmds.createNode('transform',name='corner')
        names=[]
        for index in (0,1,2):
            node=cmds.createNode('multMatrix',name='C_lipCorner%dFrame_MMX'%index)
            cmds.setAttr(node+'.matrixIn[0]',*list(om.MMatrix()),type='matrix')
            cmds.connectAttr(source+'.matrix',node+'.matrixIn[1]');names.append(node)
        self.assertEqual(rig_exact_cleanup.share_identical_lip_math(nodes=[])['removed'],[])
        report=rig_exact_cleanup.share_identical_lip_math(nodes=names[1:])
        self.assertEqual(report['removed'],[names[2]])
        self.assertTrue(cmds.objExists(names[0]))

    def test_build_math_scope_supports_namespaces(self):
        cmds.namespace(add='Character')
        nodes=[]
        for index in (1,2):
            node=cmds.createNode('multMatrix',name='Character:C_lipCorner%dFrame_MMX'%index)
            cmds.setAttr(node+'.matrixIn[0]',*list(om.MMatrix()),type='matrix')
            cmds.connectAttr(self.joints[0]+'.matrix',node+'.matrixIn[1]');nodes.append(node)
        self.assertEqual(rig_exact_cleanup.share_identical_lip_math(nodes=nodes)['removed'],[nodes[1]])


result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NewBindTests))
assert result.wasSuccessful(),'New exact binding regression'
