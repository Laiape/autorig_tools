"""Native leg builds: push motion, paw branches, scale and scene persistence."""
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.environ['MAYA_SKIP_USERSETUP_PY'] = '1'
_CACHE = tempfile.TemporaryDirectory()
os.environ['AUTORIG_BUILD_CACHE_DIR'] = _CACHE.name
import maya.standalone
maya.standalone.initialize(name='python')
from maya import cmds
from maya.api import OpenMaya as om
from maya_tools.scripts.utils import data_manager, guides_manager, rig_manager
from maya_tools.scripts.quadruped.autorig import leg_module_self as lm


def build(bendys=True):
    cmds.file(new=True, force=True)
    cmds.optionVar(sv=('currentAssetRigName', 'chihuahua'))
    guides_manager.clear_guides_cache()
    rig = cmds.createNode('transform', name='rig_GRP')
    modules = cmds.createNode('transform', name='modules_GRP', parent=rig)
    skin = cmds.createNode('transform', name='skel_GRP', parent=rig)
    master = cmds.createNode('transform', name='C_masterwalk_CTL')
    cmds.addAttr(master, ln='globalScale', at='double', dv=1, k=True)
    for axis in 'XYZ':cmds.connectAttr(master+'.globalScale', master+'.scale'+axis)
    dm = data_manager.DataExportBiped()
    dm.new_build()
    dm.append_data('basic_structure', {'modules_GRP':modules, 'skel_GRP':skin, 'masterwalk_ctl':master})
    legs = []
    for cls in (lm.BackLegModule, lm.FrontLegModule):
        for side in ('L', 'R'):
            leg = cls()
            leg.make(side, solver=lm.SOLVER_SC_RP_SC_CARPUS, skinning_joints_number=5, bendys=bendys)
            legs.append(leg)
    rig_manager.skeleton_hierarchy()
    return legs


