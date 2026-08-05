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

class EyebrowModule(object):

    def __init__(self):

        """
        Initialize the EyebrowModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")
        self.settings_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")
        self.face_ctl = data_manager.DataExportBiped().get_data("neck_module", "face_ctl")

    def make(self, side):

        """ 
        Create the eyebrow module structure and controllers. Call this method with the side ('L' or 'R') to create the respective eyebrow module.
        Args:
            side (str): The side of the eyebrow ('L' or 'R').

        """
        self.side = side
        self.module_name = f"C_eyebrow"
        if cmds.objExists(f"{self.module_name}Module_GRP"):
            self.module_trn = f"{self.module_name}Module_GRP"
            self.skeleton_grp = f"{self.module_name}Skinning_GRP"
            self.controllers_grp = f"{self.module_name}Controllers_GRP"
        else:
            self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
            cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)
            self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
            self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.face_ctl)
        
            cmds.addAttr(self.face_ctl, longName="Brows", attributeType="long", defaultValue=2, max=3, min=0, keyable=True)


        self.load_guides()
        self.create_controllers()
        self.curve_setup()
        self.ribbon_setup()
        self.slide_setup()
        self.auto_tangent_setup()

        data_manager.DataExportBiped().append_data("eyebrow_module",
                            {
                                f"{self.side}_main_eyebrow_ctl": self.main_eyebrow_ctl
                            })

        # Clean up
        cmds.delete(self.main_eyebrow)
        if self.side == "L":
            cmds.delete(self.mid_eyebrow)

    def local(self, ctl):

        """
        Create the local matrix network for a controller WITHOUT transforms:
        - Local_MMT: ctl.worldMatrix * GRP.worldInverseMatrix (the ctl local motion)
        - LocalGrp_MMX: replaces the old Local_GRP (baked bind matrix, or bind
          offset * parent local matrixSum after local_parent)
        - Local_MMX: replaces the old Local_TRN worldMatrix (Local_MMT * LocalGrp_MMX)
        Args:
            ctl (str): The name of the controller.
        Returns:
            tuple: (LocalGrp_MMX, Local_MMX) multMatrix nodes.
        """

        local_grp = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "LocalGrp_MMX"), ss=True)
        cmds.setAttr(f"{local_grp}.matrixIn[0]", cmds.getAttr(f"{ctl}.worldMatrix[0]"), type="matrix")
        local_trn = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMX"), ss=True)
        grp = ctl.replace("_CTL", "_GRP")
        mult_matrix = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Local_MMT"))
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{mult_matrix}.matrixIn[0]")
        cmds.connectAttr(f"{grp}.worldInverseMatrix[0]", f"{mult_matrix}.matrixIn[1]")
        cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{local_trn}.matrixIn[0]")
        cmds.connectAttr(f"{local_grp}.matrixSum", f"{local_trn}.matrixIn[1]")

        return local_grp, local_trn

    def local_parent(self, local_grp_mmx, ctl, parent_local_mmx, parent_ctl):

        """
        Equivalent of parenting the old Local_GRP under another Local_TRN, without
        transforms: bake the bind offset between both controllers and chain the
        parent local network.
        Args:
            local_grp_mmx (str): the LocalGrp_MMX of the child controller.
            ctl (str): the child controller.
            parent_local_mmx (str): the Local_MMX of the parent controller.
            parent_ctl (str): the parent controller.
        """

        offset = om.MMatrix(cmds.getAttr(f"{ctl}.worldMatrix[0]")) * om.MMatrix(cmds.getAttr(f"{parent_ctl}.worldMatrix[0]")).inverse()
        cmds.setAttr(f"{local_grp_mmx}.matrixIn[0]", list(offset), type="matrix")
        cmds.connectAttr(f"{parent_local_mmx}.matrixSum", f"{local_grp_mmx}.matrixIn[1]", force=True)

    def load_guides(self):

        cmds.select(clear=True)

        # Si existe la curva de guía {side}_eyebrow_CRV (guardada como shape), cada CV
        # -> una joint (las secciones de la ceja) y el main se coloca en el centro de
        # la curva. Si NO existe, se sigue con el método actual (guía {side}_eyebrowMain_JNT
        # con sus hijas). get_guides para una curva DEVUELVE el nombre del SHAPE (string).
        eyebrow_shape = None
        try:
            res = guides_manager.get_guides(f"{self.side}_eyebrow_CRVShape", parent=self.module_trn)
            if res and isinstance(res, str) and cmds.objExists(res):
                eyebrow_shape = res
        except Exception:
            pass

        if eyebrow_shape:
            cvs = cmds.ls(f"{eyebrow_shape}.cv[*]", flatten=True)
            self.eyebrows = []
            for i, cv in enumerate(cvs):
                pos = cmds.pointPosition(cv, world=True)
                jnt = cmds.createNode("joint", name=f"{self.side}_eyebrow{i:02d}_JNT", ss=True, p=self.module_trn)
                cmds.xform(jnt, worldSpace=True, translation=pos)
                self.eyebrows.append(jnt)

            # Orientar cada joint a lo largo de la curva: X aim al siguiente CV, Y up
            # (coherente con el ribbon: aim_axis='x', up_axis='y'). El último copia la
            # orientación del anterior.
            for i in range(len(self.eyebrows)):
                if i < len(self.eyebrows) - 1:
                    ac = cmds.aimConstraint(self.eyebrows[i + 1], self.eyebrows[i],
                                            aimVector=(1, 0, 0), upVector=(0, 1, 0),
                                            worldUpType="vector", worldUpVector=(0, 1, 0))
                    cmds.delete(ac)
                elif len(self.eyebrows) > 1:
                    cmds.matchTransform(self.eyebrows[i], self.eyebrows[i - 1], rotation=True, position=False, scale=False)

            # Con la curva no hay guía main: el main se coloca en el centro de la curva,
            # con la orientación de la sección central.
            mid_jnt = self.eyebrows[len(self.eyebrows) // 2]
            mid_pos = cmds.xform(mid_jnt, q=True, ws=True, t=True)
            self.main_eyebrow = cmds.createNode("joint", name=f"{self.side}_eyebrowMain_JNT", ss=True, p=self.module_trn)
            cmds.xform(self.main_eyebrow, worldSpace=True, translation=mid_pos)
            cmds.matchTransform(self.main_eyebrow, mid_jnt, rotation=True, position=False, scale=False)

            crv_tf = cmds.listRelatives(eyebrow_shape, parent=True, fullPath=True)
            cmds.delete(crv_tf[0] if crv_tf else eyebrow_shape)
        else:
            eyebrows = guides_manager.get_guides(f"{self.side}_eyebrowMain_JNT")
            cmds.parent(eyebrows[0], self.module_trn)
            self.main_eyebrow = eyebrows[0]
            self.eyebrows = sorted(eyebrows[1:])
            for jnt in self.eyebrows:
                cmds.parent(jnt, self.module_trn)

        cmds.select(clear=True)

        if self.side == "L":
            self.mid_eyebrow = guides_manager.get_guides("C_eyebrowMid_JNT")[0]
            cmds.parent(self.mid_eyebrow, self.module_trn)

            

    def create_controllers(self):

        """
        Create controllers for the eyebrow module.
        """
        self.eyebrow_controllers = []
        self.eyebrow_nodes = []
        self.local_trns = []
        self.local_grps = []

        if self.side == "L":

            self.sphere = guides_manager.get_guides("C_eyebrowSlide_NURBShape", parent=self.module_trn)
            cmds.parent(self.sphere, self.module_trn)
        
        self.sphere = cmds.ls("C_eyebrowSlide_NURB", long=True)[0]
        cmds.hide(self.sphere)

        condition_primary = cmds.createNode("condition", name="C_eyebrowPrimary_COND", ss=True)
        cmds.setAttr(f"{condition_primary}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_primary}.secondTerm", 1)
        cmds.setAttr(f"{condition_primary}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_primary}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Brows", f"{condition_primary}.firstTerm") 
            
        self.main_eyebrow_nodes, self.main_eyebrow_ctl = curve_tool.create_controller(f"{self.side}_eyebrowMain", offset=["GRP", "OFF"])
        cmds.matchTransform(self.main_eyebrow_nodes[0], self.main_eyebrow)
        cmds.connectAttr(f"{condition_primary}.outColorR", f"{self.main_eyebrow_nodes[0]}.visibility") # Connect visibility
        
        cmds.parent(self.main_eyebrow_nodes[0], self.controllers_grp)
        curve_tool.lock_attributes(self.main_eyebrow_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])
        main_local_grp, main_local_trn = self.local(self.main_eyebrow_ctl)

        if self.side == "L":
            mid_eyebrow_nodes, mid_eyebrow_ctl = curve_tool.create_controller("C_eyebrowMid", offset=["GRP", "OFF"])

            cmds.connectAttr(f"{condition_primary}.outColorR", f"{mid_eyebrow_nodes[0]}.visibility") # Connect visibility

            cmds.parent(mid_eyebrow_nodes[0], self.controllers_grp)
            curve_tool.lock_attributes(mid_eyebrow_ctl, ["scaleX", "scaleY", "scaleZ", "visibility"])

            mid_local_grp, mid_local_trn = self.local(mid_eyebrow_ctl)
            mid_eyebrow_guide = cmds.createNode("transform", name="C_eyebrowMid_GUIDE", ss=True, p=self.module_trn)
            cmds.matchTransform(mid_eyebrow_guide, self.mid_eyebrow)
            jnt = cmds.createNode("joint", name="C_eyebrowMidSkinning_JNT", ss=True, p=self.skeleton_grp)
            cmds.connectAttr(f"{mid_local_trn}.matrixSum", f"{jnt}.offsetParentMatrix")

            # Set up mid eyebrow parentMatrix
            fbf_mid = cmds.createNode("fourByFourMatrix", name="C_eyebrowMid_FBF", ss=True)
            cmds.setAttr(f"{fbf_mid}.in30", cmds.getAttr(f"{mid_eyebrow_guide}.translateX"))
            cmds.setAttr(f"{fbf_mid}.in31", cmds.getAttr(f"{mid_eyebrow_guide}.translateY"))
            cmds.setAttr(f"{fbf_mid}.in32", cmds.getAttr(f"{mid_eyebrow_guide}.translateZ"))
            
            
            parent_matrix = cmds.createNode("parentMatrix", name="C_eyebrowMid_PM", ss=True)
            cmds.connectAttr(f"{fbf_mid}.output", f"{parent_matrix}.inputMatrix")
            cmds.connectAttr(f"{main_local_trn}.matrixSum", f"{parent_matrix}.target[0].targetMatrix")

            mult_matrix = cmds.createNode("multMatrix", name="C_eyebrowMid_MMX", ss=True)
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{mult_matrix}.matrixIn[0]")
            cmds.setAttr(f"{mult_matrix}.matrixIn[1]", cmds.getAttr(f"{self.head_ctl}.worldInverseMatrix[0]"), type="matrix")
            cmds.connectAttr(f"{mult_matrix}.matrixSum", f"{mid_eyebrow_nodes[0]}.offsetParentMatrix")
            # The old mid Local_GRP took the parentMatrix output as its whole world
            cmds.setAttr(f"{mid_local_grp}.matrixIn[0]", list(om.MMatrix.kIdentity), type="matrix")
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{mid_local_grp}.matrixIn[1]")
            cmds.setAttr(f"{parent_matrix}.envelope", 0.5)

            cmds.xform(mid_eyebrow_nodes[0], m=om.MMatrix.kIdentity)

        else:
            parent_matrix = "C_eyebrowMid_PM"
            mid_eyebrow_nodes = "C_eyebrowMid_GRP" # Dummy for get_offset_matrix
            mid_eyebrow_guide = "C_eyebrowMid_GUIDE" # Dummy for get_offset_matrix
            cmds.connectAttr(f"{main_local_trn}.matrixSum", f"{parent_matrix}.target[1].targetMatrix")

        if self.side == "L":
            cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", *matrix_manager.get_offset_matrix(mid_eyebrow_guide, f"{main_local_trn}.matrixSum"), type="matrix")
        else:
            cmds.setAttr(f"{parent_matrix}.target[1].offsetMatrix", *matrix_manager.get_offset_matrix(mid_eyebrow_guide, f"{main_local_trn}.matrixSum"), type="matrix")
            cmds.delete(mid_eyebrow_guide)

        # Tangentes proporcionales al número de guías: InTan/OutTan caen al cuarto
        # y tres cuartos del recorrido en vez de pegadas al vecino de In/Out. Con
        # 5 guías coincide con el comportamiento anterior (índices 1 y -2).
        n = len(self.eyebrows)
        in_tan = max(1, round((n - 1) * 0.25))
        out_tan = min(n - 2, round((n - 1) * 0.75))
        names = {"In": 0, "InTan": in_tan, "Mid": n // 2, "OutTan": out_tan, "Out": n - 1}

        for name, value in names.items():

            eyebrow_nodes, eyebrow_ctl = curve_tool.create_controller(f"{self.side}_eyebrow{name}", offset=["GRP", "OFF"])
            cmds.matchTransform(eyebrow_nodes[0], self.eyebrows[value], pos=True, rot=True)
            cmds.parent(eyebrow_nodes[0], self.main_eyebrow_ctl)
            curve_tool.lock_attributes(eyebrow_ctl, ["visibility"])

            local_grp, local_trn = self.local(eyebrow_ctl)
            self.local_parent(local_grp, eyebrow_ctl, main_local_trn, self.main_eyebrow_ctl)
            self.eyebrow_controllers.append(eyebrow_ctl)
            self.eyebrow_nodes.append(eyebrow_nodes)
            self.local_trns.append(local_trn)
            self.local_grps.append(local_grp)

        cmds.parent(self.eyebrow_nodes[-2], self.eyebrow_controllers[-1]) # OutTan to Out
        cmds.parent(self.eyebrow_nodes[1], self.eyebrow_controllers[0]) # InTan to In
        self.local_parent(self.local_grps[-2], self.eyebrow_controllers[-2], self.local_trns[-1], self.eyebrow_controllers[-1]) # OutTan to Out
        self.local_parent(self.local_grps[1], self.eyebrow_controllers[1], self.local_trns[0], self.eyebrow_controllers[0]) # InTan to In

        condition_secondary = cmds.createNode("condition", name="C_eyebrowSecondary_COND", ss=True)
        cmds.setAttr(f"{condition_secondary}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_secondary}.secondTerm", 2)
        cmds.setAttr(f"{condition_secondary}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_secondary}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Brows", f"{condition_secondary}.firstTerm")
        cmds.connectAttr(f"{condition_secondary}.outColorR", f"{self.eyebrow_nodes[1][0]}.visibility") # InTan visibility
        cmds.connectAttr(f"{condition_secondary}.outColorR", f"{self.eyebrow_nodes[-2][0]}.visibility") # OutTan visibility


    def auto_tangent_setup(self):
        """
        Keeps InTan and OutTan on the straight line between In and Out when displaced in Y.
        Adds autoTangent attr (0=manual, 1=auto) to main_eyebrow_ctl.
        """
        
        cmds.addAttr(self.main_eyebrow_ctl,
                     longName="autoTangent",
                     attributeType="float",
                     min=0, max=1,
                     defaultValue=1,
                     keyable=True)

        in_local_trn  = self.local_trns[0]
        out_local_trn = self.local_trns[-1]

        # Shared translation-row nodes for In and Out world Y (row 3 = translation)
        rfm_in = cmds.createNode("rowFromMatrix",
                                  name=f"{self.side}_eyebrowAutoTanIn_RFM", ss=True)
        rfm_out = cmds.createNode("rowFromMatrix",
                                   name=f"{self.side}_eyebrowAutoTanOut_RFM", ss=True)
        cmds.setAttr(f"{rfm_in}.input", 3)
        cmds.setAttr(f"{rfm_out}.input", 3)
        cmds.connectAttr(f"{in_local_trn}.matrixSum",  f"{rfm_in}.matrix")
        cmds.connectAttr(f"{out_local_trn}.matrixSum", f"{rfm_out}.matrix")

        # Project each tangent onto the In-Out line to get its t parameter
        in_pos  = om.MVector(cmds.xform(self.eyebrow_controllers[0],  q=True, ws=True, t=True))
        out_pos = om.MVector(cmds.xform(self.eyebrow_controllers[-1], q=True, ws=True, t=True))
        line        = out_pos - in_pos
        line_len_sq = line * line

        for idx, name in [(1, "InTan"), (-2, "OutTan")]:
            local_trn = self.local_trns[idx]
            local_grp = self.local_grps[idx]

            tan_pos = om.MVector(cmds.xform(self.eyebrow_controllers[idx], q=True, ws=True, t=True))
            if line_len_sq > 0.0001:
                t_val = float(((tan_pos - in_pos) * line) / line_len_sq)
            else:
                t_val = 0.333 if idx == 1 else 0.667

            # Target world Y = In.Y*(1-t) + Out.Y*t
            mul_in_t = cmds.createNode("multiply",
                                       name=f"{self.side}_eyebrow{name}AutoTanInT_MUL", ss=True)
            mul_out_t = cmds.createNode("multiply",
                                        name=f"{self.side}_eyebrow{name}AutoTanOutT_MUL", ss=True)
            cmds.connectAttr(f"{rfm_in}.outputY",  f"{mul_in_t}.input[0]")
            cmds.setAttr(f"{mul_in_t}.input[1]",  1.0 - t_val)
            cmds.connectAttr(f"{rfm_out}.outputY", f"{mul_out_t}.input[0]")
            cmds.setAttr(f"{mul_out_t}.input[1]", t_val)

            pma_world_y = cmds.createNode("plusMinusAverage",
                                           name=f"{self.side}_eyebrow{name}AutoTanWorldY_PMA", ss=True)
            cmds.setAttr(f"{pma_world_y}.operation", 1)  # Add
            cmds.connectAttr(f"{mul_in_t}.output",  f"{pma_world_y}.input1D[0]")
            cmds.connectAttr(f"{mul_out_t}.output", f"{pma_world_y}.input1D[1]")

            # Auto local Y (in GRP space) = target_world_Y - GRP_world_Y
            rfm_grp = cmds.createNode("rowFromMatrix",
                                       name=f"{self.side}_eyebrow{name}AutoTanGRP_RFM", ss=True)
            cmds.setAttr(f"{rfm_grp}.input", 3)  # translation row
            cmds.connectAttr(f"{local_grp}.matrixSum", f"{rfm_grp}.matrix")

            pma_local_y = cmds.createNode("plusMinusAverage",
                                           name=f"{self.side}_eyebrow{name}AutoTanLocalY_PMA", ss=True)
            cmds.setAttr(f"{pma_local_y}.operation", 2)  # Subtract
            cmds.connectAttr(f"{pma_world_y}.output1D",       f"{pma_local_y}.input1D[0]")
            cmds.connectAttr(f"{rfm_grp}.outputY",            f"{pma_local_y}.input1D[1]")

            # Manual Y: CTL offset from its GRP (already driving local_trn.offsetParentMatrix)
            mmt_name = self.eyebrow_controllers[idx].replace("_CTL", "Local_MMT")
            rfm_curr_t = cmds.createNode("rowFromMatrix",
                                          name=f"{self.side}_eyebrow{name}AutoTanManual_RFM", ss=True)
            cmds.setAttr(f"{rfm_curr_t}.input", 3)  # translation row
            cmds.connectAttr(f"{mmt_name}.matrixSum", f"{rfm_curr_t}.matrix")

            # Auto ADITIVO: en auto la Y del control se SUMA al seguimiento de la
            # línea In-Out, no se sustituye — si no, con autoTangent=1 (default)
            # el ty del tangente quedaba muerto y parecía un control roto.
            pma_auto_sum = cmds.createNode("plusMinusAverage",
                                            name=f"{self.side}_eyebrow{name}AutoTanSum_PMA", ss=True)
            cmds.setAttr(f"{pma_auto_sum}.operation", 1)  # Add
            cmds.connectAttr(f"{pma_local_y}.output1D", f"{pma_auto_sum}.input1D[0]")
            cmds.connectAttr(f"{rfm_curr_t}.outputY",   f"{pma_auto_sum}.input1D[1]")

            # Blend: attributesBlender=0 -> manual puro, =1 -> línea + offset manual
            bta = cmds.createNode("blendTwoAttr",
                                   name=f"{self.side}_eyebrow{name}AutoTan_BTA", ss=True)
            cmds.connectAttr(f"{self.main_eyebrow_ctl}.autoTangent", f"{bta}.attributesBlender")
            cmds.connectAttr(f"{rfm_curr_t}.outputY",                 f"{bta}.input[0]")
            cmds.connectAttr(f"{pma_auto_sum}.output1D",              f"{bta}.input[1]")

            # Recompose with rowFromMatrix + fourByFourMatrix (no decompose/compose):
            # rows 0-2 keep rotation/scale from the CTL, row 3 keeps X/Z and takes
            # the blended Y
            fbf = cmds.createNode("fourByFourMatrix",
                                   name=f"{self.side}_eyebrow{name}AutoTan_FBF", ss=True)
            for row_index in range(3):
                rfm_row = cmds.createNode("rowFromMatrix",
                                           name=f"{self.side}_eyebrow{name}AutoTan0{row_index}_RFM", ss=True)
                cmds.setAttr(f"{rfm_row}.input", row_index)
                cmds.connectAttr(f"{mmt_name}.matrixSum", f"{rfm_row}.matrix")
                for col_index, axis in enumerate("XYZ"):
                    cmds.connectAttr(f"{rfm_row}.output{axis}", f"{fbf}.in{row_index}{col_index}")
            cmds.connectAttr(f"{rfm_curr_t}.outputX", f"{fbf}.in30")
            cmds.connectAttr(f"{bta}.output",         f"{fbf}.in31")
            cmds.connectAttr(f"{rfm_curr_t}.outputZ", f"{fbf}.in32")

            cmds.connectAttr(f"{fbf}.output", f"{local_trn}.matrixIn[0]", force=True)

    def curve_setup(self):

        """
        Asymmetric brow curve when the main control is raised (no set driven keys).

        Imitates the kessi brow behaviour: lifting the main eyebrow control bends
        the brow into an arch because the controllers closer to the ear "lag
        behind" the lift, while lowering keeps a straight line.

        Mechanism (same spirit as kessi's per-section setRange + sum, here solved
        with matrices): only the POSITIVE part of the main control translateY is
        taken (a clamp -> down keeps the strip straight). That up amount, scaled
        by the 'browCurve' attribute and by a per-controller weight that grows
        toward the ear, is subtracted in Y from every sub-controller before the
        ribbon reads it. Inner controllers barely lag (weight ~0), the outer ear
        controller lags the most (weight 1) -> arch on the way up, straight on the
        way down.

        Each sub-controller matrix that feeds the ribbon becomes:
            curve = local_trn * translate(0, -weight * upAmount * browCurve, 0)
        Post-multiplying by the translation adds a pure +Y in the ribbon (head
        local) space, leaving rotation/scale untouched.
        """
        cmds.addAttr(self.main_eyebrow_ctl,
                     longName="EXTRA_ATTRIBUTES",
                     niceName="EXTRA_ATTRIBUTES ------",
                     attributeType="enum",
                     enumName="------")
        cmds.setAttr(f"{self.main_eyebrow_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(self.main_eyebrow_ctl, longName="browCurve", attributeType="float",
                     min=0, max=2, defaultValue=0.7, keyable=True)

        up_clamp = cmds.createNode("clamp", name=f"{self.side}_eyebrowCurveUp_CLAMP", ss=True)
        cmds.setAttr(f"{up_clamp}.minR", 0)
        cmds.setAttr(f"{up_clamp}.maxR", 100000)
        cmds.connectAttr(f"{self.main_eyebrow_ctl}.translateY", f"{up_clamp}.inputR")

        num = len(self.local_trns)
        self.curve_trns = []

        for i, local_trn in enumerate(self.local_trns):

            t = i / (num - 1) if num > 1 else 0.0
            weight = t * t

            ctl = self.eyebrow_controllers[i]

            if weight == 0.0:
                self.curve_trns.append(local_trn)
                continue

            mult = cmds.createNode("multiply", name=ctl.replace("_CTL", "Curve_MUL"), ss=True)
            cmds.connectAttr(f"{up_clamp}.outputR", f"{mult}.input[0]")
            cmds.connectAttr(f"{self.main_eyebrow_ctl}.browCurve", f"{mult}.input[1]")
            cmds.setAttr(f"{mult}.input[2]", -weight)
            fbf = cmds.createNode("fourByFourMatrix", name=ctl.replace("_CTL", "Curve_FBF"), ss=True)
            cmds.connectAttr(f"{mult}.output", f"{fbf}.in31")
            curve_mmx = cmds.createNode("multMatrix", name=ctl.replace("_CTL", "Curve_MMX"), ss=True)
            cmds.connectAttr(f"{local_trn}.matrixSum", f"{curve_mmx}.matrixIn[0]")
            cmds.connectAttr(f"{fbf}.output", f"{curve_mmx}.matrixIn[1]")

            self.curve_trns.append(curve_mmx)

    def ribbon_setup(self):

        """
        Set up ribbon system for the eyebrow module.
        """

        sel = [trn for trn in self.curve_trns]

        self.output_joints, temp = ribbon.de_boor_ribbon(sel, name=f"{self.side}_eyebrowSkinning", aim_axis='x', up_axis='y', num_joints=len(self.eyebrows), skeleton_grp=self.skeleton_grp)

        for t in temp:
            cmds.delete(t)


    def slide_setup(self):

        """
        Set up the slide functionality for the eyebrow module.

        """
        
        cmds.addAttr(self.main_eyebrow_ctl, longName="slide", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)


        for i, jnt in enumerate(self.output_joints):

            closest_point = cmds.createNode("closestPointOnSurface", name=jnt.replace("_JNT", "Slide_CPOS"), ss=True)
            row_from_matrix_projection = cmds.createNode("rowFromMatrix", name=jnt.replace("_JNT", "Slide_RFM"), ss=True)
            cmds.setAttr(f"{row_from_matrix_projection}.input", 3) # Getting the translation row
            parent_matrix = cmds.createNode("parentMatrix", name=jnt.replace("_JNT", "Slide_PM"), ss=True)
            jnt_input = cmds.listConnections(jnt, source=True, destination=True, plugs=True)[0] # Getting the input matrix of the joint

            cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{closest_point}.inputSurface") # Sphere world matrix to CPOS
            cmds.connectAttr(jnt_input, f"{row_from_matrix_projection}.matrix") # Joint input matrix to RFM
            cmds.connectAttr(f"{row_from_matrix_projection}.outputX", f"{closest_point}.inPositionX")
            cmds.connectAttr(f"{row_from_matrix_projection}.outputY", f"{closest_point}.inPositionY")
            cmds.connectAttr(f"{row_from_matrix_projection}.outputZ", f"{closest_point}.inPositionZ")

            # Rebuild the slid matrix with rowFromMatrix + fourByFourMatrix (no
            # decompose/compose): rows 0-2 keep the joint rotation/scale, row 3
            # takes the CPOS projected position
            four_by_four = cmds.createNode("fourByFourMatrix", name=jnt.replace("_JNT", "Slide_FBF"), ss=True)
            for row_index in range(3):
                rfm_row = cmds.createNode("rowFromMatrix", name=jnt.replace("_JNT", f"Slide0{row_index}_RFM"), ss=True)
                cmds.setAttr(f"{rfm_row}.input", row_index)
                cmds.connectAttr(jnt_input, f"{rfm_row}.matrix")
                for col_index, axis in enumerate("XYZ"):
                    cmds.connectAttr(f"{rfm_row}.output{axis}", f"{four_by_four}.in{row_index}{col_index}")
            for col_index, axis in enumerate("XYZ"):
                cmds.connectAttr(f"{closest_point}.position{axis}", f"{four_by_four}.in3{col_index}")

            cmds.connectAttr(jnt_input, f"{parent_matrix}.target[0].targetMatrix")
            cmds.connectAttr(f"{four_by_four}.output", f"{parent_matrix}.inputMatrix")
            reverse_slide = cmds.createNode("reverse", name=jnt.replace("_JNT", "Slide_Reverse"), ss=True)
            cmds.connectAttr(f"{self.main_eyebrow_ctl}.slide", f"{reverse_slide}.inputX")
            cmds.connectAttr(f"{reverse_slide}.outputX", f"{parent_matrix}.target[0].weight")
            cmds.connectAttr(f"{parent_matrix}.outputMatrix", f"{jnt}.offsetParentMatrix", force=True)
            cmds.setAttr(f"{parent_matrix}.target[0].offsetMatrix", matrix_manager.get_offset_matrix(f"{four_by_four}.output", jnt_input), type="matrix")

        for jnt in self.eyebrows:
            cmds.delete(jnt)

            
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


            

