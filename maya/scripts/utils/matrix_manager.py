import maya.cmds as cmds
import maya.api.OpenMaya as om
from maya.scripts.utils import data_manager

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


def fk_blend(blend_joint, ik_joint, fk_ctl, before_blend_jnt, settings_ctl):

    """
    Blend a bind joint between its IK joint and its FK controller, without an
    intermediate FK joint: the FK side reads the controller worldMatrix directly.
    args:
        blend_joint (str): the bind joint (_JNT) driven by the blend output.
        ik_joint (str|None): the IK joint feeding the IK side of the blend, or
            None when an analytic matrix solver connects `inputMatrix` afterwards.
        fk_ctl (str): the FK controller feeding the FK side of the blend.
        before_blend_jnt (str|None): previous bind joint for the relative offset
            (None for the root joint).
        settings_ctl (str|None): settings control holding the Ik_Fk attribute.
    returns:
        list: [blend_matrix] node, mirroring fk_constraint's return shape.
    """
    blend_matrix = cmds.createNode("blendMatrix", name=blend_joint.replace("JNT", "BM"), ss=True)
    if ik_joint is not None:
        cmds.connectAttr(f"{ik_joint}.worldMatrix[0]", f"{blend_matrix}.inputMatrix", force=True)
    # else: the IK side (inputMatrix) is connected later by the analytic solver
    cmds.connectAttr(f"{fk_ctl}.worldMatrix[0]", f"{blend_matrix}.target[0].targetMatrix", force=True)
    cmds.xform(blend_joint, m=om.MMatrix.kIdentity)

    if before_blend_jnt is not None:
        mult_matrix_off = cmds.createNode("multMatrix", name=blend_joint.replace("_JNT", "Off_MMT"), ss=True)
        cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{mult_matrix_off}.matrixIn[0]", force=True)
        cmds.connectAttr(f"{before_blend_jnt}.worldInverseMatrix[0]", f"{mult_matrix_off}.matrixIn[1]", force=True)
        cmds.connectAttr(f"{mult_matrix_off}.matrixSum", f"{blend_joint}.offsetParentMatrix", force=True)
    else:
        cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{blend_joint}.offsetParentMatrix", force=True)

    if settings_ctl is not None:
        cmds.connectAttr(f"{settings_ctl}.Ik_Fk", f"{blend_matrix}.target[0].weight", force=True)

    return [blend_matrix]


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

