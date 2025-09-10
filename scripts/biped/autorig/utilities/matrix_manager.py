import maya.cmds as cmds
import maya.api.OpenMaya as om

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
    cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{mult_matrix}.matrixIn[0]")
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

        name = matrix.split("_")[1].capitalize()

        condition_nodes.append(condition)
        source_matrices.append(name)

    cmds.addAttr(target, longName="SpaceSwitchSep", niceName = "SPACE_SWITCHES", attributeType="enum", enumName="____", keyable=True)
    cmds.setAttr(f"{target}.SpaceSwitchSep", channelBox=True, lock=True)   
    if len(sources) == 1:     
        cmds.addAttr(target, longName="SpaceSwitch", attributeType="enum", enumName=":".join(source_matrices), keyable=False)
        cmds.setAttr(f"{target}.SpaceSwitchSep", channelBox=True, lock=True)   
    else:
        cmds.addAttr(target, longName="SpaceSwitch", attributeType="enum", enumName=":".join(source_matrices), keyable=True)

    cmds.addAttr(target, longName="FollowValue", attributeType="float", min=0, max=1, defaultValue=default_value, keyable=True)

    for i, condition in enumerate(condition_nodes):
        cmds.connectAttr(f"{target}.SpaceSwitch", f"{condition}.secondTerm")
        cmds.connectAttr(f"{target}.FollowValue", f"{condition}.colorIfTrueR")
        cmds.connectAttr(f"{condition}.outColorR", f"{parent_matrix}.target[{i}].weight")

    
    cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{target}.offsetParentMatrix")


def get_offset_matrix(child, parent):

    """
    Calculate the offset matrix between a child and parent transform in Maya.
    Args:
        child (str): The name of the child transform.
        parent (str): The name of the parent transform. 
    Returns:
        om.MMatrix: The offset matrix that transforms the child into the parent's space.
    """
    child_dag = om.MSelectionList().add(child).getDagPath(0)
    parent_dag = om.MSelectionList().add(parent).getDagPath(0)

    child_world_matrix = child_dag.inclusiveMatrix()
    parent_world_matrix = parent_dag.inclusiveMatrix()
    
    offset_matrix = child_world_matrix * parent_world_matrix.inverse()

    
    return offset_matrix

    