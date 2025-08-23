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


    if before_jnt == None:

        cmds.connectAttr(f"{joint_ctl}.worldMatrix[0]", f"{joint}.offsetParentMatrix")

    else:

        mult_matrix_offset = cmds.createNode("multMatrix", name=joint.replace("JNT", "MMT"), ss=True)
        cmds.connectAttr(f"{joint_ctl}.worldMatrix[0]", f"{mult_matrix_offset}.matrixIn[0]", force=True)
        cmds.connectAttr(f"{before_jnt}.worldInverseMatrix[0]", f"{mult_matrix_offset}.matrixIn[1]", force=True)
        cmds.connectAttr(f"{mult_matrix_offset}.matrixSum", f"{joint}.offsetParentMatrix", force=True)


        if pair_blend == True:

            blend_matrix = cmds.createNode("blendMatrix", name=joint.replace("JNT", "BM"), ss=True)
            cmds.connectAttr(f"{ik_joint}.worldMatrix[0]", f"{blend_matrix}.inputMatrix", force=True)
            cmds.connectAttr(f"{joint}.worldMatrix[0]", f"{blend_matrix}.target[0].targetMatrix", force=True)
            cmds.xform(blend_joint, m=om.MMatrix.kIdentity)
            mult_matrix_off = cmds.createNode("multMatrix", name=joint.replace("_JNT", "Off_MMT"), ss=True)
            cmds.connectAttr(f"{blend_matrix}.outputMatrix", f"{mult_matrix_off}.matrixIn[0]", force=True)
            cmds.connectAttr(f"{before_blend_jnt}.worldInverseMatrix[0]", f"{mult_matrix_off}.matrixIn[1]", force=True)
            cmds.connectAttr(f"{mult_matrix_off}.matrixSum", f"{blend_joint}.offsetParentMatrix", force=True)

            if settings_ctl != None:

                cmds.connectAttr(f"{settings_ctl}.Ik_Fk", f"{blend_matrix}.target[0].weight", force=True)

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

    