def space_switches(target, sources=[], default_rotate=1, default_translate=1, sources_names=[], pv=False):
    """
    Versión optimizada de space_switches siguiendo la lógica de fk_switch.
    """
    target_grp = target.replace("CTL", "GRP")
    if not cmds.objExists(target):
        target_grp = target
        
    if not cmds.objExists(target_grp):
        om.MGlobal.displayError(f"El grupo objetivo '{target_grp}' no existe.")
        return

    cmds.setAttr(f"{target_grp}.inheritsTransform", 0)

    conn = cmds.listConnections(f"{target_grp}.offsetParentMatrix", plugs=True, source=True, destination=False)
    input_connection = conn[0] if conn else None

    pm_master = cmds.createNode("parentMatrix", name=target.replace("_CTL", "_MasterSpace_PMT"), ss=True)
    pm_sources = cmds.createNode("parentMatrix", name=target.replace("_CTL", "_SourcesSpace_PMT"), ss=True)
    bmx_final = cmds.createNode("blendMatrix", name=target.replace("_CTL", "_Space_BMX"), ss=True)

    if not cmds.attributeQuery("SpaceSwitchSep", node=target, exists=True):
        cmds.addAttr(target, longName="SpaceSwitchSep", niceName="SPACE SWITCHES ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{target}.SpaceSwitchSep", channelBox=True, lock=True)

    if not sources_names:
        sources_names = [src.split("_")[1] for src in sources]

    if len(sources) > 0:
        cmds.addAttr(target, longName="SpaceFollow", attributeType="enum", enumName=":".join(sources_names), keyable=True)
    
    cmds.addAttr(target, longName="TranslateValue", attributeType="float", min=0, max=1, defaultValue=default_translate, keyable=True)
    cmds.addAttr(target, longName="RotateValue", attributeType="float", min=0, max=1, defaultValue=default_rotate, keyable=True)


    data_exporter = data_manager.DataExportBiped()
    masterwalk_ctl = data_exporter.get_data("basic_structure", "masterwalk_ctl")

    if input_connection:
        cmds.connectAttr(input_connection, f"{pm_master}.inputMatrix")
        cmds.connectAttr(input_connection, f"{pm_sources}.inputMatrix")
        
    offset_master = get_offset_matrix(target_grp, masterwalk_ctl)
    cmds.connectAttr(f"{masterwalk_ctl}.worldMatrix[0]", f"{pm_master}.target[0].targetMatrix")
    cmds.setAttr(f"{pm_master}.target[0].offsetMatrix", offset_master, type="matrix")

    for i, driver in enumerate(sources):
     
        cond = cmds.createNode("condition", name=target.replace('_CTL', f"_Space{i:02d}_CON"), ss=True)
        cmds.setAttr(f"{cond}.firstTerm", i)
        cmds.connectAttr(f"{target}.SpaceFollow", f"{cond}.secondTerm")
        cmds.setAttr(f"{cond}.operation", 0) # Equal
        cmds.setAttr(f"{cond}.colorIfTrueR", 1)
        cmds.setAttr(f"{cond}.colorIfFalseR", 0)

        cmds.connectAttr(f"{cond}.outColorR", f"{pm_sources}.target[{i}].weight")
        driver_attr = driver if "." in driver else f"{driver}.worldMatrix[0]"
        cmds.connectAttr(driver_attr, f"{pm_sources}.target[{i}].targetMatrix")
        if pv:
            mmx_live = cmds.createNode("multMatrix", name=target.replace("_CTL", f"_Src{i:02d}Live_MMT"), ss=True)
            if input_connection:
                cmds.connectAttr(input_connection, f"{mmx_live}.matrixIn[0]")
            inv_matrix = cmds.getAttr(f"{driver}.worldInverseMatrix[0]")
            cmds.setAttr(f"{mmx_live}.matrixIn[1]", inv_matrix, type="matrix")
            cmds.connectAttr(f"{mmx_live}.matrixSum", f"{pm_sources}.target[{i}].offsetMatrix")
        else:
            off_mat = get_offset_matrix(target_grp, driver)
            cmds.setAttr(f"{pm_sources}.target[{i}].offsetMatrix", off_mat, type="matrix")


    cmds.connectAttr(f"{pm_master}.outputMatrix", f"{bmx_final}.inputMatrix")
    cmds.connectAttr(f"{pm_sources}.outputMatrix", f"{bmx_final}.target[0].targetMatrix")

    cmds.connectAttr(f"{target}.TranslateValue", f"{bmx_final}.target[0].translateWeight")
    cmds.connectAttr(f"{target}.RotateValue", f"{bmx_final}.target[0].rotateWeight")
    
    cmds.setAttr(f"{bmx_final}.target[0].scaleWeight", 0)
    cmds.setAttr(f"{bmx_final}.target[0].shearWeight", 0)

    cmds.connectAttr(f"{bmx_final}.outputMatrix", f"{target_grp}.offsetParentMatrix", force=True)

    # om.MGlobal.displayInfo(f"Space Switch creado con éxito para: {target}")


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


def mirror_controllers(controllers_grp = [], input_matrix=None, secondary_axis=(0, 1, 0), rotate_180=False):

    for ctl in controllers_grp:

        name = ctl.replace("_GRP", "")

        if rotate_180 and secondary_axis == (0, 1, 0) or secondary_axis == (0, -1, 0):
            rotate_axis = "Y"
        elif rotate_180 and secondary_axis == (0, 0, 1) or secondary_axis == (0, 0, -1):
            rotate_axis = "Z"
        elif rotate_180 and secondary_axis == (1, 0, 0) or secondary_axis == (-1, 0, 0):
            rotate_axis = "X"

        mmx_negate = cmds.createNode("multMatrix", name=f"{name}_MMX", ss=True)
        compose_matrix_mirror = cmds.createNode("composeMatrix", name=f"{name}_Mirror_CMP", ss=True)
        
        if secondary_axis[0] == 1 or secondary_axis[0] == -1: # Set the matrix to mirror in the correct axis based on the primary input axis
            cmds.setAttr(f"{compose_matrix_mirror}.inputScaleX", -1)
        
        elif secondary_axis[1] == 1 or secondary_axis[1] == -1:
            cmds.setAttr(f"{compose_matrix_mirror}.inputScaleZ", -1)
        
        elif secondary_axis[2] == 1 or secondary_axis[2] == -1:
            cmds.setAttr(f"{compose_matrix_mirror}.inputScaleY", -1)
        
        if rotate_180:
            cmds.setAttr(f"{compose_matrix_mirror}.inputRotate{rotate_axis}", 180)

        matrix_values = cmds.getAttr(f"{compose_matrix_mirror}.outputMatrix")

        cmds.setAttr(f"{mmx_negate}.matrixIn[0]", *matrix_values, type="matrix")
        cmds.connectAttr(input_matrix, f"{mmx_negate}.matrixIn[1]")
        cmds.connectAttr(f"{mmx_negate}.matrixSum", f"{ctl}.offsetParentMatrix", force=True)

        cmds.delete(compose_matrix_mirror)


