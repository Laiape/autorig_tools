import maya.cmds as cmds
import maya.api.OpenMaya as om
from utils import data_manager

def fk_constraint(joint, before_jnt, pair_blend, settings_ctl):

    """
    Create a parent constraint from source to target. Rememeber to don't put values in the Fk controllers.
    args:
        joint (str): the joint to be constrained.
        before_jnt (str): the joint to add the offset.
        before_ctl (str): the before control to add the offset.
    """
    joint_ctl = joint.replace("_JNT", "_CTL")
    ik_joint = joint.replace("Fk_JNT", "Ik_JNT")
    blend_joint = joint.replace("Fk_JNT", "_JNT")
    if before_jnt != None:
        before_blend_jnt = before_jnt.replace("Fk_JNT", "_JNT")
    else:

        module_trn = cmds.listRelatives(joint, parent=True)[0]


    if before_jnt == None:

        cmds.connectAttr(f"{joint_ctl}.worldMatrix[0]", f"{joint}.offsetParentMatrix")

    else:

        mult_matrix_offset = cmds.createNode("multMatrix", name=joint.replace("JNT", "MMT"), ss=True)
        cmds.connectAttr(f"{joint_ctl}.worldMatrix[0]", f"{mult_matrix_offset}.matrixIn[0]", force=True)
        cmds.connectAttr(f"{before_jnt}.worldInverseMatrix[0]", f"{mult_matrix_offset}.matrixIn[1]", force=True)
        cmds.connectAttr(f"{mult_matrix_offset}.matrixSum", f"{joint}.offsetParentMatrix", force=True)

    blend_matrices = []

    if pair_blend == True:

        blend_matrix = cmds.createNode("blendMatrix", name=joint.replace("JNT", "BM"), ss=True)
        cmds.connectAttr(f"{ik_joint}.worldMatrix[0]", f"{blend_matrix}.inputMatrix", force=True)
        cmds.connectAttr(f"{joint}.worldMatrix[0]", f"{blend_matrix}.target[0].targetMatrix", force=True)
        cmds.xform(blend_joint, m=om.MMatrix.kIdentity)
        blend_matrices.append(blend_matrix)

        if before_jnt != None:
            mult_matrix_off = cmds.createNode("multMatrix", name=joint.replace("_JNT", "Off_MMT"), ss=True)
            cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{mult_matrix_off}.matrixIn[0]", force=True)
            cmds.connectAttr(f"{before_blend_jnt}.worldInverseMatrix[0]", f"{mult_matrix_off}.matrixIn[1]", force=True)
            cmds.connectAttr(f"{mult_matrix_off}.matrixSum", f"{blend_joint}.offsetParentMatrix", force=True)
        else:
            cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{blend_joint}.offsetParentMatrix", force=True)

        if settings_ctl != None:

            cmds.connectAttr(f"{settings_ctl}.Ik_Fk", f"{blend_matrix}.target[0].weight", force=True)

    return blend_matrices if pair_blend else None


def ik_constraint(source, target):

    """
    Create an ik constraint from source to target.
    args:
        source (str): The name of the source object to constrain.
        target (str): The name of the target object to be constrained.
    """
    if not cmds.objExists(source) or not cmds.objExists(target):
        om.MGlobal.displayError("Source or target does not exist.")
        return

