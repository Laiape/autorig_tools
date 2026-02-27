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

    