def skeleton_hierarchy(joint_list, parent_to_root=False):

    """
    Create a skeleton hierarchy based on a list of joints. The first joint in the list will be the root joint.
    args:
        joint_list (list): A list of joint names in the order they should be parented.
        parent_to_root (bool): If True, the first joint will be parented to the root of the rig. If False, it will be left unparented.
    """
    
    # Get rig group from data manager to parent our new TRN
    rig_grp = data_manager.DataExportBiped().get_data("basic_structure", "rig_GRP")
    skeleton_hierarchy_grp = cmds.createNode("transform", name="skeletonHierarchy_GRP", parent=rig_grp)

    for i, joint in enumerate(joint_list):
        if i == 0 and parent_to_root:
            cmds.parent(joint, skeleton_hierarchy_grp)
        elif i > 0:
            cmds.parent(joint, joint_list[i-1])


def getClosestParamsToPositionSurface(surface, position):
    """
    Returns the closest parameters (u, v) on the given NURBS surface 
    to a world-space position.

    Args:
        surface (str or MObject or MDagPath): The surface to evaluate.
        position (list or tuple): A 3D world-space position [x, y, z].

    Returns:
        tuple: (u, v) parameters on the surface closest to the given position.
    """
    # Get MDagPath for surface
    if isinstance(surface, str):
        sel = om.MSelectionList()
        sel.add(surface)
        surface_dag_path = sel.getDagPath(0)
    elif isinstance(surface, om.MObject):
        surface_dag_path = om.MDagPath.getAPathTo(surface)
    elif isinstance(surface, om.MDagPath):
        surface_dag_path = surface
    else:
        raise TypeError("Surface must be a string name, MObject, or MDagPath.")

    # Create function set for NURBS surface
    surface_fn = om.MFnNurbsSurface(surface_dag_path)

    # Convert position to MPoint
    point = om.MPoint(*position)

    # Get closest point and parameters
    closest_point, u, v = surface_fn.closestPoint(point, space=om.MSpace.kWorld)

    return u, v

def getClosestParamToWorldMatrixCurve(curve, pos, point=False, both=False):
    """
    Returns the closest parameter (u) on the curve to the given worldMatrix.
    """
    selection_list = om.MSelectionList()
    selection_list.add(curve)
    curve_dag_path = selection_list.getDagPath(0)

    curveFn = om.MFnNurbsCurve(curve_dag_path)

    point_pos = om.MPoint(*pos)
    closestPoint, paramU = curveFn.closestPoint(point_pos, space=om.MSpace.kWorld)

    if point:
        return closestPoint
    
    elif both:
        return closestPoint, paramU

    return paramU


def local_mmx(ctl, grp):

        """
        Create a local matrix manager for a controller.
        Args:
            ctl (str): The name of the controller.
        Returns:
            matrix_manager.MatrixManager: The local matrix manager.
        """

        mmx = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMX"), ss=True)
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{mmx}.matrixIn[0]")
        cmds.connectAttr(f"{grp}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]")
        grp_wm = cmds.getAttr(f"{grp}.worldMatrix[0]")
        cmds.setAttr(f"{mmx}.matrixIn[2]", grp_wm, type="matrix")

        return mmx


