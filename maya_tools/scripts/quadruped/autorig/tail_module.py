import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils import guides_manager
from maya_tools.scripts.utils import curve_tool
from maya_tools.scripts.utils import matrix_manager
from maya_tools.scripts.utils import ribbon
from maya_tools.scripts.utils import guide_frames
from maya_tools.scripts.utils.module_nurbs import organize_module_nurbs

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)

class TailModule(object):

    def __init__(self):

        """
        Initialize the tailModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

        self.primary_axis = (1,0,0)
        self.secondary_axis = (0,-1,0)

    @organize_module_nurbs
    def make(self, side, skinning_joints_number, controllers_number):

        """ 
        Create the tail module structure and controllers. Call this method with the side ('L' or 'R') to create the respective tail module.
        Args:
            side (str): The side of the tail ('C').

        """
        self.side = side
        self.authored_orientation = guide_frames.enabled()
        self.skinning_joints_number = skinning_joints_number
        self.controllers_number = controllers_number

        self.module_trn = cmds.createNode("transform", name=f"{self.side}_tailModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_tailSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_tailControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.import_guides()
        self.fk_setup()
        # self.ik_setup()
        # self.pair_blends_setup()
        self.de_boors_call()

        data_manager.DataExportBiped().append_data("tail_module",
                            {
                                "tail_ctl": self.tail_controllers[0] if self.tail_controllers else None,
                            })

    
    def import_guides(self):

        """
        Import the tail guides and set up the tail joint chain based on the guides.
        """

        self.tail_chain = guides_manager.get_guides(f"{self.side}_tail00_JNT")

        self.tail_guides_matrices = guides_manager.sample_chain_matrices(
            self.tail_chain, self.controllers_number,
            self.primary_axis, self.secondary_axis)
        self.solver_guides_matrices = self.tail_guides_matrices
        if self.authored_orientation:
            self.tail_guides_matrices = guides_manager.sample_chain_matrices(
                self.tail_chain, len(self.solver_guides_matrices),
                self.primary_axis, self.secondary_axis, preserve_orientation=True)
        self.controllers_number = len(self.tail_guides_matrices)

    def fk_setup(self):

        """
        Create the tail controllers and set up their hierarchy and constraints.
        """

        self.tail_controllers = []

        for i in range(self.controllers_number):
            
            controller_name = f"{self.side}_tailFk{str(i).zfill(2)}"
            
            nodes, ctl = curve_tool.create_controller(
                name=controller_name,
                offset=["GRP", "ANM"],
                parent=self.tail_controllers[-1] if self.tail_controllers else self.controllers_grp,
                matrix=self.tail_guides_matrices[i],
                locked_attrs=["tx", "ty", "tz", "sx", "sy", "sz", "v"])
            
            self.tail_controllers.append(ctl)

        self.bendy_controllers = []
        #Create bendys
        for i, ctl in enumerate(self.tail_controllers):
            if i < self.controllers_number -1:
                bendy_name = f"{self.side}_tailBendy{str(i).zfill(2)}"
                bendy_nodes, bendy_ctl = curve_tool.create_controller(
                    name=bendy_name,
                    offset=["GRP", "ANM"],
                    parent=self.controllers_grp,
                    locked_attrs=["v"])
                
                cmds.addAttr(bendy_ctl, ln="EXTRA_ATTRIBUTES", niceName="EXTRA ATTRIBUTES ----", at="enum", en="-----", k=True)
                cmds.setAttr(f"{bendy_ctl}.EXTRA_ATTRIBUTES", e=True, keyable=False, channelBox=True)
                cmds.addAttr(bendy_ctl, ln="Bendy", at="double", min=0, max=1, dv=0.5, k=True)
                
                blend_matrix_node = cmds.createNode("blendMatrix", name=bendy_name.replace("CTL", "BLM"))
                cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{blend_matrix_node}.inputMatrix")
                cmds.connectAttr(f"{self.tail_controllers[i+1]}.worldMatrix[0]", f"{blend_matrix_node}.target[0].targetMatrix")
                cmds.connectAttr(f"{bendy_ctl}.Bendy", f"{blend_matrix_node}.envelope")
                cmds.connectAttr(f"{blend_matrix_node}.outputMatrix", f"{bendy_nodes[0]}.offsetParentMatrix")
                cmds.setAttr(f"{bendy_nodes[0]}.inheritsTransform", 0)
                self.bendy_controllers.append(bendy_ctl)

    def ik_setup(self):

        """
        Set up the IK handle for the tail and connect it to the tail controllers.
        """
        ik_controllers = []
        
        for i in range(self.controllers_number):

            if i == 0 or  i == self.controllers_number // 2 or i == self.controllers_number - 1:

                controller_name = f"{self.side}_tailIk{str(i).zfill(2)}"

                nodes, ctl = curve_tool.create_controller(
                    name=controller_name,
                    offset=["GRP", "ANM"],
                    parent=self.controllers_grp,
                    locked_attrs=["v"])
                
                if i == self.controllers_number // 2:
                    cmds.parent(nodes[0], ik_controllers[0])
                elif i == self.controllers_number - 1:
                    cmds.parent(nodes[0], ik_controllers[-2])
                ik_controllers.append(ctl)
                
            if i == 1 or i == self.controllers_number - 2:

                controller_name = f"{self.side}_tailIkTan{str(i).zfill(2)}"

                nodes, tan_ctl = curve_tool.create_controller(
                    name=controller_name,
                    offset=["GRP", "ANM"],
                    parent=ik_controllers[-1],
                    locked_attrs=["v"])
                
                ik_controllers.append(tan_ctl)

            # Store the sampled world frame in the current parent space.
            parent = cmds.listRelatives(nodes[0], parent=True)[0]
            local = om.MMatrix(self.tail_guides_matrices[i]) * om.MMatrix(cmds.getAttr(parent + ".worldInverseMatrix[0]"))
            cmds.setAttr(nodes[0] + ".offsetParentMatrix", list(local), type="matrix")
            cmds.xform(nodes[0], m=om.MMatrix.kIdentity)

        # Create IK chain
        ik_chain = []
        for ctl in range(self.controllers_number):

            jnt = cmds.createNode("joint", name=f"{self.side}_tailIk{str(ctl).zfill(2)}_JNT", ss=True, p=self.module_trn)
            if ik_chain:
                cmds.parent(jnt, ik_chain[-1])
            ik_chain.append(jnt)
        
        # Create IK curve 
        ik_curve = cmds.curve(
            name=f"{self.side}_tailIk_CRV",
            degree=3,
            point=[cmds.xform(jnt, q=True, ws=True, t=True) for jnt in ik_chain])
        
        # Create IK handle
        ik_handle = cmds.ikHandle(
            name=f"{self.side}_tailIk_HDL",
            startJoint=ik_chain[0],
            endEffector=ik_chain[-1],
            solver="ikSplineSolver",
            createCurve=False,
            curve=ik_curve)[0]
        
        cmds.parent(ik_curve, self.module_trn)
        cmds.parent(ik_handle, self.module_trn)

    def pair_blends_setup(self):

        """
        Set up pair blend constraints between tail controllers and joints for smooth deformation.
        """
        # Create pair blends between ik controllers and fk controllers
        self.blend_matrices_out = []

        for ctl, jnt in zip(self.tail_controllers, self.tail_chain):
            
            blend_matrix_node = cmds.createNode("blendMatrix", name=jnt.replace("JNT", "BLM"))
            cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{blend_matrix_node}.inputMatrix")
            cmds.connectAttr(f"{jnt}.worldMatrix[0]", f"{blend_matrix_node}.target[0].targetMatrix")
            self.blend_matrices_out.append(blend_matrix_node)


    def de_boors_call(self):

        """
        Set up the de Boor's algorithm for smooth tail deformation.
        """

        first_driver = [self.tail_controllers[0], self.bendy_controllers[0]]
        last_driver = [self.bendy_controllers[-1], self.tail_controllers[-1]]
        middle_drivers = self.tail_controllers[1:-1] if len(self.tail_controllers) > 2 else []
        ribbon_drivers = first_driver + middle_drivers + last_driver

        if self.tail_chain and cmds.objExists(self.tail_chain[0]):
            cmds.delete(self.tail_chain[0])

        if self.authored_orientation:
            solver = self.solver_guides_matrices
            solver_frames = ([solver[0], guide_frames.interpolate(solver[:2], 0.5)] +
                             solver[1:-1] + [guide_frames.interpolate(solver[-2:], 0.5), solver[-1]])
            rest_frames = [cmds.getAttr(guide_frames.matrix_plug(node)) for node in ribbon_drivers]
            ribbon_drivers = guide_frames.control_drivers(ribbon_drivers, rest_frames, solver_frames,
                                                         f"{self.side}_tailRibbon")
        skinning_jnts, temp = ribbon.de_boor_ribbon(cvs=ribbon_drivers, name=f"{self.side}_tail", num_joints=self.skinning_joints_number, skeleton_grp=self.skeleton_grp)
        if self.authored_orientation:
            guide_frames.orient_outputs(skinning_jnts, self.tail_guides_matrices, f"{self.side}_tail")

        for t in temp:
            cmds.delete(t)

    def extra_setup(self):

        """
        Perform any additional setup required for the tail module.
        """
        pass
