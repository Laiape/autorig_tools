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

class JawModule(object):

    def __init__(self):

        """
        Initialize the jawModule class, setting up the necessary groups and controllers.
        """
        
        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")
        self.settings_ctl = data_manager.DataExportBiped().get_data("basic_structure", "preferences_ctl")
        self.face_ctl = data_manager.DataExportBiped().get_data("neck_module", "face_ctl")
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")

    
    def make(self, side):

        """ 
        Create the jaw module structure and controllers. Call this method with the side ('L' or 'R') to create the respective jaw module.
        Args:
            side (str): The side of the jaw ('L' or 'R').

        """
        self.side = side
        self.module_name = f"C_jaw"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.masterwalk_ctl)

        cmds.addAttr(self.face_ctl, longName="Jaw", attributeType="long", defaultValue=1, max=2, min=0, keyable=True)
        cmds.addAttr(self.face_ctl, longName="Lips", attributeType="long", defaultValue=2, max=3, min=0, keyable=True)

        self.load_guides()
        self.create_controllers()
        self.collision_setup()
        self.create_lips_setup()

        cmds.parent(self.controllers_grp, self.face_ctl)

        # Clean up
        # cmds.delete("L_jaw_JNT", "R_jaw_JNT")

        data_manager.DataExportBiped().append_data("jaw_module", 
                                                
                                                {"jaw_ctl": self.jaw_ctl,
                                                 "upper_jaw_ctl": self.upper_jaw_ctl,
                                                 "local_jaw_mmx" : self.mult_matrix_jaw_local,
                                                 "local_upper_jaw_mmx" : self.mult_matrix_upper_jaw_local
                                                })
        
        cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)

    def lock_attributes(self, ctl, attrs):

        """
        Lock and hide attributes on a controller.
        Args:
            ctl (str): The name of the controller.
            attrs (list): A list of attributes to lock and hide.
        """
        
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)

    
    def load_guides(self):

        """
        Load the guide positions for the jaw module.
        Returns:
            dict: A dictionary containing the guide positions.
        """

        self.jaw_guides = guides_manager.get_guides("C_jaw_JNT") # Jaw father, l_jaw_JNT, r_jaw_JNT and c_chin_JNT

        for guide in self.jaw_guides:
            cmds.parent(guide, self.module_trn)
        
        self.jaw_jnt = self.jaw_guides[0]
    def create_controllers(self):
        
        """
        Create the controllers for the jaw module.  
        """

        # ---- Jaw controller ----
        # Matriz horneada (solo posición) de la guía del jaw, sin transform _GUIDE vivo
        jaw_pos = cmds.xform(self.jaw_guides[0], q=True, ws=True, t=True)
        self.jaw_guide_matrix = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, jaw_pos[0], jaw_pos[1], jaw_pos[2], 1]

        self.jaw_nodes, self.jaw_ctl = curve_tool.create_controller("C_jaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        jaw_skinning = cmds.createNode("joint", name="C_jawSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.setAttr(f"{self.jaw_nodes[0]}.offsetParentMatrix", self.jaw_guide_matrix, type="matrix")
        self.lock_attributes(self.jaw_ctl, ["sx", "sy", "sz", "v"])

        mult_matrix_jaw = cmds.createNode("multMatrix", name="C_jawSkinning_MMX")
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{mult_matrix_jaw}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_jaw}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_jaw}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_jaw}.matrixSum", f"{jaw_skinning}.offsetParentMatrix")

        # ---- Upper jaw controller ----
        self.upper_jaw_nodes, self.upper_jaw_ctl = curve_tool.create_controller("C_upperJaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.setAttr(f"{self.upper_jaw_nodes[0]}.offsetParentMatrix", self.jaw_guide_matrix, type="matrix")
        self.lock_attributes(self.upper_jaw_ctl, ["sx", "sy", "sz", "v"])

        upper_jaw_skinning = cmds.createNode("joint", name="C_upperJawSkinning_JNT", ss=True, p=self.skeleton_grp)

        mult_matrix_upper_jaw = cmds.createNode("multMatrix", name="C_upperJawLocal_MMX")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{mult_matrix_upper_jaw}.matrixIn[0]")
        cmds.connectAttr(f"{self.upper_jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_upper_jaw}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.upper_jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_upper_jaw}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_upper_jaw}.matrixSum", f"{upper_jaw_skinning}.offsetParentMatrix")



    def collision_setup(self):

        """
        Set up collision detection for the jaw module.
        """

        # Add attribute to the jaw controller
        cmds.addAttr(self.jaw_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
        cmds.setAttr(f"{self.jaw_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(self.jaw_ctl, longName="Auto_Collision", attributeType="float", min=0, max=1, defaultValue=1, keyable=True)

        # Create nodes for collision detection
        sum_matrix_jaw = cmds.createNode("sum", name=f"{self.module_name}_collisionJaw_SMM")
        cmds.connectAttr(f"{self.jaw_ctl}.rotateX", f"{sum_matrix_jaw}.input[0]")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.rotateX", f"{sum_matrix_jaw}.input[1]")


        clamp_jaw = cmds.createNode("clamp", name=f"{self.module_name}_collisionJaw_CLP")
        cmds.setAttr(f"{clamp_jaw}.minR", -360)
        cmds.connectAttr(f"{sum_matrix_jaw}.output", f"{clamp_jaw}.inputR")

        float_constant_0 = cmds.createNode("floatConstant", name=f"{self.module_name}_collisionJaw_FC0")
        cmds.setAttr(f"{float_constant_0}.inFloat", 0)

        attribute_blender = cmds.createNode("blendTwoAttr", name=f"{self.module_name}_collisionJaw_BTA")
        cmds.connectAttr(f"{self.jaw_ctl}.Auto_Collision", f"{attribute_blender}.attributesBlender")
        cmds.connectAttr(f"{float_constant_0}.outFloat", f"{attribute_blender}.input[0]")
        cmds.connectAttr(f"{clamp_jaw}.outputR", f"{attribute_blender}.input[1]")
        self.compose_matrix_jaw = cmds.createNode("composeMatrix", name=f"{self.module_name}_collisionJaw_CMP")
        cmds.connectAttr(f"{attribute_blender}.output", f"{self.compose_matrix_jaw}.inputRotateX")
        cmds.connectAttr(f"{self.compose_matrix_jaw}.outputMatrix", f"{self.upper_jaw_ctl}.offsetParentMatrix")  # Connect the output of the blendTwoAttr to the rotateX of the upper jaw controller


    def _skin_lip_curve_to_locals(self, skin_cluster, curve, local_jnts):

        """
        Reparte cada CV del rebuild curve entre los 3 joints locales (2 esquinas +
        medio) según su posición a lo largo de la curva: blend lineal
        esquina_inicio -> medio -> esquina_fin. Asignación GEOMÉTRICA (no por
        índice): el medio es el joint más cercano al CV central y las esquinas se
        asignan a inicio/fin por cercanía a los CVs extremos. Vale para cualquier
        número de CVs (resolución escalable con los spans de la guía).
        """
        def jpos(j):
            return cmds.xform(j, q=True, ws=True, translation=True)

        def dist(a, b):
            return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5

        cvs = cmds.ls(f"{curve}.cv[*]", flatten=True)
        n = len(cvs)
        start_p = cmds.pointPosition(cvs[0], world=True)
        mid_p = cmds.pointPosition(cvs[n // 2], world=True)

        mid_jnt = min(local_jnts, key=lambda j: dist(jpos(j), mid_p))
        corners = [j for j in local_jnts if j != mid_jnt]
        start_corner = min(corners, key=lambda j: dist(jpos(j), start_p))
        end_corner = corners[1] if corners[0] == start_corner else corners[0]

        for i, cv in enumerate(cvs):
            t = i / (n - 1) if n > 1 else 0.0
            if t <= 0.5:
                w = t / 0.5  # 0 en la esquina de inicio, 1 en el medio
                vals = [(start_corner, 1.0 - w), (mid_jnt, w)]
            else:
                w = (t - 0.5) / 0.5  # 0 en el medio, 1 en la esquina de fin
                vals = [(mid_jnt, 1.0 - w), (end_corner, w)]
            cmds.skinPercent(skin_cluster, cv, transformValue=vals)

    def _ribbon_from_curve(self, curve, width, name, lock_axis=(0.0, 1.0, 0.0)):

        """
        Cinta NURBS estable que sigue la curva SIN twist (portado del core del
        módulo de referencia). El binormal sale de `tangente × up_bloqueado` (con
        fallback si son casi paralelos), así no se retuerce en curvas 3D. La curva
        queda en el CENTRO de la cinta (V=0.5) → las joints pineadas a V=0.5 caen
        sobre el labio. Normal de la superficie ≈ eje del lock_axis (Y), que es lo
        que esperan los uvPin (normalAxis=Y). Construye los CVs en el reposo.
        """
        sel = om.MSelectionList()
        sel.add(curve)
        crv_path = sel.getDagPath(0)
        crv_path.extendToShape()
        fn_crv = om.MFnNurbsCurve(crv_path)

        cvs = fn_crv.cvPositions(om.MSpace.kWorld)
        knots_u = fn_crv.knots()
        degree_u = fn_crv.degree
        form_u = fn_crv.form
        n = len(cvs)
        half = width * 0.5
        up = om.MVector(*lock_axis).normalize()

        pts = om.MPointArray()
        for i in range(n):
            p = cvs[i]
            pv = om.MVector(p)
            if i == 0:
                tangent = om.MVector(cvs[1]) - pv
            elif i == n - 1:
                tangent = pv - om.MVector(cvs[n - 2])
            else:
                tangent = (pv - om.MVector(cvs[i - 1])) + (om.MVector(cvs[i + 1]) - pv)
            tangent.normalize()

            cur_up = up
            if abs(tangent * cur_up) > 0.95:
                cur_up = om.MVector(0, 0, 1)
                if abs(tangent * cur_up) > 0.95:
                    cur_up = om.MVector(1, 0, 0)
            binormal = (tangent ^ cur_up).normalize()

            left = pv + binormal * half
            right = pv - binormal * half
            pts.append(om.MPoint(left.x, left.y, left.z, p.w))
            pts.append(p)
            pts.append(om.MPoint(right.x, right.y, right.z, p.w))

        knots_v = om.MDoubleArray([0.0, 0.0, 1.0, 1.0])
        fn_surf = om.MFnNurbsSurface()
        tf = fn_surf.create(
            pts, knots_u, knots_v, degree_u, 2,
            form_u, om.MFnNurbsSurface.kOpen, True, om.MObject.kNullObj
        )
        final = cmds.rename(om.MFnDagNode(tf).fullPathName(), name)
        cmds.sets(final, edit=True, forceElement="initialShadingGroup")
        return final

    def create_lips_setup(self):

        """
        Create lip curves for the jaw module.
        """
        
             
        # Load guides
        self.upper_linear_lip_curve = guides_manager.get_guides("C_upperLipLinear_CRVShape", parent=self.module_trn)
        self.lower_linear_lip_curve = guides_manager.get_guides("C_lowerLipLinear_CRVShape", parent=self.module_trn)
    
        # Create NURBS surface
        self.sphere = guides_manager.get_guides("C_jaw_NURBShape", parent=self.module_trn) # NURBS surface guide
        cmds.hide(self.sphere)
        cmds.parent(self.sphere, self.module_trn)

        # Create a bbox
        bbox = cmds.exactWorldBoundingBox(self.sphere)
        
        center = [
            (bbox[0] + bbox[3]) / 2,
            (bbox[1] + bbox[4]) / 2,
            (bbox[2] + bbox[5]) / 2
        ]
        
        bbox_loc = cmds.spaceLocator(name="C_bboxCenterMouth_LOC")[0]
        cmds.xform(bbox_loc, worldSpace=True, translation=center)
        cmds.parent(bbox_loc, self.module_trn)

        # Jaw local joint
        cmds.delete(self.jaw_jnt)
        self.jaw_jnt = cmds.createNode("joint", name="C_jaw_JNT", ss=True, p=self.module_trn)
        self.mult_matrix_jaw_local = cmds.createNode("multMatrix", name="C_jawLocal_MMT")
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{self.mult_matrix_jaw_local}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_nodes[0]}.worldInverseMatrix[0]", f"{self.mult_matrix_jaw_local}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{self.mult_matrix_jaw_local}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{self.mult_matrix_jaw_local}.matrixSum", f"{self.jaw_jnt}.offsetParentMatrix")


        # Upper jaw local joint
        self.upper_jaw_jnt = cmds.createNode("joint", name="C_upperJaw_JNT", ss=True, p=self.module_trn)
        self.mult_matrix_upper_jaw_local = cmds.createNode("multMatrix", name="C_upperJawLocal_MMT")
        cmds.connectAttr(f"{self.upper_jaw_ctl}.worldMatrix[0]", f"{self.mult_matrix_upper_jaw_local}.matrixIn[0]")
        cmds.connectAttr(f"{self.upper_jaw_nodes[0]}.worldInverseMatrix[0]", f"{self.mult_matrix_upper_jaw_local}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.upper_jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{self.mult_matrix_upper_jaw_local}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{self.mult_matrix_upper_jaw_local}.matrixSum", f"{self.upper_jaw_jnt}.offsetParentMatrix")

        
        # Create main lip controllers
        lips_controllers_grp = cmds.createNode("transform", name="C_lipsControllers_GRP", ss=True, p=self.controllers_grp)
        main_lips_controllers = cmds.createNode("transform", name="C_primaryLipsControllers_GRP", ss=True, p=lips_controllers_grp)

        # Create upper controller
        upper_lip_nodes, upper_lip_ctl = curve_tool.create_controller("C_upperLip", offset=["GRP", "OFF"], parent=main_lips_controllers)
        self.lock_attributes(upper_lip_ctl, ["v"])
        cmds.addAttr(upper_lip_ctl, longName="EXTRA_ATTRIBUTES", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{upper_lip_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(upper_lip_ctl, longName="Roll", attributeType="float", defaultValue=0, keyable=True)
        mtp_upper_lip = cmds.createNode("motionPath", name="C_upperLip_MTP", ss=True) 
        cmds.connectAttr(f"{self.upper_linear_lip_curve}.worldSpace[0]", f"{mtp_upper_lip}.geometryPath")
        cmds.setAttr(f"{mtp_upper_lip}.uValue", 0.5)
        cmds.setAttr(f"{mtp_upper_lip}.fractionMode", 1)
        fbf_upper_lip = cmds.createNode("fourByFourMatrix", name="C_upperLip_FBF", ss=True)
        cmds.connectAttr(f"{mtp_upper_lip}.allCoordinates.xCoordinate", f"{fbf_upper_lip}.in30")
        cmds.connectAttr(f"{mtp_upper_lip}.allCoordinates.yCoordinate", f"{fbf_upper_lip}.in31")
        cmds.connectAttr(f"{mtp_upper_lip}.allCoordinates.zCoordinate", f"{fbf_upper_lip}.in32") 
        upper_lip_parent_wm = cmds.createNode("parentMatrix", name="C_upperLip_PMX", ss=True)
        cmds.connectAttr(f"{fbf_upper_lip}.output", f"{upper_lip_parent_wm}.inputMatrix")
        cmds.connectAttr(f"{self.mult_matrix_upper_jaw_local}.matrixSum", f"{upper_lip_parent_wm}.target[0].targetMatrix")
        cmds.connectAttr(f"{upper_lip_parent_wm}.outputMatrix", f"{upper_lip_nodes[0]}.offsetParentMatrix")
        cmds.setAttr(f"{upper_lip_parent_wm}.target[0].offsetMatrix", self.get_offset_matrix(f"{fbf_upper_lip}.output", self.upper_jaw_ctl), type="matrix")

        # Local joint for upper lip
        upper_local_jnt = cmds.createNode("joint", name="C_upperLip_JNT", ss=True, p=self.module_trn)
        mmx_upper_local = cmds.createNode("multMatrix", name="C_upperLipLocal_MMT", ss=True)
        rfm_upper_local = cmds.createNode("rowFromMatrix", name="C_upperLipLocal_RMF", ss=True)
        cps_upper_local = cmds.createNode("closestPointOnSurface", name="C_upperLipLocal_CPS", ss=True)
        fbf_upper_lip_projected = cmds.createNode("fourByFourMatrix", name="C_upperLipProjected_FBF", ss=True)
        mmx_offset_jaw_pos_up = cmds.createNode("multMatrix", name="C_upperLipOffsetJawPos_MMT", ss=True)
        parent_matrix_upper_local = cmds.createNode("parentMatrix", name="C_upperLipLocal_PMX", ss=True)
        inverse_matrix_upper = cmds.createNode("inverseMatrix", name="C_upperLipInverse_IMT", ss=True)
        cmds.setAttr(f"{rfm_upper_local}.input", 3)  # Set rowFromMatrix to output translation

        cmds.connectAttr(f"{upper_lip_ctl}.matrix", f"{mmx_upper_local}.matrixIn[0]")
        cmds.connectAttr(f"{fbf_upper_lip}.output", f"{mmx_upper_local}.matrixIn[1]")
        cmds.connectAttr(f"{mmx_upper_local}.matrixSum", f"{rfm_upper_local}.matrix")
        cmds.connectAttr(f"{rfm_upper_local}.outputX", f"{cps_upper_local}.inPositionX")
        cmds.connectAttr(f"{rfm_upper_local}.outputY", f"{cps_upper_local}.inPositionY")
        cmds.connectAttr(f"{rfm_upper_local}.outputZ", f"{cps_upper_local}.inPositionZ")
        cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{cps_upper_local}.inputSurface")
        cmds.connectAttr(f"{cps_upper_local}.positionX", f"{fbf_upper_lip_projected}.in30")
        cmds.connectAttr(f"{cps_upper_local}.positionY", f"{fbf_upper_lip_projected}.in31")
        cmds.connectAttr(f"{cps_upper_local}.positionZ", f"{fbf_upper_lip_projected}.in32")
        cmds.connectAttr(f"{fbf_upper_lip}.output", f"{parent_matrix_upper_local}.inputMatrix")
        cmds.connectAttr(f"{self.mult_matrix_upper_jaw_local}.matrixSum", f"{parent_matrix_upper_local}.target[0].targetMatrix")
        cmds.setAttr(f"{parent_matrix_upper_local}.target[0].offsetMatrix", self.get_offset_matrix(f"{fbf_upper_lip_projected}.output", f"{self.mult_matrix_upper_jaw_local}.matrixSum"), type="matrix")
        cmds.connectAttr(f"{fbf_upper_lip}.output", f"{inverse_matrix_upper}.inputMatrix")
        cmds.connectAttr(f"{fbf_upper_lip_projected}.output", f"{mmx_offset_jaw_pos_up}.matrixIn[0]")
        cmds.connectAttr(f"{inverse_matrix_upper}.outputMatrix", f"{mmx_offset_jaw_pos_up}.matrixIn[1]")
        cmds.connectAttr(f"{parent_matrix_upper_local}.outputMatrix", f"{mmx_offset_jaw_pos_up}.matrixIn[2]")
        cmds.connectAttr(f"{mmx_offset_jaw_pos_up}.matrixSum", f"{upper_local_jnt}.offsetParentMatrix")
        # El roll del labio NO se aplica rotando el joint central (quedaba feo:
        # solo se retorcía el centro). Se aplica por joint de salida alrededor de
        # su tangente, con falloff centro->esquinas (ver loop de output joints).
        cmds.connectAttr(f"{upper_lip_ctl}.scale", f"{upper_local_jnt}.scale")

        # Create lower controller
        lower_lip_nodes, lower_lip_ctl = curve_tool.create_controller("C_lowerLip", offset=["GRP", "OFF"], parent=main_lips_controllers)
        self.lock_attributes(lower_lip_ctl, ["v"])
        cmds.addAttr(lower_lip_ctl, longName="EXTRA_ATTRIBUTES", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------")
        cmds.setAttr(f"{lower_lip_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(lower_lip_ctl, longName="Roll", attributeType="float", defaultValue=0, keyable=True)
        mtp_lower_lip = cmds.createNode("motionPath", name="C_lowerLip_MTP", ss=True) 
        cmds.connectAttr(f"{self.lower_linear_lip_curve}.worldSpace[0]", f"{mtp_lower_lip}.geometryPath")
        cmds.setAttr(f"{mtp_lower_lip}.uValue", 0.5)      
        cmds.setAttr(f"{mtp_lower_lip}.fractionMode", 1)
        fbf_lower_lip = cmds.createNode("fourByFourMatrix", name="C_lowerLip_FBF", ss=True)
        cmds.setAttr(f"{fbf_lower_lip}.in11", -1)  # Flip Y 
        cmds.connectAttr(f"{mtp_lower_lip}.allCoordinates.xCoordinate", f"{fbf_lower_lip}.in30")
        cmds.connectAttr(f"{mtp_lower_lip}.allCoordinates.yCoordinate", f"{fbf_lower_lip}.in31")
        cmds.connectAttr(f"{mtp_lower_lip}.allCoordinates.zCoordinate", f"{fbf_lower_lip}.in32")
        lower_lip_parent_wm = cmds.createNode("parentMatrix", name="C_lowerLip_PMX", ss=True)
        cmds.connectAttr(f"{fbf_lower_lip}.output", f"{lower_lip_parent_wm}.inputMatrix")
        cmds.connectAttr(f"{self.mult_matrix_jaw_local}.matrixSum", f"{lower_lip_parent_wm}.target[0].targetMatrix")
        cmds.connectAttr(f"{lower_lip_parent_wm}.outputMatrix", f"{lower_lip_nodes[0]}.offsetParentMatrix")
        cmds.setAttr(f"{lower_lip_parent_wm}.target[0].offsetMatrix", self.get_offset_matrix(f"{fbf_lower_lip}.output", self.jaw_ctl), type="matrix")

        # Local joints for lower lips
        lower_local_jnt = cmds.createNode("joint", name="C_lowerLip_JNT", ss=True, p=self.module_trn)
        mmx_lower_local = cmds.createNode("multMatrix", name="C_lowerLipLocal_MMT", ss=True)
        rfm_lower_local = cmds.createNode("rowFromMatrix", name="C_lowerLipLocal_RMF", ss=True)
        cps_lower_local = cmds.createNode("closestPointOnSurface", name="C_lowerLipLocal_CPS", ss=True)
        fbf_lower_lip_projected = cmds.createNode("fourByFourMatrix", name="C_lowerLipProjected_FBF", ss=True)
        fbf_lower_lip_pos_only = cmds.createNode("fourByFourMatrix", name="C_lowerLipPosOnly_FBF", ss=True)
        mmx_offset_jaw_pos_low = cmds.createNode("multMatrix", name="C_lowerLipOffsetJawPos_MMT", ss=True)
        parent_matrix_lower_local = cmds.createNode("parentMatrix", name="C_lowerLipLocal_PMX", ss=True)
        inverse_matrix_lower = cmds.createNode("inverseMatrix", name="C_lowerLipInverse_IMT", ss=True)
        cmds.setAttr(f"{rfm_lower_local}.input", 3)  # Set rowFromMatrix to output translation

        cmds.connectAttr(f"{mtp_lower_lip}.allCoordinates.xCoordinate", f"{fbf_lower_lip_pos_only}.in30")
        cmds.connectAttr(f"{mtp_lower_lip}.allCoordinates.yCoordinate", f"{fbf_lower_lip_pos_only}.in31")
        cmds.connectAttr(f"{mtp_lower_lip}.allCoordinates.zCoordinate", f"{fbf_lower_lip_pos_only}.in32")

        cmds.connectAttr(f"{lower_lip_ctl}.matrix", f"{mmx_lower_local}.matrixIn[0]")
        cmds.connectAttr(f"{fbf_lower_lip}.output", f"{mmx_lower_local}.matrixIn[1]")
        cmds.connectAttr(f"{mmx_lower_local}.matrixSum", f"{rfm_lower_local}.matrix")
        cmds.connectAttr(f"{rfm_lower_local}.outputX", f"{cps_lower_local}.inPositionX")
        cmds.connectAttr(f"{rfm_lower_local}.outputY", f"{cps_lower_local}.inPositionY")
        cmds.connectAttr(f"{rfm_lower_local}.outputZ", f"{cps_lower_local}.inPositionZ")
        cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{cps_lower_local}.inputSurface")
        cmds.connectAttr(f"{cps_lower_local}.positionX", f"{fbf_lower_lip_projected}.in30")
        cmds.connectAttr(f"{cps_lower_local}.positionY", f"{fbf_lower_lip_projected}.in31")
        cmds.connectAttr(f"{cps_lower_local}.positionZ", f"{fbf_lower_lip_projected}.in32")
        cmds.connectAttr(f"{fbf_lower_lip_pos_only}.output", f"{parent_matrix_lower_local}.inputMatrix")
        cmds.connectAttr(f"{self.mult_matrix_jaw_local}.matrixSum", f"{parent_matrix_lower_local}.target[0].targetMatrix")
        cmds.setAttr(f"{parent_matrix_lower_local}.target[0].offsetMatrix", self.get_offset_matrix(f"{fbf_lower_lip_projected}.output", f"{self.mult_matrix_jaw_local}.matrixSum"), type="matrix")
        cmds.connectAttr(f"{fbf_lower_lip_pos_only}.output", f"{inverse_matrix_lower}.inputMatrix")
        cmds.connectAttr(f"{fbf_lower_lip_projected}.output", f"{mmx_offset_jaw_pos_low}.matrixIn[0]")
        cmds.connectAttr(f"{inverse_matrix_lower}.outputMatrix", f"{mmx_offset_jaw_pos_low}.matrixIn[1]")
        cmds.connectAttr(f"{parent_matrix_lower_local}.outputMatrix", f"{mmx_offset_jaw_pos_low}.matrixIn[2]")
        cmds.connectAttr(f"{mmx_offset_jaw_pos_low}.matrixSum", f"{lower_local_jnt}.offsetParentMatrix")
        # Roll por joint de salida (abajo), no rotando el joint central.
        cmds.connectAttr(f"{lower_lip_ctl}.scale", f"{lower_local_jnt}.scale")
        
        

        upper_local_jnts = []
        lower_local_jnts = []

        corner_nodes_ctls = []
        corner_controllers = []

        # Create corner controllers
        for side in ["L", "R"]:
            
            # Create corner controller and place them
            aim_vector = (0, 0, -1)

            corner_nodes, corner_ctl = curve_tool.create_controller(f"{side}_lipCorner", offset=["GRP", "OFF"], parent=main_lips_controllers)
            self.lock_attributes(corner_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])
            mtp_corner_lip = cmds.createNode("motionPath", name=f"{side}_lipCorner_MTP", ss=True)
            cmds.connectAttr(f"{self.upper_linear_lip_curve}.worldSpace[0]", f"{mtp_corner_lip}.geometryPath")
            corner_nodes_ctls.append(corner_nodes[0])
            corner_controllers.append(corner_ctl)

            if side == "L":
                cmds.setAttr(f"{mtp_corner_lip}.uValue", 1)

            else:

                cmds.setAttr(f"{mtp_corner_lip}.uValue", 0)

            cmds.setAttr(f"{mtp_corner_lip}.fractionMode", 1)
            fbf_corner_lip = cmds.createNode("fourByFourMatrix", name=f"{side}_lipCorner_FBF", ss=True)
            cmds.connectAttr(f"{mtp_corner_lip}.allCoordinates.xCoordinate", f"{fbf_corner_lip}.in30")
            cmds.connectAttr(f"{mtp_corner_lip}.allCoordinates.yCoordinate", f"{fbf_corner_lip}.in31")
            cmds.connectAttr(f"{mtp_corner_lip}.allCoordinates.zCoordinate", f"{fbf_corner_lip}.in32")

            aim_matrix_corner = cmds.createNode("aimMatrix", name=f"{side}_lipCorner_AMT", ss=True)
            cmds.connectAttr(f"{fbf_corner_lip}.output", f"{aim_matrix_corner}.inputMatrix")
            cmds.connectAttr(f"{bbox_loc}.worldMatrix[0]", f"{aim_matrix_corner}.primary.primaryTargetMatrix")
            cmds.setAttr(f"{aim_matrix_corner}.primaryInputAxis", *aim_vector, type="double3")  # Aim down Z axis

            if side == "R":

                cmds.setAttr(f"{fbf_corner_lip}.in00", -1)  # Invert X axis for right corner

            # Create blending between upper and lower lips
            cmds.addAttr(corner_ctl, longName="EXTRA_ATTRIBUTES", attributeType="enum", enumName="____")
            cmds.setAttr(f"{corner_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)
            cmds.addAttr(corner_ctl, longName="Height", attributeType="float", min=0, max=1, defaultValue=0.5, keyable=True)
            cmds.addAttr(corner_ctl, longName="Zip", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

            parent_matrix_blender = cmds.createNode("parentMatrix", name=f"{side}_lipCorner_PMX", ss=True)
            cmds.connectAttr(f"{aim_matrix_corner}.outputMatrix", f"{parent_matrix_blender}.inputMatrix")
            cmds.connectAttr(f"{self.mult_matrix_jaw_local}.matrixSum", f"{parent_matrix_blender}.target[0].targetMatrix")
            cmds.connectAttr(f"{self.mult_matrix_upper_jaw_local}.matrixSum", f"{parent_matrix_blender}.target[1].targetMatrix")
            reverse_blender = cmds.createNode("reverse", name=f"{side}_lipCorner_REV", ss=True)
            cmds.connectAttr(f"{corner_ctl}.Height", f"{reverse_blender}.inputX")
            cmds.connectAttr(f"{reverse_blender}.outputX", f"{parent_matrix_blender}.target[0].weight")
            cmds.connectAttr(f"{corner_ctl}.Height", f"{parent_matrix_blender}.target[1].weight")
            cmds.connectAttr(f"{parent_matrix_blender}.outputMatrix", f"{corner_nodes[0]}.offsetParentMatrix")

            cmds.setAttr(f"{parent_matrix_blender}.target[0].offsetMatrix", self.get_offset_matrix(f"{aim_matrix_corner}.outputMatrix", f"{self.mult_matrix_jaw_local}.matrixSum"), type="matrix")
            cmds.setAttr(f"{parent_matrix_blender}.target[1].offsetMatrix", self.get_offset_matrix(f"{aim_matrix_corner}.outputMatrix", f"{self.mult_matrix_upper_jaw_local}.matrixSum"), type="matrix")
            

            local_jnt = cmds.createNode("joint", name=f"{side}_cornerLip_JNT", ss=True, p=self.module_trn)
            mmx_local = cmds.createNode("multMatrix", name=f"{side}_lowerLipLocal_MMT", ss=True)
            rfm_local = cmds.createNode("rowFromMatrix", name=f"{side}_lowerLipLocal_RMF", ss=True)
            cps_local = cmds.createNode("closestPointOnSurface", name=f"{side}_lowerLipLocal_CPS", ss=True)
            fbf_lip_projected = cmds.createNode("fourByFourMatrix", name=f"{side}_lowerLipProjected_FBF", ss=True)
            wta_local = cmds.createNode("wtAddMatrix", name=f"{side}_lowerLipLocal_WTA", ss=True)
            parent_matrix_blender_local = cmds.createNode("parentMatrix", name=f"{side}_lowerLipLocal_PMX", ss=True)
            mmx_offset_jaw_pos = cmds.createNode("multMatrix", name=f"{side}_lowerLipOffsetJawPos_MMT", ss=True)
            inverse_matrix_jaw = cmds.createNode("inverseMatrix", name=f"{side}_lowerLipInverse_IMT", ss=True)
            cmds.setAttr(f"{rfm_local}.input", 3)  # Set rowFromMatrix to output translation

            cmds.connectAttr(f"{corner_ctl}.matrix", f"{mmx_local}.matrixIn[0]")
            cmds.connectAttr(f"{aim_matrix_corner}.outputMatrix", f"{mmx_local}.matrixIn[1]")
            cmds.connectAttr(f"{mmx_local}.matrixSum", f"{rfm_local}.matrix")
            cmds.connectAttr(f"{rfm_local}.outputX", f"{cps_local}.inPositionX")
            cmds.connectAttr(f"{rfm_local}.outputY", f"{cps_local}.inPositionY")
            cmds.connectAttr(f"{rfm_local}.outputZ", f"{cps_local}.inPositionZ")
            cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{cps_local}.inputSurface")
            cmds.connectAttr(f"{cps_local}.positionX", f"{fbf_lip_projected}.in30")
            cmds.connectAttr(f"{cps_local}.positionY", f"{fbf_lip_projected}.in31")
            cmds.connectAttr(f"{cps_local}.positionZ", f"{fbf_lip_projected}.in32")
            fbf_corner_lip_pos_only = cmds.createNode("fourByFourMatrix", name=f"{side}_lipCornerPosOnly_FBF", ss=True)
            cmds.connectAttr(f"{mtp_corner_lip}.allCoordinates.xCoordinate", f"{fbf_corner_lip_pos_only}.in30")
            cmds.connectAttr(f"{mtp_corner_lip}.allCoordinates.yCoordinate", f"{fbf_corner_lip_pos_only}.in31")
            cmds.connectAttr(f"{mtp_corner_lip}.allCoordinates.zCoordinate", f"{fbf_corner_lip_pos_only}.in32")
            cmds.connectAttr(f"{self.mult_matrix_upper_jaw_local}.matrixSum", f"{wta_local}.wtMatrix[0].matrixIn")
            cmds.connectAttr(f"{corner_ctl}.Height", f"{wta_local}.wtMatrix[0].weightIn")
            cmds.connectAttr(f"{self.mult_matrix_jaw_local}.matrixSum", f"{wta_local}.wtMatrix[1].matrixIn")
            cmds.connectAttr(f"{reverse_blender}.outputX", f"{wta_local}.wtMatrix[1].weightIn")
            cmds.connectAttr(f"{fbf_corner_lip_pos_only}.output", f"{parent_matrix_blender_local}.inputMatrix")
            cmds.connectAttr(f"{wta_local}.matrixSum", f"{parent_matrix_blender_local}.target[0].targetMatrix")
            cmds.setAttr(f"{parent_matrix_blender_local}.target[0].offsetMatrix", self.get_offset_matrix(f"{fbf_lip_projected}.output", f"{wta_local}.matrixSum"), type="matrix")
            cmds.connectAttr(f"{fbf_corner_lip_pos_only}.output", f"{inverse_matrix_jaw}.inputMatrix")
            cmds.connectAttr(f"{fbf_lip_projected}.output", f"{mmx_offset_jaw_pos}.matrixIn[0]")
            cmds.connectAttr(f"{inverse_matrix_jaw}.outputMatrix", f"{mmx_offset_jaw_pos}.matrixIn[1]")
            cmds.connectAttr(f"{parent_matrix_blender_local}.outputMatrix", f"{mmx_offset_jaw_pos}.matrixIn[2]")
            cmds.connectAttr(f"{mmx_offset_jaw_pos}.matrixSum", f"{local_jnt}.offsetParentMatrix")

            

            upper_local_jnts.append(local_jnt)
            lower_local_jnts.append(local_jnt)
            if side == "L":
                upper_local_jnts.append(upper_local_jnt)
                lower_local_jnts.append(lower_local_jnt)
            

        # Get CV count once per curve
        up_cvs = cmds.ls(f"{self.upper_linear_lip_curve}.cv[*]", flatten=True)
        low_cvs = cmds.ls(f"{self.lower_linear_lip_curve}.cv[*]", flatten=True)
        up_positions = [cmds.pointPosition(f"{self.upper_linear_lip_curve}.cv[{i}]", world=True) for i in range(len(up_cvs))]
        low_positions = [cmds.pointPosition(f"{self.lower_linear_lip_curve}.cv[{i}]", world=True) for i in range(len(low_cvs))]

        self.upper_curve = cmds.curve(name="C_upperLip_CRV", degree=1, point=up_positions)
        self.lower_curve = cmds.curve(name="C_lowerLip_CRV", degree=1, point=low_positions)
        upper_shape = cmds.listRelatives(self.upper_curve, shapes=True)[0]
        lower_shape = cmds.listRelatives(self.lower_curve, shapes=True)[0]
        cmds.rename(upper_shape, f"{self.upper_curve}Shape_CRV")
        cmds.rename(lower_shape, f"{self.lower_curve}Shape_CRV")

        # Nº de controladores (= CVs del rebuild) en 6-10 pero IMPAR, para que la C
        # caiga en el CV CENTRAL exacto de la curva/nurbs y R/L queden simétricos.
        # Grado 3: nCVs = spans + 3. Mismo span en upper/lower (topología para el
        # blendShape de sticky lips).
        n_controllers = max(6, min(10, len(up_cvs)))
        if n_controllers % 2 == 0:
            n_controllers -= 1
        controller_spans = n_controllers - 3
        self.upper_rebuild_lip_curve = cmds.rebuildCurve(
            self.upper_curve, ch=0, rpo=1, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0,
            s=controller_spans, d=3, tol=0.01, name="C_upperLip_CRV"
        )[0]
        self.lower_rebuild_lip_curve = cmds.rebuildCurve(
            self.lower_curve, ch=0, rpo=1, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0,
            s=controller_spans, d=3, tol=0.01, name="C_lowerLip_CRV"
        )[0]

        cmds.parent(self.upper_rebuild_lip_curve, self.lower_rebuild_lip_curve, self.module_trn)

        # Skin cluster to local joints
        self.upper_skin_cluster = cmds.skinCluster(upper_local_jnts, self.upper_rebuild_lip_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name="C_upperLip_SKIN")[0]
        self.lower_skin_cluster = cmds.skinCluster(lower_local_jnts, self.lower_rebuild_lip_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name="C_lowerLip_SKIN")[0]
        self._skin_lip_curve_to_locals(self.upper_skin_cluster, self.upper_rebuild_lip_curve, upper_local_jnts)
        self._skin_lip_curve_to_locals(self.lower_skin_cluster, self.lower_rebuild_lip_curve, lower_local_jnts)
        rebuilded_cvs = len(cmds.ls(f"{self.upper_rebuild_lip_curve}.cv[*]", flatten=True))

        def _span_len(crv):
            a = cmds.pointPosition(f"{crv}.cv[0]", world=True)
            b = cmds.pointPosition(f"{crv}.cv[{rebuilded_cvs - 1}]", world=True)
            return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5

        lip_width = max(0.2, _span_len(self.upper_rebuild_lip_curve) * 0.08)

        self.upper_lip_nurbs = self._ribbon_from_curve(self.upper_rebuild_lip_curve, lip_width, "C_upperLip_NURB")
        self.lower_lip_nurbs = self._ribbon_from_curve(self.lower_rebuild_lip_curve, lip_width, "C_lowerLip_NURB")
        cmds.parent(self.upper_lip_nurbs, self.lower_lip_nurbs, self.module_trn)

        # Create secondary nodes GRP to control visibility
        secondary_controllers_nodes = cmds.createNode("transform", name="C_secondaryLipsControllers_GRP", ss=True, parent=lips_controllers_grp)

        all_secondary_joints = {"upper": [], "lower": []}

        for part, nurbs in (["upper", self.upper_lip_nurbs], ["lower", self.lower_lip_nurbs]):

            curve = self.upper_rebuild_lip_curve if part == "upper" else self.lower_rebuild_lip_curve
            mid_point = rebuilded_cvs // 2

            secondary_grps = []
            secondary_ctls = []
            secondary_local_joints_mmx = []

            for index in range(0, rebuilded_cvs):

                if index < mid_point:
                    side = "R"
                    i = index
                elif index == mid_point:
                    side = "C"
                    i = 0  # la C es el centro -> nombre 00 (mirror limpio)
                else:
                    side = "L"
                    i = rebuilded_cvs - 1 - index

                ctl_name = f"{side}_{part}Lip{str(i).zfill(2)}"

                secondary_nodes, secondary_ctl = curve_tool.create_controller(
                    ctl_name,
                    offset=["GRP", "OFF"],
                    parent=secondary_controllers_nodes
                )
                self.lock_attributes(secondary_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])

                secondary_local_joint = cmds.createNode(
                    "joint", name=f"{ctl_name}Driver_JNT", ss=True, parent=self.module_trn
                )


                rebuilded_cv = cmds.ls(f"{curve}.cv[{index}]", flatten=True)[0]
                pos_rebuilded_cv = cmds.xform(rebuilded_cv, query=True, worldSpace=True, translation=True)
                real_param = self.getClosestParamToPosition(curve, pos_rebuilded_cv)

                mp = cmds.createNode("motionPath", name=f"{ctl_name}_MPT", ss=True)
                cmds.setAttr(f"{mp}.fractionMode", False)
                cmds.setAttr(f"{mp}.uValue", real_param)
                cmds.connectAttr(f"{curve}.worldSpace[0]", f"{mp}.geometryPath")

                fbf = cmds.createNode("fourByFourMatrix", name=f"{ctl_name}_FBF", ss=True)
                cmds.connectAttr(f"{mp}.xCoordinate", f"{fbf}.in30")
                cmds.connectAttr(f"{mp}.yCoordinate", f"{fbf}.in31")
                cmds.connectAttr(f"{mp}.zCoordinate", f"{fbf}.in32")

                if side == "R":
                        cmds.setAttr(f"{fbf}.in00", -1)
                if part == "lower":
                        cmds.setAttr(f"{fbf}.in11", -1)

                cmds.connectAttr(f"{fbf}.output", f"{secondary_nodes[0]}.offsetParentMatrix")

                mult_matrix_secondary_local = cmds.createNode(
                    "multMatrix", name=f"{ctl_name}Local_MMX", ss=True
                )
                cmds.connectAttr(f"{secondary_ctl}.matrix", f"{mult_matrix_secondary_local}.matrixIn[0]")
                cmds.connectAttr(f"{fbf}.output", f"{mult_matrix_secondary_local}.matrixIn[1]")
                cmds.connectAttr(
                    f"{mult_matrix_secondary_local}.matrixSum",
                    f"{secondary_local_joint}.offsetParentMatrix"
                )

                secondary_grps.append(secondary_nodes[0])
                secondary_ctls.append(secondary_ctl)
                secondary_local_joints_mmx.append(mult_matrix_secondary_local)
                all_secondary_joints[part].append(secondary_local_joint)

            # ----- PROJECT CURVE DRIVER TO NURBS SURFACE -----
            # for i, joint in enumerate(secondary_joints):
                
            #     joint_name = joint.split("_JNT")[0]
            #     ctl = secondary_ctls[i]

            #     input_connections = cmds.listConnections(f"{joint}.offsetParentMatrix", source=True, destination=False)
            #     if not input_connections:
            #         continue
            #     input_connection = input_connections[0]
                
            #     pick_matrix = cmds.createNode("pickMatrix", name=f"{joint_name}_PCM", ss=True)
            #     decompose_matrix = cmds.createNode("decomposeMatrix", name=f"{joint_name}_DCM", ss=True)
            #     rfm_project = cmds.createNode("rowFromMatrix", name=f"{joint_name}Project_RMF", ss=True)
            #     cps_project = cmds.createNode("closestPointOnSurface", name=f"{joint_name}Project_CPS", ss=True)
                
            #     cmds.setAttr(f"{pick_matrix}.useTranslate", 0)
            #     cmds.setAttr(f"{pick_matrix}.useShear", 0)
            #     cmds.setAttr(f"{rfm_project}.input", 3) # Fila 3 = Traslación
                
            #     cmds.connectAttr(f"{input_connection}.matrixSum", f"{pick_matrix}.inputMatrix")
            #     cmds.connectAttr(f"{pick_matrix}.outputMatrix", f"{decompose_matrix}.inputMatrix")
            #     cmds.connectAttr(f"{decompose_matrix}.outputRotate", f"{joint}.rotate")
            #     cmds.connectAttr(f"{decompose_matrix}.outputScale", f"{joint}.scale")
                
            #     cmds.connectAttr(f"{input_connection}.matrixSum", f"{rfm_project}.matrix")
            #     cmds.connectAttr(f"{rfm_project}.outputX", f"{cps_project}.inPositionX")
            #     cmds.connectAttr(f"{rfm_project}.outputY", f"{cps_project}.inPositionY")
            #     cmds.connectAttr(f"{rfm_project}.outputZ", f"{cps_project}.inPositionZ")

            #     cmds.connectAttr(f"{self.sphere}.worldSpace[0]", f"{cps_project}.inputSurface")
            #     cmds.connectAttr(f"{cps_project}.position", f"{joint}.translate")
            #     cmds.disconnectAttr(f"{input_connection}.matrixSum", f"{joint}.offsetParentMatrix")
            #     identity = [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]
            #     cmds.setAttr(f"{joint}.offsetParentMatrix", identity, type="matrix")


            skin_cluster = cmds.skinCluster(all_secondary_joints[part], nurbs, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name=f"C_{part}Nurbs_SKIN")[0]

        output_joints = { "upper": [], "lower": [] }
        non_rotate_output_joints = { "upper": [], "lower": [] }
        aim_matrices = { "upper": [], "lower": [] }
        orient_plugs = { "upper": [], "lower": [] }
        pick_matrices = { "upper": [], "lower": [] }

        for part, nurbs in (["upper", self.upper_lip_nurbs], ["lower", self.lower_lip_nurbs]):
            
            _skin_curve = self.upper_rebuild_lip_curve if part == "upper" else self.lower_rebuild_lip_curve
            linear_curve = self.upper_linear_lip_curve if part == "upper" else self.lower_linear_lip_curve
            linear_curve_cvs = len(cmds.ls(f"{linear_curve}.cv[*]", flatten=True))
            driver_joints = all_secondary_joints[part]
            mid_point = linear_curve_cvs // 2
            normal_vector = (0, 1, 0)

            # Duplicate the skinned curve so offsetCurve has no history to warn about
            _dup_for_offset = cmds.duplicate(_skin_curve, name=f"C_{part}LipOffsetInput_TMP")[0]
            cmds.delete(_dup_for_offset, constructionHistory=True)
            cmds.select(clear=True)

            # Create offset curve for the up-vector
            offset_curve = cmds.offsetCurve(
                _dup_for_offset,
                distance=1,
                useGivenNormal=1,
                normal=normal_vector,
                constructionHistory=False,
                name=f"C_{part}LipOffset_CRV"
            )[0]
            cmds.delete(_dup_for_offset)

            cmds.rebuildCurve(
            offset_curve, ch=0, rpo=1, rt=0, end=1, kr=0, kcp=0, kep=1, kt=0,
            s=4, d=3, tol=0.01, name=f"C_{part}LipOffset_CRV"
            )[0]

            cmds.skinCluster(driver_joints, offset_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name=f"C_{part}LipOffset_SKIN")

            cmds.parent(offset_curve, self.module_trn)

            # Create uvPin
            uv_pin_nurbs = cmds.createNode("uvPin", name=f"C_{part}LipAimVector_UVP", ss=True)
            uv_pin_up = cmds.createNode("uvPin", name=f"C_{part}LipUpVector_UVP", ss=True)

            cmds.setAttr(f"{uv_pin_nurbs}.normalAxis", 1)  # Y
            cmds.setAttr(f"{uv_pin_nurbs}.tangentAxis", 0)  # X
            cmds.setAttr(f"{uv_pin_up}.normalAxis", 0)  # X
            cmds.setAttr(f"{uv_pin_up}.tangentAxis", 2)  # Z

            cmds.connectAttr(f"{nurbs}.worldSpace[0]", f"{uv_pin_nurbs}.deformedGeometry")
            cmds.connectAttr(f"{offset_curve}.worldSpace[0]", f"{uv_pin_up}.deformedGeometry")

            

            for i in range(0, linear_curve_cvs):

                surface_cv = f"{nurbs}.cv[{i}][0]"
                curve_cv = f"{linear_curve}.cv[{i}]"
                offset_cv = f"{offset_curve}.cv[{i}]"

                if i < mid_point:
                    side = "R"
                    name_index = i  # Empieza en 0 y suma (0, 1, 2...)
                    
                elif i == mid_point:
                    side = "C"
                    name_index = 0  # El centro siempre será 0
                    
                else:
                    side = "L"
                    name_index = (linear_curve_cvs - 1) - i

                cv_ws_pos = cmds.xform(curve_cv, query=True, worldSpace=True, translation=True)
                u_param, v_param = matrix_manager.getClosestParamsToPositionSurface(nurbs, cv_ws_pos)
                vertex_cv_pos = cmds.xform(curve_cv, query=True, worldSpace=True, translation=True)
                param_linear = self.getClosestParamToPosition(offset_curve, vertex_cv_pos)
 
                cmds.setAttr(f"{uv_pin_nurbs}.coordinate[{i}].coordinateU", u_param)
                cmds.setAttr(f"{uv_pin_nurbs}.coordinate[{i}].coordinateV", 0.5)
                # uv_pin_linear is on a curve (1D), use U param from linear curve and V=0.5
                cmds.setAttr(f"{uv_pin_up}.coordinate[{i}].coordinateU", u_param)
                cmds.setAttr(f"{uv_pin_up}.coordinate[{i}].coordinateV", 0.5)

                aim_matrix_vector = cmds.createNode("aimMatrix", name=f"{side}_{part}Lip{name_index:02d}Vector_AMX", ss=True)
                cmds.connectAttr(f"{uv_pin_nurbs}.outputMatrix[{i}]", f"{aim_matrix_vector}.inputMatrix")
                cmds.connectAttr(f"{uv_pin_up}.outputMatrix[{i}]", f"{aim_matrix_vector}.primaryTargetMatrix")
                cmds.connectAttr(f"{uv_pin_nurbs}.outputMatrix[{i}]", f"{aim_matrix_vector}.secondaryTargetMatrix")
                cmds.setAttr(f"{aim_matrix_vector}.primaryInputAxis", 0,0,-1)
                cmds.setAttr(f"{aim_matrix_vector}.primaryMode", 1) # Aim
                cmds.setAttr(f"{aim_matrix_vector}.secondaryInputAxis", 1,0,0)
                cmds.setAttr(f"{aim_matrix_vector}.secondaryTargetVector", 1,0,0)
                cmds.setAttr(f"{aim_matrix_vector}.secondaryMode", 2) # Align to World
    
                out_joint = cmds.createNode("joint", name=f"{side}_{part}Lip{name_index:02d}_JNT", ss=True, parent=self.skeleton_grp)
                cmds.connectAttr(f"{aim_matrix_vector}.outputMatrix", f"{out_joint}.offsetParentMatrix")

                aim_matrices[part].append(aim_matrix_vector)
                orient_plugs[part].append(f"{aim_matrix_vector}.outputMatrix")
                output_joints[part].append(out_joint)

            for i, aim_matrix_vector in enumerate(aim_matrices[part]):

                if i < mid_point:
                    side = "R"
                    name_index = i
                    
                elif i == mid_point:
                    side = "C"
                    name_index = 0
                    
                else:
                    side = "L"
                    name_index = (linear_curve_cvs - 1) - i

                non_rot_out_joint = cmds.createNode("joint", name=f"{side}_{part}Lip{name_index:02d}NonRot_JNT", ss=True, parent=self.skeleton_grp)
                pick_matrix_non_rot = cmds.createNode("pickMatrix", name=f"{side}_{part}Lip{name_index:02d}NonRot_PCM", ss=True)
                cmds.setAttr(f"{pick_matrix_non_rot}.useRotate", 0)
                cmds.connectAttr(f"{aim_matrix_vector}.outputMatrix", f"{pick_matrix_non_rot}.inputMatrix")
                cmds.connectAttr(f"{pick_matrix_non_rot}.outputMatrix", f"{non_rot_out_joint}.offsetParentMatrix")
                non_rotate_output_joints[part].append(non_rot_out_joint)
                pick_matrices[part].append(pick_matrix_non_rot)
        


        # ----- ANTI-PINCH DE ESQUINAS -----
        # En cada esquina coinciden (misma posición) el primer/último joint de upper
        # y de lower con ORIENTACIÓN distinta -> la malla pegada a ambos pinza. Para
        # evitarlo, cerca de cada esquina las joints de upper y lower CONVERGEN en
        # rotación hacia su orientación MEDIA, con un falloff que decrece de la
        # esquina hacia dentro (1 -> 0 en `corner_blend` joints). Solo rotación: cada
        # joint conserva su propia posición (translateWeight=0), así no se mueven.
        n_out = len(output_joints["upper"])
        corner_blend = min(4, n_out // 2)  # nº de joints desde cada esquina que convergen
        for corner_idx in (0, n_out - 1):
            for k in range(corner_blend):
                idx = corner_idx + k if corner_idx == 0 else corner_idx - k
                w = 1.0 - k / float(corner_blend)  # 1 en la esquina -> baja hacia dentro
                up_aim = aim_matrices["upper"][idx]
                lo_aim = aim_matrices["lower"][idx]
                avg = cmds.createNode("blendMatrix", name=f"C_lipCorner{idx:02d}Avg_BMX", ss=True)
                cmds.connectAttr(f"{up_aim}.outputMatrix", f"{avg}.inputMatrix")
                cmds.connectAttr(f"{lo_aim}.outputMatrix", f"{avg}.target[0].targetMatrix")
                cmds.setAttr(f"{avg}.target[0].weight", 0.5)
                for part in ("upper", "lower"):
                    own = aim_matrices[part][idx]
                    jb = cmds.createNode("blendMatrix", name=f"C_{part}LipCorner{idx:02d}Blend_BMX", ss=True)
                    cmds.connectAttr(f"{own}.outputMatrix", f"{jb}.inputMatrix")
                    cmds.connectAttr(f"{avg}.outputMatrix", f"{jb}.target[0].targetMatrix")
                    cmds.setAttr(f"{jb}.target[0].translateWeight", 0)  # conserva la posición propia
                    cmds.setAttr(f"{jb}.target[0].rotateWeight", w)     # converge en rotación hacia la media
                    cmds.setAttr(f"{jb}.target[0].scaleWeight", 0)
                    cmds.setAttr(f"{jb}.target[0].shearWeight", 0)
                    orient_plugs[part][idx] = f"{jb}.outputMatrix"
                    cmds.connectAttr(f"{jb}.outputMatrix", f"{output_joints[part][idx]}.offsetParentMatrix", force=True)

        # ----- STICKY LIPS SETUP -----
        mid_nurbs = cmds.duplicate(self.upper_lip_nurbs, name="C_midLip_NURB")[0]
        # cmds.parent(mid_nurbs, self.module_trn)
        blend_shape_mid_nurbs = cmds.blendShape(self.upper_lip_nurbs, self.lower_lip_nurbs, mid_nurbs, name="C_midLip_BLS")[0]
        cmds.setAttr(f"{blend_shape_mid_nurbs}.{self.upper_lip_nurbs}", 0.5)
        cmds.setAttr(f"{blend_shape_mid_nurbs}.{self.lower_lip_nurbs}", 0.5)

        uv_pin_mid = cmds.createNode("uvPin", name="C_midLip_UVP", ss=True)
        cmds.setAttr(f"{uv_pin_mid}.normalAxis", 1)  # Y
        cmds.setAttr(f"{uv_pin_mid}.tangentAxis", 0)  # X
        cmds.connectAttr(f"{mid_nurbs}.worldSpace[0]", f"{uv_pin_mid}.deformedGeometry")

        for i in range(0, linear_curve_cvs):
            vertex_cv_pos = cmds.xform(f"{linear_curve}.cv[{i}]", query=True, worldSpace=True, translation=True)
            param_linear = self.getClosestParamToPosition(offset_curve, vertex_cv_pos)
            cmds.setAttr(f"{uv_pin_mid}.coordinate[{i}].coordinateU", param_linear)
            cmds.setAttr(f"{uv_pin_mid}.coordinate[{i}].coordinateV", 0.5)

        # Identificamos los controladores L y R explícitamente desde tu lista previa
        l_corner_ctl = next((c for c in corner_controllers if "L_" in c), corner_controllers[0])
        r_corner_ctl = next((c for c in corner_controllers if "R_" in c), corner_controllers[1])

        # Creamos un nodo Condition para calcular el MÁXIMO entre el Zip L y el Zip R para el Centro
        center_zip_cond = cmds.createNode("condition", name=f"C_{part}LipZipMax_COND", ss=True)
        cmds.setAttr(f"{center_zip_cond}.operation", 2) # Greater Than (Mayor que)
        cmds.connectAttr(f"{l_corner_ctl}.Zip", f"{center_zip_cond}.firstTerm")
        cmds.connectAttr(f"{r_corner_ctl}.Zip", f"{center_zip_cond}.secondTerm")
        cmds.connectAttr(f"{l_corner_ctl}.Zip", f"{center_zip_cond}.colorIfTrueR")
        cmds.connectAttr(f"{r_corner_ctl}.Zip", f"{center_zip_cond}.colorIfFalseR")
        
        for part in ["upper", "lower"]:

            for i, (non_rot_joint, out_joint) in enumerate(zip(non_rotate_output_joints[part], output_joints[part])):

                roll_controller = upper_lip_ctl if part == "upper" else lower_lip_ctl

                real_index = i if i <= mid_point else (linear_curve_cvs - 1) - i
                activate_min = (float(real_index) / float(mid_point)) * 0.95
                activate_max = activate_min + 0.05 

                side = non_rot_joint.split("_")[0]

                remap_value = cmds.createNode("remapValue", name=f"{non_rot_joint}Sticky_RMV", ss=True)
                
                # --- CONEXIÓN INDEPENDIENTE POR LADOS ---
                if side == "L":
                    cmds.connectAttr(f"{l_corner_ctl}.Zip", f"{remap_value}.inputValue")
                elif side == "R":
                    cmds.connectAttr(f"{r_corner_ctl}.Zip", f"{remap_value}.inputValue")
                else: 
                    # side == "C" (El centro usa el valor máximo de ambos lados)
                    cmds.connectAttr(f"{center_zip_cond}.outColorR", f"{remap_value}.inputValue")

                cmds.setAttr(f"{remap_value}.inputMin", 0)
                cmds.setAttr(f"{remap_value}.inputMax", 1)
                cmds.setAttr(f"{remap_value}.outputMin", 0)
                cmds.setAttr(f"{remap_value}.outputMax", 1)
                
                cmds.setAttr(f"{remap_value}.value[0].value_Position", activate_min)
                cmds.setAttr(f"{remap_value}.value[0].value_FloatValue", 0)
                
                cmds.setAttr(f"{remap_value}.value[1].value_Position", activate_max)
                cmds.setAttr(f"{remap_value}.value[1].value_FloatValue", 1)

                # Conexión del blendMatrix sticky a la joint de salida.
                # (Antes se creaba además un blend_matrix_sticky_no_rot para las
                # non_rotate joints, pero su salida estaba comentada → era un
                # nodo muerto por joint de labio; eliminado.)
                blend_matrix_sticky_rot = cmds.createNode("blendMatrix", name=f"{out_joint}Sticky_BMX", ss=True)
                cmds.connectAttr(orient_plugs[part][i], f"{blend_matrix_sticky_rot}.inputMatrix")
                cmds.connectAttr(f"{uv_pin_mid}.outputMatrix[{i}]", f"{blend_matrix_sticky_rot}.target[0].targetMatrix")
                cmds.connectAttr(f"{remap_value}.outValue", f"{blend_matrix_sticky_rot}.target[0].weight")
                cmds.connectAttr(f"{blend_matrix_sticky_rot}.outputMatrix", f"{out_joint}.offsetParentMatrix", f=True)

                max_index = mid_point - 1
                if side == "C":
                    roll_factor = 1.0
                else:
                    # real_index=0 at corners, real_index=max_index near center
                    t = float(real_index) / float(max_index) if max_index > 0 else 1.0
                    # Smoothstep: concentrate roll in center, fade to 0 at corners
                    roll_factor = t * t * (3.0 - 2.0 * t)

                if roll_factor == 0:
                    roll_factor = 0.001

                # Driver del roll = rotateX del control + atributo Roll, para que
                # ROTAR el control (rotateX) también role (no solo el attr Roll). El
                # roll va al rotateX LOCAL de la joint -> rota alrededor de su
                # tangente (curl hacia dentro/fuera), encima del sticky, con falloff
                # smoothstep (máximo en el centro, 0 en las esquinas).
                # (rotateX -> nodo multiply lo expone en grados, coherente con Roll.)
                roll_rx_deg = cmds.createNode("multiply", name=f"{out_joint}RollRxDeg_MUL", ss=True)
                cmds.connectAttr(f"{roll_controller}.rotateX", f"{roll_rx_deg}.input[0]")
                cmds.setAttr(f"{roll_rx_deg}.input[1]", 1.0)
                roll_drive = cmds.createNode("plusMinusAverage", name=f"{out_joint}RollDrive_PMA", ss=True)
                cmds.connectAttr(f"{roll_rx_deg}.output", f"{roll_drive}.input1D[0]")
                cmds.connectAttr(f"{roll_controller}.Roll", f"{roll_drive}.input1D[1]")

                # ---MULTIPLY ---
                roll_mul = cmds.createNode("multiply", name=f"{out_joint}_Roll_MUL", ss=True)

                cmds.connectAttr(f"{roll_drive}.output1D", f"{roll_mul}.input[0]")
                cmds.setAttr(f"{roll_mul}.input[1]", roll_factor)
                cmds.connectAttr(f"{roll_mul}.output", f"{out_joint}.rotateX", f=True)
        
        

        # ------ Conditions to control visibility of lip controllers ------
        condition_primary = cmds.createNode("condition", name="C_lipsPrimaryControllers_COND", ss=True)
        cmds.setAttr(f"{condition_primary}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_primary}.secondTerm", 1)
        cmds.setAttr(f"{condition_primary}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_primary}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Lips", f"{condition_primary}.firstTerm")
        cmds.connectAttr(f"{condition_primary}.outColorR", f"{main_lips_controllers}.visibility", f=True)
        condition_secondary = cmds.createNode("condition", name="C_lipsSecondaryControllers_COND", ss=True)
        cmds.setAttr(f"{condition_secondary}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_secondary}.secondTerm", 2)
        cmds.setAttr(f"{condition_secondary}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_secondary}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Lips", f"{condition_secondary}.firstTerm")
        cmds.connectAttr(f"{condition_secondary}.outColorR", f"{secondary_controllers_nodes}.visibility", f=True)
        condition_jaw = cmds.createNode("condition", name="C_jawControllers_COND", ss=True)
        cmds.setAttr(f"{condition_jaw}.operation", 3)  # Greater Than or Equal
        cmds.setAttr(f"{condition_jaw}.secondTerm", 1)
        cmds.setAttr(f"{condition_jaw}.colorIfTrueR", 1)
        cmds.setAttr(f"{condition_jaw}.colorIfFalseR", 0)
        cmds.connectAttr(f"{self.face_ctl}.Jaw", f"{condition_jaw}.firstTerm")
        cmds.connectAttr(f"{condition_jaw}.outColorR", f"{self.jaw_nodes[0]}.visibility")
        cmds.connectAttr(f"{condition_jaw}.outColorR", f"{self.upper_jaw_nodes[0]}.visibility")

    def main_mouth_setup(self):
        """
        Main setup for the mouth rig, including creating joints, curves, skinning, and setting up the sticky lips system.
        """
        
        main_mouth_nodes, main_mouth_ctl = curve_tool.create_controller(
            name="C_mainMouth_CTL",
            offset=["GRP", "OFF"],
            parent=self.face_ctl
        )

        mmx_main_mouth = cmds.createNode("multMatrix", name="C_mainMouth_MMX", ss=True)
        cmds.connectAttr(f"{main_mouth_ctl}.worldMatrix[0]", f"{mmx_main_mouth}.matrixIn[0]")
        cmds.connectAttr(f"{main_mouth_nodes[0]}.worldInverseMatrix[0]", f"{mmx_main_mouth}.matrixIn[1]")

    
    def get_offset_matrix(self, child, parent):
        """
        Calculate the offset matrix between a child and parent transform in Maya.
        Args:
            child (str | list | om.MMatrix): The name of the child transform, matrix attribute, 
                                            a flat list of 16 floats, or an MMatrix.
            parent (str | list | om.MMatrix): Same as child but for the parent.
        Returns:
            list: The offset matrix as a flat list of 16 floats in row-major order that 
                transforms the child into the parent's space.
        """
        def get_world_matrix(node):
            # If it's already an MMatrix, return it directly
            if isinstance(node, om.MMatrix):
                return node
            # If it's a list/tuple of 16 floats, convert to MMatrix
            if isinstance(node, (list, tuple)):
                return om.MMatrix(node)
            # Otherwise, treat it as a node/attribute name
            try:
                dag = om.MSelectionList().add(node).getDagPath(0)
                return dag.inclusiveMatrix()
            except:
                matrix = cmds.getAttr(node)
                return om.MMatrix(matrix)

        child_world_matrix = get_world_matrix(child)
        parent_world_matrix = get_world_matrix(parent)

        offset_matrix = child_world_matrix * parent_world_matrix.inverse()

        # Convert to Python list (row-major order)
        offset_matrix_list = list(offset_matrix)

        return offset_matrix_list
    
    def getClosestParamToPosition(self, curve, position):
        """
        Returns the closest parameter (u) on the given NURBS curve to a world-space position.
        
        Args:
            curve (str or MObject or MDagPath): The curve to evaluate.
            position (list or tuple): A 3D world-space position [x, y, z].

        Returns:
            float: The parameter (u) value on the curve closest to the given position.
        """
        if isinstance(curve, str):
            sel = om.MSelectionList()
            sel.add(curve)
            curve_dag_path = sel.getDagPath(0)
        elif isinstance(curve, om.MObject):
            curve_dag_path = om.MDagPath.getAPathTo(curve)
        elif isinstance(curve, om.MDagPath):
            curve_dag_path = curve
        else:
            raise TypeError("Curve must be a string name, MObject, or MDagPath.")

        curve_fn = om.MFnNurbsCurve(curve_dag_path)

        point = om.MPoint(*position)

        closest_point, paramU = curve_fn.closestPoint(point, space=om.MSpace.kWorld)

        return paramU
    
    def get_offset_matrix_from_identity(self, child_attr):
        child_matrix = om.MMatrix(cmds.getAttr(child_attr))
        # offset = identity * child.inverse() = child.inverse()
        offset_matrix = child_matrix.inverse()
        return list(offset_matrix)