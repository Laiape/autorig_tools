"""Run with mayapy: digit settings placement, hidden controls and persistence."""
import ast
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

os.environ.setdefault('MAYA_SKIP_USERSETUP_PY','1')
import maya.standalone
from maya import cmds
from maya.api import OpenMaya as om

ROOT=Path(__file__).resolve().parents[4]
SCRIPTS=ROOT/'maya_tools/scripts'
sys.path.insert(0,str(ROOT))


def close(a,b):
    assert max(abs(x-y) for x,y in zip(a,b))<1e-7,(a,b)


def run():
    maya.standalone.initialize(name='python')
    try:
        from maya_tools.scripts.utils import controller_display
        from test_quadruped_guide_paths import functions
        curve_scope=dict(cmds=cmds,om=om,build_curves_from_template=lambda name:None)
        curves=functions(SCRIPTS/'utils/curve_tool.py',{'create_controller','lock_attributes'},curve_scope)
        with tempfile.TemporaryDirectory() as folder:
            for side in ('L','R'):
                cmds.file(new=True,force=True)
                parent=cmds.createNode('transform',name='controls')
                cmds.setAttr(parent+'.translate',5,4,-3)
                cmds.setAttr(parent+'.rotateY',20)
                cmds.setAttr(parent+'.scale',2.2,.7,1.4)
                follow=cmds.createNode('transform',name='paw')
                cmds.setAttr(follow+'.translate',3,1,5)
                digit_group=cmds.createNode('transform',name='digits')
                cmds.setAttr(digit_group+'.inheritsTransform',0)
                cmds.connectAttr(follow+'.worldMatrix[0]',digit_group+'.offsetParentMatrix')
                prefix=side+'_frontLegDigit'
                chains={}
                for d,roman in enumerate(('II','III','IV','V')):
                    chains[roman]=[]
                    for i in range(3):
                        n=prefix+roman+'%02dFk'%i
                        nodes,ctl=curves.create_controller(n,offset=['GRP','SDK','ANM'],
                            parent=digit_group if i==0 else chains[roman][-1])
                        world=[1,0,0,0,0,1,0,0,0,0,1,0,3+d*.6,1.0,5+i*.7,1]
                        cmds.xform(nodes[0],ws=True,m=world)
                        chains[roman].append(ctl)
                before={ctl:cmds.xform(ctl,q=True,ws=True,m=True) for chain in chains.values() for ctl in chain}
                # Execute the actual PawFoot authoring method, excluding unrelated imports/build code.
                path=SCRIPTS/'quadruped/autorig/leg_module_self.py'
                tree=ast.parse(path.read_text(encoding='utf-8'))
                method=next(m for c in tree.body if isinstance(c,ast.ClassDef) and c.name=='PawFoot'
                            for m in c.body if isinstance(m,ast.FunctionDef) and m.name=='digits_attributes')
                scope=dict(cmds=cmds,om=om,curve_tool=curves)
                exec(compile(ast.Module(body=[method],type_ignores=[]),str(path),'exec'),scope)
                paw=SimpleNamespace(finger_base_name=prefix,leg_digit_fk_ctls=chains,
                                    digit_chains={k:{} for k in chains})
                leg=SimpleNamespace(controllers_grp=parent,blend_plugs=[follow+'.worldMatrix[0]'],leg_end_index=0)
                scope['digits_attributes'](paw,leg)
                ctl=paw.paw_attributes_ctl
                group=paw.paw_attributes_grp[0]
                p=cmds.xform(ctl,q=True,ws=True,t=True)
                close((p[0],p[2]),(3.9,5.7))
                assert p[1]>1.0
                assert cmds.getAttr(ctl+'.visibility')
                assert not cmds.getAttr(ctl+'.Controllers_Visibility')
                assert cmds.attributeQuery('Controllers_Visibility',node=ctl,listDefault=True)==[0]
                for chain in chains.values():
                    assert not cmds.getAttr(chain[0].replace('_CTL','_GRP')+'.visibility')
                for enabled in (True,False):
                    cmds.setAttr(ctl+'.Controllers_Visibility',enabled)
                    for chain in chains.values():
                        assert cmds.getAttr(chain[0].replace('_CTL','_GRP')+'.visibility')==enabled
                    for node,matrix in before.items():
                        close(cmds.xform(node,q=True,ws=True,m=True),matrix)
                rest=om.MMatrix(cmds.xform(group,q=True,ws=True,m=True))
                inv=om.MMatrix(cmds.xform(follow,q=True,ws=True,m=True)).inverse()
                cmds.setAttr(follow+'.translate',9,3,7)
                cmds.setAttr(follow+'.rotate',13,37,-5)
                cmds.setAttr(follow+'.scale',1.7,.8,1.2)
                expected=list(rest*inv*om.MMatrix(cmds.xform(follow,q=True,ws=True,m=True)))
                for mode in ('off','serial','parallel'):
                    cmds.evaluationManager(mode=mode)
                    close(cmds.xform(group,q=True,ws=True,m=True),expected)
                # Legacy digit builder calls the same helper before its MTP attachment.
                extra,_=curves.create_controller(side+'_backLegDigitsAttributes',offset=['GRP'],parent=parent)
                legacy=extra[0].replace('_GRP','_CTL')
                # Use independent controls so the existing visibility connections remain protected.
                legacy_nodes,legacy_ctl=curves.create_controller(side+'_legacyDigit00',offset=['GRP'],parent=parent)
                controller_display.configure_digit_settings(legacy,[[legacy_ctl]])
                assert not cmds.getAttr(legacy_nodes[0]+'.visibility')
                scene=Path(folder)/(side+'_digit_display.ma')
                cmds.file(rename=str(scene));cmds.file(save=True,type='mayaAscii',force=True)
                cmds.file(str(scene),open=True,force=True)
                close(cmds.xform(group,q=True,ws=True,m=True),expected)
                assert not cmds.getAttr(ctl+'.Controllers_Visibility')
                assert not cmds.cycleCheck(all=True,list=True)
                print('PASS',side,'PawFoot placement, both visibility states, unchanged FK matrices, native follow, DG/Serial/Parallel, reopen',flush=True)
    finally:
        cmds.file(new=True,force=True)
        maya.standalone.uninitialize()


if __name__=='__main__':
    run()
