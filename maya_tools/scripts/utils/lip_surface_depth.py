"""Control projection-induced lip recession while preserving its neutral offset."""
import maya.cmds as cmds


def install(controller, raw_z, projected_z, destinations, rest_offset=None, follow=0.5):
    """Blend projected depth with unprojected depth, calibrated in neutral pose.

    These plugs use the jaw module's construction space (its existing depth axis
    is Z). X/Y projection, jaw following, pucker push and roll remain downstream.
    Supply rest_offset when retrofitting a posed rig; never calibrate in that pose.
    """
    if rest_offset is None:
        rest_offset = cmds.getAttr(raw_z) - cmds.getAttr(projected_z)
    attribute = controller + ".SurfaceDepthFollow"
    if cmds.objExists(attribute):
        raise RuntimeError("SurfaceDepthFollow ya existe: " + controller)
    for destination in destinations:
        if not cmds.isConnected(projected_z, destination):
            raise RuntimeError("Conexion de profundidad inesperada: " + destination)
    prefix = controller.rsplit("|", 1)[-1].removesuffix("_CTL") + "SurfaceDepth"
    cmds.addAttr(controller, longName="SurfaceDepthFollow", attributeType="double",
                 minValue=0, maxValue=1, defaultValue=follow, keyable=True)
    # correction = (1-follow) * [(raw-projected) - (raw0-projected0)]
    difference = cmds.createNode("plusMinusAverage", name=prefix + "Delta_PMA")
    cmds.setAttr(difference + ".operation", 2)
    cmds.connectAttr(raw_z, difference + ".input1D[0]")
    cmds.connectAttr(projected_z, difference + ".input1D[1]")
    cmds.setAttr(difference + ".input1D[2]", rest_offset)
    reverse = cmds.createNode("reverse", name=prefix + "_REV")
    cmds.connectAttr(attribute, reverse + ".inputX")
    multiply = cmds.createNode("multiply", name=prefix + "_MUL")
    cmds.connectAttr(difference + ".output1D", multiply + ".input[0]")
    cmds.connectAttr(reverse + ".outputX", multiply + ".input[1]")
    result = cmds.createNode("sum", name=prefix + "_SUM")
    cmds.connectAttr(projected_z, result + ".input[0]")
    cmds.connectAttr(multiply + ".output", result + ".input[1]")
    for destination in destinations:
        cmds.connectAttr(result + ".output", destination, force=True)
    return result + ".output"