def extract_twist(source_plug, ref_plug, axis="x", name="twist", return_quat=False):
    """
    Swing-twist decomposition (quaternion) as a node network: extract ONLY the
    axial twist of `source_plug` relative to `ref_plug` around `axis`, discarding
    the swing.  The rest pose is neutralized so the twist is 0 at build time.

    By default returns a quatToEuler node (use `.outputRotate`). With
    `return_quat=True` it skips the euler conversion and returns the
    quatNormalize node (use `.outputQuat`); feed it into a `composeMatrix.inputQuat`
    with `useEulerRotation=0` to rebuild the twist matrix WITHOUT the
    matrix->rotate->matrix round-trip (cheaper, see [[reference-matrix-roundtrip]]).

    Args:
        source_plug (str): matrix plug with the twist (e.g. the real joint).
        ref_plug (str): no-twist reference matrix plug.
        axis (str): 'x', 'y' or 'z' — the bone aim axis.
        name (str): prefix for the created nodes.
        return_quat (bool): return the quatNormalize node (`.outputQuat`) instead
            of a quatToEuler node (`.outputRotate`).

    Returns:
        str: the quatNormalize node if `return_quat`, else the quatToEuler node.
    """
    axis = axis.lower()
    comp = {"x": "X", "y": "Y", "z": "Z"}[axis]

    inv = cmds.createNode("inverseMatrix", name=f"{name}TwistRef_INV", ss=True)
    cmds.connectAttr(ref_plug, f"{inv}.inputMatrix")

    rel = cmds.createNode("multMatrix", name=f"{name}TwistRel_MMX", ss=True)
    cmds.connectAttr(source_plug, f"{rel}.matrixIn[0]")
    cmds.connectAttr(f"{inv}.outputMatrix", f"{rel}.matrixIn[1]")

    # neutralize the rest pose so the extracted twist is zero by default
    rest_inv = om.MMatrix(cmds.getAttr(f"{rel}.matrixSum")).inverse()
    neutral = cmds.createNode("multMatrix", name=f"{name}TwistNeutral_MMX", ss=True)
    cmds.setAttr(f"{neutral}.matrixIn[0]", list(rest_inv), type="matrix")
    cmds.connectAttr(f"{rel}.matrixSum", f"{neutral}.matrixIn[1]")

    dcm = cmds.createNode("decomposeMatrix", name=f"{name}Twist_DCM", ss=True)
    cmds.connectAttr(f"{neutral}.matrixSum", f"{dcm}.inputMatrix")

    # keep only the axis imaginary component + W, then renormalize -> pure twist
    qn = cmds.createNode("quatNormalize", name=f"{name}Twist_QTN", ss=True)
    cmds.connectAttr(f"{dcm}.outputQuat{comp}", f"{qn}.inputQuat{comp}")
    cmds.connectAttr(f"{dcm}.outputQuatW", f"{qn}.inputQuatW")

    if return_quat:
        return qn

    q2e = cmds.createNode("quatToEuler", name=f"{name}Twist_QTE", ss=True)
    cmds.connectAttr(f"{qn}.outputQuat", f"{q2e}.inputQuat")

    return q2e


