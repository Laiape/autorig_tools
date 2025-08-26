import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload

from utils import guides_manager
from utils import basic_structure
from utils import data_manager

from autorig import arm_module_de_boor as arm_module
from autorig import spine_module
from autorig import leg_module_de_boor as leg_module
from autorig import neck_module_de_boor as neck_module
from autorig import fingers_module

reload(guides_manager) 
reload(basic_structure)
reload(data_manager)
reload(arm_module)
reload(spine_module)
reload(leg_module)
reload(neck_module)
reload(fingers_module)


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
        self.inherit_transforms()
        

    def basic_structure(self):

        """
        Create the basic structure for the rig, including character, rig, controls, meshes, and deformers groups.
        """

        basic_structure.create_basic_structure()
    

    def make_rig(self):

        """
        Create the rig for the character, including joints, skinning, and control curves.
        """
        spine_module.SpineModule().make("C")
        arm_module.ArmModule().make("L")
        arm_module.ArmModule().make("R")
        leg_module.LegModule().make("L")
        leg_module.LegModule().make("R")
        neck_module.NeckModule().make("C")
        fingers_module.FingersModule().make("L")
        fingers_module.FingersModule().make("R")

        cmds.inViewMessage(
    amg='Completed <hl>BIPED RIG</hl> build.',
    pos='midCenter',
    fade=True,
    alpha=0.8)


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

    def inherit_transforms(self):

        """
        Set the inherit transforms for the rig controls to ensure proper movement and rotation.
        """

        curves = cmds.ls("*CRV")

        for crv in curves:
           if "Shape" in crv:
               continue
           else:
               try:
                   cmds.setAttr(crv + ".inheritsTransform", 0)
               except Exception as e:
                   print(f"Error setting inherit transforms for {crv}: {e}")

        print("Inherit transforms set successfully.")

    
    


