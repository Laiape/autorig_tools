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

class LegModule(object):

    def __init__(self):

        """
        Initialize the LegModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.local_hip_ctl = data_manager.DataExportBiped().get_data("spine_module", "local_hip_ctl")

    def make(self, side, skinning_jnts, primaryInputAxis=(1, 0, 0), secondaryInputAxis=(0, -1, 0)):

        """ 
        Create the leg module structure and controllers. Call this method with the side ('L' or 'R') to create the respective leg module.
        Args:
            side (str): The side of the leg ('L' or 'R').

        """
        self.skinning_joint_numbers = skinning_jnts
        self.side = side

        self.primary_axis = primaryInputAxis if self.side == "L" else tuple(-x for x in primaryInputAxis)
        self.secondary_axis = secondaryInputAxis if self.side == "L" else tuple(-x for x in secondaryInputAxis)

        # Set the axis information based on the primary and secondary input axes
        def get_axis_info(axis_tuple):
            for i, val in enumerate(axis_tuple):
                if val != 0:
                    return i, val
            return 0, 1

        aim_idx, aim_sign = get_axis_info(self.primary_axis)
        up_idx, up_sign = get_axis_info(self.secondary_axis)

        axis_map = ['x', 'y', 'z']
        aim_axis = axis_map[aim_idx]
        up_axis = axis_map[up_idx]
        self.aim_axis_signed = (f"{'-' if aim_sign < 0 else ''}{aim_axis}")
        self.up_axis_signed = f"{'' if up_sign < 0 else ''}{up_axis}"

        # Create the main groups for the leg module
        self.module_name = f"{self.side}_leg"
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_legModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_legSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_legControllers_GRP", ss=True, p=self.masterwalk_ctl)

        
        # Build the leg module by calling the respective methods
        self.load_guides()
        self.create_chains()
        self.controllers_creation()
        self.fk_stretch()
        self.ik_setup()
        self.knee_pin_setup()
        self.foot_attributes()
        self.de_boor_ribbon(self.skinning_joint_numbers)

        cmds.delete(self.leg_chain[0]) 

        data_manager.DataExportBiped().append_data("leg_module",
                            {
                                f"{self.side}_hip_JNT": self.leg_chain[0],
                                f"{self.side}_knee_JNT": self.leg_chain[1],
                                f"{self.side}_ankle_JNT": self.leg_chain[2],
                                f"{self.side}_legIk": self.ik_controllers[0],
                                f"{self.side}_hipFk": self.fk_controllers[0],
                                f"{self.side}_legPv": self.pv_ctl,
                                f"{self.side}_rootIk": self.root_ik_ctl,
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

        self.leg_chain = guides_manager.get_guides(f"{self.side}_hip_JNT")
        cmds.parent(self.leg_chain[0], self.module_trn)
        self.settings_loc = guides_manager.get_guides(f"{self.side}_legSettings_LOCShape")
        self.bank_out_loc = guides_manager.get_guides(f"{self.side}_bankOut_LOCShape")
        self.bank_in_loc = guides_manager.get_guides(f"{self.side}_bankIn_LOCShape")
        self.heel_loc = guides_manager.get_guides(f"{self.side}_heel_LOCShape")


        self.guides_matrices, self.guides_trns = guides_manager.orient_guides(guides=self.leg_chain, primaryInputAxis=self.primary_axis, secondaryInputAxis=self.secondary_axis)


    def create_chains(self):

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.side}_legSettings", offset=["GRP"])
        self.lock_attributes(self.settings_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility", "rotateOrder"])
        cmds.matchTransform(self.settings_node[0], self.settings_loc, pos=True, rot=True)
        cmds.delete(self.settings_loc)
        cmds.addAttr(self.settings_ctl, longName="Ik_Fk", niceName= "Switch IK --> FK", attributeType="float", defaultValue=0, minValue=0, maxValue=1, keyable=True)
        cmds.parent(self.settings_node[0], self.controllers_grp)

        # IK is solved analytically (cosine law) as a pure matrix network in
        # ik_setup() -> no IK joint chain, no ikHandle, no evaluation cycle.

    def controllers_creation(self):

        """
        Create controllers for the leg module.
        """
        # FK Controllers
        self.fk_nodes = []
        self.fk_controllers = []
        self.blend_matrices = []

        fk_controllers_trn = cmds.createNode("transform", name=f"{self.side}_legFkControllers_GRP", ss=True, p=self.controllers_grp)
        

        for i, joint in enumerate(self.leg_chain):

            if i < len(self.leg_chain) - 1:
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
                    blend_matrix = matrix_manager.fk_blend(joint, None, fk_ctl, self.leg_chain[i-1], self.settings_ctl)

                cmds.xform(fk_node[0], m=om.MMatrix.kIdentity)

                self.blend_matrices.append(blend_matrix)

        cmds.parent(self.fk_nodes[0], fk_controllers_trn)
        

        # IK Controllers
        ik_controllers_trn = cmds.createNode("transform", name=f"{self.side}_legIkControllers_GRP", ss=True, p=self.controllers_grp)
        reverse_node = cmds.createNode("reverse", name=f"{self.side}_legIkFkReverse", ss=True)
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{reverse_node}.inputX")
        cmds.connectAttr(f"{reverse_node}.outputX", f"{ik_controllers_trn}.visibility")
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{fk_controllers_trn}.visibility")
        
        ik_controller_dict = {

            "ankleIk": self.guides_matrices[2],
            "bankOut": self.bank_out_loc,
            "bankIn": self.bank_in_loc,
            "heel": self.heel_loc,
            "toeIk": self.guides_matrices[4],
            "ballIk": self.guides_matrices[3],

        }

        self.ik_nodes = []
        self.ik_sdk_nodes = []
        self.ik_controllers = []

        for i, (name, guide) in enumerate(ik_controller_dict.items()):

            ik_node, ik_ctl = curve_tool.create_controller(name=f"{self.side}_{name}", offset=["GRP", "SDK"])
            self.lock_attributes(ik_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])

            # Rest world matrix of this control's guide (matrix plug or locator).
            if "." in str(guide):
                guide_rest = om.MMatrix(cmds.getAttr(guide))
                is_locator = False
            else:
                guide_rest = om.MMatrix(cmds.getAttr(f"{guide}.worldMatrix[0]"))
                is_locator = True

            if i == 0:
                # Ankle foot control: world-oriented position (no rotation).
                pick_matrix = cmds.createNode("pickMatrix", name=f"{self.side}_{name}_PKM", ss=True)
                cmds.setAttr(f"{pick_matrix}.useRotate", 0)
                cmds.connectAttr(self.guides_matrices[2], f"{pick_matrix}.inputMatrix")
                if self.side == "R":
                    matrix_manager.mirror_controllers(controllers_grp=[ik_node[0]], input_matrix=f"{pick_matrix}.outputMatrix", secondary_axis=self.secondary_axis, rotate_180=True)
                else:
                    cmds.connectAttr(f"{pick_matrix}.outputMatrix", f"{ik_node[0]}.offsetParentMatrix")
            else:
                # Parent under the previous reverse-foot control, then bake a
                # CONSTANT offsetParentMatrix = guide_rest * parent_rest^-1, so the
                # control's pivot rests on its guide AND it follows its parent in
                # the reverse-foot chain (live opm would pin it to the guide).
                cmds.parent(ik_node[0], self.ik_controllers[-1])
                parent_rest = om.MMatrix(cmds.getAttr(f"{self.ik_controllers[-1]}.worldMatrix[0]"))
                opm = guide_rest * parent_rest.inverse()
                cmds.setAttr(f"{ik_node[0]}.offsetParentMatrix", list(opm), type="matrix")
                cmds.xform(ik_node[0], matrix=list(om.MMatrix.kIdentity))

            # Delete the locator guide once its position has been captured.
            if is_locator:
                child = cmds.listRelatives(guide, children=True, type="locator")
                if child:
                    cmds.delete(guide)

            self.ik_nodes.append(ik_node[0])
            self.ik_sdk_nodes.append(ik_node[1])
            self.ik_controllers.append(ik_ctl)

        cmds.parent(self.ik_nodes[0], ik_controllers_trn)

        self.root_ik_nodes, self.root_ik_ctl = curve_tool.create_controller(name=f"{self.side}_legRootIk", offset=["GRP", "ANM"])
        self.lock_attributes(self.root_ik_ctl, ["rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.connectAttr(self.guides_matrices[0], f"{self.root_ik_nodes[0]}.offsetParentMatrix")

        cmds.xform(self.root_ik_nodes[0], m=om.MMatrix.kIdentity)
        for attr in ["translate", "rotate", "jointOrient"]:
            for axis in ["X", "Y", "Z"]:
                cmds.setAttr(f"{self.leg_chain[0]}.{attr}{axis}", 0)

        cmds.parent(self.root_ik_nodes[0], ik_controllers_trn)

        # Create PV controller
        self.pv_nodes, self.pv_ctl = curve_tool.create_controller(name=f"{self.side}_legPv", offset=["GRP", "ANM"])
        self.lock_attributes(self.pv_ctl, ["rx", "ry", "rz", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.pv_nodes[0], ik_controllers_trn)

        cmds.addAttr(self.pv_ctl, shortName="extraAttr", niceName="EXTRA_ATTRIBUTES", enumName="———", attributeType="enum", keyable=True)
        cmds.setAttr(self.pv_ctl + ".extraAttr", channelBox=True, lock=True)
        cmds.addAttr(self.pv_ctl, shortName="pvOrientation", niceName="Pv Orientation", defaultValue=1, minValue=0, maxValue=1, keyable=True)

        # Place the pole vector in the guide plane (matrix math) so the IK aim
        # frame keeps the guide secondary axis on the hip and the knee.
        pv_pos = self.create_matrix_pole_vector(
            f"{self.guides_matrices[0]}", f"{self.guides_matrices[1]}", f"{self.guides_matrices[2]}",
            name=f"{self.side}_{self.module_name}PV")
        cmds.connectAttr(f"{self.pv_ctl}.pvOrientation", f"{pv_pos}.target[0].weight")
        cmds.connectAttr(f"{pv_pos}.outputMatrix", f"{self.pv_nodes[0]}.offsetParentMatrix", force=True)

        crv_point_pv = cmds.curve(d=1, p=[(0, 0, 1), (0, 1, 0)], n=f"{self.side}_legPv_CRV") # Create a line that points always to the PV
        row_knee = cmds.createNode("rowFromMatrix", name=f"{self.side}_legPv_RFM", ss=True)
        row_ctl = cmds.createNode("rowFromMatrix", name=f"{self.side}_legPvCtl_RFM", ss=True)
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
        cmds.parent(crv_point_pv, self.pv_ctl)
        cmds.setAttr(f"{crv_point_pv}.hiddenInOutliner", 1)


    
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
        Analytic IK (cosine law) as a pure matrix network (custom_ik_solver.
        triangle_solver) with the foot driven through the ikHandle manager — no
        ikHandle, no IK joint chain, no evaluation cycle.  Stretch/soft are solved
        inside the solver; the ball uses single_chain_solver.
        """

        cmds.addAttr(self.ik_controllers[0], shortName="STRETCHY____", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.ik_controllers[0]}.STRETCHY____", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.ik_controllers[0], shortName="upperLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_controllers[0], shortName="lowerLengthMult", minValue=0.001, defaultValue=1, keyable=True)
        cmds.addAttr(self.ik_controllers[0], shortName="Stretch", minValue=0, defaultValue=0, maxValue=1, keyable=True)
        cmds.addAttr(self.ik_controllers[0], shortName="SOFT____", attributeType="enum", enumName="____", keyable=True)
        cmds.setAttr(f"{self.ik_controllers[0]}.SOFT____", lock=True, keyable=False, channelBox=True)
        cmds.addAttr(self.ik_controllers[0], shortName="Soft", minValue=0, defaultValue=0, maxValue=1, keyable=True)
        cmds.addAttr(self.ik_controllers[0], shortName="Soft_Start", minValue=0, defaultValue=0.8, maxValue=1, keyable=True)

        # IK handle manager driven by the ankle control (base) AND the ball
        # control (target) inside the solver: controllers[2]=ankle foot control
        # (holds the stretch/soft attrs + world-oriented base), controllers[3]=
        # ballIk (reverse-foot end).  secondary_mode = Y so hip/knee come out
        # X = aim to next joint, Y = forward, Z = bend axis.
        self.ik_matrices = custom_ik_solver.triangle_solver(
            name=f"{self.side}_legIk", guides=self.guides_matrices,
            controllers=[self.root_ik_ctl, self.pv_ctl, self.ik_controllers[0], self.ik_controllers[-1]],
            use_stretch=True, use_soft=True, ik_handle_manager=True,
            secondary_mode=(0, 1, 0) if self.side == "L" else (0, -1, 0))

        for ik_matrix, blend_matrix in zip(self.ik_matrices, self.blend_matrices):
            cmds.connectAttr(f"{ik_matrix}", f"{blend_matrix[0]}.inputMatrix")

        # Ball: single-chain solver ankle->ball, driven by ballIk (ik_controllers[-1]).
        # Base = the ankle-control position rigidly parented to the TIP pivot (toeIk)
        # via a constant offset, NOT the reverse-foot root.  This way:
        #   - ball roll (ballIk rotates, toeIk static)  -> base static -> ball stays
        #     planted while only the ankle/instep lifts  (same behaviour as before),
        #   - tip roll (toeIk rotates)                   -> base swings about the tip
        #     so the WHOLE foot lifts from its pivot.
        # Output -> the last blend (ankle->ball segment).
        ankle_ctl_rest = om.MMatrix(cmds.getAttr(f"{self.ik_controllers[0]}.worldMatrix[0]"))
        toe_rest = om.MMatrix(cmds.getAttr(f"{self.ik_controllers[-2]}.worldMatrix[0]"))
        ball_base_offset = ankle_ctl_rest * toe_rest.inverse()
        ball_base_mmx = cmds.createNode("multMatrix", name=f"{self.side}_legBallBase_MMX", ss=True)
        cmds.setAttr(f"{ball_base_mmx}.matrixIn[0]", list(ball_base_offset), type="matrix")
        cmds.connectAttr(f"{self.ik_controllers[-2]}.worldMatrix[0]", f"{ball_base_mmx}.matrixIn[1]")

        self.ball_ik = custom_ik_solver.single_chain_solver(
            blend_matrix=f"{ball_base_mmx}.matrixSum", controller=self.ik_controllers[-1],
            guides=[self.guides_trns[2], self.guides_trns[-2]])
        cmds.connectAttr(f"{self.ball_ik}", f"{self.blend_matrices[-1][0]}.inputMatrix")

        # Toe (tip): single-chain solver ball->tip, driven by toeIk (ik_controllers[-2]),
        # chained off the LIVE ball result so it follows the ball.  Drives the toe joint.
        self.toe_ik = custom_ik_solver.single_chain_solver(
            blend_matrix=self.ball_ik, controller=self.ik_controllers[-2],
            guides=[self.guides_trns[-2], self.guides_trns[-1]])

    def foot_attributes(self):

        """
        Add foot attributes to the leg module.
        """
        cmds.addAttr(self.ik_controllers[0], longName = "EXTRA_ATTRIBUTES", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.ik_controllers[0]}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        
        attr_list = [
            "Ankle_Twist",
            "Ball_Twist",
            "Toe_Twist",
            "Heel_Twist",
            "Bank",
            "Roll"
        ]

        for attr in attr_list:
            cmds.addAttr(self.ik_controllers[0], longName=attr, attributeType="float", defaultValue=0, keyable=True)
        
        cmds.addAttr(self.ik_controllers[0], longName="Roll_Break_Angle", attributeType="float", defaultValue=45, keyable=True)
        cmds.addAttr(self.ik_controllers[0], longName="Roll_Straight_Angle", attributeType="float", defaultValue=90, keyable=True)

        cmds.connectAttr(f"{self.ik_controllers[0]}.Ankle_Twist", f"{self.ik_sdk_nodes[0]}.rotateY")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Ball_Twist", f"{self.ik_sdk_nodes[-1]}.rotateY")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Toe_Twist", f"{self.ik_sdk_nodes[-2]}.rotateY")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Heel_Twist", f"{self.ik_sdk_nodes[-3]}.rotateY")
        bank_clamp = cmds.createNode("clamp", name=f"{self.side}_legBank_CLM", ss=True)
        cmds.setAttr(f"{bank_clamp}.minG", -360)
        cmds.setAttr(f"{bank_clamp}.maxR", 360)
        cmds.connectAttr(f"{self.ik_controllers[0]}.Bank", f"{bank_clamp}.inputR")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Bank", f"{bank_clamp}.inputG")
        if self.side == "L":
            cmds.connectAttr(f"{bank_clamp}.outputG", f"{self.ik_sdk_nodes[1]}.rotateZ")
            cmds.connectAttr(f"{bank_clamp}.outputR", f"{self.ik_sdk_nodes[2]}.rotateZ")
        else:
            cmds.connectAttr(f"{bank_clamp}.outputG", f"{self.ik_sdk_nodes[2]}.rotateZ")
            cmds.connectAttr(f"{bank_clamp}.outputR", f"{self.ik_sdk_nodes[1]}.rotateZ")

        roll_straight_angle = cmds.createNode("remapValue", name=f"{self.side}_legRollStraightAngle_RMV", ss=True)
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{roll_straight_angle}.inputValue")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll_Straight_Angle", f"{roll_straight_angle}.inputMax")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll_Break_Angle", f"{roll_straight_angle}.inputMin")
        cmds.setAttr(f"{roll_straight_angle}.outputMin", 0)
        cmds.setAttr(f"{roll_straight_angle}.outputMax", 1)

        multiply_node = cmds.createNode("multiply", name=f"{self.side}_legRollStraightAngle_MUL", ss=True)
        cmds.connectAttr(f"{roll_straight_angle}.outValue", f"{multiply_node}.input[0]")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{multiply_node}.input[1]")
        negate_roll_straight = cmds.createNode("negate", name=f"{self.side}_legRollStraight_NEG", ss=True)
        cmds.connectAttr(f"{multiply_node}.output", f"{negate_roll_straight}.input")
        cmds.connectAttr(f"{negate_roll_straight}.output", f"{self.ik_sdk_nodes[-2]}.rotateZ")

        roll_break_angle = cmds.createNode("remapValue", name=f"{self.side}_legRollBreakAngle_RMV", ss=True)
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{roll_break_angle}.inputValue")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll_Break_Angle", f"{roll_break_angle}.inputMax")
        cmds.setAttr(f"{roll_break_angle}.outputMin", 0)
        cmds.setAttr(f"{roll_break_angle}.outputMax", 1)

        reverse = cmds.createNode("reverse", name=f"{self.side}_legRollBreakAngle_REV", ss=True)
        cmds.connectAttr(f"{roll_straight_angle}.outValue", f"{reverse}.inputX")

        roll_angle_enable_mul = cmds.createNode("multiply", name=f"{self.side}_legRollAngleEnable_MUL", ss=True)
        cmds.connectAttr(f"{reverse}.outputX", f"{roll_angle_enable_mul}.input[0]")
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{roll_angle_enable_mul}.input[1]")

        roll_lift_angle_mul = cmds.createNode("multiply", name=f"{self.side}_legRollLiftAngle_MUL", ss=True)
        cmds.connectAttr(f"{roll_break_angle}.outValue", f"{roll_lift_angle_mul}.input[0]")
        cmds.connectAttr(f"{roll_angle_enable_mul}.output", f"{roll_lift_angle_mul}.input[1]")
        negate_roll_lift = cmds.createNode("negate", name=f"{self.side}_legRollLift_NEG", ss=True)
        cmds.connectAttr(f"{roll_lift_angle_mul}.output", f"{negate_roll_lift}.input")
        cmds.connectAttr(f"{negate_roll_lift}.output", f"{self.ik_sdk_nodes[-1]}.rotateZ")

        roll_heel_clamp = cmds.createNode("clamp", name=f"{self.side}_legRollHeel_CLM", ss=True)
        cmds.setAttr(f"{roll_heel_clamp}.minR", -360)
        cmds.setAttr(f"{roll_heel_clamp}.maxR", 0)
        cmds.connectAttr(f"{self.ik_controllers[0]}.Roll", f"{roll_heel_clamp}.inputR")
        cmds.connectAttr(f"{roll_heel_clamp}.outputR", f"{self.ik_sdk_nodes[-3]}.rotateX")

    def fk_stretch(self):

        """
        Setup FK stretch for the leg module.
        """


        for i, ctl in enumerate(self.fk_controllers):
            if i < len(self.fk_controllers) - 2:
                
                cmds.addAttr(ctl, longName="STRETCHY", niceName="STRETCHY ------", attributeType="enum", enumName="------")
                cmds.setAttr(f"{ctl}.STRETCHY", keyable=False, channelBox=True, lock=True)
                cmds.addAttr(ctl, shortName="Stretch", minValue=0, defaultValue=1, keyable=True)

                label = ctl.split("_")[1]
                mult_node = cmds.createNode("multiply", n=f"{self.side}_leg{label}_MUL")
                dist_node = cmds.createNode("distanceBetween", name=f"{self.side}_leg{label}DistanceBetween_DBT", ss=True)

                cmds.connectAttr(f"{ctl}.Stretch", f"{mult_node}.input[0]")
                cmds.connectAttr(self.guides_matrices[i], f"{dist_node}.inMatrix1")
                cmds.connectAttr(self.guides_matrices[i+1], f"{dist_node}.inMatrix2")
                
                if self.side == "R":
                    multiply_negate = cmds.createNode("multiply", name=f"{self.side}_leg{label}Negate_MUL", ss=True)
                    cmds.connectAttr(f"{dist_node}.distance", f"{multiply_negate}.input[0]")
                    cmds.setAttr(f"{multiply_negate}.input[1]", -1)
                    cmds.connectAttr(f"{multiply_negate}.output", f"{mult_node}.input[1]")
                else:
                    cmds.connectAttr(f"{dist_node}.distance", f"{mult_node}.input[1]")

                target_node = self.fk_nodes[i+1]
                connection = cmds.listConnections(f"{target_node}.offsetParentMatrix", source=True, destination=False, plugs=True)[0]
                
                fbf = cmds.createNode("fourByFourMatrix", name=f"{self.side}_leg{label}_FBF", ss=True)

                for row_index in range(4):
                    rfm = cmds.createNode("rowFromMatrix", name=f"{self.side}_leg{label}0{row_index}_RFM", ss=True)
                    cmds.connectAttr(connection, f"{rfm}.matrix")
                    cmds.setAttr(f"{rfm}.input", row_index)

                    for col_index in range(3):
                        cmds.connectAttr(
                            f"{rfm}.outputX" if col_index == 0 else
                            f"{rfm}.outputY" if col_index == 1 else
                            f"{rfm}.outputZ",
                            f"{fbf}.in{row_index}{col_index}"
                        )

                cmds.connectAttr(f"{mult_node}.output", f"{fbf}.in30", force=True)
                cmds.connectAttr(f"{fbf}.output", f"{target_node}.offsetParentMatrix", force=True)

    def knee_pin_setup(self):
        """
        Knee pin: snap the IK knee matrix (ik_matrices[1]) to the pole vector
        controller position, weighted by the pv_ctl 'Pin' attribute.  Pure matrix
        network (blendMatrix) feeding the knee blend's IK input.
        """
        cmds.addAttr(self.pv_ctl, longName="EXTRA_ATTRIBUTES", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{self.pv_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(self.pv_ctl, longName="Pin", niceName="Knee Pin", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)

        pin_blm = cmds.createNode("blendMatrix", name=f"{self.side}_legKneePin_BLM", ss=True)
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

        nonRollAlign = cmds.createNode("blendMatrix", name=f"{self.side}_legNonRollAlign_BLM", ss=True)
        nonRollAim = cmds.createNode("aimMatrix", name=f"{self.side}_legNonRollAim_AMX", ss=True)
        self.nonRollAim = nonRollAim
        blend_matrix_nodes = cmds.createNode("blendMatrix", name=f"{self.side}_legNonRollControllers_BLM", ss=True)

        cmds.connectAttr(f"{self.root_ik_nodes[0]}.worldMatrix[0]", f"{blend_matrix_nodes}.inputMatrix")
        cmds.connectAttr(f"{self.fk_nodes[0]}.worldMatrix[0]", f"{blend_matrix_nodes}.target[0].targetMatrix")
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{blend_matrix_nodes}.target[0].weight")

        cmds.connectAttr(f"{self.blend_matrices[0][0]}.outputMatrix", f"{nonRollAlign}.inputMatrix")
        cmds.connectAttr(f"{blend_matrix_nodes}.outputMatrix", f"{nonRollAlign}.target[0].targetMatrix")
        cmds.setAttr(f"{nonRollAlign}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{nonRollAlign}.target[0].translateWeight", 0)
        cmds.setAttr(f"{nonRollAlign}.target[0].shearWeight", 0)
        

        cmds.connectAttr(f"{nonRollAlign}.outputMatrix", f"{nonRollAim}.inputMatrix")
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{nonRollAim}.primaryTargetMatrix")
        cmds.setAttr(f"{nonRollAim}.primaryInputAxis", *self.primary_axis, type="double3")
       

        # ----- Roll setup via swing-twist (quaternion), composed entirely with
        # MATRIX nodes so the roll is no longer a DAG joint chain that slows the
        # rig (no joints, no ikSC handles, no flips).
        aim_letter = ['x', 'y', 'z'][[abs(v) for v in self.primary_axis].index(1)]
        aim_comp = aim_letter.upper()

        knee = om.MVector(cmds.xform(self.leg_chain[1], q=True, ws=True, t=True))
        ankle = om.MVector(cmds.xform(self.leg_chain[2], q=True, ws=True, t=True))
        shin_len = (ankle - knee).length()
        shin_len = shin_len if self.side == "L" else -shin_len

        # UPPER — twisted hip frame (rotation only) feeding the up-roll blend.
        # Quaternion fed straight into composeMatrix.inputQuat (useEulerRotation=0):
        # avoids the matrix->rotate->matrix round-trip (no quatToEuler).
        upper_twist = matrix_manager.extract_twist(
            f"{self.blend_matrices[0][0]}.outputMatrix", f"{nonRollAim}.outputMatrix",
            axis=aim_letter, name=f"{self.side}_legUpper", return_quat=True)
        upper_twist_cmp = cmds.createNode("composeMatrix", name=f"{self.side}_legUpperRollTwist_CMP", ss=True)
        cmds.setAttr(f"{upper_twist_cmp}.useEulerRotation", 0)
        cmds.connectAttr(f"{upper_twist}.outputQuat", f"{upper_twist_cmp}.inputQuat")
        upper_twist_mm = cmds.createNode("multMatrix", name=f"{self.side}_legUpperRollTwist_MMX", ss=True)
        cmds.connectAttr(f"{upper_twist_cmp}.outputMatrix", f"{upper_twist_mm}.matrixIn[0]")
        cmds.connectAttr(f"{nonRollAim}.outputMatrix", f"{upper_twist_mm}.matrixIn[1]")

        # LOWER — twisted shin frame offset to the ankle (aim target for the ribbon)
        lower_twist = matrix_manager.extract_twist(
            f"{self.blend_matrices[2][0]}.outputMatrix", f"{self.blend_matrices[1][0]}.outputMatrix",
            axis=aim_letter, name=f"{self.side}_legLower", return_quat=True)
        lower_twist_cmp = cmds.createNode("composeMatrix", name=f"{self.side}_legLowerRollTwist_CMP", ss=True)
        cmds.setAttr(f"{lower_twist_cmp}.useEulerRotation", 0)
        cmds.connectAttr(f"{lower_twist}.outputQuat", f"{lower_twist_cmp}.inputQuat")
        cmds.setAttr(f"{lower_twist_cmp}.inputTranslate{aim_comp}", shin_len)
        lower_twist_mm = cmds.createNode("multMatrix", name=f"{self.side}_legLowerRollTwist_MMX", ss=True)
        cmds.connectAttr(f"{lower_twist_cmp}.outputMatrix", f"{lower_twist_mm}.matrixIn[0]")
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{lower_twist_mm}.matrixIn[1]")
        # Far anchor must track the REAL ankle position (so it follows stretch),
        # taking only the twisted shin rotation — mirrors the upper's up_roll_blm.
        lower_roll_pm = cmds.createNode("blendMatrix", name=f"{self.side}_legLowerRoll_BLM", ss=True)
        cmds.connectAttr(f"{self.blend_matrices[2][0]}.outputMatrix", f"{lower_roll_pm}.inputMatrix")
        cmds.connectAttr(f"{lower_twist_mm}.matrixSum", f"{lower_roll_pm}.target[0].targetMatrix")
        cmds.setAttr(f"{lower_roll_pm}.target[0].translateWeight", 0)
        cmds.setAttr(f"{lower_roll_pm}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{lower_roll_pm}.target[0].shearWeight", 0)

        # Up Roll Blend Matrix — replaces the hip rotation with the twisted frame
        up_roll_blm = cmds.createNode("blendMatrix", name=f"{self.side}_legUpperRoll_BLM", ss=True)
        cmds.connectAttr(f"{self.blend_matrices[1][0]}.outputMatrix", f"{up_roll_blm}.inputMatrix")
        cmds.connectAttr(f"{upper_twist_mm}.matrixSum", f"{up_roll_blm}.target[0].targetMatrix")
        cmds.setAttr(f"{up_roll_blm}.target[0].translateWeight", 0)
        cmds.setAttr(f"{up_roll_blm}.target[0].rotateWeight", 1)
        cmds.setAttr(f"{up_roll_blm}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{up_roll_blm}.target[0].shearWeight", 0)

        self.upper_skinning_jnt_trn = self.de_boor_ribbon_callout([nonRollAim], [up_roll_blm], "Upper", skinning_joint_numbers)
        self.lower_skinning_jnt_trn = self.de_boor_ribbon_callout(self.blend_matrices[1], [lower_roll_pm], "Lower", skinning_joint_numbers)

        cmds.select(clear=True)
        ball_skinning_jnt = cmds.joint(name=f"{self.module_name}BallSkinning_JNT")
        cmds.connectAttr(f"{self.ball_ik}", f"{ball_skinning_jnt}.offsetParentMatrix")
        cmds.select(clear=True)
        ankle_skinning_jnt = cmds.joint(name=f"{self.module_name}AnkleSkinning_JNT")
        cmds.connectAttr(f"{self.blend_matrices[2][0]}.outputMatrix", f"{ankle_skinning_jnt}.offsetParentMatrix")
        cmds.select(clear=True)
        toe_skinning_jnt = cmds.joint(name=f"{self.module_name}ToeSkinning_JNT")
        cmds.connectAttr(f"{self.toe_ik}", f"{toe_skinning_jnt}.offsetParentMatrix")
        cmds.parent(ankle_skinning_jnt, self.skeleton_grp)
        cmds.parent(ball_skinning_jnt, self.skeleton_grp)
        cmds.parent(toe_skinning_jnt, self.skeleton_grp)

        # Blend the skinning joints toward a single smooth cubic (hip -> ankle)
        self.curvature_setup()
        # Volume preservation squash on the skinning joints
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

        cmds.setAttr(f"{aim_matrix}.primaryInputAxis", *self.primary_axis, type="double3") # Aim X+
        cmds.setAttr(f"{aim_matrix}.secondaryInputAxis", *self.secondary_axis, type="double3")

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
                cmds.addAttr(ctl, longName="Height", attributeType="float", defaultValue=0.5, minValue=0, maxValue=1, keyable=True)
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

        # Create ribbon

        output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.module_name}{part}", custom_parameter=params, aim_axis=self.aim_axis_signed, up_axis=self.up_axis_signed, skeleton_grp=self.skeleton_grp, num_joints=skinning_joint_numbers)

        for t in temp:
            cmds.delete(t)

        return output_joints

    def curvature_setup(self):

        """
        Build a single smooth cubic (degree 3) de Boor curve spanning the whole
        leg (hip -> knee -> ankle, using the main bendy controllers as the
        intermediate CVs) and blend the existing skinning joints toward it with a
        'Curvature' attribute on the settings controller.

        At Curvature = 0 the joints keep the current two-ribbon solution; at
        Curvature = 1 they follow the smooth cubic, rounding out the knee into a
        continuous arc from hip to ankle.  The same output joints are reused
        (only a blendMatrix is inserted before each joint's offsetParentMatrix).
        """

        # ----- whole-leg control vertices (5 CVs -> degree 3 cubic B-spline)
        cvs = [
            self.nonRollAim,                  # hip
            self.upper_main_bendy_ctl,        # mid thigh
            self.blend_matrices[1][0],        # knee
            self.lower_main_bendy_ctl,        # mid shin
            self.blend_matrices[2][0],        # ankle
        ]

        # ----- global parameter for every existing joint (upper then lower),
        # split proportionally to the rest length of each segment so the smooth
        # targets stay aligned with the current joints
        hip = om.MVector(cmds.xform(self.leg_chain[0], q=True, ws=True, t=True))
        knee = om.MVector(cmds.xform(self.leg_chain[1], q=True, ws=True, t=True))
        ankle = om.MVector(cmds.xform(self.leg_chain[2], q=True, ws=True, t=True))
        upper_len = (knee - hip).length()
        lower_len = (ankle - knee).length()
        total = upper_len + lower_len
        split = upper_len / total if total else 0.5

        seg = [i / 4.0 for i in range(5)]
        seg[-1] = 0.95
        global_params = [p * split for p in seg] + [split + p * (1 - split) for p in seg]

        # ----- build the smooth cubic ribbon as temporary driver joints
        driver_jnts, temp = ribbon.de_boor_ribbon(
            cvs, name=f"{self.module_name}Curvature", d=3, custom_parameter=global_params,
            aim_axis=self.aim_axis_signed, up_axis=self.up_axis_signed, skeleton_grp=self.skeleton_grp,
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

        # auto curvature from the knee bend (dot-based, no flip), added to the manual value
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
        Volume preservation: squash/stretch the skinning joints' secondary axes by
        1/sqrt(stretch) per segment, driven by a 'Volume' attribute (0 = off).
        Upper joints follow the thigh stretch, lower joints the shin stretch.
        """

        if not cmds.attributeQuery("Volume", node=self.settings_ctl, exists=True):
            cmds.addAttr(self.settings_ctl, longName="Volume", attributeType="float",
                         minValue=0, maxValue=1, defaultValue=0, keyable=True)

        hip = om.MVector(cmds.xform(self.leg_chain[0], q=True, ws=True, t=True))
        knee = om.MVector(cmds.xform(self.leg_chain[1], q=True, ws=True, t=True))
        ankle = om.MVector(cmds.xform(self.leg_chain[2], q=True, ws=True, t=True))

        upper_scale = matrix_manager.segment_volume(
            self.blend_matrices[0][0], self.blend_matrices[1][0], (knee - hip).length(),
            f"{self.settings_ctl}.Volume", f"{self.masterwalk_ctl}.globalScale",
            name=f"{self.module_name}Upper")
        lower_scale = matrix_manager.segment_volume(
            self.blend_matrices[1][0], self.blend_matrices[2][0], (ankle - knee).length(),
            f"{self.settings_ctl}.Volume", f"{self.masterwalk_ctl}.globalScale",
            name=f"{self.module_name}Lower")

        for grp in self.upper_bendy_grps:
            cmds.connectAttr(upper_scale, f"{grp}.scaleY")
            cmds.connectAttr(upper_scale, f"{grp}.scaleZ")
        for grp in self.lower_bendy_grps:
            cmds.connectAttr(lower_scale, f"{grp}.scaleY")
            cmds.connectAttr(lower_scale, f"{grp}.scaleZ")

        