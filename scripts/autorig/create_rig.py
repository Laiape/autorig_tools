import maya.cmds as cmds
from importlib import reload

from utils import guides_manager
from utils import basic_structure
from utils import data_manager

from autorig import arm_module

reload(guides_manager) 
reload(basic_structure)
reload(data_manager)
reload(arm_module)


class AutoRig(object):

    """
    AutoRig class to create a custom rig for a character in Maya.
    """

    def build(self):

        """
        Initialize the AutoRig class, setting up the basic structure and connecting UI elements.
        """

        data_manager.DataExport().new_build()

        self.basic_structure()
        self.make_rig()
        self.label_joints()
        self.hide_connections()
        

    def basic_structure(self):

        """
        Create the basic structure for the rig, including character, rig, controls, meshes, and deformers groups.
        """

        basic_structure.create_basic_structure()
    

    def make_rig(self):

        """
        Create the rig for the character, including joints, skinning, and control curves.
        """
        
        arm_module.ArmModule().make("L")
        arm_module.ArmModule().make("R")

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

        print("Joints labeled successfully.")

    def delete_unused_nodes(self):

        """
        Delete unused nodes in the scene to clean up the workspace.
        """

        all_nodes = cmds.ls(ap=True)

        unused_nodes = []

        for node in all_nodes:
            connections = cmds.listConnections(node, source=True, destination=True)
            if not connections:
                unused_nodes.append(node)
        
        if unused_nodes:

            cmds.delete(unused_nodes)
            
            print(f"Deleted unused nodes")
    
    def hide_connections(self):

        """
        Hide the connections in the rig to clean up the scene.
        """

        float_math = cmds.createNode("floatConstant", name="hide_connections")
        cmds.setAttr(float_math + ".inFloat", 0)

        skin_clusters = cmds.ls(type="skinCluster")
        all_nodes = cmds.ls(ap=True)

        for node in all_nodes:
            if node not in skin_clusters:
                cmds.connectAttr(float_math + ".outFloat", node + ".isHistoricallyInteresting", force=True)

        cmds.delete(float_math)
        print("Connections hidden successfully.")

    
    


