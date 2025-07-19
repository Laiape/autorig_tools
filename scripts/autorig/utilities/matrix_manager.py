import maya.cmds as cmds
import maya.api.OpenMaya as om

def fk_constraint(joint, before_jnt, pair_blend):

    """
    Create a parent constraint from source to target. Rememeber to don't put values in the Fk controllers.
    args:
        joint (str): the joint to be constrained.
        before_jnt (str): the joint to add the offset.
        before_ctl (str): the before control to add the offset.
    """
    before_ctl = before_jnt.replace("_JNT", "_CTL")
    joint_ctl = joint.replace("_JNT", "_CTL")
    joint_grp = joint.replace("_JNT", "_GRP")

    if before_jnt == "None":

        cmds.connectAttr(f"{joint_ctl}.worldMatrix[0]", f"{joint}.offsetParentMatrix")

    else:

        mult_matrix_offset = cmds.createNode("multMatrix", name=joint.replace("JNT", "MMT"), ss=True)
        cmds.connectAttr(f"{before_ctl}.worldMatrix[0]", f"{mult_matrix_offset}.matrixIn[0]")
        cmds.connectAttr(f"{before_jnt}.worldInverseMatrix[0]", f"{mult_matrix_offset}.matrixIn[1]")
        cmds.connectAttr(f"{joint_ctl}.worldMatrix[0]", f"{mult_matrix_offset}.matrixIn[2]")
        cmds.connectAttr(f"{mult_matrix_offset}.matrixSum", f"{joint}.offsetParentMatrix")

    if pair_blend != "None":
        
        cmds.connectAttr(f"{joint_ctl}.rotate", f"{pair_blend}.inRotate2", force=True)
        cmds.connectAttr(f"{joint_grp}.translate", f"{pair_blend}.inTranslate2", force=True)



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

    