def space_switches(target, sources = [None], default_value = 1):

    """
    Create space switches for a given target and a list of source objects.
    Args:
        target (str): The name of the target object.
        sources (list): A list of source objects to switch between.
        default_value (int): The default value for the space switch.
    """
    
    target_grp = target.replace("CTL", "GRP")

    if not cmds.objExists(target_grp): 

        om.MGlobal.displayError(f"Target group {target_grp} does not exist.")
        return

    parent_matrix = cmds.createNode("parentMatrix", name=target.replace("CTL", "PMT"), ss=True)
    cmds.connectAttr(f"{target_grp}.worldMatrix[0]", f"{parent_matrix}.inputMatrix")
    mult_matrix = cmds.createNode("multMatrix", name=target.replace("CTL", "MMT"), ss=True)
    blend_matrix = cmds.createNode("blendMatrix", name=target.replace("CTL", "BMT"), ss=True)
    
    masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl") 

    masterwalk_parent_matrix = cmds.createNode("parentMatrix", name=target.replace("_CTL", "MasterWalk_PM"), ss=True)
    cmds.connectAttr(f"{masterwalk_ctl}.worldMatrix[0]", f"{masterwalk_parent_matrix}.inputMatrix")
    try:
        grp_connections = cmds.listConnections(f"{target_grp}.offsetParentMatrix", source=True, destination=False, plugs=True)
        print(f"Connections to {target_grp}.offsetParentMatrix: {grp_connections}")
    except TypeError:
        grp_connections = None

    if grp_connections:
        cmds.connectAttr(grp_connections[0], f"{masterwalk_parent_matrix}.target[0].targetMatrix")
        offset = get_offset_matrix(target_grp, grp_connections[0])
        cmds.setAttr(f"{masterwalk_parent_matrix}.target[0].offsetMatrix", offset, type="matrix")

    cmds.connectAttr(f"{masterwalk_parent_matrix}.outputMatrix", f"{blend_matrix}.inputMatrix")
    cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{blend_matrix}.target[0].targetMatrix")

    cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{mult_matrix}.matrixIn[0]")
    cmds.connectAttr(f"{target_grp}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[1]")
    
    
    condition_nodes = []
    source_matrices = []

    for i, matrix in enumerate(sources):

        offset = get_offset_matrix(target_grp, matrix)

        cmds.connectAttr(f"{matrix}.worldMatrix[0]", f"{parent_matrix}.target[{i}].targetMatrix")
        cmds.setAttr(f"{parent_matrix}.target[{i}].offsetMatrix", offset, type="matrix")

        condition = cmds.createNode("condition", name=sources[i].replace("CTL", "COND"), ss=True)
        cmds.setAttr(f"{condition}.firstTerm", i)
        cmds.setAttr(f"{condition}.operation", 0)
        cmds.setAttr(f"{condition}.colorIfFalseR", 0)
        cmds.setAttr(f"{condition}.colorIfFalseG", 0)
        cmds.setAttr(f"{condition}.colorIfTrueG", 1)

        name = matrix.split("_")[1].capitalize()

        condition_nodes.append(condition)
        source_matrices.append(name)

    cmds.addAttr(target, longName="SpaceSwitchSep", niceName = "SPACE SWITCHES ------", attributeType="enum", enumName="------", keyable=True)
    cmds.setAttr(f"{target}.SpaceSwitchSep", channelBox=True, lock=True)   
    if len(sources) == 1:     
        cmds.addAttr(target, longName="SpaceSwitch", attributeType="enum", enumName=":".join(source_matrices), keyable=False)
        cmds.setAttr(f"{target}.SpaceSwitchSep", channelBox=True, lock=True)
        
    else:
        cmds.addAttr(target, longName="SpaceSwitch", attributeType="enum", enumName=":".join(source_matrices), keyable=True)
        if len(sources) == 2:
            cmds.setAttr(f"{target}.SpaceSwitch", keyable=False, channelBox=False)

    cmds.addAttr(target, longName="Translate_Value", attributeType="float", min=0, max=1, defaultValue=default_value, keyable=True)
    cmds.addAttr(target, longName="Rotate_Value", attributeType="float", min=0, max=1, defaultValue=default_value, keyable=True)

    for i, condition in enumerate(condition_nodes):
        cmds.connectAttr(f"{target}.SpaceSwitch", f"{condition}.secondTerm")
        cmds.connectAttr(f"{target}.Translate_Value", f"{condition}.colorIfTrueR")
        cmds.connectAttr(f"{target}.Rotate_Value", f"{condition}.colorIfTrueG")
        
        cmds.connectAttr(f"{condition}.outColorR", f"{blend_matrix}.target[{i}].translateWeight")
        cmds.connectAttr(f"{condition}.outColorG", f"{blend_matrix}.target[{i}].rotateWeight")

    
    cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{target}.offsetParentMatrix")


def get_offset_matrix(child, parent):
    """
    Calcula la matriz de offset. Acepta tanto objetos DAG como atributos de matriz.
    """
    def get_matrix_input(node_or_attr):
        if "." in node_or_attr:
            try:
                mat_vals = cmds.getAttr(node_or_attr)
                return om.MMatrix(mat_vals)
            except Exception as e:
                raise ValueError(f"No se pudo leer el atributo {node_or_attr}: {e}")

        try:
            sel = om.MSelectionList()
            sel.add(node_or_attr)
            dag = sel.getDagPath(0)
            return dag.inclusiveMatrix()
        except:
            if cmds.attributeQuery("worldMatrix", node=node_or_attr, exists=True):
                mat_vals = cmds.getAttr(f"{node_or_attr}.worldMatrix[0]")
                return om.MMatrix(mat_vals)
            else:
                raise ValueError(f"No se pudo obtener una matriz de: {node_or_attr}")

    child_matrix = get_matrix_input(child)
    parent_matrix = get_matrix_input(parent)

    offset_matrix = child_matrix * parent_matrix.inverse()
    
    return list(offset_matrix)


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
        cmds.setAttr(f'{aim_matrix}.primaryInputAxis', 0, -1, 0, type='double3')
        if self.side == "L":
            cmds.setAttr(f'{aim_matrix}.secondaryInputAxis', -1, 0, 0, type='double3')
        else:
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