def bend_factor(m0, m1, m2, name="bend"):
    """
    0-1 factor from the bend of a 3-joint chain (m0->m1->m2), computed from the
    NORMALIZED DOT of the two bone vectors: `(1 - cos) / 2`.  Straight chain
    (colinear) -> 0, right angle -> 0.5, fully folded (180) -> 1.

    Uses the dot product instead of an `angleBetween` node so it stays smooth and
    monotonic and never flips (angleBetween's rotation axis is undefined near 180).

    Args:
        m0, m1, m2 (str): the three nodes with a `.outputMatrix` (start/mid/end).
        name (str): prefix for the created nodes.

    Returns:
        str: a `.output` plug (0-1).
    """
    def pos(m, tag):
        r = cmds.createNode("rowFromMatrix", name=f"{name}{tag}Pos_RFM", ss=True)
        cmds.setAttr(f"{r}.input", 3)
        cmds.connectAttr(f"{m}.outputMatrix", f"{r}.matrix")
        return r

    def sub(a, b, tag):
        n = cmds.createNode("plusMinusAverage", name=f"{name}{tag}_PMA", ss=True)
        cmds.setAttr(f"{n}.operation", 2)  # subtract
        for ax in "XYZ":
            cmds.connectAttr(f"{a}.output{ax}", f"{n}.input3D[0].input3D{ax.lower()}")
            cmds.connectAttr(f"{b}.output{ax}", f"{n}.input3D[1].input3D{ax.lower()}")
        return n

    def norm(src, tag):
        n = cmds.createNode("normalize", name=f"{name}{tag}_NRM", ss=True)
        cmds.connectAttr(f"{src}.output3D", f"{n}.input")
        return n

    p0, p1, p2 = pos(m0, "Sh"), pos(m1, "Md"), pos(m2, "En")
    upper = norm(sub(p1, p0, "Upper"), "UpperN")   # mid - start (normalized)
    lower = norm(sub(p2, p1, "Lower"), "LowerN")   # end - mid (normalized)

    dot = cmds.createNode("vectorProduct", name=f"{name}_DOT", ss=True)
    cmds.setAttr(f"{dot}.operation", 1)  # dot product
    cmds.connectAttr(f"{upper}.output", f"{dot}.input1")
    cmds.connectAttr(f"{lower}.output", f"{dot}.input2")

    one_minus = cmds.createNode("subtract", name=f"{name}OneMinus_SUB", ss=True)  # 1 - cos
    cmds.setAttr(f"{one_minus}.input1", 1.0)
    cmds.connectAttr(f"{dot}.outputX", f"{one_minus}.input2")

    half = cmds.createNode("multiply", name=f"{name}Half_MUL", ss=True)  # * 0.5
    cmds.connectAttr(f"{one_minus}.output", f"{half}.input[0]")
    cmds.setAttr(f"{half}.input[1]", 0.5)

    return f"{half}.output"


def segment_volume(m_start, m_end, rest_len, volume_attr, global_scale_attr, name="vol"):
    """
    Volume-preservation scale factor for a bone: `1 + Volume*(1/sqrt(stretch) - 1)`,
    where `stretch = currentLength / restLength`.  Drive a skinning joint's
    scaleY/scaleZ with the returned plug so it squashes/stretches by volume.

    Args:
        m_start, m_end (str): bone end nodes with `.outputMatrix`.
        rest_len (float): rest length of the bone.
        volume_attr (str): 0-1 attribute plug (amount of volume preservation).
        global_scale_attr (str): masterwalk globalScale plug (rig scale safety).
        name (str): prefix for the created nodes.

    Returns:
        str: the `.output` plug with the secondary scale factor.
    """
    dist = cmds.createNode("distanceBetween", name=f"{name}Vol_DBT", ss=True)
    cmds.connectAttr(f"{m_start}.outputMatrix", f"{dist}.inMatrix1")
    cmds.connectAttr(f"{m_end}.outputMatrix", f"{dist}.inMatrix2")

    norm = cmds.createNode("divide", name=f"{name}VolNorm_DIV", ss=True)
    cmds.connectAttr(f"{dist}.distance", f"{norm}.input1")
    cmds.connectAttr(global_scale_attr, f"{norm}.input2")

    stretch = cmds.createNode("divide", name=f"{name}VolStretch_DIV", ss=True)
    cmds.connectAttr(f"{norm}.output", f"{stretch}.input1")
    cmds.setAttr(f"{stretch}.input2", rest_len if rest_len else 1.0)

    inv_sqrt = cmds.createNode("power", name=f"{name}VolInvSqrt_POW", ss=True)
    cmds.connectAttr(f"{stretch}.output", f"{inv_sqrt}.input")
    cmds.setAttr(f"{inv_sqrt}.exponent", -0.5)  # 1/sqrt(stretch)

    minus = cmds.createNode("subtract", name=f"{name}VolMinus_SUB", ss=True)
    cmds.connectAttr(f"{inv_sqrt}.output", f"{minus}.input1")
    cmds.setAttr(f"{minus}.input2", 1.0)

    mult = cmds.createNode("multiply", name=f"{name}VolMult_MUL", ss=True)
    cmds.connectAttr(f"{minus}.output", f"{mult}.input[0]")
    cmds.connectAttr(volume_attr, f"{mult}.input[1]")

    add = cmds.createNode("sum", name=f"{name}VolAdd_SUM", ss=True)
    cmds.connectAttr(f"{mult}.output", f"{add}.input[0]")
    cmds.setAttr(f"{add}.input[1]", 1.0)

    return f"{add}.output"