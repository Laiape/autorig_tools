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

class NeckModule(object):

    def __init__(self):

        """
        Initialize the neckModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.preferences_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")

        self.primary_axis = (1,0,0)
        self.secondary_axis = (0,1,0)

    @organize_module_nurbs
    def make(self, side, skinning_joints_number, controllers_number):

        """ 
        Create the neck module structure and controllers. Call this method with the side ('L' or 'R') to create the respective neck module.
        Args:
            side (str): The side of the neck ('L' or 'R').

        """
        self.side = side
        self.authored_orientation = guide_frames.enabled()
        self.controllers_number = controllers_number

        self.module_trn = cmds.createNode("transform", name=f"{self.side}_neckModule_GRP", ss=True, p=self.modules)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_neckControllers_GRP", ss=True, p=self.masterwalk_ctl)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_neckSkinning_GRP", ss=True, p=self.skel_grp)

        self.load_guides()
        self.controller_creation()
        self.ribbon_setup(skinning_joints_number)

        data_manager.DataExportBiped().append_data("neck_module",
                            {
                                "head_ctl": self.head_ctl,
                                "neck_ctl": self.neck_ctls[0],
                                "head_guide_matrix": self.head_guide_matrix,
                                "face_ctl": self.face_ctl,
                            })
        

    def load_guides(self):

        """
        Load the neck guides for the specified side and parent them to the module transform.
        """

        self.neck_chain = guides_manager.get_guides(f"{self.side}_neck00_JNT", parent=self.module_trn)
        cmds.select(clear=True)

        self.head_guide_matrix = cmds.getAttr(self.neck_chain[-1] + '.worldMatrix[0]')
        self.neck_guides_matrices = guides_manager.sample_chain_matrices(
            self.neck_chain, self.controllers_number,
            self.primary_axis, self.secondary_axis)
        self.solver_guides_matrices = self.neck_guides_matrices
        if self.authored_orientation:
            self.neck_guides_matrices = guides_manager.sample_chain_matrices(
                self.neck_chain, len(self.solver_guides_matrices),
                self.primary_axis, self.secondary_axis, preserve_orientation=True)
        self.controllers_number = len(self.neck_guides_matrices)
        cmds.delete(self.neck_chain[0])

    def controller_creation(self):

        """
        Create controllers for the neck module.
        """

        self.neck_nodes = []
        self.neck_ctls = []

        face_nodes, self.face_ctl = curve_tool.create_controller(name=f"{self.side}_face", offset=["GRP", "ANM"])
        curve_tool.lock_attributes(self.face_ctl, ["tx", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
        cmds.addAttr(self.face_ctl, longName="FACE_VIS", niceName="FACE VISIBILITY ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{self.face_ctl}.FACE_VIS", lock=True, keyable=False, channelBox=True)
        
        for i, matrix in enumerate(self.neck_guides_matrices):

            corner_nodes, corner_ctl = curve_tool.create_controller(name=f"{self.side}_neck{str(i).zfill(2)}", offset=["GRP", "ANM"], locked_attrs=["v"], parent=self.controllers_grp)
            cmds.setAttr(f"{corner_nodes[0]}.offsetParentMatrix", matrix, type="matrix")
                
            self.neck_nodes.append(corner_nodes[0])
            self.neck_ctls.append(corner_ctl)

        self.parent_neck_controls()
        self.control_follow_setup()

        # # Make hierarchy
        # for i, node in enumerate(self.neck_nodes):
        #     print(node)
        #     print(self.neck_ctls[i])
        #     if i == 1:
        #         cmds.parent(node, self.neck_ctls[0])
        #     if i == len(self.neck_nodes) // 2:
        #         ctl = self.neck_ctls[i]
        #         cmds.addAttr(ctl, longName="TANGENT_VISIBILITY", niceName="TANGENT VISIBILITY -----", attributeType="enum", enumName="-----")
        #         cmds.setAttr(f"{ctl}.TANGENT_VISIBILITY", lock=True, keyable=False, channelBox=True)
        #         cmds.addAttr(ctl, longName="Controllers_Visibility", niceName="Controllers Visibility", attributeType="float", minValue=0, maxValue=1, defaultValue=1, keyable=True)
        #         cmds.parent(node, self.neck_ctls[0])
        #     elif i == len(self.neck_nodes) - 2:
        #         cmds.parent(node, self.neck_ctls[-1])
        #     elif i == len(self.neck_nodes) - 1:
        #         cmds.parent(node, self.neck_ctls[len(self.neck_ctls)// 2])

        self.head_nodes, self.head_ctl = curve_tool.create_controller(name=f"{self.side}_head", offset=["GRP", "ANM"], parent=self.controllers_grp, locked_attrs=["v"])
        cmds.parent(face_nodes[0], self.head_ctl)
        cmds.setAttr(f"{self.head_nodes[0]}.inheritsTransform", 0)
        self.local_head()


        # ----- Stretch setup -----

        # Stretch UNIFORME (igual que el spine): un factor único multiplica por
        # igual la distancia entre todos los joints. factor = longitud real total
        # de la cadena de controles / longitud de reposo. Stretch float 0-1.
        cmds.addAttr(self.neck_ctls[0], longName="Stretch", niceName="STRETCH ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.neck_ctls[0]}.Stretch", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.neck_ctls[0], longName="Stretch_Activate", niceName="Stretch", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)

        if self.primary_axis == (1, 0, 0):
            translate_attr = "inputTranslateX"
        elif self.primary_axis == (0, 0, 1):
            translate_attr = "inputTranslateZ"
        else:
            translate_attr = "inputTranslateY"

        guide_positions = [om.MVector(m[12], m[13], m[14]) for m in self.neck_guides_matrices]
        rest_lengths = [(guide_positions[i] - guide_positions[i - 1]).length() for i in range(1, len(self.neck_ctls))]
        total_rest = sum(rest_lengths)

        # Longitud real total = suma de las distancias entre controles consecutivos
        total_dist = cmds.createNode("plusMinusAverage", name=f"{self.side}_neckStretchTotal_PMA", ss=True)
        cmds.setAttr(f"{total_dist}.operation", 1)  # sum
        for i in range(1, len(self.neck_ctls)):
            dbt = cmds.createNode("distanceBetween", name=f"{self.side}_neck{str(i).zfill(2)}StretchDist_DBT", ss=True)
            cmds.connectAttr(f"{self.neck_ctls[i - 1]}.worldMatrix[0]", f"{dbt}.inMatrix1")
            endpoint = self.head_ctl if i == len(self.neck_ctls) - 1 else self.neck_ctls[i]
            cmds.connectAttr(f"{endpoint}.worldMatrix[0]", f"{dbt}.inMatrix2")
            cmds.connectAttr(f"{dbt}.distance", f"{total_dist}.input1D[{i - 1}]")

        # Factor uniforme = (longitud real / globalScale) / longitud de reposo
        global_div = cmds.createNode("divide", name=f"{self.side}_neckStretchGlobal_DIV", ss=True)
        cmds.connectAttr(f"{total_dist}.output1D", f"{global_div}.input1")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{global_div}.input2")

        factor_div = cmds.createNode("divide", name=f"{self.side}_neckStretchFactor_DIV", ss=True)
        cmds.connectAttr(f"{global_div}.output", f"{factor_div}.input1")
        cmds.setAttr(f"{factor_div}.input2", total_rest)

        # Blend 1 (sin stretch) <-> factor (con stretch), por Stretch (float 0-1)
        factor_blend = cmds.createNode("blendTwoAttr", name=f"{self.side}_neckStretchFactor_B2A", ss=True)
        cmds.setAttr(f"{factor_blend}.input[0]", 1.0)
        cmds.connectAttr(f"{factor_div}.output", f"{factor_blend}.input[1]")
        cmds.connectAttr(f"{self.neck_ctls[0]}.Stretch_Activate", f"{factor_blend}.attributesBlender")

        endpoint_controls = self.neck_ctls[:-1] + [self.head_ctl]
        solve_controls = (guide_frames.control_drivers(endpoint_controls, self.neck_guides_matrices,
                           self.solver_guides_matrices, f"{self.side}_neck")
                          if self.authored_orientation else endpoint_controls)
        self.stretch_drivers = [solve_controls[0]]
        prev_plug = guide_frames.matrix_plug(solve_controls[0])

        for i in range(1, len(self.neck_ctls)):

            target_plug = guide_frames.matrix_plug(solve_controls[i])

            # Longitud uniforme de este segmento = rest_length * factor
            seg_len = cmds.createNode("multiply", name=f"{self.side}_neck{str(i).zfill(2)}StretchLen_MUL", ss=True)
            cmds.setAttr(f"{seg_len}.input[0]", rest_lengths[i - 1])
            cmds.connectAttr(f"{factor_blend}.output", f"{seg_len}.input[1]")

            aim = cmds.createNode("aimMatrix", name=f"{self.side}_neck{str(i).zfill(2)}Stretch_AIM", ss=True)
            cmds.setAttr(f"{aim}.primaryInputAxis", *self.primary_axis, type="double3")
            cmds.setAttr(f"{aim}.secondaryInputAxis", *self.secondary_axis, type="double3")
            cmds.setAttr(f"{aim}.secondaryTargetVector", *self.secondary_axis, type="double3")
            cmds.setAttr(f"{aim}.secondaryMode", 2)  # Align: el twist sigue al control
            cmds.connectAttr(prev_plug, f"{aim}.inputMatrix")
            cmds.connectAttr(target_plug, f"{aim}.primary.primaryTargetMatrix")
            cmds.connectAttr(target_plug, f"{aim}.secondary.secondaryTargetMatrix")

            cmx = cmds.createNode("composeMatrix", name=f"{self.side}_neck{str(i).zfill(2)}Stretch_CMX", ss=True)
            cmds.connectAttr(f"{seg_len}.output", f"{cmx}.{translate_attr}")

            mmx = cmds.createNode("multMatrix", name=f"{self.side}_neck{str(i).zfill(2)}Stretch_MMX", ss=True)
            cmds.connectAttr(f"{cmx}.outputMatrix", f"{mmx}.matrixIn[0]")
            cmds.connectAttr(f"{aim}.outputMatrix", f"{mmx}.matrixIn[1]")

            self.stretch_drivers.append(mmx)
            prev_plug = f"{mmx}.matrixSum"

        # A pinned head is an endpoint target, including when stretch is off.
        # Internal neck points can retain their normal fixed-length behavior.
        self.stretch_drivers[-1] = solve_controls[-1]

    def ribbon_setup(self, skinning_joints_number):

        """
        Set up the ribbon for the neck module.
        """
        # Los drivers del ribbon son la cadena de stretch (nodos DG).
        # tangent_cvs: sin tangentes la curva solo lee traslaciones y rotar un
        # driver únicamente twistea; con ellas el bend llega a los joints.
        guide_positions = [om.MVector(m[12], m[13], m[14]) for m in self.neck_guides_matrices]
        segment_length = (guide_positions[-1] - guide_positions[0]).length() / (len(guide_positions) - 1)

        sel = tuple(self.stretch_drivers)
        self.output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_neck", aim_axis="x", up_axis="y", skeleton_grp=self.skeleton_grp, num_joints=skinning_joints_number, d=3, tangent_cvs=0, tangent_axis="x", param_from_length=True) # Do the ribbon setup, with the created controllers (tangent_cvs=0 -> stretch uniforme)
        self.volume_setup(self.output_joints)
        if self.authored_orientation:
            guide_frames.orient_outputs(self.output_joints, self.neck_guides_matrices, f"{self.side}_neck")
        for t in temp:
            cmds.delete(t)

        for jnt in self.output_joints:
            cmds.setAttr(f"{jnt}.inheritsTransform", 1)

        self.output_joints[-1] = cmds.rename(self.output_joints[-1], f"{self.side}_headSkinning_JNT")
        self.head_skinning_setup(self.output_joints[-1])

    
    def local_head(self):

        """
        Create the local head setup to have the head follow the neck's movement.
        """

        cmds.addAttr(self.head_ctl, longName="SpaceFollow", niceName="Head Space",
                     attributeType="enum", enumName="Local:Global", defaultValue=0, keyable=True)

        head_neck_offset = om.MMatrix(self.head_guide_matrix) * om.MMatrix(cmds.getAttr(f"{self.neck_ctls[-1]}.worldMatrix[0]")).inverse()
        neck_space_mmx = cmds.createNode("multMatrix", name=f"{self.side}_headNeckSpace_MMX", ss=True)
        cmds.setAttr(f"{neck_space_mmx}.matrixIn[0]", list(head_neck_offset), type="matrix")
        cmds.connectAttr(f"{self.neck_ctls[-1]}.worldMatrix[0]", f"{neck_space_mmx}.matrixIn[1]")

        blend_matrix_head = cmds.createNode("blendMatrix", name=f"{self.side}_headLocal_BLM", ss=True)
        cmds.connectAttr(f"{neck_space_mmx}.matrixSum", f"{blend_matrix_head}.inputMatrix")
        cmds.setAttr(f"{blend_matrix_head}.target[0].targetMatrix", self.head_guide_matrix, type="matrix")
        cmds.setAttr(f"{blend_matrix_head}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_head}.target[0].shearWeight", 0)
        cmds.connectAttr(f"{self.head_ctl}.SpaceFollow", f"{blend_matrix_head}.target[0].weight")
        cmds.connectAttr(f"{blend_matrix_head}.outputMatrix", f"{self.head_nodes[0]}.offsetParentMatrix", force=True)

    def parent_neck_controls(self):
        """Make local neck/head follow the neck root's selected body space."""
        for i in range(1, len(self.neck_ctls)):
            cmds.parent(self.neck_nodes[i], self.neck_ctls[0], relative=True)
            rest = om.MMatrix(self.neck_guides_matrices[i]) * om.MMatrix(self.neck_guides_matrices[0]).inverse()
            cmds.setAttr(self.neck_nodes[i] + '.offsetParentMatrix', list(rest), type='matrix')
            cmds.xform(self.neck_nodes[i], matrix=list(om.MMatrix.kIdentity))

    def head_skinning_setup(self, joint, rest=None):
        """Move the actual head skin with the animator control, preserving bind."""
        rest = rest if rest is not None else cmds.getAttr(joint + '.worldMatrix[0]')
        driver = guide_frames.calibrated_output(self.head_ctl + '.worldMatrix[0]', rest,
                                                f'{self.side}_headControlSkin',
                                                scale_plug=self.masterwalk_ctl + '.globalScale')
        cmds.connectAttr(driver, joint + '.offsetParentMatrix', force=True)

    def control_follow_setup(self):
        """Let each non-root neck control opt out of following the neck root."""
        from maya_tools.scripts.utils.matrix_manager import control_follow_switch
        for ctl in self.neck_ctls[1:]:
            parent = cmds.listRelatives(ctl.replace('_CTL', '_GRP'), parent=True)[0]
            control_follow_switch(ctl, parent, self.masterwalk_ctl)

    def volume_setup(self, joints, drivers=None, connect=True):
        """Keep neck volume in the solver frame independently of the head."""
        from maya_tools.scripts.utils.ribbon_volume import create_volume_matrix
        drivers = drivers or [cmds.connectionInfo(j + '.offsetParentMatrix', sourceFromDestination=True) for j in joints]
        volume = create_volume_matrix(drivers, self.neck_ctls[0], self.masterwalk_ctl, f'{self.side}_neckVolume')
        result = []
        for i, (joint, plug) in enumerate(zip(joints, drivers)):
            node = cmds.createNode('multMatrix', name=f'{self.side}_neckVolume{i:02d}_MMX', ss=True)
            cmds.connectAttr(volume, node + '.matrixIn[0]')
            cmds.connectAttr(plug, node + '.matrixIn[1]')
            result.append(node + '.matrixSum')
            if connect:
                cmds.connectAttr(result[-1], joint + '.offsetParentMatrix', force=True)
        return result
