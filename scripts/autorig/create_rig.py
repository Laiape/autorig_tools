import maya.cmds as cmds
from utils import guides_manager
from utils import basic_structure

class AutoRig(object):

    """
    AutoRig class to create a custom rig for a character in Maya.
    """

    def __init__(self):

        """
        Initialize the AutoRig class, setting up the basic structure and connecting UI elements.
        """

        basic_structure.create_basic_structure()
        self.make_rig()
        self.label_joints()
        self.hide_connections()
    

    def make_rig(self):

        """
        Create the rig for the character, including joints, skinning, and control curves.
        """
        pass

    def label_joints(self):

        """
        Label the joints in the rig with appropriate names.
        """
        
        for jnt in cmds.ls(type="joint"):
            if "L" in jnt:
                cmds.setAttr(jnt + ".side", 1)
            if "R" in jnt:
                cmds.setAttr(jnt + ".side", 2)
            if "C" in jnt:
                cmds.setAttr(jnt + ".side", 0)
            cmds.setAttr(jnt + ".type", 18)
            cmds.setAttr(jnt + ".otherType", jnt.split("_")[1], type= "string")

    def hide_connections(self):

        """
        Hide the connections in the rig to clean up the scene.
        """

        float_math = cmds.createNode("floatConstant", name="hide_connections")
        cmds.setAttr(float_math + ".inValue", 0)

        skin_clusters = cmds.ls(type="skinCluster")
        all_nodes = cmds.ls(ap=True)

        for node in all_nodes:
            if node not in skin_clusters:
                cmds.connectAttr(float_math + ".outValue", node + ".isHistoricallyInteresting", force=True)


