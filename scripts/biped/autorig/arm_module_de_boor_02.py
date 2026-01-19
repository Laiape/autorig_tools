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

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)

class ArmModule(object):

    def __init__(self):

        """
        Initialize the ArmModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side, primary_axis=(1,0,0), secondary_axis=(0,1,0)):

        """ 
        Create the arm module structure and controllers. Call this method with the side ('L' or 'R') to create the respective arm module.
        Args:
            side (str): The side of the arm ('L' or 'R').

        """
        self.side = side
        self.module_name = f"{self.side}_arm"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.primary_axis = primary_axis if self.side == "L" else (-primary_axis[0], primary_axis[1], primary_axis[2])
        self.secondary_axis = secondary_axis

        self.load_guides()
        self.create_chains()
        self.controllers_creation()
        self.ik_setup()
        self.fk_stretch()
        # self.soft_ik()
        self.de_boor_ribbon()
        
        data_manager.DataExportBiped().append_data("arm_module",
                            {
                                f"{self.side}_shoulder_JNT": self.arm_chain[0],
                                f"{self.side}_wrist_JNT": self.arm_chain[-1],
                                f"{self.side}_armSettings": self.settings_ctl,
                                f"{self.side}_armIk": self.ik_wrist_ctl,
                                f"{self.side}_armPv": self.pv_ctl,
                                f"{self.side}_shoulderFk": self.fk_controllers[0],
                                f"{self.side}_armIkRoot": self.ik_root_ctl,
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


        self.guides = [] # List to store guide names
        for i, node in enumerate(self.arm_chain):
            
            guide = cmds.createNode("transform", name=node.replace("_JNT", "_GUIDE"), ss=True, p=self.module_trn)
            cmds.matchTransform(guide, node, pos=True, rot=True)
            cmds.setAttr(f"{guide}.rotate", 0, 0, 0, type="double3")
            if self.guides:
                cmds.parent(guide, self.guides[-1])
            self.guides.append(guide)

        self.guides_matrices = []
        for i, guide in enumerate(self.guides):
            if i == 0:
                guide_00 = cmds.createNode("aimMatrix", name=f"{self.side}_shoulder_AMT", ss=True)
                cmds.connectAttr(guide+".worldMatrix[0]", guide_00+".inputMatrix")
                cmds.connectAttr(f"{self.guides[i+1]}.worldMatrix[0]", f"{guide_00}.primaryTargetMatrix")
                cmds.connectAttr(f"{self.guides[i+2]}.worldMatrix[0]", f"{guide_00}.secondaryTargetMatrix")
                cmds.setAttr(f"{guide_00}.primaryInputAxis", *self.primary_axis, type="double3")
                cmds.setAttr(f"{guide_00}.secondaryInputAxis", 0,0,1, type="double3")
                cmds.setAttr(f"{guide_00}.secondaryTargetVector", 0,0,1, type="double3")
                cmds.setAttr(f"{guide_00}.secondaryMode", 1) # Aim
                self.guides_matrices.append(f"{guide_00}.outputMatrix")
            if i == 1:
                guide_01 = cmds.createNode("aimMatrix", name=f"{self.side}_elbow_AMT", ss=True)
                cmds.connectAttr(guide+".worldMatrix[0]", guide_01+".inputMatrix")
                cmds.connectAttr(f"{self.guides[i+1]}.worldMatrix[0]", f"{guide_01}.primaryTargetMatrix") # Next guide
                cmds.connectAttr(f"{self.guides[i-1]}.worldMatrix[0]", f"{guide_01}.secondaryTargetMatrix") # Previous guide
                cmds.setAttr(f"{guide_01}.secondaryInputAxis", 0,0,1, type="double3")
                cmds.setAttr(f"{guide_01}.secondaryTargetVector", 0,0,1, type="double3")
                cmds.setAttr(f"{guide_01}.secondaryMode", 1) # Aim
                self.guides_matrices.append(f"{guide_01}.outputMatrix")
            if i == 2:
                guide_02 = cmds.createNode("blendMatrix", name=f"{self.side}_wrist_BLM", ss=True)
                cmds.connectAttr(f"{guide_01}.outputMatrix", f"{guide_02}.inputMatrix")
                cmds.connectAttr(f"{guide}.worldMatrix[0]", f"{guide_02}.target[0].targetMatrix")
                cmds.setAttr(f"{guide_02}.target[0].weight", 1)
                cmds.setAttr(f"{guide_02}.target[0].scaleWeight", 0)
                cmds.setAttr(f"{guide_02}.target[0].rotateWeight", 0)
                cmds.setAttr(f"{guide_02}.target[0].shearWeight", 0)
                cmds.setAttr(f"{guide_02}.target[0].translateWeight", 1)
                self.guides_matrices.append(f"{guide_02}.outputMatrix")



    def create_chains(self):

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.side}_armSettings", offset=["GRP"])
        self.lock_attributes(self.settings_ctl, ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.matchTransform(self.settings_node[0], self.settings_loc, pos=True, rot=True)
        cmds.delete(self.settings_loc)
        cmds.addAttr(self.settings_ctl, longName="Ik_Fk", niceName= "Switch IK --> FK", attributeType="float", defaultValue=1, minValue=0, maxValue=1, keyable=True)
        cmds.parent(self.settings_node[0], self.controllers_grp)


    def controllers_creation(self):

        """
        Create controllers for the arm module.
        """
        self.fk_nodes = []
        self.fk_controllers = []
        self.blend_matrices = []

        fk_controllers_trn = cmds.createNode("transform", name=f"{self.side}_armFkControllers_GRP", ss=True, p=self.controllers_grp)

        for i, guide in enumerate(self.guides):

            fk_node, fk_ctl = curve_tool.create_controller(name=guide.replace("_GUIDE", "Fk"), offset=["GRP"]) # create FK controllers
            self.lock_attributes(fk_ctl, ["translateX", "translateY", "translateZ", "scaleX", "scaleY", "scaleZ", "visibility"])

            if self.fk_controllers:
                cmds.parent(fk_node[0], self.fk_controllers[-1])

            self.fk_nodes.append(fk_node[0])
            self.fk_controllers.append(fk_ctl)

            blend_matrix = cmds.createNode("blendMatrix", name=guide.replace("GUIDE", "BLM"), ss=True)

            if i == 0:
                cmds.connectAttr(f"{self.guides_matrices[i]}", f"{fk_node[0]}.offsetParentMatrix") # First FK controller follows the guide
                
            else:
                inverse_matrix = cmds.createNode("inverseMatrix", name=guide.replace("GUIDE", "INV"), ss=True)
                cmds.connectAttr(f"{self.guides_matrices[i-1]}", f"{inverse_matrix}.inputMatrix")
                mult_matrix = cmds.createNode("multMatrix", name=guide.replace("GUIDE", "MMT"), ss=True)
                cmds.connectAttr(f"{self.guides_matrices[i]}", f"{mult_matrix}.matrixIn[0]")
                cmds.connectAttr(f"{inverse_matrix}.outputMatrix", f"{mult_matrix}.matrixIn[1]")
                cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{fk_node[0]}.offsetParentMatrix") # Other FK controllers follow the relative guide position

            cmds.connectAttr(f"{fk_ctl}.worldMatrix[0]", f"{blend_matrix}.target[0].targetMatrix")
            cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{blend_matrix}.target[0].weight")

            cmds.xform(fk_node, m=om.MMatrix.kIdentity) # Reset fk node transform

            self.blend_matrices.append(blend_matrix)

        cmds.parent(self.fk_nodes[0], fk_controllers_trn)


        self.ik_controllers = []
        self.ik_controllers = []

        ik_controllers_trn = cmds.createNode("transform", name=f"{self.side}_armIkControllers_GRP", ss=True, p=self.controllers_grp)

        self.ik_wrist_nodes, self.ik_wrist_ctl = curve_tool.create_controller(name=f"{self.side}_armIkWrist", offset=["GRP", "SPC"])
        self.lock_attributes(self.ik_wrist_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.ik_wrist_nodes[0], ik_controllers_trn)
        cmds.connectAttr(self.guides_matrices[2], f"{self.ik_wrist_nodes[0]}.offsetParentMatrix")

        self.pv_nodes, self.pv_ctl = curve_tool.create_controller(name=f"{self.side}_armPv", offset=["GRP", "SPC"])
        self.lock_attributes(self.pv_ctl, ["rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.pv_nodes[0], ik_controllers_trn)
        

        cmds.addAttr(self.pv_ctl, shortName="extraAttr", niceName="EXTRA_ATTRIBUTES", enumName="———",attributeType="enum", keyable=True)
        cmds.setAttr(self.pv_ctl+".extraAttr", channelBox=True, lock=True)
        cmds.addAttr(self.pv_ctl, shortName="pvOrientation", niceName="Pv Orientation",defaultValue=1, minValue=0, maxValue=1, keyable=True)
        cmds.addAttr(self.pv_ctl, shortName="pin", niceName="Pin",minValue=0,maxValue=1,defaultValue=0, keyable=True)

        pv_pos = self.create_matrix_pole_vector(
            f"{self.guides_matrices[0]}",
            f"{self.guides_matrices[1]}",
            f"{self.guides_matrices[2]}",
            name=f"{self.side}_{self.module_name}PV"
        )

        cmds.connectAttr(f"{self.pv_ctl}.pvOrientation", f"{pv_pos}.target[0].weight")
        cmds.connectAttr(f"{pv_pos}.outputMatrix", f"{self.pv_nodes[0]}.offsetParentMatrix", force=True)

        crv_point_pv = cmds.curve(d=1, p=[(0, 0, 1), (0, 1, 0)], n=f"{self.side}_armPv_CRV") # Create a line that points always to the PV
        decompose_knee = cmds.createNode("decomposeMatrix", name=f"{self.side}_armPv_DCM", ss=True)
        decompose_ctl = cmds.createNode("decomposeMatrix", name=f"{self.side}_armPvCtl_DCM", ss=True)
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{decompose_ctl}.inputMatrix")
        cmds.connectAttr(self.guides_matrices[1], f"{decompose_knee}.inputMatrix")
        cmds.connectAttr(f"{decompose_knee}.outputTranslate", f"{crv_point_pv}.controlPoints[0]")
        cmds.connectAttr(f"{decompose_ctl}.outputTranslate", f"{crv_point_pv}.controlPoints[1]")
        cmds.setAttr(f"{crv_point_pv}.inheritsTransform", 0)
        cmds.setAttr(f"{crv_point_pv}.overrideEnabled", 1)
        cmds.setAttr(f"{crv_point_pv}.overrideDisplayType", 1)

        cmds.parent(crv_point_pv, self.pv_ctl)

        self.ik_root_nodes, self.ik_root_ctl = curve_tool.create_controller(name=f"{self.side}_armIkRoot", offset=["GRP"])
        self.lock_attributes(self.ik_root_ctl, ["rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"])
        cmds.parent(self.ik_root_nodes[0], ik_controllers_trn)
        cmds.connectAttr(self.guides_matrices[0], f"{self.ik_root_nodes[0]}.offsetParentMatrix")

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
            md = cmds.createNode('multiplyDivide', name=f"{self.side}_{self.module_name}Pv{name.capitalize()}_MDV", ss=True)
            cmds.setAttr(f'{md}.operation', 1)
            cmds.connectAttr(input_vec, f'{md}.input1')
            for axis in 'XYZ':
                cmds.connectAttr(scalar_attr, f'{md}.input2{axis}')
            return md, f'{md}.output'

        def add_vectors(vecA, vecB, name):
            node = cmds.createNode('plusMinusAverage', name=f"{self.side}_{self.module_name}Pv{name.capitalize()}_PMA", ss=True)
            for i, vector in enumerate([vecA, vecB]):
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
        Setup the IK for the arm module.
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

        self.ik_matrices = custom_ik_solver.triangle_solver(name=f"{self.side}_armIk", guides=self.guides_matrices, controllers=[self.ik_root_ctl, self.pv_ctl, self.ik_wrist_ctl], trn_guides=self.guides, use_stretch=True, use_soft=True)
        
        for ik_matrix, blend_matrix in zip(self.ik_matrices, self.blend_matrices):
            cmds.connectAttr(f"{ik_matrix}", f"{blend_matrix}.inputMatrix")
        
    def fk_stretch(self):

        """
        Setup FK stretch for the arm module.
        """

        for i, ctl in enumerate(self.fk_controllers):
            if i < 2:  # Only for upper arm and lower arm FK controllers
                cmds.setAttr(f"{ctl}.translateX", lock=False)
                cmds.addAttr(ctl, longName="STRETCHY", attributeType="enum", enumName="____")
                cmds.setAttr(f"{ctl}.STRETCHY", keyable=False, channelBox=True)
                cmds.addAttr(ctl, shortName="Stretch", minValue=0, defaultValue=1, keyable=True)

        subtract_upper = cmds.createNode("subtract", name=f"{self.side}_armFkUpperLength_SUB", ss=True)
        cmds.connectAttr(f"{self.fk_controllers[0]}.Stretch", f"{subtract_upper}.input1")
        cmds.setAttr(f"{subtract_upper}.input2", 1)

        subtract_lower = cmds.createNode("subtract", name=f"{self.side}_armFkLowerLength_SUB", ss=True)
        cmds.connectAttr(f"{self.fk_controllers[1]}.Stretch", f"{subtract_lower}.input1")
        cmds.setAttr(f"{subtract_lower}.input2", 1)

        cmds.connectAttr(f"{subtract_upper}.output", f"{self.fk_nodes[1]}.translateX")
        cmds.connectAttr(f"{subtract_lower}.output", f"{self.fk_nodes[2]}.translateX")

    def de_boor_ribbon(self):

        """
        Create a de Boor ribbon setup.
        """

        primary_aim_vector = (1, 0, 0)
        secondary_aim_vector = (0, 0, 1)

        

        guides_aim = cmds.createNode("aimMatrix", name=f"{self.side}_armGuides_AIM", ss=True)
        cmds.connectAttr(f"{self.guides[0]}.worldMatrix[0]", f"{guides_aim}.inputMatrix")
        cmds.connectAttr(f"{self.guides[1]}.worldMatrix[0]", f"{guides_aim}.primary.primaryTargetMatrix")
        cmds.connectAttr(f"{self.guides[2]}.worldMatrix[0]", f"{guides_aim}.secondary.secondaryTargetMatrix")
        cmds.setAttr(f"{guides_aim}.primaryInputAxis", *primary_aim_vector, type="double3")
        cmds.setAttr(f"{guides_aim}.secondaryInputAxis", *secondary_aim_vector, type="double3")
        cmds.setAttr(f"{guides_aim}.secondaryMode", 1) # Aim


        nonRollAlign = cmds.createNode("blendMatrix", name=f"{self.side}_armNonRollAlign_BLM", ss=True)
        nonRollAim = cmds.createNode("aimMatrix", name=f"{self.side}_armNonRollAim_AMX", ss=True)
        nonRollMasterWalk_mmx = cmds.createNode("multMatrix", name=f"{self.side}_armNonRollMasterWalk_MMX", ss=True)

        cmds.connectAttr(f"{guides_aim}.outputMatrix", f"{nonRollMasterWalk_mmx}.matrixIn[0]")
        cmds.connectAttr(f"{self.masterwalk_ctl}.worldMatrix[0]", f"{nonRollMasterWalk_mmx}.matrixIn[1]")

        cmds.connectAttr(f"{self.blend_matrices[0]}.outputMatrix", f"{nonRollAlign}.inputMatrix")
        cmds.connectAttr(f"{nonRollMasterWalk_mmx}.matrixSum", f"{nonRollAlign}.target[0].targetMatrix")
        cmds.setAttr(f"{nonRollAlign}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{nonRollAlign}.target[0].translateWeight", 0)
        cmds.setAttr(f"{nonRollAlign}.target[0].shearWeight", 0)
        

        cmds.connectAttr(f"{nonRollAlign}.outputMatrix", f"{nonRollAim}.inputMatrix")
        cmds.connectAttr(f"{self.blend_matrices[1]}.outputMatrix", f"{nonRollAim}.primaryTargetMatrix")
        cmds.setAttr(f"{nonRollAim}.primaryInputAxis", *primary_aim_vector, type="double3")


        # Placeholder for de Boor ribbon setup
        self.upper_skinning_jnt_trn = self.de_boor_ribbon_callout([nonRollAim], self.blend_matrices[1], "Upper")
        self.lower_skinning_jnt_trn = self.de_boor_ribbon_callout(self.blend_matrices[1], self.blend_matrices[2], "Lower")

        cmds.select(clear=True)
        wrist_skinning = cmds.joint(name=f"{self.side}_wristSkinning_JNT")
        cmds.connectAttr(f"{self.arm_chain[-1]}.worldMatrix[0]", f"{wrist_skinning}.offsetParentMatrix")
        cmds.parent(wrist_skinning, self.skeleton_grp)

    def de_boor_ribbon_callout(self, first_sel, second_sel, part):

        if f"{first_sel}.outputMatrix":
            first_sel_output = f"{first_sel}.outputMatrix"
        elif f"{first_sel}.worldMatrix":
            first_sel_output = f"{first_sel}.worldMatrix"

        if f"{second_sel}.outputMatrix":
            second_sel_output = f"{second_sel}.outputMatrix"
        elif f"{second_sel}.worldMatrix":
            second_sel_output = f"{second_sel}.worldMatrix"
        
        print( first_sel_output, second_sel_output)

        main_bendy_nodes, main_bendy_ctl = curve_tool.create_controller(name=f"{self.side}_{part}MainBendy", offset=["GRP"])
        up_bendy_nodes, up_bendy_ctl = curve_tool.create_controller(name=f"{self.side}_{part}UpBendy", offset=["GRP"])
        low_bendy_nodes, low_bendy_ctl = curve_tool.create_controller(name=f"{self.side}_{part}LowBendy", offset=["GRP"])

        for ctl in [main_bendy_ctl, up_bendy_ctl, low_bendy_ctl]:
            self.lock_attributes(ctl, ["rotateX", "rotateY", "rotateZ", "visibility"])

        for node in [main_bendy_nodes[0], up_bendy_nodes[0], low_bendy_nodes[0]]:

            cmds.parent(node, self.controllers_grp)
            cmds.setAttr(f"{node}.inheritsTransform", 0)

        blend_matrix_main = cmds.createNode("blendMatrix", name=f"{self.side}_{part}MainBendy_BM", ss=True)
        cmds.connectAttr(first_sel_output, f"{blend_matrix_main}.inputMatrix")
        cmds.connectAttr(second_sel_output, f"{blend_matrix_main}.target[0].targetMatrix")
        cmds.setAttr(f"{blend_matrix_main}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend_matrix_main}.target[0].rotateWeight", 0)
        cmds.setAttr(f"{blend_matrix_main}.target[0].shearWeight", 0)
        cmds.setAttr(f"{blend_matrix_main}.target[0].translateWeight", 0.5)
        cmds.connectAttr(f"{blend_matrix_main}.outputMatrix", f"{main_bendy_nodes[0]}.offsetParentMatrix")

        pM_s = []
        
        for i , node in enumerate([up_bendy_nodes[0], low_bendy_nodes[0]]):

            blend_matrix = cmds.createNode("blendMatrix", name=node.replace("_CTL", "_BM"), ss=True)
            if i == 0:
                cmds.connectAttr(first_sel_output, f"{blend_matrix}.inputMatrix")
            else:
                cmds.connectAttr(second_sel_output, f"{blend_matrix}.inputMatrix")
            cmds.connectAttr(f"{main_bendy_ctl}.worldMatrix[0]", f"{blend_matrix}.target[0].targetMatrix")
            cmds.setAttr(f"{blend_matrix}.target[0].scaleWeight", 0)
            cmds.setAttr(f"{blend_matrix}.target[0].rotateWeight", 0)
            cmds.setAttr(f"{blend_matrix}.target[0].shearWeight", 0)
            cmds.setAttr(f"{blend_matrix}.target[0].translateWeight", 0.5)
            position = cmds.getAttr(f"{blend_matrix}.outputMatrix")
            
            parent_m = cmds.createNode("parentMatrix", name=f"{self.side}_{part}UpBendy_PM", ss=True)
            cmds.setAttr(f"{parent_m}.inputMatrix", position, type="matrix")
            if i == 0:
                cmds.connectAttr(first_sel_output, f"{parent_m}.target[0].targetMatrix")
            else:
                cmds.connectAttr(second_sel_output, f"{parent_m}.target[0].targetMatrix")
            cmds.connectAttr(f"{main_bendy_ctl}.worldMatrix[0]", f"{parent_m}.target[1].targetMatrix")
            cmds.connectAttr(f"{parent_m}.outputMatrix", f"{node}.offsetParentMatrix")
            cmds.delete(blend_matrix)
            pM_s.append(parent_m)

        sel = (first_sel[0], up_bendy_ctl, main_bendy_ctl, low_bendy_ctl, second_sel[0])

        params = [i / (len(sel) - 1) for i in range(len(sel))]
        params[-1] = 0.95

        if self.side == "L":
            output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.module_name}{part}", custom_parameter=params, aim_axis='x', up_axis='y', skeleton_grp=self.skeleton_grp) # Call the ribbon script to create de Boors system
        elif self.side == "R":
            output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.module_name}{part}", custom_parameter=params, aim_axis='-x', up_axis='y', skeleton_grp=self.skeleton_grp)

        for t in temp:
            cmds.delete(t)

        for i, ctl in enumerate([main_bendy_ctl, up_bendy_ctl, low_bendy_ctl]):

            self.lock_attributes(ctl, ["visibility"])

            cmds.addAttr(ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
            cmds.setAttr(f"{ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True)
            cmds.addAttr(ctl, longName="Bendy_Height", attributeType="float", minValue=0, defaultValue=0.5, maxValue=1, keyable=True)

            if i == 0:

                cmds.addAttr(ctl, longName="Extra_Bendys", attributeType="bool", keyable=False)
                cmds.setAttr(f"{ctl}.Extra_Bendys", channelBox=True)

        cmds.connectAttr(f"{main_bendy_ctl}.Bendy_Height", f"{blend_matrix_main}.target[0].translateWeight") # Connect Bendy_Height to blend_matrix_main

        float_math_up = cmds.createNode("floatMath", name=f"{self.side}_{part}UpBendy_FLM", ss=True) # Create a FLM node to control the up bendy
        cmds.setAttr(f"{float_math_up}.operation", 1)
        cmds.connectAttr(f"{up_bendy_ctl}.Bendy_Height", f"{float_math_up}.floatB")
        cmds.connectAttr(f"{float_math_up}.outFloat", f"{pM_s[0]}.target[0].weight")
        cmds.connectAttr(f"{up_bendy_ctl}.Bendy_Height", f"{pM_s[0]}.target[1].weight")

        float_math_low = cmds.createNode("floatMath", name=f"{self.side}_{part}LowBendy_FLM", ss=True) # Create a FLM node to control the low bendy
        cmds.setAttr(f"{float_math_low}.operation", 1)
        cmds.connectAttr(f"{low_bendy_ctl}.Bendy_Height", f"{float_math_low}.floatB")
        cmds.connectAttr(f"{float_math_low}.outFloat", f"{pM_s[1]}.target[1].weight")
        cmds.connectAttr(f"{low_bendy_ctl}.Bendy_Height", f"{pM_s[1]}.target[0].weight")

        cmds.connectAttr(f"{main_bendy_ctl}.Extra_Bendys", f"{up_bendy_nodes[0]}.visibility")
        cmds.connectAttr(f"{main_bendy_ctl}.Extra_Bendys", f"{low_bendy_nodes[0]}.visibility")
        

        

    def curvature(self):

        """
        Calculate the curvature of the arm module.
        This method is a placeholder for future implementation.
        Calculate the curvature of the arm module.
        This method is a placeholder for future implementation.

        """
        
        # Placeholder for curvature calculation
        pass

