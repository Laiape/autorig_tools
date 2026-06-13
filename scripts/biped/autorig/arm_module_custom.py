from turtle import up

import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool
from utils import matrix_manager
from utils import ribbon
from utils import custom_ik_solver

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)
reload(custom_ik_solver)

class ArmModule(object):

    def __init__(self):

        """
        Initialize the ArmModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        
    def make(self, side, skinning_jnts, primaryInputAxis = (1, 0, 0), secondaryInputAxis = (0, 0, 1)):

        """ 
        Create the arm module structure and controllers. Call this method with the side ('L' or 'R') to create the respective arm module.
        Args:
            side (str): The side of the arm ('L' or 'R').
            primaryInputAxis (tuple): The primary axis for orientation.
            secondaryInputAxis (tuple): The secondary axis for orientation.

        """
        self.skinning_joint_numbers = skinning_jnts
        self.side = side

        self.primaryInputAxis = primaryInputAxis if self.side == "L" else tuple(-x for x in primaryInputAxis)
        self.secondaryInputAxis = secondaryInputAxis if self.side == "L" else tuple(-x for x in secondaryInputAxis)

        self.module_name = f"{self.side}_arm"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_chains()
        self.controllers_creation()
        self.ik_setup()
        self.fk_stretch()
        self.elbow_pin_setup()
        skel_env = self.de_boor_ribbon(self.skinning_joint_numbers)

        cmds.delete(self.arm_chain[0])
        
        data_manager.DataExportBiped().append_data("arm_module",
                            {
                                f"{self.side}_shoulder_JNT": self.arm_chain[0],
                                f"{self.side}_wrist_JNT": self.wrist_skinning,
                                f"{self.side}_armSettings": self.settings_ctl,
                                f"{self.side}_armIk": self.ik_wrist_ctl,
                                f"{self.side}_armPv": self.pv_ctl,
                                f"{self.side}_shoulderFk": self.fk_controllers[0],
                                f"{self.side}_armIkRoot": self.ik_root_ctl,
                                f"{self.side}_skinningJoints": skel_env
                            })

    def lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)
    
    def load_guides(self):

        self.arm_chain = guides_manager.get_guides(f"{self.side}_shoulder_JNT")
        cmds.parent(self.arm_chain[0], self.module_trn)
        self.settings_loc = guides_manager.get_guides(f"{self.side}_armSettings_LOCShape")

        self.guides_matrices, self.guides_trns = guides_manager.orient_guides(self.arm_chain, self.primaryInputAxis, self.secondaryInputAxis)

    def create_chains(self):

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.side}_armSettings", offset=["GRP"], parent=self.controllers_grp, locked_attrs=["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility", "rotateOrder"], match=self.settings_loc)
        cmds.delete(self.settings_loc)
        cmds.addAttr(self.settings_ctl, longName="Ik_Fk", niceName= "Switch IK --> FK", attributeType="float", defaultValue=1, minValue=0, maxValue=1, keyable=True)

        # IK is solved analytically (cosine law) as a pure matrix network in
        # ik_setup() -> no IK joint chain, no ikHandle, no evaluation cycle.

    def controllers_creation(self):

        """
        Create controllers for the arm module.
        """
        self.fk_nodes = []
        self.fk_controllers = []
        self.blend_matrices = []

        fk_controllers_trn = cmds.createNode("transform", name=f"{self.side}_armFkControllers_GRP", ss=True, p=self.controllers_grp)

        for i, joint in enumerate(self.arm_chain):

            fk_node, fk_ctl = curve_tool.create_controller(name=joint.replace("_JNT", "Fk"), offset=["GRP", "ANM"]) # create FK controllers
            self.lock_attributes(fk_ctl, ["translateX", "translateY", "translateZ", "scaleX", "scaleY", "scaleZ", "visibility"])

            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])

            self.fk_nodes.append(fk_node[0])
            self.fk_controllers.append(fk_ctl)

            if i == 0:
                cmds.connectAttr(self.guides_matrices[i], f"{fk_node[0]}.offsetParentMatrix") # First FK controller follows the guide
                blend_matrix = matrix_manager.fk_blend(joint, None, fk_ctl, None, self.settings_ctl)

            else:
                mmx_negate = cmds.createNode("multMatrix", name=joint.replace("JNT", "MMX"), ss=True)
                inverse_matrix = cmds.createNode("inverseMatrix", name=joint.replace("JNT", "INV"), ss=True)
                cmds.connectAttr(self.guides_matrices[i-1], f"{inverse_matrix}.inputMatrix")

                cmds.connectAttr(self.guides_matrices[i], f"{mmx_negate}.matrixIn[0]")
                cmds.connectAttr(f"{inverse_matrix}.outputMatrix", f"{mmx_negate}.matrixIn[1]")

                cmds.connectAttr(f"{mmx_negate}.matrixSum", f"{fk_node[0]}.offsetParentMatrix", force=True) # Other FK controllers follow the relative guide position
                blend_matrix = matrix_manager.fk_blend(joint, None, fk_ctl, self.arm_chain[i-1], self.settings_ctl)

            cmds.xform(fk_node[0], m=om.MMatrix.kIdentity)

            self.blend_matrices.append(blend_matrix)

        cmds.parent(self.fk_nodes[0], fk_controllers_trn)


        self.ik_controllers = []
        self.ik_controllers = []

        ik_controllers_trn = cmds.createNode("transform", name=f"{self.side}_armIkControllers_GRP", ss=True, p=self.controllers_grp)

        self.ik_wrist_nodes, self.ik_wrist_ctl = curve_tool.create_controller(name=f"{self.side}_armIkWrist", offset=["GRP", "SPC"])
        self.lock_attributes(self.ik_wrist_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.ik_wrist_nodes[0], ik_controllers_trn)
        # cmds.matchTransform(self.ik_wrist_nodes[0], self.arm_chain[-1], pos=True, rot=True)
        cmds.connectAttr(self.guides_matrices[-1], f"{self.ik_wrist_nodes[0]}.offsetParentMatrix")

        self.pv_nodes, self.pv_ctl = curve_tool.create_controller(name=f"{self.side}_armPv", offset=["GRP", "SPC"])
        self.lock_attributes(self.pv_ctl, ["rx", "ry", "rz", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.pv_nodes[0], ik_controllers_trn)

        cmds.addAttr(self.pv_ctl, shortName="extraAttr", niceName="EXTRA_ATTRIBUTES", enumName="———", attributeType="enum", keyable=True)
        cmds.setAttr(self.pv_ctl + ".extraAttr", channelBox=True, lock=True)
        cmds.addAttr(self.pv_ctl, shortName="pvOrientation", niceName="Pv Orientation", defaultValue=1, minValue=0, maxValue=1, keyable=True)

        # Place the pole vector in the guide plane (matrix math) so the IK aim
        # frame keeps the guide secondary axis on the shoulder and the elbow.
        pv_pos = self.create_matrix_pole_vector(
            f"{self.guides_matrices[0]}", f"{self.guides_matrices[1]}", f"{self.guides_matrices[2]}",
            name=f"{self.side}_{self.module_name}PV")
        cmds.connectAttr(f"{self.pv_ctl}.pvOrientation", f"{pv_pos}.target[0].weight")
        cmds.connectAttr(f"{pv_pos}.outputMatrix", f"{self.pv_nodes[0]}.offsetParentMatrix", force=True)

        crv_point_pv = cmds.curve(d=1, p=[(0, 0, 1), (0, 1, 0)], n=f"{self.side}_armPv_CRV") # Create a line that points always to the PV
        row_knee = cmds.createNode("rowFromMatrix", name=f"{self.side}_armPv_RFM", ss=True)
        row_ctl = cmds.createNode("rowFromMatrix", name=f"{self.side}_armPvCtl_RFM", ss=True)
        cmds.setAttr(f"{row_knee}.input", 3)  # translation row
        cmds.setAttr(f"{row_ctl}.input", 3)
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{row_ctl}.matrix")
        cmds.connectAttr(self.guides_matrices[1], f"{row_knee}.matrix")
        for axis, value in zip("XYZ", ("xValue", "yValue", "zValue")):
            cmds.connectAttr(f"{row_knee}.output{axis}", f"{crv_point_pv}.controlPoints[0].{value}")
            cmds.connectAttr(f"{row_ctl}.output{axis}", f"{crv_point_pv}.controlPoints[1].{value}")
        cmds.setAttr(f"{crv_point_pv}.inheritsTransform", 0)
        cmds.setAttr(f"{crv_point_pv}.overrideEnabled", 1)
        cmds.setAttr(f"{crv_point_pv}.overrideDisplayType", 1)
        cmds.setAttr(f"{crv_point_pv}.hiddenInOutliner", 1)

        cmds.parent(crv_point_pv, self.pv_ctl)

        self.ik_root_nodes, self.ik_root_ctl = curve_tool.create_controller(name=f"{self.side}_armIkRoot", offset=["GRP"])
        self.lock_attributes(self.ik_root_ctl, ["rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.ik_root_nodes[0], ik_controllers_trn)
        cmds.connectAttr(self.guides_matrices[0], f"{self.ik_root_nodes[0]}.offsetParentMatrix")
        cmds.xform(self.ik_root_nodes[0], m=om.MMatrix.kIdentity)

        reverse_node = cmds.createNode("reverse", name=f"{self.side}_armIkFK_REV", ss=True)
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{reverse_node}.inputX")
        cmds.connectAttr(f"{reverse_node}.outputX", f"{ik_controllers_trn}.visibility")
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{fk_controllers_trn}.visibility")

    def create_matrix_pole_vector(self, m1_attr, m2_attr, m3_attr, pole_distance=1.0, name="poleVector_LOC"):
        """
        Given three matrix attributes (e.g. joint.worldMatrix[0]), compute a proper pole vector
        position using Maya matrix and math nodes (no Python vector math).
        """
        def matrix_to_translation(matrix_attr, prefix):
            dm = cmds.createNode('rowFromMatrix', name=f"{self.side}_{self.module_name}Pv{prefix.capitalize()}Offset_RFM", ss=True)
            cmds.connectAttr(matrix_attr, f'{dm}.matrix')
            cmds.setAttr(f'{dm}.input', 3)
            return f'{dm}.output'

        def create_vector_subtract(name, inputA, inputB):
            node = cmds.createNode('plusMinusAverage', name=f"{self.side}_{self.module_name}Pv{name.capitalize()}_PMA", ss=True)
            cmds.setAttr(f'{node}.operation', 2)
            for i, input in enumerate([inputA, inputB]):
                try:
                    cmds.connectAttr(input, f'{node}.input3D[{i}]')
                except:
                    for attr in ["X", "Y", "Z"]:
                        cmds.connectAttr(f'{input}.output{attr}', f'{node}.input3D[{i}].input3D{attr.lower()}')
            return node, f'{node}.output3D'

        def normalize_vector(input_vec, name):
            vp = cmds.createNode('normalize', name=f"{self.side}_{self.module_name}Pv{name.capitalize()}_NRM", ss=True)
            cmds.connectAttr(input_vec, f'{vp}.input')
            return f'{vp}.output'

        def scale_vector(input_vec, scalar_attr, name):
            mults = []
            outputs = []
            for axis in 'XYZ':
                mult = cmds.createNode('multiply', name=f"{self.side}_{self.module_name}Pv{name.capitalize()}{axis}_MUL", ss=True)
                cmds.connectAttr(f'{input_vec}{axis}', f'{mult}.input[0]')
                cmds.connectAttr(scalar_attr, f'{mult}.input[1]')
                mults.append(mult)
                outputs.append(f'{mult}.output')
            return mults, outputs

        def add_vectors(vecA, vecB, name):
            node = cmds.createNode('plusMinusAverage', name=f"{self.side}_{self.module_name}Pv{name.capitalize()}_PMA", ss=True)
            for i, vector in enumerate([vecA, vecB]):
                if isinstance(vector, (list, tuple)):
                    for axis, plug in zip("xyz", vector):
                        cmds.connectAttr(plug, f'{node}.input3D[{i}].input3D{axis}')
                    continue
                try:
                    cmds.connectAttr(vector, f'{node}.input3D[{i}]')
                except:
                    for attr in ["X", "Y", "Z"]:
                        cmds.connectAttr(f'{vector}.output{attr}', f'{node}.input3D[{i}].input3D{attr.lower()}')
            return node, f'{node}.output3D'

        vec1_attr = matrix_to_translation(m1_attr, 'vec1')
        vec2_attr = matrix_to_translation(m2_attr, 'vec2')
        vec3_attr = matrix_to_translation(m3_attr, 'vec3')

        dist1 = cmds.createNode('distanceBetween', name=f"{self.side}_{self.module_name}PvVec1Vec2_DBT", ss=True)
        for attr in ["X", "Y", "Z"]:
            cmds.connectAttr(f'{vec1_attr}{attr}', f'{dist1}.point1{attr}')
            cmds.connectAttr(f'{vec2_attr}{attr}', f'{dist1}.point2{attr}')

        dist2 = cmds.createNode('distanceBetween', name=f"{self.side}_{self.module_name}PvVec2Vec3_DBT", ss=True)
        for attr in ["X", "Y", "Z"]:
            cmds.connectAttr(f'{vec2_attr}{attr}', f'{dist2}.point1{attr}')
            cmds.connectAttr(f'{vec3_attr}{attr}', f'{dist2}.point2{attr}')

        avg = cmds.createNode('sum', name=f"{self.side}_{self.module_name}PvAvgDist_SUM", ss=True)
        cmds.connectAttr(f'{dist1}.distance', f'{avg}.input[0]')
        cmds.connectAttr(f'{dist2}.distance', f'{avg}.input[1]')

        half = cmds.createNode('divide', name=f"{self.side}_{self.module_name}PvHalfDist_DIV", ss=True)
        cmds.setAttr(f'{half}.input2', 2.0 / pole_distance)
        cmds.connectAttr(f'{avg}.output', f'{half}.input1')

        vec1_sub_node, vec1_sub = create_vector_subtract('vec1MinusVec2', vec1_attr, vec2_attr)
        vec1_norm = normalize_vector(vec1_sub, 'vec1Norm')

        vec3_sub_node, vec3_sub = create_vector_subtract('vec3MinusVec2', vec3_attr, vec2_attr)
        vec3_norm = normalize_vector(vec3_sub, 'vec3Norm')

        vec1_scaled_node, vec1_scaled = scale_vector(vec1_norm, f'{half}.output', 'vec1Scaled')
        vec3_scaled_node, vec3_scaled = scale_vector(vec3_norm, f'{half}.output', 'vec3Scaled')

        vec1_final_node, vec1_final = add_vectors(vec2_attr, vec1_scaled, 'vec1Final')
        vec3_final_node, vec3_final = add_vectors(vec2_attr, vec3_scaled, 'vec3Final')

        proj_dir_node, proj_dir = create_vector_subtract('projDir', vec3_final, vec1_final)

        proj_dir_norm = normalize_vector(proj_dir, 'projDirNorm')

        vec_to_project_node, vec_to_project = create_vector_subtract('vecToProject', vec2_attr, vec1_final)

        dot_node = cmds.createNode('vectorProduct', name=f"{self.side}_{self.module_name}PvDot_VCP", ss=True)
        cmds.setAttr(f'{dot_node}.operation', 1)
        cmds.connectAttr(vec_to_project, f'{dot_node}.input1')
        cmds.connectAttr(proj_dir_norm, f'{dot_node}.input2')

        proj_vec_node, proj_vec = scale_vector(proj_dir_norm, f'{dot_node}.outputX', 'projVector')

        mid_node, mid = add_vectors(vec1_final, proj_vec, 'midPoint')

        pointer_node, pointer_vec = create_vector_subtract('pointerVec', vec2_attr, mid)

        pointer_norm = normalize_vector(pointer_vec, 'pointerNorm')
        pointer_scaled_node, pointer_scaled = scale_vector(pointer_norm, f'{half}.output', 'pointerScaled')

        pole_pos_node, pole_pos = add_vectors(vec2_attr, pointer_scaled, 'poleVectorPos')

        fourByFour = cmds.createNode('fourByFourMatrix', name=f"{self.side}_{self.module_name}PvFourByFour_FBM", ss=True)
        cmds.connectAttr(f"{pole_pos}.output3Dx", f'{fourByFour}.in30')
        cmds.connectAttr(f"{pole_pos}.output3Dy", f'{fourByFour}.in31')
        cmds.connectAttr(f"{pole_pos}.output3Dz", f'{fourByFour}.in32')

        aim_matrix = cmds.createNode('aimMatrix', name=f"{self.side}_{self.module_name}PvAim_AMX", ss=True)
        cmds.setAttr(f'{aim_matrix}.primaryInputAxis', 0, 0, 1, type='double3')
        cmds.setAttr(f'{aim_matrix}.secondaryInputAxis', 1, 0, 0, type='double3')
        cmds.setAttr(f'{aim_matrix}.secondaryTargetVector', 1, 0, 0, type='double3')
        cmds.setAttr(f'{aim_matrix}.primaryMode', 1)
        cmds.setAttr(f'{aim_matrix}.secondaryMode', 2)
        cmds.connectAttr(f'{fourByFour}.output', f'{aim_matrix}.inputMatrix')
        cmds.connectAttr(f'{m2_attr}', f"{aim_matrix}.primaryTargetMatrix")
        cmds.connectAttr(f'{m2_attr}', f'{aim_matrix}.secondaryTargetMatrix')

        blend_matrix = cmds.createNode('blendMatrix', name=f"{self.side}_{self.module_name}PvBlend_BLM", ss=True)
        cmds.connectAttr(f'{fourByFour}.output', f'{blend_matrix}.inputMatrix')
        cmds.connectAttr(f'{aim_matrix}.outputMatrix', f'{blend_matrix}.target[0].targetMatrix')

        return blend_matrix

    def ik_setup(self):

        """
        Analytic IK (cosine law) built as a pure matrix network via
        custom_ik_solver.triangle_solver — no ikHandle, no IK joint chain and no
        evaluation cycle.  Stretch and soft IK are solved inside the solver.
        The arm has NO ikHandle manager (that is a foot-only feature), so it is
        not passed here.
        """

        cmds.addAttr(self.ik_wrist_ctl, shortName="STRETCHY____", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.ik_wrist_ctl}.STRETCHY____", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="upperLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="lowerLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="Stretch", minValue=0, defaultValue=0, maxValue=1, keyable=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="SOFT____", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.ik_wrist_ctl}.SOFT____", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="Soft", minValue=0, defaultValue=0, maxValue=1, keyable=True)
        cmds.addAttr(self.ik_wrist_ctl, shortName="Soft_Start", minValue=0, defaultValue=0.8, maxValue=1, keyable=True)

        self.lock_attributes(self.pv_ctl, ["sx", "sy", "sz", "v"])

        secondary_mode = (0, 1, 0) if self.side == "L" else (0, -1, 0)

        raw_ik_matrices = custom_ik_solver.triangle_solver(
            name=f"{self.side}_armIk", guides=self.guides_matrices,
            controllers=[self.ik_root_ctl, self.pv_ctl, self.ik_wrist_ctl],
            use_stretch=True, use_soft=True,
            primary_mode=self.primaryInputAxis, secondary_mode=secondary_mode)

        self.ik_matrices = []
        for i, raw in enumerate(raw_ik_matrices):
            if i == 2:
                self.ik_matrices.append(raw)
                continue
            raw_rest = om.MMatrix(cmds.getAttr(raw))
            guide_rest = om.MMatrix(cmds.getAttr(self.guides_matrices[i]))
            offset = guide_rest * raw_rest.inverse()
            offset_mmx = cmds.createNode("multMatrix", name=f"{self.side}_armIkAxisRoll{i}_MMX", ss=True)
            cmds.setAttr(f"{offset_mmx}.matrixIn[0]", list(offset), type="matrix")
            cmds.connectAttr(raw, f"{offset_mmx}.matrixIn[1]")
            self.ik_matrices.append(f"{offset_mmx}.matrixSum")

        for ik_matrix, blend_matrix in zip(self.ik_matrices, self.blend_matrices):
            cmds.connectAttr(f"{ik_matrix}", f"{blend_matrix[0]}.inputMatrix")

    def fk_stretch(self):

        """
        Setup FK stretch for the arm module.
        """

        for i, ctl in enumerate(self.fk_controllers):
            if i < len(self.fk_controllers) - 1:
                
                # cmds.setAttr(f"{ctl}.translateX", lock=False)
                cmds.addAttr(ctl, longName="STRETCHY", niceName="STRETCHY ------", attributeType="enum", enumName="------")
                cmds.setAttr(f"{ctl}.STRETCHY", keyable=False, channelBox=True, lock=True)
                cmds.addAttr(ctl, shortName="Stretch", minValue=0, defaultValue=1, keyable=True)

                label = ctl.split("_")[1]
                mult_node = cmds.createNode("multiply", n=f"{self.side}_arm{label}_MUL")
                dist_node = cmds.createNode("distanceBetween", name=f"{self.side}_arm{label}DistanceBetween_DBT", ss=True)

                cmds.connectAttr(f"{ctl}.Stretch", f"{mult_node}.input[0]")
                cmds.connectAttr(self.guides_matrices[i], f"{dist_node}.inMatrix1")
                cmds.connectAttr(self.guides_matrices[i+1], f"{dist_node}.inMatrix2")
                
                if self.side == "R":
                    multiply_negate = cmds.createNode("multiply", name=f"{self.side}_arm{label}_Negate_MUL", ss=True)
                    cmds.connectAttr(f"{dist_node}.distance", f"{multiply_negate}.input[0]")
                    cmds.setAttr(f"{multiply_negate}.input[1]", -1)
                    cmds.connectAttr(f"{multiply_negate}.output", f"{mult_node}.input[1]")
                else:
                    cmds.connectAttr(f"{dist_node}.distance", f"{mult_node}.input[1]")

                target_node = self.fk_nodes[i+1]
                
                row_translate = cmds.createNode("rowFromMatrix", name=f"{self.side}_arm{label}RowFromMatrix_RFM", ss=True)
                cmds.setAttr(f"{row_translate}.input", 3)
                
                connection = cmds.listConnections(f"{target_node}.offsetParentMatrix", source=True, destination=False, plugs=True)[0]
                cmds.connectAttr(connection, f"{row_translate}.matrix")
                fbf = cmds.createNode("fourByFourMatrix", name=f"{self.side}_arm{label}_FBF", ss=True)

                row_x = cmds.createNode("rowFromMatrix", name=f"{self.side}_arm{label}RowX_RFM", ss=True)
                row_y = cmds.createNode("rowFromMatrix", name=f"{self.side}_arm{label}RowY_RFM", ss=True)
                row_z = cmds.createNode("rowFromMatrix", name=f"{self.side}_arm{label}RowZ_RFM", ss=True)
                cmds.setAttr(f"{row_x}.input", 0)
                cmds.setAttr(f"{row_y}.input", 1)
                cmds.setAttr(f"{row_z}.input", 2)
                cmds.connectAttr(connection, f"{row_x}.matrix")
                cmds.connectAttr(connection, f"{row_y}.matrix")
                cmds.connectAttr(connection, f"{row_z}.matrix")

                cmds.connectAttr(f"{row_x}.outputX", f"{fbf}.in00")
                cmds.connectAttr(f"{row_x}.outputY", f"{fbf}.in01")
                cmds.connectAttr(f"{row_x}.outputZ", f"{fbf}.in02")

                cmds.connectAttr(f"{row_y}.outputX", f"{fbf}.in10")
                cmds.connectAttr(f"{row_y}.outputY", f"{fbf}.in11")
                cmds.connectAttr(f"{row_y}.outputZ", f"{fbf}.in12")

                cmds.connectAttr(f"{row_z}.outputX", f"{fbf}.in20")
                cmds.connectAttr(f"{row_z}.outputY", f"{fbf}.in21")
                cmds.connectAttr(f"{row_z}.outputZ", f"{fbf}.in22")

                cmds.connectAttr(f"{mult_node}.output", f"{fbf}.in30")
                cmds.connectAttr(f"{row_translate}.outputY", f"{fbf}.in31")
                cmds.connectAttr(f"{row_translate}.outputZ", f"{fbf}.in32")

                cmds.connectAttr(f"{fbf}.output", f"{target_node}.offsetParentMatrix", force=True)


    def elbow_pin_setup(self):

        """
        Elbow pin: snap the IK elbow matrix (ik_matrices[1]) to the pole vector
        controller position, weighted by the pv_ctl 'Pin' attribute.  Pure matrix
        network (blendMatrix) feeding the elbow blend's IK input.
        """
        cmds.addAttr(self.pv_ctl, longName="EXTRA_ATTRIBUTES", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{self.pv_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(self.pv_ctl, longName="Pin", niceName="Elbow Pin", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)

        pin_blm = cmds.createNode("blendMatrix", name=f"{self.side}_armElbowPin_BLM", ss=True)
        cmds.connectAttr(self.ik_matrices[1], f"{pin_blm}.inputMatrix")
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{pin_blm}.target[0].targetMatrix")
        cmds.connectAttr(f"{self.pv_ctl}.Pin", f"{pin_blm}.target[0].weight")
        cmds.setAttr(f"{pin_blm}.target[0].rotateWeight", 0)
        cmds.setAttr(f"{pin_blm}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{pin_blm}.target[0].shearWeight", 0)
        cmds.connectAttr(f"{pin_blm}.outputMatrix", f"{self.blend_matrices[1][0]}.inputMatrix", force=True)


    def de_boor_ribbon(self, skinning_joint_numbers):

        """
        Create a de Boor ribbon setup.
        """




        nonRollAlign = cmds.createNode("blendMatrix", name=f"{self.side}_armNonRollAlign_BLM", ss=True)
        nonRollAim = cmds.createNode("aimMatrix", name=f"{self.side}_armNonRollAim_AMX", ss=True)
        self.nonRollAim = nonRollAim
        blend_matrix_nodes = cmds.createNode("blendMatrix", name=f"{self.side}_armNonRollControllers_BLM", ss=True)

        cmds.connectAttr(f"{self.ik_root_nodes[0]}.worldMatrix[0]", f"{blend_matrix_nodes}.inputMatrix")
        cmds.connectAttr(f"{self.fk_nodes[0]}.worldMatrix[0]", f"{blend_matrix_nodes}.target[0].targetMatrix")
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{blend_matrix_nodes}.target[0].weight")

        cmds.connectAttr(f"{self.blend_matrices[0][0]}.outputMatrix", f"{nonRollAlign}.inputMatrix")
        cmds.connectAttr(f"{blend_matrix_nodes}.outputMatrix", f"{nonRollAlign}.target[0].targetMatrix")
        cmds.setAttr(f"{nonRollAlign}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{nonRollAlign}.target[0].translateWeight", 0)
        cmds.setAttr(f"{nonRollAlign}.target[0].shearWeight", 0)
        

        cmds.connectAttr(f"{nonRollAlign}.outputMatrix", f"{nonRollAim}.inputMatrix")
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{nonRollAim}.primaryTargetMatrix")
        cmds.setAttr(f"{nonRollAim}.primaryInputAxis", *self.primaryInputAxis, type="double3")
       

        # ----- Roll setup via swing-twist (quaternion), composed entirely with utility nodes -----
        aim_letter = ['x', 'y', 'z'][[abs(v) for v in self.primaryInputAxis].index(1)]
        aim_comp = aim_letter.upper()

        el = om.MVector(cmds.xform(self.arm_chain[1], q=True, ws=True, t=True))
        wr = om.MVector(cmds.xform(self.arm_chain[2], q=True, ws=True, t=True))
        forearm_len = (wr - el).length()
        forearm_len = forearm_len if self.side == "L" else -forearm_len

        # UPPER — twisted shoulder frame (rotation only) feeding the up-roll blend.
        # Quaternion fed straight into composeMatrix.inputQuat (useEulerRotation=0):
        # avoids the matrix->rotate->matrix round-trip (no quatToEuler).
        upper_twist = matrix_manager.extract_twist(
            f"{self.blend_matrices[0][0]}.outputMatrix", f"{nonRollAim}.outputMatrix",
            axis=aim_letter, name=f"{self.side}_armUpper", return_quat=True)
        upper_twist_cmp = cmds.createNode("composeMatrix", name=f"{self.side}_armUpperRollTwist_CMP", ss=True)
        cmds.setAttr(f"{upper_twist_cmp}.useEulerRotation", 0)
        cmds.connectAttr(f"{upper_twist}.outputQuat", f"{upper_twist_cmp}.inputQuat")
        upper_twist_mm = cmds.createNode("multMatrix", name=f"{self.side}_armUpperRollTwist_MMX", ss=True)
        cmds.connectAttr(f"{upper_twist_cmp}.outputMatrix", f"{upper_twist_mm}.matrixIn[0]")
        cmds.connectAttr(f"{nonRollAim}.outputMatrix", f"{upper_twist_mm}.matrixIn[1]")

        # LOWER — twisted forearm frame offset to the wrist (aim target for the ribbon)
        lower_twist = matrix_manager.extract_twist(
            f"{self.blend_matrices[2][0]}.outputMatrix", f"{self.blend_matrices[1][0]}.outputMatrix",
            axis=aim_letter, name=f"{self.side}_armLower", return_quat=True)
        lower_twist_cmp = cmds.createNode("composeMatrix", name=f"{self.side}_armLowerRollTwist_CMP", ss=True)
        cmds.setAttr(f"{lower_twist_cmp}.useEulerRotation", 0)
        cmds.connectAttr(f"{lower_twist}.outputQuat", f"{lower_twist_cmp}.inputQuat")
        cmds.setAttr(f"{lower_twist_cmp}.inputTranslate{aim_comp}", forearm_len)
        lower_twist_mm = cmds.createNode("multMatrix", name=f"{self.side}_armLowerRollTwist_MMX", ss=True)
        cmds.connectAttr(f"{lower_twist_cmp}.outputMatrix", f"{lower_twist_mm}.matrixIn[0]")
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{lower_twist_mm}.matrixIn[1]")
        # Far anchor must track the REAL wrist position (so it follows stretch),
        # taking only the twisted forearm rotation — mirrors the upper's up_roll_blm.
        lower_roll_pm = cmds.createNode("blendMatrix", name=f"{self.side}_armLowerRoll_BLM", ss=True)
        cmds.connectAttr(f"{self.blend_matrices[2][0]}.outputMatrix", f"{lower_roll_pm}.inputMatrix")
        cmds.connectAttr(f"{lower_twist_mm}.matrixSum", f"{lower_roll_pm}.target[0].targetMatrix")
        cmds.setAttr(f"{lower_roll_pm}.target[0].translateWeight", 0)
        cmds.setAttr(f"{lower_roll_pm}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{lower_roll_pm}.target[0].shearWeight", 0)

        # Up Roll Blend Matrix — replaces the shoulder rotation with the twisted frame
        up_roll_blm = cmds.createNode("blendMatrix", name=f"{self.side}_armUpperRoll_BLM", ss=True)
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{up_roll_blm}.inputMatrix")
        cmds.connectAttr(f"{upper_twist_mm}.matrixSum", f"{up_roll_blm}.target[0].targetMatrix")
        cmds.setAttr(f"{up_roll_blm}.target[0].translateWeight", 0)
        cmds.setAttr(f"{up_roll_blm}.target[0].rotateWeight", 1)
        cmds.setAttr(f"{up_roll_blm}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{up_roll_blm}.target[0].shearWeight", 0)

        self.upper_skinning_jnt_trn = self.de_boor_ribbon_callout([nonRollAim], [up_roll_blm], "Upper", skinning_joint_numbers)
        self.lower_skinning_jnt_trn = self.de_boor_ribbon_callout(self.blend_matrices[1], [lower_roll_pm], "Lower", skinning_joint_numbers)

        cmds.select(clear=True)
        self.wrist_skinning = cmds.joint(name=f"{self.side}_wristSkinning_JNT")
        cmds.connectAttr(f"{self.blend_matrices[-1][0]}.outputMatrix", f"{self.wrist_skinning}.offsetParentMatrix")
        cmds.parent(self.wrist_skinning, self.skeleton_grp)

        self.curvature_setup()
        self.volume_preservation()

        # Contraint settings controller to first skinning joint
        first_skinning_jnt = self.upper_skinning_jnt_trn[0]
        parent_matrix = cmds.createNode("parentMatrix", name=first_skinning_jnt.replace("JNT", "PMX"), ss=True)
        settings_ctl_world_matrix = cmds.getAttr(f"{self.settings_node[0]}.worldMatrix[0]")
        cmds.setAttr(f"{parent_matrix}.inputMatrix", settings_ctl_world_matrix, type="matrix")
        cmds.connectAttr(f"{first_skinning_jnt}.worldMatrix[0]", f"{parent_matrix}.target[0].targetMatrix")
        offset_matrix = matrix_manager.get_offset_matrix(self.settings_node[0], first_skinning_jnt)
        cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{self.settings_node[0]}.offsetParentMatrix")
        cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", offset_matrix, type="matrix")
        cmds.xform(self.settings_node[0], m=om.MMatrix.kIdentity)
        cmds.setAttr(f"{self.settings_node[0]}.inheritsTransform", 0)

    def de_boor_ribbon_callout(self, first_sel, second_sel, part, skinning_joint_numbers):

        if cmds.objExists(f"{first_sel[0]}.outputMatrix"):
            first_sel_output = f"{first_sel[0]}.outputMatrix"
        if cmds.objExists(f"{first_sel}.outputMatrix"):
            first_sel_output = f"{first_sel}.outputMatrix"
        elif cmds.objExists(f"{first_sel[0]}.worldMatrix[0]"):
            first_sel_output = f"{first_sel[0]}.worldMatrix[0]"

        if cmds.objExists(f"{second_sel[0]}.outputMatrix"):
            second_sel_output = f"{second_sel[0]}.outputMatrix"
        elif cmds.objExists(f"{second_sel[0]}.worldMatrix[0]"):
            second_sel_output = f"{second_sel[0]}.worldMatrix[0]"

        main_bendy_nodes, main_bendy_ctl = curve_tool.create_controller(name=f"{self.module_name}{part}MainBendy", offset=["GRP"])
        up_bendy_nodes, up_bendy_ctl = curve_tool.create_controller(name=f"{self.module_name}{part}UpBendy", offset=["GRP"])
        low_bendy_nodes, low_bendy_ctl = curve_tool.create_controller(name=f"{self.module_name}{part}LowBendy", offset=["GRP"])

        # Store the main bendy controller (curvature CV) and the bendy groups (volume scale)
        setattr(self, f"{part.lower()}_main_bendy_ctl", main_bendy_ctl)
        setattr(self, f"{part.lower()}_bendy_grps", [up_bendy_nodes[0], main_bendy_nodes[0], low_bendy_nodes[0]])

        for node in [main_bendy_nodes[0], up_bendy_nodes[0], low_bendy_nodes[0]]:

            cmds.parent(node, self.controllers_grp)
            cmds.setAttr(f"{node}.inheritsTransform", 0)

        
        aim_matrix = cmds.createNode("aimMatrix", name=f"{self.module_name}{part}MainBendy_AMT", ss=True)
        cmds.connectAttr(first_sel_output, f"{aim_matrix}.inputMatrix")
        cmds.connectAttr(second_sel_output, f"{aim_matrix}.primaryTargetMatrix")

        cmds.setAttr(f"{aim_matrix}.primaryInputAxis", *self.primaryInputAxis, type="double3")
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxis", *self.secondaryInputAxis, type="double3")

        blend_matrix = cmds.createNode("blendMatrix", name=f"{self.module_name}{part}MainBendy_BMT", ss=True)
        cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{blend_matrix}.inputMatrix")
        cmds.connectAttr(second_sel_output, f"{blend_matrix}.target[0].targetMatrix")
        cmds.setAttr(f"{blend_matrix}.target[0].translateWeight", 0.5)
        cmds.setAttr(f"{blend_matrix}.target[0].rotateWeight", 0)
        cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{main_bendy_nodes[0]}.offsetParentMatrix")

        for i, ctl in enumerate([main_bendy_ctl, up_bendy_ctl, low_bendy_ctl]):

            self.lock_attributes(ctl, ["visibility"])

            if i == 0:
                cmds.addAttr(ctl, longName = "BENDY", niceName="BENDY ------", attributeType="enum", enumName="------", keyable=True)
                cmds.setAttr(f"{ctl}.BENDY", keyable=False, channelBox=True, lock=True)
                cmds.addAttr(ctl, longName="Height", attributeType="float", minValue=0, defaultValue=0.5, maxValue=1, keyable=True)
                cmds.addAttr(ctl, longName="Extra_Controllers", attributeType="bool", keyable=False)
                cmds.setAttr(f"{ctl}.Extra_Controllers", channelBox=True)

        cmds.connectAttr(f"{main_bendy_ctl}.Height", f"{blend_matrix}.target[0].translateWeight") # Connect Height to blend_matrix_main
        cmds.connectAttr(f"{main_bendy_ctl}.Extra_Controllers", f"{up_bendy_nodes[0]}.visibility")
        cmds.connectAttr(f"{main_bendy_ctl}.Extra_Controllers", f"{low_bendy_nodes[0]}.visibility")

        for i, ctl in enumerate([up_bendy_nodes[0], low_bendy_nodes[0]]):

            blend_matrix_ = cmds.createNode("blendMatrix", name=f"{ctl}_BMT", ss=True)
            cmds.connectAttr(f"{aim_matrix}.outputMatrix", f"{blend_matrix_}.inputMatrix")
            cmds.connectAttr(second_sel_output, f"{blend_matrix_}.target[0].targetMatrix")
            if i == 0:
                cmds.setAttr(f"{blend_matrix_}.target[0].translateWeight", 0.25)
            elif i == 1:
                cmds.setAttr(f"{blend_matrix_}.target[0].translateWeight", 0.75)
            cmds.setAttr(f"{blend_matrix_}.target[0].rotateWeight", 0)
            cmds.connectAttr(f"{blend_matrix_}.outputMatrix", f"{ctl}.offsetParentMatrix")


        sel = (first_sel[0], up_bendy_ctl, main_bendy_ctl, low_bendy_ctl, second_sel[0])

        params = [i / (len(sel) - 1) for i in range(len(sel))] # Custom parameter to place the last joint in the 0.95 position
        params[-1] = 0.95

        def get_axis_info(axis_tuple):
            for i, val in enumerate(axis_tuple):
                if val != 0:
                    return i, val
            return 0, 1

        aim_idx, aim_sign = get_axis_info(self.primaryInputAxis)
        up_idx, up_sign = get_axis_info(self.secondaryInputAxis)

        # 3. Mapeo a letras
        axis_map = ['x', 'y', 'z']
        aim_axis = axis_map[aim_idx]
        up_axis = axis_map[up_idx]
        aim_axis_signed = f"{'-' if aim_sign < 0 else ''}{aim_axis}"
        up_axis_signed = f"{'' if up_sign < 0 else ''}{up_axis}"
        
        output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.module_name}{part}", custom_parameter=params, aim_axis=aim_axis_signed, up_axis=up_axis_signed, skeleton_grp=self.skeleton_grp, num_joints=skinning_joint_numbers) # Call the ribbon script to create de Boors system

        for t in temp:
            cmds.delete(t)

        return output_joints
  

    def curvature_setup(self):

        """
        Build a single smooth cubic (degree 3) de Boor curve spanning the whole
        arm (shoulder -> elbow -> wrist, using the main bendy controllers as the
        intermediate CVs) and blend the existing skinning joints toward it with a
        'Curvature' attribute on the settings controller.

        At Curvature = 0 the joints keep the current two-ribbon solution; at
        Curvature = 1 they follow the smooth cubic, rounding out the elbow into a
        continuous arc from shoulder to wrist.  The same output joints are reused
        (only a blendMatrix is inserted before each joint's offsetParentMatrix).
        """

        # ----- axis info (matches the per-segment ribbon axes)
        def axis_info(axis_tuple):
            for i, val in enumerate(axis_tuple):
                if val != 0:
                    return i, val
            return 0, 1

        aim_idx, aim_sign = axis_info(self.primaryInputAxis)
        up_idx, _ = axis_info(self.secondaryInputAxis)
        axis_map = ['x', 'y', 'z']
        aim_axis = f"{'-' if aim_sign < 0 else ''}{axis_map[aim_idx]}"
        up_axis = axis_map[up_idx]

        # ----- whole-arm control vertices (5 CVs -> degree 3 cubic B-spline)
        cvs = [
            self.nonRollAim,                  # shoulder
            self.upper_main_bendy_ctl,        # mid upper arm
            self.blend_matrices[1][0],        # elbow
            self.lower_main_bendy_ctl,        # mid forearm
            self.blend_matrices[2][0],        # wrist
        ]

        # ----- global parameter for every existing joint (upper then lower),
        # split proportionally to the rest length of each segment so the smooth
        # targets stay aligned with the current joints
        sh = om.MVector(cmds.xform(self.arm_chain[0], q=True, ws=True, t=True))
        el = om.MVector(cmds.xform(self.arm_chain[1], q=True, ws=True, t=True))
        wr = om.MVector(cmds.xform(self.arm_chain[2], q=True, ws=True, t=True))
        upper_len = (el - sh).length()
        lower_len = (wr - el).length()
        total = upper_len + lower_len
        split = upper_len / total if total else 0.5

        seg = [i / 4.0 for i in range(5)]
        seg[-1] = 0.95
        global_params = [p * split for p in seg] + [split + p * (1 - split) for p in seg]

        # ----- build the smooth cubic ribbon as temporary driver joints
        driver_jnts, temp = ribbon.de_boor_ribbon(
            cvs, name=f"{self.module_name}Curvature", d=3, custom_parameter=global_params,
            aim_axis=aim_axis, up_axis=up_axis, skeleton_grp=self.skeleton_grp,
            num_joints=len(global_params))

        for t in temp:
            cmds.delete(t)

        # capture the matrix plug feeding each driver joint, then disconnect and
        # delete the joints.  Disconnecting first leaves the feeder nodes alive
        # (a plain joint delete would otherwise drag its input history with it).
        driver_plugs = []
        for dj in driver_jnts:
            src = cmds.listConnections(f"{dj}.offsetParentMatrix", source=True, destination=False, plugs=True)
            plug = src[0] if src else None
            driver_plugs.append(plug)
            if plug:
                cmds.disconnectAttr(plug, f"{dj}.offsetParentMatrix")
        cmds.delete(driver_jnts)

        # ----- Curvature attributes on the settings controller
        if not cmds.attributeQuery("Curvature", node=self.settings_ctl, exists=True):
            cmds.addAttr(self.settings_ctl, longName="Curvature", attributeType="float",
                         minValue=0, maxValue=1, defaultValue=0, keyable=True)
            cmds.addAttr(self.settings_ctl, longName="AutoBend", niceName="Auto Curvature",
                         attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)

        # auto curvature from the elbow bend (dot-based, no flip), added to the manual value
        bend_plug = matrix_manager.bend_factor(
            self.blend_matrices[0][0], self.blend_matrices[1][0], self.blend_matrices[2][0],
            name=f"{self.module_name}Curvature")
        auto_mult = cmds.createNode("multiply", name=f"{self.module_name}AutoCurvature_MUL", ss=True)
        cmds.connectAttr(bend_plug, f"{auto_mult}.input[0]")
        cmds.connectAttr(f"{self.settings_ctl}.AutoBend", f"{auto_mult}.input[1]")
        curv_sum = cmds.createNode("sum", name=f"{self.module_name}Curvature_SUM", ss=True)
        cmds.connectAttr(f"{self.settings_ctl}.Curvature", f"{curv_sum}.input[0]")
        cmds.connectAttr(f"{auto_mult}.output", f"{curv_sum}.input[1]")
        curv_clamp = cmds.createNode("clamp", name=f"{self.module_name}Curvature_CLP", ss=True)
        cmds.setAttr(f"{curv_clamp}.maxR", 1)
        cmds.connectAttr(f"{curv_sum}.output", f"{curv_clamp}.inputR")
        curvature_weight = f"{curv_clamp}.outputR"

        # ----- blend every existing skinning joint toward its smooth target
        existing = list(self.upper_skinning_jnt_trn) + list(self.lower_skinning_jnt_trn)
        for jnt, dplug in zip(existing, driver_plugs):

            if dplug is None:
                continue

            current = cmds.listConnections(f"{jnt}.offsetParentMatrix", source=True, destination=False, plugs=True)
            if not current:
                continue

            blend = cmds.createNode("blendMatrix", name=jnt.replace("_JNT", "Curvature_BLM"), ss=True)
            cmds.connectAttr(current[0], f"{blend}.inputMatrix")
            cmds.connectAttr(dplug, f"{blend}.target[0].targetMatrix")
            cmds.connectAttr(curvature_weight, f"{blend}.target[0].weight")
            cmds.connectAttr(f"{blend}.outputMatrix", f"{jnt}.offsetParentMatrix", force=True)

    def volume_preservation(self):

        """
        Volume preservation: squash/stretch the cross-section by 1/sqrt(stretch)
        per segment, driven by a 'Volume' attribute (0 = off).

        The scale is applied to the BENDY CONTROL groups (the ribbon CVs) instead
        of to the skinning joints directly: the ribbon then interpolates the scale
        smoothly along the output joints, tapering to 1 at the segment ends, so it
        never tears the mesh (which raw per-joint scaling did with hard weights).
        """

        if not cmds.attributeQuery("Volume", node=self.settings_ctl, exists=True):
            cmds.addAttr(self.settings_ctl, longName="Volume", attributeType="float",
                         minValue=0, maxValue=1, defaultValue=0, keyable=True)

        sh = om.MVector(cmds.xform(self.arm_chain[0], q=True, ws=True, t=True))
        el = om.MVector(cmds.xform(self.arm_chain[1], q=True, ws=True, t=True))
        wr = om.MVector(cmds.xform(self.arm_chain[2], q=True, ws=True, t=True))

        upper_scale = matrix_manager.segment_volume(
            self.blend_matrices[0][0], self.blend_matrices[1][0], (el - sh).length(),
            f"{self.settings_ctl}.Volume", f"{self.masterwalk_ctl}.globalScale",
            name=f"{self.module_name}Upper")
        lower_scale = matrix_manager.segment_volume(
            self.blend_matrices[1][0], self.blend_matrices[2][0], (wr - el).length(),
            f"{self.settings_ctl}.Volume", f"{self.masterwalk_ctl}.globalScale",
            name=f"{self.module_name}Lower")

        for grp in self.upper_bendy_grps:
            cmds.connectAttr(upper_scale, f"{grp}.scaleY")
            cmds.connectAttr(upper_scale, f"{grp}.scaleZ")
        for grp in self.lower_bendy_grps:
            cmds.connectAttr(lower_scale, f"{grp}.scaleY")
            cmds.connectAttr(lower_scale, f"{grp}.scaleZ")