class LegPushTests(unittest.TestCase):
    def test_non_ribbon_paws_keep_push_and_digit_branches(self):
        legs=build(bendys=False)
        self.assertFalse(cmds.ls('*LegTip_ENV'))
        self.assertFalse(cmds.ls('*LegTipSkinning_JNT'))
        for leg in legs:
            self.assertEqual(len(leg.push_joints),4)
            for joint in leg.push_joints:
                self.assertAlmostEqual(cmds.getAttr(joint+'.pushActivation'),0,places=6)
            for controls in leg.foot.leg_digit_fk_ctls.values():
                self.assertEqual(cmds.listRelatives(controls[0].replace('Fk_CTL','_ENV'),parent=True)[0],leg.module_name+'Pastern_ENV')
            cmds.setAttr(leg.ik_ctl['ankle']+'.translateY',2)
            self.assertGreater(max(cmds.getAttr(j+'.pushActivation') for j in leg.push_joints),.001)

    def test_rigid_tip_weight_transfer_preserves_other_weights_and_undo(self):
        cmds.file(new=True,force=True)
        parent=cmds.createNode('joint',name='Pastern_ENV')
        tip=cmds.createNode('joint',name='Tip_ENV',parent=parent)
        cmds.setAttr(tip+'.translateZ',2)
        other=cmds.createNode('joint',name='Other_ENV')
        mesh=cmds.polyCube(ch=False)[0]
        skin=cmds.skinCluster([parent,tip,other],mesh,tsb=True)[0]
        cmds.skinPercent(skin,mesh+'.vtx[*]',transformValue=[(parent,.3),(tip,.2),(other,.5)])
        cmds.setAttr(parent+'.rotateY',35)
        points={}
        for method in (0,1,2):
            cmds.setAttr(skin+'.skinningMethod',method)
            points[method]=cmds.xform(mesh+'.vtx[*]',q=True,ws=True,t=True)
        lm.merge_rigid_tip_weights(skin,tip,parent)
        self.assertAlmostEqual(cmds.skinPercent(skin,mesh+'.vtx[0]',q=True,transform=parent),.5)
        self.assertAlmostEqual(cmds.skinPercent(skin,mesh+'.vtx[0]',q=True,transform=other),.5)
        self.assertAlmostEqual(cmds.skinPercent(skin,mesh+'.vtx[0]',q=True,transform=tip),0)
        for method in (0,1,2):
            cmds.setAttr(skin+'.skinningMethod',method)
            actual=cmds.xform(mesh+'.vtx[*]',q=True,ws=True,t=True)
            self.assertLess(max(abs(a-b) for a,b in zip(points[method],actual)),1e-5)
        # The native move operation participates in normal Maya undo.
        cmds.undo();cmds.undo();cmds.undo();cmds.undo()
        self.assertAlmostEqual(cmds.skinPercent(skin,mesh+'.vtx[0]',q=True,transform=tip),.2)

    def test_native_builds_motion_branches_and_reopen(self):
        signatures = []
        for repetition in range(2):
            legs = build()
            pushes = [joint for leg in legs for joint in leg.push_joints]
            self.assertEqual(len(pushes), 16)
            self.assertFalse(cmds.ls('*LegTip_ENV'))
            self.assertFalse(cmds.ls('*LegTipSkinning_JNT'))
            for leg in legs:
                # Each digit is an independent branch after Pastern.
                for controls in leg.foot.leg_digit_fk_ctls.values():
                    envs = [c.replace('Fk_CTL', '_ENV') for c in controls]
                    self.assertEqual(cmds.listRelatives(envs[0],parent=True)[0], leg.module_name+'Pastern_ENV')
                    for child,parent in zip(envs[1:],envs):
                        self.assertEqual(cmds.listRelatives(child,parent=True)[0],parent)
                for joint in leg.push_joints:
                    self.assertAlmostEqual(cmds.getAttr(joint+'.pushActivation'),0,places=6)
                    self.assertLess(om.MVector(cmds.getAttr(joint+'.translate')[0]).length(),1e-7)
                    env = joint.replace('_JNT','_ENV')
                    self.assertTrue(cmds.objExists(env))
                    parent = cmds.listRelatives(joint,parent=True)[0]
                    self.assertEqual(cmds.listRelatives(env,parent=True)[0], parent.replace('Skinning_JNT','_ENV').replace('_JNT','_ENV'))
                before = len(cmds.ls())
                self.assertEqual(leg.push_joint_setup(),leg.push_joints)
                self.assertEqual(len(cmds.ls()),before)
                ankle = leg.ik_ctl['ankle']
                fk_rest = cmds.getAttr(leg.fk_controllers[1]+'.rotate')[0]
                cmds.setAttr(ankle+'.translateY',2)
                cmds.setAttr(ankle+'.translateZ',-1)
                activation = [cmds.getAttr(j+'.pushActivation') for j in leg.push_joints]
                self.assertGreater(max(activation),.001,(leg.module_name,activation))
                self.assertEqual(cmds.getAttr(leg.fk_controllers[1]+'.rotate')[0],fk_rest)
                cmds.setAttr(ankle+'.translate',0,0,0)
                cmds.setAttr(leg.settings_ctl+'.switchIkFk',1)
                cmds.setAttr(leg.fk_controllers[1]+'.rotateZ',35)
                self.assertGreater(cmds.getAttr(leg.push_joints[0]+'.pushActivation'),.01)
                p = leg.push_joints[0]
                vec = cmds.getAttr(p+'.translate')[0]
                attr = leg.settings_ctl+'.'+p.split(leg.LEG_PREFIX,1)[1].split('CorrectivePush')[0]+'_Push'
                cmds.setAttr(attr,-cmds.getAttr(attr))
                reverse = cmds.getAttr(p+'.translate')[0]
                self.assertLess(max(abs(a+b) for a,b in zip(vec,reverse)),1e-6)
                cmds.setAttr(attr,-cmds.getAttr(attr))
                cmds.setAttr(leg.settings_ctl+'.Push_Enable',0)
                self.assertLess(om.MVector(cmds.getAttr(p+'.translate')[0]).length(),1e-7)
                cmds.setAttr(leg.settings_ctl+'.Push_Enable',1)
                cmds.setAttr(leg.fk_controllers[1]+'.rotateZ',0)
                cmds.setAttr(leg.settings_ctl+'.switchIkFk',0)
            # A push is a usable skin influence and retains its actual deformation.
            joint = pushes[0]
            mesh = cmds.polyCube(name='pushTestMesh',ch=False)[0]
            cmds.xform(mesh,ws=True,t=cmds.xform(joint,q=True,ws=True,t=True))
            cmds.skinCluster(joint,mesh,tsb=True)
            neutral = cmds.xform(mesh+'.vtx[*]',q=True,ws=True,t=True)
            leg=legs[0]
            cmds.setAttr(leg.settings_ctl+'.switchIkFk',1)
            cmds.setAttr(leg.fk_controllers[1]+'.rotateZ',40)
            posed = cmds.xform(mesh+'.vtx[*]',q=True,ws=True,t=True)
            self.assertGreater(max(abs(a-b) for a,b in zip(neutral,posed)),.001)
            for module in legs:cmds.setAttr(module.settings_ctl+'.switchIkFk',1)
            activation = [cmds.getAttr(j+'.pushActivation') for j in pushes]
            cmds.setAttr('C_masterwalk_CTL.globalScale',1.7)
            errors = {j:(a,cmds.getAttr(j+'.pushActivation')) for a,j in zip(activation,pushes)
                      if abs(a-cmds.getAttr(j+'.pushActivation'))>1e-4}
            self.assertFalse(errors,errors)
            evaluations=[]
            for mode in ('off','serial','parallel'):
                cmds.evaluationManager(mode=mode)
                cmds.dgdirty(allPlugs=True)
                evaluations.append([v for j in pushes for v in cmds.xform(j,q=True,ws=True,m=True)])
            for values in evaluations[1:]:
                self.assertLess(max(abs(a-b) for a,b in zip(values,evaluations[0])),1e-5)
            self.assertTrue(all(math.isfinite(v) for v in evaluations[0]))
            self.assertFalse(cmds.cycleCheck(all=True,list=True))
            signatures.append(evaluations[0])
            path=Path(_CACHE.name)/('push_%d.mb'%repetition)
            cmds.file(rename=str(path));cmds.file(save=True,type='mayaBinary',force=True)
            cmds.file(new=True,force=True);cmds.file(str(path),open=True,force=True)
            reopened=[v for j in pushes for v in cmds.xform(j,q=True,ws=True,m=True)]
            self.assertLess(max(abs(a-b) for a,b in zip(reopened,evaluations[0])),1e-5)
        self.assertLess(max(abs(a-b) for a,b in zip(*signatures)),1e-5)


if __name__ == '__main__':unittest.main(verbosity=2)
