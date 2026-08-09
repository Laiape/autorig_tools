import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from maya.scripts.utils import data_manager
from maya.scripts.utils import guides_manager
from maya.scripts.utils import curve_tool
from maya.scripts.utils import matrix_manager
from maya.scripts.utils import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)

class ClavicleModule(object):

    # Floating clavicle: tamaño de la NURBS surface relativo a la longitud de la
    # clavícula (clavícula -> hombro). Ancho = U (deslizamiento adelante/atrás),
    # alto = V (arriba/abajo); con holgura para que el control deslice sin salirse.
    FLOATING_WIDTH_MULT = 3.0
    FLOATING_LENGTH_MULT = 2.0

    def __init__(self):

        """
        Initialize the clavicleModule class, setting up the necessary groups and controllers.
        """

        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side, floating=False):

        """
        Create the clavicle module structure and controllers. Call this method with the side ('L' or 'R') to create the respective clavicle module.
        Args:
            side (str): The side of the clavicle ('L' or 'R').
            floating (bool): si es True, la clavícula se desliza sobre una NURBS
                surface (movimiento realista tipo "floating shoulder") en vez de
                seguir directamente al control. Se mezcla con el atributo Floating.

        """
        self.side = side
        self.floating = floating
        self.module_trn = cmds.createNode("transform", name=f"{self.side}_clavicleModule_GRP", ss=True, p=self.modules)
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleX")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleY")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{self.module_trn}.scaleZ")
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.side}_clavicleSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.side}_clavicleControllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.clavicle_setup()

        data_manager.DataExportBiped().append_data("clavicle_module",
                            {
                                f"{self.side}_clavicle": self.ctl_ik
                            })


    def get_offset_matrix(self, child, parent):

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
    
    def load_guides(self):

        """
        Load clavicle joint guides and parent it to the module transform.
        """

        self.clavicle_joint = guides_manager.get_guides(f"{self.side}_clavicle_JNT")

        cmds.parent(self.clavicle_joint, self.module_trn)

        # Matriz horneada de la guía (estática) en lugar de un transform _GUIDE vivo
        self.clavicle_guide_matrix = cmds.getAttr(f"{self.clavicle_joint[0]}.worldMatrix[0]")

        # Longitud de la clavícula (al hombro) para dimensionar la superficie
        # floating. El hombro aún existe como guía (el brazo se construye después).
        m = self.clavicle_guide_matrix
        self.clavicle_pos = om.MVector(m[12], m[13], m[14])
        shoulder_guide = f"{self.side}_shoulder_JNT"
        if cmds.objExists(shoulder_guide):
            shoulder_pos = om.MVector(*cmds.xform(shoulder_guide, q=True, ws=True, t=True))
            self.clavicle_length = (shoulder_pos - self.clavicle_pos).length()
        else:
            self.clavicle_length = 0.0

    def clavicle_setup(self):

        cmds.select(clear=True)

        created_grps, self.ctl_ik = curve_tool.create_controller(f"{self.side}_clavicle", ["GRP", "OFF"])
        cmds.parent(created_grps[0], self.controllers_grp)
        cmds.setAttr(f"{created_grps[0]}.offsetParentMatrix", self.clavicle_guide_matrix, type="matrix")
        curve_tool.lock_attributes(self.ctl_ik, ["sx", "sy", "sz", "v"])

        # Matriz que dirige el joint: directa (control) o proyectada sobre la
        # NURBS surface (floating shoulder), según la flag.
        if self.floating:
            drive_plug = self._floating_setup(created_grps[0])
        else:
            drive_plug = f"{self.ctl_ik}.worldMatrix[0]"

        cmds.select(clear=True)
        clavicle_skinning = cmds.joint(name=f"{self.side}_clavicleSkinning_JNT")
        cmds.makeIdentity(clavicle_skinning, apply=True, t=1, r=1, s=1, n=0)
        cmds.parent(clavicle_skinning, self.skeleton_grp)
        cmds.connectAttr(drive_plug, f"{clavicle_skinning}.offsetParentMatrix")

        # Clean up: la guía importada ya solo servía de posición
        cmds.delete(self.clavicle_joint)

    def _floating_setup(self, grp):

        """
        Floating clavicle ("floating shoulder"): la clavícula se desliza sobre una
        NURBS surface para un movimiento realista. El control proyecta su posición
        sobre la superficie (closestPointOnSurface -> pointOnSurfaceInfo) y la
        clavícula sigue el punto proyectado + el frame de la superficie
        (tangentes/normal), con la ROTACIÓN del control compuesta encima. El
        atributo Floating (0-1) mezcla entre el comportamiento directo y el
        flotante. La superficie cuelga del GRP del control (que sigue al cuerpo vía
        space switch), así que la proyección viaja con el torso.

        Returns:
            str: el plug de matriz (worldMatrix) que dirige el joint de skinning.
        """
        length = self.clavicle_length or 10.0
        width = length * self.FLOATING_WIDTH_MULT
        height = length * self.FLOATING_LENGTH_MULT

        # Plano centrado en el origen, normal +Z -> U=X, V=Y, normal=Z: coincide
        # con el frame de la guía cuando cuelga del GRP (local identidad).
        surf_tf = cmds.nurbsPlane(axis=(0, 0, 1), width=width, lengthRatio=height / width,
                                  patchesU=4, patchesV=4, name=f"{self.side}_clavicleFloating_NRB")[0]
        cmds.delete(surf_tf, ch=True)  # sin historia: CVs editables (el rigger esculpe la curvatura del torso)
        cmds.parent(surf_tf, grp, relative=True)
        cmds.xform(surf_tf, matrix=list(om.MMatrix.kIdentity))
        cmds.setAttr(f"{surf_tf}.overrideEnabled", 1)
        cmds.setAttr(f"{surf_tf}.overrideDisplayType", 2)  # reference: visible para esculpir, no seleccionable
        cmds.setAttr(f"{surf_tf}.visibility", 0)
        curve_tool.lock_attributes(surf_tf, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
        self.floating_surface = surf_tf
        surf_shape = cmds.listRelatives(surf_tf, shapes=True)[0]

        ctl = self.ctl_ik

        # Posición world del control -> parámetro U,V de la superficie
        rfm = cmds.createNode("rowFromMatrix", name=f"{self.side}_clavicleFloatingPos_RFM", ss=True)
        cmds.setAttr(f"{rfm}.input", 3)
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{rfm}.matrix")

        cps = cmds.createNode("closestPointOnSurface", name=f"{self.side}_clavicleFloating_CPS", ss=True)
        cmds.connectAttr(f"{surf_shape}.worldSpace[0]", f"{cps}.inputSurface")
        for axis in "XYZ":
            cmds.connectAttr(f"{rfm}.output{axis}", f"{cps}.inPosition{axis}")

        # Frame de la superficie en ese U,V (posición + tangentes + normal)
        posi = cmds.createNode("pointOnSurfaceInfo", name=f"{self.side}_clavicleFloating_POSI", ss=True)
        cmds.connectAttr(f"{surf_shape}.worldSpace[0]", f"{posi}.inputSurface")
        cmds.connectAttr(f"{cps}.parameterU", f"{posi}.parameterU")
        cmds.connectAttr(f"{cps}.parameterV", f"{posi}.parameterV")

        fbf = cmds.createNode("fourByFourMatrix", name=f"{self.side}_clavicleFloating_FBF", ss=True)
        for row, attr in ((0, "normalizedTangentU"), (1, "normalizedTangentV"), (2, "normalizedNormal")):
            for col, axis in enumerate("XYZ"):
                cmds.connectAttr(f"{posi}.{attr}{axis}", f"{fbf}.in{row}{col}")
        for col, axis in enumerate("XYZ"):
            cmds.connectAttr(f"{posi}.position{axis}", f"{fbf}.in3{col}")

        # Rotación local del control compuesta sobre el frame de la superficie
        # (la traslación del control ya se gastó en la proyección U,V)
        pick_rot = cmds.createNode("pickMatrix", name=f"{self.side}_clavicleFloatingRot_PMX", ss=True)
        cmds.connectAttr(f"{ctl}.matrix", f"{pick_rot}.inputMatrix")
        cmds.setAttr(f"{pick_rot}.useTranslate", 0)
        cmds.setAttr(f"{pick_rot}.useScale", 0)
        cmds.setAttr(f"{pick_rot}.useShear", 0)

        floating_mmx = cmds.createNode("multMatrix", name=f"{self.side}_clavicleFloating_MMX", ss=True)
        cmds.connectAttr(f"{pick_rot}.outputMatrix", f"{floating_mmx}.matrixIn[0]")
        cmds.connectAttr(f"{fbf}.output", f"{floating_mmx}.matrixIn[1]")

        # Atributo Floating (0-1): mezcla directo <-> flotante
        cmds.addAttr(ctl, longName="FLOATING_SEP", niceName="FLOATING ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{ctl}.FLOATING_SEP", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(ctl, longName="Floating", attributeType="float", min=0, max=1, defaultValue=1, keyable=True)

        blend = cmds.createNode("blendMatrix", name=f"{self.side}_clavicleFloating_BLM", ss=True)
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{blend}.inputMatrix")
        cmds.connectAttr(f"{floating_mmx}.matrixSum", f"{blend}.target[0].targetMatrix")
        cmds.connectAttr(f"{ctl}.Floating", f"{blend}.target[0].weight")
        cmds.setAttr(f"{blend}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend}.target[0].shearWeight", 0)

        return f"{blend}.outputMatrix"