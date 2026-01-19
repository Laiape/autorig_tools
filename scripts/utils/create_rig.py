import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload

# Utils
from utils import guides_manager
from utils import basic_structure
from utils import data_manager
from utils import rig_manager
from utils import matrix_manager
from tools import skin_manager_api

# Body mechanics
from biped.autorig import arm_module_de_boor as arm_module
from biped.autorig import spine_module as spine_module
from biped.autorig import clavicle_module
from biped.autorig import leg_module_de_boor as leg_module
from biped.autorig import neck_module_de_boor as neck_module
from biped.autorig import fingers_module

# Facial
from biped.autorig import eyebrow_module
from biped.autorig import eyelid_module
from biped.autorig import ear_module
from biped.autorig import nose_module
from biped.autorig import jaw_module
from biped.autorig import cheekbone_module
from biped.autorig import tongue_module
from biped.autorig import teeth_module

# Reload utils
reload(guides_manager) 
reload(basic_structure)
reload(data_manager)
reload(matrix_manager)
reload(rig_manager)
reload(skin_manager_api)

# Reload body mechanics
reload(arm_module)
reload(spine_module)
reload(leg_module)
reload(neck_module)
reload(fingers_module)
reload(clavicle_module)

# Reload facial
reload(eyebrow_module)
reload(eyelid_module)
reload(ear_module)
reload(nose_module)
reload(jaw_module)
reload(cheekbone_module)
reload(tongue_module)
reload(teeth_module)



class AutoRig(object):

    """
    AutoRig class to create a custom rig for a character in Maya.
    """

    def build(self):

        """
        Initialize the AutoRig class, setting up the basic structure and connecting UI elements.
        """

        data_manager.DataExportBiped().new_build()
        
        self.basic_structure()
        self.make_rig()
        self.space_switches()
        self.label_joints()
        
        skinner = skin_manager_api.SkinManager()
        skinner.import_skins() # Import skin clusters after rig creation

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
        char_name = rig_manager.get_character_name_from_build().upper()
        rig_manager.build_rig()

        cmds.inViewMessage(
    amg=f'Completed <hl>{char_name} RIG</hl> build.',
    pos='midCenter',
    fade=True,
    alpha=0.8)

    def space_switches(self):

        """
        Els controls han de tenir els següents spaceSwitches de translació i rotació:

        armIk: masterWalk, chest, body, localHip, head (per defecte ha d'estar a masterWalk)

        armPv: masterWalk, armIk, clavicle, chest, body (per defecte ha d'estar a armIk)

        legIk: masterWalk, body, localHip (per defecte ha d'estar a masterWalk)

        legPv: masterWalk, legIk, body (per defecte ha d'estar a legIk)

        Els controls han de tenir els següents spaceSwitches de només rotació, però han de seguir el seu hook:

        armFk00: clavicle, chest, body (per defecte ha d'estar en clavicle)

        legFk00: masterWalk, localHip, body (per defecte ha d'estar en localHip)

        El control del head ha de tenir un spaceSwitch de només rotació que a més a més hi hagi un atribut de tipus float amb màxim a 1 i mínim a 0 i valor per defecte a 1 que permeti escollir la quantitat d’space que s’està aplicant. 

        head: masterWalk, neck, chest, body (per defecte ha d’estar a chest)
        """

        # Drivens
        masterwalk = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        chest = data_manager.DataExportBiped().get_data("spine_module", "local_chest_ctl")
        body = data_manager.DataExportBiped().get_data("spine_module", "body_ctl")
        local_hip = data_manager.DataExportBiped().get_data("spine_module", "local_hip_ctl")
        head = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")
        neck = data_manager.DataExportBiped().get_data("neck_module", "neck_ctl")

        for side in ["L", "R"]:

            # Drivers
            arm_ik = data_manager.DataExportBiped().get_data("arm_module", f"{side}_armIk")
            arm_pv = data_manager.DataExportBiped().get_data("arm_module", f"{side}_armPv")
            leg_ik = data_manager.DataExportBiped().get_data("leg_module", f"{side}_legIk")
            leg_pv = data_manager.DataExportBiped().get_data("leg_module", f"{side}_legPv")
            shoulder_fk = data_manager.DataExportBiped().get_data("arm_module", f"{side}_shoulderFk")
            hip_fk = data_manager.DataExportBiped().get_data("leg_module", f"{side}_hipFk")
            clavicle = data_manager.DataExportBiped().get_data("clavicle_module", f"{side}_clavicle")
            root_ik = data_manager.DataExportBiped().get_data("leg_module", f"{side}_rootIk")
            arm_ik_root = data_manager.DataExportBiped().get_data("arm_module", f"{side}_armIkRoot")

            # Space switches
            matrix_manager.space_switches(target=arm_ik, sources=[body, masterwalk, clavicle, chest, local_hip, head], default_value=1) # Arm ik
            matrix_manager.space_switches(target=arm_pv, sources=[body, arm_ik, masterwalk, clavicle, chest], default_value=1) # Arm pv
            matrix_manager.space_switches(target=leg_ik, sources=[masterwalk, local_hip, body], default_value=1) # Leg ik
            matrix_manager.space_switches(target=leg_pv, sources=[body, leg_ik, masterwalk], default_value=1) # Leg pv
            matrix_manager.space_switches(target=shoulder_fk, sources=[clavicle, chest, body], default_value=1) # Shoulder fk
            matrix_manager.space_switches(target=hip_fk, sources=[body, local_hip, masterwalk], default_value=1) # Hip fk
            matrix_manager.space_switches(target=root_ik, sources=[local_hip, masterwalk], default_value=1) # Root ik
            matrix_manager.space_switches(target=clavicle, sources=[chest, body], default_value=1) # Clavicle
            matrix_manager.space_switches(target=arm_ik_root, sources=[clavicle, chest, masterwalk], default_value=1) # Arm ik root
        matrix_manager.space_switches(target=neck, sources=[chest, body], default_value=1) # Neck
        matrix_manager.space_switches(target=local_hip, sources=[body, masterwalk], default_value=1) # Local hip

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
                if cmds.objectType(node) == "fourByFourMatrix" or cmds.objectType(node) == "rowFromMatrix":
                    continue
                else:
                    cmds.connectAttr(float_math + ".outFloat", node + ".isHistoricallyInteresting", force=True)

        cmds.delete(float_math)

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
                   om.MGlobal.displayError(f"Error setting inherit transforms for {crv}: {e}")

    
    


