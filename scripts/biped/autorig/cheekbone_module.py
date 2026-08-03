import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool
from utils import matrix_manager
from utils import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)

class CheekboneModule(object):

    def __init__(self):

        """
        Initialize the CheekboneModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")
        self.settings_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")
        self.face_ctl = data_manager.DataExportBiped().get_data("neck_module", "face_ctl")
        self.head_guide_matrix = data_manager.DataExportBiped().get_data("neck_module", "head_guide_matrix")
        self.mGear = data_manager.DataExportBiped().get_data("neck_module", "mGear")
        

    def make(self, side):

        """ 
        Create the cheekbone module structure and controllers. Call this method with the side ('L' or 'R') to create the respective cheekbone module.
        Args:
            side (str): The side of the cheekbone ('L' or 'R').

        """
        self.side = side
        self.module_name = f"C_cheekbone"
        self.lower_socket_ctl = data_manager.DataExportBiped().get_data("eyelid_module", f"{self.side}_lower_socket_ctl")
        if self.side == "L":
        
            self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
            cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
            self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
            self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.face_ctl)
            cmds.addAttr(self.face_ctl, longName="Cheekbones", attributeType="long", defaultValue=2, max=2, min=0, keyable=True)
            cmds.addAttr(self.face_ctl, longName="Cheek", attributeType="long", defaultValue=1, max=1, min=0, keyable=True)
        else:

            self.module_trn = self.module_name + "Module_GRP"
            self.skeleton_grp = self.module_name + "Skinning_GRP"
            self.controllers_grp = self.module_name + "Controllers_GRP"


        self.load_guides()
        self.create_controllers()

    def load_guides(self):

        """
        Load cheekbone guides from the guide manager.
        """
        self.cheekbone_guides = guides_manager.get_guides(f"{self.side}_cheekbone_JNT")
        cmds.select(clear=True)
        self.cheek_guide = guides_manager.get_guides(f"{self.side}_cheek_JNT")

    def local_mmx(self, ctl):

        """
        Create a local matrix manager for a controller.
        Args:
            ctl (str): The name of the controller. 
        Returns:
            matrix_manager.MatrixManager: The local matrix manager.
        """

        mmx = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMX"), ss=True)
        grp = ctl.replace("_CTL", "_GRP")

        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{mmx}.matrixIn[0]")
        cmds.connectAttr(f"{grp}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]")
        grp_matrix_values = cmds.getAttr(f"{grp}.worldMatrix[0]")
        cmds.setAttr(f"{mmx}.matrixIn[2]", *grp_matrix_values, type="matrix")

        return mmx

    def create_controllers(self):

        """
        Create controllers for the cheekbone module.
        """

        condition_cheekbones = cmds.createNode("condition", name="C_cheekbonesControllers_COND", ss=True)
        cmds.setAttr(f"{condition_cheekbones}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_cheekbones}.secondTerm", 1)
        cmds.setAttr(f"{condition_cheekbones}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_cheekbones}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Cheekbones", f"{condition_cheekbones}.firstTerm")

        condition_secondary = cmds.createNode("condition", name="C_cheekboneControllers_COND", ss=True)
        cmds.setAttr(f"{condition_secondary}.operation", 0)  # Equal
        cmds.setAttr(f"{condition_secondary}.secondTerm", 2)
        cmds.setAttr(f"{condition_secondary}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_secondary}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Cheekbones", f"{condition_secondary}.firstTerm")

        # El eyelid puede haberse construido sin sockets (sin guías): entonces no
        # hay ctl que empujar y este bloque se omite entero.
        condition_socket = None
        if self.lower_socket_ctl and cmds.objExists(self.lower_socket_ctl):
            socket_off_grp = self.lower_socket_ctl.replace("CTL", "OFF")
            condition_socket = cmds.createNode("condition", name=f"C_{self.side}_socketMovement_CON", ss=True)
            cmds.setAttr(f"{condition_socket}.operation", 3)  # Greater Than or Equal
            cmds.setAttr(f"{condition_socket}.secondTerm", 0)
            cmds.setAttr(f"{condition_socket}.colorIfFalseR", 0)
            cmds.connectAttr(f"{condition_socket}.outColorR", f"{socket_off_grp}.translateY")
        
        cheeckbones_ctls = []
        cheeckbones_grps = []
        skinning_jnts = []

        for i, guide in enumerate(self.cheekbone_guides):

            name = guide.replace("_JNT", "")

            if i == 0:
                grp, ctl = curve_tool.create_controller(name=name, parent=self.controllers_grp, offset=["GRP", "OFF"])
                if condition_socket:
                    cmds.connectAttr(f"{ctl}.translateY", f"{condition_socket}.firstTerm")
                    cmds.connectAttr(f"{ctl}.translateY", f"{condition_socket}.colorIfTrueR")

                cmds.connectAttr(f"{condition_cheekbones}.outColorR", f"{grp[0]}.visibility")
                cheeckbones_ctls.append(ctl)
                cheeckbones_grps.append(grp)
            else:
                grp, ctl = curve_tool.create_controller(name=name, offset=["GRP", "OFF"])
                cmds.parent(grp[0], f"{cheeckbones_ctls[0]}")
                cmds.connectAttr(f"{condition_secondary}.outColorR", f"{grp[0]}.visibility")
                cheeckbones_ctls.append(ctl)
                cheeckbones_grps.append(grp)
            curve_tool.lock_attributes(ctl, ["v"])

            cmds.matchTransform(grp[0], guide, pos=True)

            if i > 0: # Avoid the first guide which is the parent
                # Delta local contra el GRP del cheekbone PRINCIPAL: cancela
                # solo lo de arriba (head/face) y conserva el movimiento del
                # ctl propio y del principal con sus pivotes reales. Una única
                # worldInverse (la del GRP principal) compartida por todos los
                # secundarios, sin re-añadir matrices locales al final.
                skinning_jnt = cmds.createNode("joint", name=guide.replace("_JNT", "Skinning_JNT"), ss=True, p=self.skeleton_grp)
                mmx = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMX"), ss=True)
                cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{mmx}.matrixIn[0]")
                cmds.connectAttr(f"{cheeckbones_grps[0][0]}.worldInverseMatrix[0]", f"{mmx}.matrixIn[1]")
                cmds.setAttr(f"{mmx}.matrixIn[2]", cmds.getAttr(f"{cheeckbones_grps[0][0]}.worldMatrix[0]"), type="matrix")
                cmds.connectAttr(f"{mmx}.matrixSum", f"{skinning_jnt}.offsetParentMatrix")
                skinning_jnts.append(skinning_jnt)

        cmds.delete(self.cheekbone_guides)
            
        # Cheek 
        grp, ctl = curve_tool.create_controller(name=self.cheek_guide[0].replace("_JNT", ""), parent=self.controllers_grp, offset=["GRP", "ANM"])
        curve_tool.lock_attributes(ctl, ["rx", "ry", "rz", "v"])
        
        # Matriz horneada (solo posición) de la guía del cheek, sin transform _GUIDE vivo
        cheek_pos = cmds.xform(self.cheek_guide[0], q=True, ws=True, t=True)
        cheek_guide_matrix = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, cheek_pos[0], cheek_pos[1], cheek_pos[2], 1]
        head_inverse_matrix = list(om.MMatrix(self.head_guide_matrix).inverse())

        condition_cheek = cmds.createNode("condition", name="C_cheekControllers_COND", ss=True)
        cmds.setAttr(f"{condition_cheek}.operation", 0)  # Equal
        cmds.setAttr(f"{condition_cheek}.secondTerm", 1)
        cmds.setAttr(f"{condition_cheek}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_cheek}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Cheek", f"{condition_cheek}.firstTerm")
        cmds.connectAttr(f"{condition_cheek}.outColorR", f"{grp[0]}.visibility")

        if self.side == "L":
            mult_matrix = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "_MMX"), ss=True)
            cmds.setAttr(f"{mult_matrix}.matrixIn[0]", cheek_guide_matrix, type="matrix")
            cmds.setAttr(f"{mult_matrix}.matrixIn[1]", head_inverse_matrix, type="matrix")

        if self.side == "R":
            mult_matrix = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Flip_MMX"), ss=True)
            four_by_four = cmds.createNode("fourByFourMatrix", name=ctl.replace("_CTL", "Flip_FFM"), ss=True)
            cmds.setAttr(f"{four_by_four}.in00", -1)
            cmds.connectAttr(f"{four_by_four}.output", f"{mult_matrix}.matrixIn[0]")
            cmds.setAttr(f"{mult_matrix}.matrixIn[1]", cheek_guide_matrix, type="matrix")
            cmds.setAttr(f"{mult_matrix}.matrixIn[2]", head_inverse_matrix, type="matrix")

        cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{grp[0]}.offsetParentMatrix")
        cmds.xform(grp[0], m=om.MMatrix.kIdentity)
        mmx = self.local_mmx(ctl)
        skinning_jnt = cmds.createNode("joint", name=self.cheek_guide[0].replace("_JNT", "Skinning_JNT"), ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{mmx}.matrixSum", f"{skinning_jnt}.offsetParentMatrix")
        cmds.delete(self.cheek_guide)