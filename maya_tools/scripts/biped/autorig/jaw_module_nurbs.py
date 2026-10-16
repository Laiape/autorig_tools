import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload
import os
import math

from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils import guides_manager
from maya_tools.scripts.utils import curve_tool
from maya_tools.scripts.utils import matrix_manager
from maya_tools.scripts.utils import ribbon
from maya_tools.scripts.utils.module_nurbs import organize_module_nurbs

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
        self.face_controls_parent = (data_manager.DataExportBiped().get_data("neck_module", "face_controls_parent") or self.face_ctl)
        self.head_ctl = data_manager.DataExportBiped().get_data("neck_module", "head_ctl")

    
    @organize_module_nurbs
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

        cmds.parent(self.controllers_grp, self.face_controls_parent)

        self.main_mouth_setup()

        # Clean up
        # cmds.delete("L_jaw_JNT", "R_jaw_JNT")

        data_manager.DataExportBiped().append_data("jaw_module", 
                                                
                                                {"jaw_ctl": self.jaw_ctl,
                                                 "upper_jaw_ctl": self.upper_jaw_ctl,
                                                 "main_mouth_ctl": self.main_mouth_ctl,
                                                 "local_jaw_mmx" : self.mult_matrix_jaw_local,
                                                 "local_upper_jaw_mmx" : self.mult_matrix_upper_jaw_local
                                                })
        
        cmds.setAttr(f"{self.module_trn}.inheritsTransform", 0)

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
        curve_tool.lock_attributes(self.jaw_ctl, ["sx", "sy", "sz", "v"])

        mult_matrix_jaw = cmds.createNode("multMatrix", name="C_jawSkinning_MMX")
        cmds.connectAttr(f"{self.jaw_ctl}.worldMatrix[0]", f"{mult_matrix_jaw}.matrixIn[0]")
        cmds.connectAttr(f"{self.jaw_nodes[0]}.worldInverseMatrix[0]", f"{mult_matrix_jaw}.matrixIn[1]")
        grp_pos = cmds.getAttr(f"{self.jaw_nodes[0]}.worldMatrix[0]")
        cmds.setAttr(f"{mult_matrix_jaw}.matrixIn[2]", grp_pos, type="matrix")  # Reset any previous transformations
        cmds.connectAttr(f"{mult_matrix_jaw}.matrixSum", f"{jaw_skinning}.offsetParentMatrix")

        # ---- Upper jaw controller ----
        self.upper_jaw_nodes, self.upper_jaw_ctl = curve_tool.create_controller("C_upperJaw", offset=["GRP", "OFF"], parent=self.controllers_grp)
        cmds.setAttr(f"{self.upper_jaw_nodes[0]}.offsetParentMatrix", self.jaw_guide_matrix, type="matrix")
        curve_tool.lock_attributes(self.upper_jaw_ctl, ["sx", "sy", "sz", "v"])

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

        attribute_blender = cmds.createNode("blendTwoAttr", name=f"{self.module_name}_collisionJaw_BTA")
        cmds.connectAttr(f"{self.jaw_ctl}.Auto_Collision", f"{attribute_blender}.attributesBlender")
        cmds.setAttr(f"{attribute_blender}.input[0]", 0)
        cmds.connectAttr(f"{clamp_jaw}.outputR", f"{attribute_blender}.input[1]")
        self.compose_matrix_jaw = cmds.createNode("composeMatrix", name=f"{self.module_name}_collisionJaw_CMP")
        cmds.connectAttr(f"{attribute_blender}.output", f"{self.compose_matrix_jaw}.inputRotateX")
        cmds.connectAttr(f"{self.compose_matrix_jaw}.outputMatrix", f"{self.upper_jaw_ctl}.offsetParentMatrix")  # Connect the output of the blendTwoAttr to the rotateX of the upper jaw controller


    @staticmethod
    def _curve_cv_parameters(curve):
        """Greville parameters: ordered anchors for each cubic control vertex."""
        selection = om.MSelectionList()
        selection.add(curve)
        path = selection.getDagPath(0)
        if path.node().hasFn(om.MFn.kTransform):
            path.extendToShape()
        fn = om.MFnNurbsCurve(path)
        knots = list(fn.knots())
        full_knots = [knots[0]] + knots + [knots[-1]]
        return [sum(full_knots[i + 1:i + fn.degree + 1]) / fn.degree
                for i in range(fn.numCVs)]

    @staticmethod
    def _ordered_lip_parameters(values):
        """Repair a crossed run by interpolating between its valid neighbours."""
        result = list(values)
        i = 1
        while i < len(result) - 1:
            if result[i - 1] < result[i] < result[i + 1]:
                i += 1
                continue
            left = i - 1
            right = i + 1
            while right < len(result) - 1 and result[right] <= max(result[left:i + 1]):
                right += 1
            if result[right] <= result[left]:
                raise ValueError("Los extremos de la guia de labios no tienen un orden valido.")
            for k in range(left + 1, right):
                result[k] = result[left] + (result[right] - result[left]) * (k - left) / (right - left)
            i = right
        if any(a >= b for a, b in zip(result, result[1:])):
            raise ValueError("No se pudo ordenar los pins de la guia de labios.")
        return result

    @staticmethod
    def _neighbor_lip_aim(name, frame, target, reverse=False, positions=None):
        """Aim fine controls at independent neighbour bases, preserving rest axes."""
        if positions is None:
            positions = []
            for suffix, matrix in (("Position", frame), ("Target", target)):
                node = cmds.createNode("translationFromMatrix", name=name + "Neighbor" + suffix + "_TFM", ss=True)
                cmds.connectAttr(matrix, node + ".input")
                positions.append(node + ".output")
        direction = cmds.createNode("plusMinusAverage", name=name + "NeighborDirection_PMA", ss=True)
        cmds.setAttr(direction + ".operation", 2)
        cmds.connectAttr(positions[1], direction + ".input3D[0]")
        cmds.connectAttr(positions[0], direction + ".input3D[1]")
        length = cmds.createNode("vectorProduct", name=name + "NeighborLength_VPR", ss=True)
        cmds.setAttr(length + ".operation", 1)
        cmds.connectAttr(direction + ".output3D", length + ".input1")
        cmds.connectAttr(direction + ".output3D", length + ".input2")
        rest_direction = cmds.getAttr(direction + ".output3D")[0]
        safe = cmds.createNode("condition", name=name + "NeighborSafe_CND", ss=True)
        cmds.setAttr(safe + ".operation", 4)
        cmds.setAttr(safe + ".secondTerm", 1e-8)
        cmds.connectAttr(length + ".outputX", safe + ".firstTerm")
        cmds.setAttr(safe + ".colorIfTrue", *rest_direction)
        cmds.connectAttr(direction + ".output3D", safe + ".colorIfFalse")
        # Swing the transported frame toward its neighbour while retaining its
        # twist. A separate up-vector solve can become parallel to the chord or
        # flip hemispheres when the corner rotates. The rest-local aim direction
        # preserves the authored neutral axes, including mirrored controls.
        orientation = om.MMatrix(cmds.getAttr(frame))
        local_direction = om.MVector(*rest_direction) * orientation.inverse()
        if local_direction.length() < 1e-8:
            local_direction = om.MVector(-1 if reverse else 1, 0, 0)
            world_direction = local_direction * orientation
            cmds.setAttr(safe + ".colorIfTrue", *world_direction)
        local_direction.normalize()
        aim = cmds.createNode("aimMatrix", name=name + "Neighbor_AMX", ss=True)
        cmds.connectAttr(frame, aim + ".inputMatrix")
        cmds.setAttr(aim + ".primaryInputAxis", *local_direction)
        cmds.setAttr(aim + ".primaryMode", 2)
        cmds.connectAttr(safe + ".outColor", aim + ".primaryTargetVector")
        cmds.setAttr(aim + ".secondaryMode", 0)
        return aim + ".outputMatrix"

    @staticmethod
    def _central_profile_correction(curve, skin, joint, parameters):
        """Flatten the primary-control response at the middle without editing weights.

        Sample the existing B-spline influence and add only its difference from
        a broad quartic profile. The correction is driven by manual center
        displacement, so jaw opening and the neutral surface remain unchanged.
        """
        selection = om.MSelectionList(); selection.add(curve)
        path = selection.getDagPath(0); path.extendToShape()
        fn = om.MFnNurbsCurve(path)
        import maya.api.OpenMayaAnim as oma
        skin_selection = om.MSelectionList(); skin_selection.add(skin)
        skin_fn = oma.MFnSkinCluster(skin_selection.getDependNode(0))
        joint_path = om.MSelectionList().add(joint).getDagPath(0)
        influence = next(i for i, p in enumerate(skin_fn.influenceObjects())
                         if p.fullPathName() == joint_path.fullPathName())
        component_fn = om.MFnSingleIndexedComponent()
        component = component_fn.create(om.MFn.kCurveCVComponent)
        component_fn.addElements(range(fn.numCVs))
        all_weights, count = skin_fn.getWeights(path, component)
        weights = [all_weights[i * count + influence] for i in range(fn.numCVs)]
        data = om.MFnNurbsCurveData().create()
        profile = om.MFnNurbsCurve()
        profile.create([om.MPoint(0, w, 0) for w in weights], fn.knots(),
                       fn.degree, fn.form, False, False, data)
        lo, hi = fn.knotDomain
        peak = profile.getPointAtParam((lo + hi) * 0.5).y
        result = []
        for u in parameters:
            t = max(0.0, min(1.0, (u - lo) / (hi - lo)))
            target = peak * (1.0 - (2.0 * t - 1.0) ** 4) ** 2
            result.append(target - profile.getPointAtParam(u).y)
        return result

    def _skin_lip_curve_to_locals(self, skin_cluster, curve, local_jnts):

        """
        Reparte cada CV del rebuild curve entre los 3 joints locales (2 esquinas +
        medio) con un perfil de semielipse para una apertura redondeada: blend
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
                w = math.sqrt(max(0.0, 1.0 - (2.0 * t - 1.0) ** 2))
                vals = [(start_corner, 1.0 - w), (mid_jnt, w)]
            else:
                w = math.sqrt(max(0.0, 1.0 - (2.0 * t - 1.0) ** 2))
                vals = [(mid_jnt, w), (end_corner, 1.0 - w)]
            cmds.skinPercent(skin_cluster, cv, transformValue=vals, zeroRemainingInfluences=True)

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

    @staticmethod
    def _lip_up_curve(curve, name, distance=1.0):
        """Same knots/CV correspondence as the ribbon; offset along its rest normal."""
        selection = om.MSelectionList()
        selection.add(curve)
        path = selection.getDagPath(0)
        path.extendToShape()
        fn = om.MFnNurbsCurve(path)
        cvs = fn.cvPositions(om.MSpace.kWorld)
        points = om.MPointArray()
        for i, point in enumerate(cvs):
            tangent = om.MVector(cvs[min(i + 1, len(cvs) - 1)]) - om.MVector(cvs[max(i - 1, 0)])
            tangent.normalize()
            up = om.MVector(0, 1, 0)
            if abs(tangent * up) > 0.95:
                up = om.MVector(0, 0, 1)
                if abs(tangent * up) > 0.95:
                    up = om.MVector(1, 0, 0)
            binormal = (tangent ^ up).normalize()
            normal = (binormal ^ tangent).normalize()
            points.append(point + normal * distance)
        obj = om.MFnNurbsCurve().create(points, fn.knots(), fn.degree, fn.form, False, True)
        return cmds.rename(om.MFnDagNode(obj).fullPathName(), name)

    @staticmethod
    def _stable_lip_aim(name, pin, auxiliary, corner_matrix, rest_position,
                        preserve_up_direction=False, corner_axes=None):
        """Stateless frame: pin Z plus a guarded auxiliary up direction."""
        def vector_node(suffix, operation, first=None, second=None):
            node = cmds.createNode("vectorProduct", name=name + suffix, ss=True)
            cmds.setAttr(node + ".operation", operation)
            if first:
                cmds.connectAttr(first, node + ".input1")
            if second:
                cmds.connectAttr(second, node + ".input2")
            return node

        pin_pos = cmds.createNode("translationFromMatrix", name=name + "Pin_TFM", ss=True)
        up_pos = cmds.createNode("translationFromMatrix", name=name + "Up_TFM", ss=True)
        cmds.connectAttr(pin, pin_pos + ".input")
        cmds.connectAttr(auxiliary, up_pos + ".input")
        subtract = cmds.createNode("plusMinusAverage", name=name + "Up_PMA", ss=True)
        cmds.setAttr(subtract + ".operation", 2)
        cmds.connectAttr(up_pos + ".output", subtract + ".input3D[0]")
        cmds.connectAttr(pin_pos + ".output", subtract + ".input3D[1]")
        # Normalize only with a guarded divisor: vectorProduct normalization of
        # a zero vector reports an error before the downstream fallback runs.
        distance = cmds.createNode("distanceBetween", name=name + "UpDistance_DST", ss=True)
        cmds.connectAttr(subtract + ".output3D", distance + ".point2")
        divisor = cmds.createNode("condition", name=name + "UpDivisor_CND", ss=True)
        cmds.setAttr(divisor + ".operation", 4)
        cmds.setAttr(divisor + ".secondTerm", 1e-8)
        cmds.setAttr(divisor + ".colorIfTrueR", 1)
        cmds.connectAttr(distance + ".distance", divisor + ".firstTerm")
        cmds.connectAttr(distance + ".distance", divisor + ".colorIfFalseR")
        raw = cmds.createNode("multiplyDivide", name=name + "UpNormal_MDV", ss=True)
        cmds.setAttr(raw + ".operation", 2)
        cmds.connectAttr(subtract + ".output3D", raw + ".input1")
        for axis in "XYZ":
            cmds.connectAttr(divisor + ".outColorR", raw + ".input2" + axis)
        primary = vector_node("Primary_VPR", 3)
        cmds.setAttr(primary + ".input1", 0, 0, 1)
        cmds.connectAttr(pin, primary + ".matrix")
        axes = corner_axes
        if axes is None:
            axes = []
            for label, axis in [("Y", (0, 1, 0)), ("X", (1, 0, 0)), ("Z", (0, 0, 1))]:
                node = vector_node("Corner" + label + "_VPR", 3)
                cmds.setAttr(node + ".input1", *axis)
                cmds.connectAttr(corner_matrix, node + ".matrix")
                cmds.setAttr(node + ".normalizeOutput", 1)
                axes.append(node + ".output")
        primary_length = vector_node("PrimaryLength_VPR", 1, primary + ".output", primary + ".output")
        primary_guard = cmds.createNode("condition", name=name + "PrimarySafety_CND", ss=True)
        cmds.setAttr(primary_guard + ".operation", 4)
        cmds.setAttr(primary_guard + ".secondTerm", 0.5)
        cmds.connectAttr(primary_length + ".outputX", primary_guard + ".firstTerm")
        cmds.connectAttr(axes[2], primary_guard + ".colorIfTrue")
        cmds.connectAttr(primary + ".output", primary_guard + ".colorIfFalse")
        primary = cmds.createNode("vectorProduct", name=name + "SafePrimary_VPR", ss=True)
        cmds.setAttr(primary + ".operation", 0)
        cmds.setAttr(primary + ".normalizeOutput", 1)
        cmds.connectAttr(primary_guard + ".outColor", primary + ".input1")
        cross = vector_node("FallbackCross_VPR", 2, primary + ".output", axes[0])
        length = vector_node("FallbackLength_VPR", 1, cross + ".output", cross + ".output")
        fallback = cmds.createNode("condition", name=name + "Fallback_CND", ss=True)
        cmds.setAttr(fallback + ".operation", 4)
        cmds.setAttr(fallback + ".secondTerm", 0.01)
        cmds.connectAttr(length + ".outputX", fallback + ".firstTerm")
        cmds.connectAttr(axes[1], fallback + ".colorIfTrue")
        cmds.connectAttr(axes[0], fallback + ".colorIfFalse")
        # A transported control normal already has an authored, continuous sign.
        # Comparing it with another orthogonal control axis makes floating-point
        # noise choose its hemisphere, flipping neighbouring controls by 180 deg.
        up_direction = raw + ".output"
        if not preserve_up_direction:
            dot = vector_node("UpSign_VPR", 1, up_direction, fallback + ".outColor")
            negate = cmds.createNode("multiplyDivide", name=name + "UpNegate_MDV", ss=True)
            cmds.connectAttr(up_direction, negate + ".input1")
            cmds.setAttr(negate + ".input2", -1, -1, -1)
            sign = cmds.createNode("condition", name=name + "UpSign_CND", ss=True)
            cmds.setAttr(sign + ".operation", 4)
            cmds.connectAttr(dot + ".outputX", sign + ".firstTerm")
            cmds.connectAttr(negate + ".output", sign + ".colorIfTrue")
            cmds.connectAttr(up_direction, sign + ".colorIfFalse")
            up_direction = sign + ".outColor"
        cross = vector_node("UpCross_VPR", 2, primary + ".output", up_direction)
        length = vector_node("UpLength_VPR", 1, cross + ".output", cross + ".output")
        # Blend to fallback before reaching the singularity, rather than snap.
        weight = cmds.createNode("remapValue", name=name + "UpSafety_RMV", ss=True)
        cmds.connectAttr(length + ".outputX", weight + ".inputValue")
        cmds.setAttr(weight + ".inputMin", 0.01)
        cmds.setAttr(weight + ".inputMax", 0.09)
        cmds.setAttr(weight + ".value[0].value_Interp", 2)
        cmds.setAttr(weight + ".value[1].value_Interp", 2)
        blend = cmds.createNode("blendColors", name=name + "UpSafety_BLC", ss=True)
        cmds.connectAttr(weight + ".outValue", blend + ".blender")
        cmds.connectAttr(up_direction, blend + ".color1")
        cmds.connectAttr(fallback + ".outColor", blend + ".color2")
        aim = cmds.createNode("aimMatrix", name=name + "Vector_AMX", ss=True)
        if cmds.nodeType(pin.split(".", 1)[0]) == "uvPin":
            # uvPin supplies a rigid frame. Two-axis aiming replaces its rotation
            # and retains its position without rebuilding a translation matrix.
            cmds.connectAttr(pin, aim + ".inputMatrix")
        else:
            # Generic callers may supply scale/shear or a degenerate matrix.
            position = cmds.createNode("composeMatrix", name=name + "Position_CMX", ss=True)
            cmds.connectAttr(pin_pos + ".output", position + ".inputTranslate")
            cmds.connectAttr(position + ".outputMatrix", aim + ".inputMatrix")
        cmds.setAttr(aim + ".primaryInputAxis", 0, 0, 1)
        cmds.connectAttr(primary + ".output", aim + ".primaryTargetVector")
        cmds.setAttr(aim + ".primaryMode", 2)
        cmds.setAttr(aim + ".secondaryInputAxis", 0, 1, 0)
        cmds.setAttr(aim + ".secondaryMode", 2)
        cmds.connectAttr(blend + ".output", aim + ".secondaryTargetVector")
        # Preserve the authored rest point and identity frame, as in the matrix rig.
        rest = om.MMatrix([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, *rest_position, 1])
        offset = rest * om.MMatrix(cmds.getAttr(aim + ".outputMatrix")).inverse()
        result = cmds.createNode("multMatrix", name=name + "Rest_MMX", ss=True)
        cmds.setAttr(result + ".matrixIn[0]", list(offset), type="matrix")
        cmds.connectAttr(aim + ".outputMatrix", result + ".matrixIn[1]")
        return aim, result + ".matrixSum"

    @staticmethod
    def _corner_drag_weight(station):
        t = min(1.0, max(0.0, station))
        return 1.0 - t * t * (3.0 - 2.0 * t)

    @staticmethod
    def _round_raised_lip_frames(name, frames, corner_drags, half_width, stations=None, offsets=None, center_follow=.3):
        """Round corner translation while leaving each lip's own motion independent.

        Capture the neutral X stations once. Only corner displacement drives
        the correction; live upper/lower positions never enter the shared graph.
        Integrate a smoothstep activation so its derivative stays between zero
        and one. The resulting vertical response cannot reverse during a raise.
        A quadratic arc distributes the rise from the middle to the corners
        without coupling either primary lip or a unilateral corner to its peer.
        """
        count = len(frames["upper"])
        mid = count // 2
        rest_x = [sum(cmds.getAttr(frames[part][index])[12] for part in ("upper", "lower")) * .5
                  for index in range(count)]
        stations = stations if stations is not None else [i / float(count - 1) for i in range(count)]

        def scalar(suffix, kind, first, second):
            node = cmds.createNode(kind, name=name + suffix, ss=True)
            inputs = ("input[0]", "input[1]") if kind in ("multiply", "sum") else ("input1", "input2")
            for value, attr in zip((first, second), inputs):
                if isinstance(value, str):
                    cmds.connectAttr(value, node + "." + attr)
                else:
                    cmds.setAttr(node + "." + attr, value)
            return node + ".output"

        def clamp(suffix, source, maximum):
            node = cmds.createNode("clamp", name=name + suffix, ss=True)
            cmds.setAttr(node + ".maxR", maximum)
            cmds.connectAttr(source, node + ".inputR")
            return node + ".outputR"

        rises, spans = {}, {}
        transition = max(half_width * .12, 1e-6)
        for side, end in (("R", 0), ("L", count - 1)):
            normalized = scalar(side + "Rise_DIV", "divide", corner_drags[side] + "y", transition)
            u = clamp(side + "Rise_CLP", normalized, 1)
            square = scalar(side + "RiseSquare_MUL", "multiply", u, u)
            cube = scalar(side + "RiseCube_MUL", "multiply", square, u)
            half_u = scalar(side + "RiseHalf_MUL", "multiply", u, .5)
            slope = scalar(side + "RiseSlope_SUB", "subtract", 1, half_u)
            integral = scalar(side + "RiseIntegral_MUL", "multiply", cube, slope)
            ramp = scalar(side + "RiseRamp_MUL", "multiply", integral, transition)
            excess = scalar(side + "RiseExcess_SUB", "subtract", corner_drags[side] + "y", transition)
            tail = clamp(side + "RiseExcess_CLP", excess, 1e10)
            rises[side] = scalar(side + "Rise_SUM", "sum", ramp, tail)
            sign = -1 if side == "R" else 1
            outward = scalar(side + "Outward_MUL", "multiply", corner_drags[side] + "x", sign)
            width = scalar(side + "Width_SUM", "sum", abs(rest_x[end] - rest_x[mid]), outward)
            safe_width = cmds.createNode("clamp", name=name + side + "Width_CLP", ss=True)
            cmds.setAttr(safe_width + ".minR", 1e-6)
            cmds.setAttr(safe_width + ".maxR", 1e10)
            cmds.connectAttr(width, safe_width + ".inputR")
            spans[side] = safe_width + ".outputR"

        product = scalar("CenterProduct_MUL", "multiply", rises["L"], rises["R"])
        # Follow * harmonic_mean(L, R): no unilateral center/opposite-side motion.
        double_gain = (scalar("CenterDouble_MUL", "multiply", center_follow, 2.)
                       if isinstance(center_follow, str) else 2. * center_follow)
        numerator = scalar("CenterGain_MUL", "multiply", product, double_gain)
        total = scalar("CenterSum_SUM", "sum", rises["L"], rises["R"])
        safe_total = scalar("CenterSafe_SUM", "sum", total, transition * 1e-8)
        center_lift = scalar("CenterRise_DIV", "divide", numerator, safe_total)

        result = {part: list(values) for part, values in frames.items()}
        corrections = [None] * count
        for index in range(1, count - 1):
            if index == mid:
                delta = center_lift
            else:
                side = "R" if index < mid else "L"
                sign = -1 if side == "R" else 1
                t = 2.0 * min(stations[index], 1.0 - stations[index])
                weight = 1.0 - t * t * (3.0 - 2.0 * t)
                shifted = scalar(f"{index:02d}Outward_MUL", "multiply", corner_drags[side] + "x", sign * weight)
                distance = scalar(f"{index:02d}Distance_SUM", "sum", abs(rest_x[index] - rest_x[mid]), shifted)
                ratio = scalar(f"{index:02d}Ratio_DIV", "divide", distance, spans[side])
                bounded = cmds.createNode("clamp", name=f"{name}{index:02d}Ratio_CLP", ss=True)
                cmds.setAttr(bounded + ".maxR", 1)
                cmds.connectAttr(ratio, bounded + ".inputR")
                square = scalar(f"{index:02d}Square_MUL", "multiply", bounded + ".outputR", bounded + ".outputR")
                difference = scalar(f"{index:02d}Delta_SUB", "subtract", square, weight)
                original = scalar(f"{index:02d}Blend_MUL", "multiply", difference, rises[side])
                # Share the same live arc in both terms. Center follow below
                # one half keeps the response ordered even for unequal raises.
                profile = scalar(f"{index:02d}CenterMask_SUB", "subtract", 1., square)
                carried = scalar(f"{index:02d}CenterCarry_MUL", "multiply", center_lift, profile)
                delta = scalar(f"{index:02d}CenterDelta_SUM", "sum", original, carried)
            if offsets is not None:
                for part in ("upper", "lower"):
                    offsets[part][index]["inputs"][1].append(delta)
                continue
            translate = cmds.createNode("composeMatrix", name=f"{name}{index:02d}Delta_CMX", ss=True)
            cmds.connectAttr(delta, translate + ".inputTranslateY")
            corrections[index] = translate + ".outputMatrix"
            for part in ("upper", "lower"):
                matrix = cmds.createNode("multMatrix", name=f"{name}{index:02d}{part}_MMX", ss=True)
                cmds.connectAttr(frames[part][index], matrix + ".matrixIn[0]")
                cmds.connectAttr(corrections[index], matrix + ".matrixIn[1]")
                result[part][index] = matrix + ".matrixSum"
        return result, corrections

    @staticmethod
    def _lip_wide_scalar(name, kind, values):
        """Small native scalar graph used by Auto Wide (no frame callbacks)."""
        node = cmds.createNode(kind, name=name, ss=True)
        inputs = ([f"input[{i}]" for i in range(len(values))]
                  if kind in ("sum", "multiply") else ["input1", "input2"])
        for attr, value in zip(inputs, values):
            if isinstance(value, str):
                cmds.connectAttr(value, node + "." + attr)
            else:
                cmds.setAttr(node + "." + attr, value)
        return node + ".output"

    @staticmethod
    def _lip_smooth_activation(name, source):
        """Bounded smoothstep, with zero slope at rest and saturation."""
        node = cmds.createNode("remapValue", name=name, ss=True)
        cmds.connectAttr(source, node + ".inputValue")
        cmds.setAttr(node + ".inputMax", 1)
        cmds.setAttr(node + ".value[0].value_Interp", 2)
        cmds.setAttr(node + ".value[1].value_Interp", 2)
        return node + ".outValue"

    def _lip_auto_wide_drivers(self, controls, control_frames, half_width, lateral, corner_inputs):
        """Read animator inputs upstream of the corrective to avoid feedback.

        Corners use negative rest-relative local X, independently of Narrow gain.
        Calibrate secondary lateral axes at build, like the corner offset vector.
        Positive inward secondary translations add compression on their own lip
        and side. Outward translations can relieve that compression. The smooth
        remap saturates at one half-width. Jaw/head motion alone cannot drive it.
        """
        scalar = self._lip_wide_scalar
        depths = {}
        for side in ("L", "R"):
            corner = side + "_lipCorner_CTL"
            cmds.addAttr(corner, longName="autoWide", niceName="Auto Wide",
                         attributeType="double", min=0, max=1, defaultValue=1.0, keyable=True)
            gain = scalar(side + "_lipAutoWideGain_MUL", "multiply",
                          [corner + ".autoWide", 1.0])
            depths[side] = scalar(side + "_lipAutoWideDepth_MUL", "multiply", [gain, half_width])
        drivers = {}
        for part, ctls in controls.items():
            inward = {side: [corner_inputs[side]] for side in ("L", "R")}
            mid = len(ctls) // 2
            for index, ctl in enumerate(ctls):
                if index == mid:
                    continue
                side = "R" if index < mid else "L"
                sign = -1 if side == "L" else 1
                frame = cmds.getAttr(control_frames[part][index])
                coefficients = [sign * (om.MVector(*frame[row * 4:row * 4 + 3]) * lateral)
                                / half_width for row in range(3)]
                dot = cmds.createNode("vectorProduct", name=ctl[:-4] + "AutoWideIn_VPR", ss=True)
                cmds.setAttr(dot + ".operation", 1)
                cmds.setAttr(dot + ".input2", *coefficients, type="double3")
                cmds.connectAttr(ctl + ".translate", dot + ".input1")
                inward[side].append(dot + ".outputX")
            drivers[part] = {}
            for side, values in inward.items():
                name = f"{side}_{part}LipAutoWide"
                total = scalar(name + "In_SUM", "sum", values)
                smooth = self._lip_smooth_activation(name + "In_RMV", total)
                drivers[part][side] = scalar(name + "Amount_MUL", "multiply",
                                             [smooth, depths[side]])
            # Harmonic mean is smooth at equal sides, unlike min(L, R).
            # It is zero for unilateral compression, keeping the other half free.
            name = f"C_{part}LipAutoWideShared"
            left, right = (drivers[part][side] for side in ("L", "R"))
            product = scalar(name + "Product_MUL", "multiply", [left, right])
            twice = scalar(name + "Twice_MUL", "multiply", [product, 2])
            total = scalar(name + "Sum_SUM", "sum", [left, right, half_width * 1e-8])
            drivers[part]["center"] = scalar(name + "_DIV", "divide", [twice, total])
        return drivers

    def _auto_wide_lip_frames(self, name, frames, drivers, forward, stations=None, offsets=None):
        """Add a bounded forward bulge once, before sticky/roll and final following.

        Both sides compressed equally produce a center-heavy smoothstep profile.
        A single side fades to zero at the center and cannot move the other half.
        Display and output stations sample the same field independently, so the
        ribbon driver positions are never corrected twice.
        """
        result = {}
        for part, values in frames.items():
            result[part] = list(values)
            params = stations[part] if stations else [i / float(len(values) - 1) for i in range(len(values))]
            for index, (frame, u) in enumerate(zip(values, params)):
                q = min(1.0, abs(2.0 * u - 1.0))
                center = 1.0 - q * q * (3.0 - 2.0 * q)
                if center <= 1e-12:
                    continue
                side = "R" if u < .5 else "L"
                prefix = f"{name}{part}{index:02d}"
                field = cmds.createNode("blendWeighted", name=prefix + "Field_BW", ss=True)
                for slot, (plug, weight) in enumerate(((drivers[part][side], center * (1.0 - center)),
                                                       (drivers[part]["center"], center * center))):
                    cmds.connectAttr(plug, field + f".input[{slot}]")
                    cmds.setAttr(field + f".weight[{slot}]", weight)
                scale = cmds.createNode("multiplyDivide", name=prefix + "Forward_MDV", ss=True)
                cmds.setAttr(scale + ".input1", *forward, type="double3")
                for axis in "XYZ":
                    cmds.connectAttr(field + ".output", scale + ".input2" + axis)
                if offsets is not None:
                    for axis, inputs in zip("XYZ", offsets[part][index]["inputs"]):
                        # Direction is constant: omit identically zero components.
                        if forward["XYZ".index(axis)]:
                            inputs.append(scale + ".output" + axis)
                    continue
                translate = cmds.createNode("composeMatrix", name=prefix + "_CMX", ss=True)
                cmds.connectAttr(scale + ".output", translate + ".inputTranslate")
                matrix = cmds.createNode("multMatrix", name=prefix + "_MMX", ss=True)
                cmds.connectAttr(frame, matrix + ".matrixIn[0]")
                cmds.connectAttr(translate + ".outputMatrix", matrix + ".matrixIn[1]")
                result[part][index] = matrix + ".matrixSum"
        return result

    @staticmethod
    def _finish_lip_offsets(offsets):
        """Sum only translations in double precision, preserving rigid frames.

        Adding matrices at every corrective stage repeats the same operation.
        Scalar sums avoid the float-vector rounding of plusMinusAverage and
        feed one translation matrix per station. Calls may append more fields.
        """
        for offset in offsets:
            for axis, sources in enumerate(offset["inputs"]):
                if not sources:
                    continue
                if len(sources) == 1:
                    output = sources[0]
                else:
                    node = offset["sums"].get(axis)
                    if node is None:
                        node = cmds.createNode("sum", name=offset["compose"][:-4] + "XYZ"[axis] + "_SUM", ss=True)
                        offset["sums"][axis] = node
                    for slot, source in enumerate(sources):
                        destination = node + f".input[{slot}]"
                        if not cmds.isConnected(source, destination):
                            cmds.connectAttr(source, destination)
                    output = node + ".output"
                destination = offset["compose"] + ".inputTranslate" + "XYZ"[axis]
                if not cmds.isConnected(output, destination):
                    cmds.connectAttr(output, destination, force=True)

    def _lip_offset_frame(self, name, frame, translations):
        """Keep display and ribbon bases independent, including at zero weights."""
        compose = cmds.createNode("composeMatrix", name=name + "Offset_CMX", ss=True)
        matrix = cmds.createNode("multMatrix", name=name + "Offset_MMX", ss=True)
        cmds.connectAttr(frame, matrix + ".matrixIn[0]")
        cmds.connectAttr(compose + ".outputMatrix", matrix + ".matrixIn[1]")
        offset = {"compose": compose, "inputs": [[], [], []], "sums": {}}
        for slot, (vector, weight) in enumerate(translations):
            if abs(weight) < 1e-12:
                continue
            scale = cmds.createNode("multiplyDivide", name=f"{name}Offset{slot}_MDV", ss=True)
            cmds.connectAttr(vector, scale + ".input1")
            cmds.setAttr(scale + ".input2", weight, weight, weight)
            for axis, sources in zip("XYZ", offset["inputs"]):
                sources.append(scale + ".output" + axis)
        self._finish_lip_offsets([offset])
        return matrix + ".matrixSum", offset

    def _corner_auto_narrow(self, corner, offset_group, local_matrix, coefficients):
        """Default-on intensity, activated only by positive rest-relative X.

        The calibrated lateral projection handles mirrored control axes. A
        full activation moves a quarter of the mouth's half-width; the existing
        paired-lip falloff carries it from the corner to zero at the center.
        Both the offset and projection pull are zero in the authored rest pose,
        even with autoNarrow=1. Negative X drives Wide through a separate branch.
        Read the control's local matrix, never its world matrix, to avoid a
        feedback loop through the corner's display offset.
        """
        attr = corner + ".autoNarrow"
        if not cmds.objExists(attr):
            cmds.addAttr(corner, longName="autoNarrow", niceName="Auto Narrow",
                         attributeType="float", min=0, max=1, defaultValue=1, keyable=True)
        name = corner.removesuffix("_CTL") + "AutoNarrow"
        coefficients = om.MVector(*coefficients)
        magnitude = coefficients * coefficients
        if magnitude <= 1e-12 or abs(coefficients.x) <= 1e-12:
            raise ValueError("Cannot determine lateral lip direction for " + corner)
        side = corner.split("_")[0]
        scalar = self._lip_wide_scalar
        rest = scalar(side + "_lipRestX_SUB", "subtract",
                      [corner + ".translateX", cmds.getAttr(corner + ".translateX")])
        signed_x = scalar(side + "_lipSignedX_MUL", "multiply", [rest, abs(coefficients.x)])
        activation = self._lip_smooth_activation(name + "Activation_RMV", signed_x)
        narrow = scalar(side + "_lipNarrow_MUL", "multiply", [activation, attr])
        wide_input = scalar(side + "_lipWideInput_MUL", "multiply", [signed_x, -1.0])
        inward = coefficients * (-0.25 / magnitude)
        translation = cmds.createNode("multiplyDivide", name=name + "_MDV", ss=True)
        cmds.setAttr(translation + ".input1", *inward, type="double3")
        for axis in "XYZ":
            cmds.connectAttr(narrow, translation + ".input2" + axis)
        compose = cmds.createNode("composeMatrix", name=name + "_CMX", ss=True)
        cmds.connectAttr(translation + ".output", compose + ".inputTranslate")
        cmds.connectAttr(compose + ".outputMatrix", offset_group + ".offsetParentMatrix")
        effective = cmds.createNode("multMatrix", name=name + "_MMX", ss=True)
        cmds.connectAttr(corner + ".matrix", effective + ".matrixIn[0]")
        cmds.connectAttr(compose + ".outputMatrix", effective + ".matrixIn[1]")
        cmds.connectAttr(effective + ".matrixSum", local_matrix + ".matrixIn[0]", force=True)
        return narrow, wide_input

    @staticmethod
    def _corner_drag_driver(side, corner_joint, jaw_blend, parent):
        """Separate animator corner displacement from its jaw-follow baseline."""
        baseline = cmds.createNode("multMatrix", name=f"{side}_cornerLipBase_MMX", ss=True)
        rest = om.MMatrix(cmds.getAttr(f"{corner_joint}.worldMatrix[0]"))
        jaw_plug = jaw_blend if "." in jaw_blend else f"{jaw_blend}.matrixSum"
        jaw_rest = om.MMatrix(cmds.getAttr(jaw_plug))
        cmds.setAttr(f"{baseline}.matrixIn[0]", list(rest * jaw_rest.inverse()), type="matrix")
        cmds.connectAttr(jaw_plug, f"{baseline}.matrixIn[1]")
        joint = cmds.createNode("joint", name=f"{side}_cornerLipBase_JNT", ss=True, parent=parent)
        cmds.connectAttr(f"{baseline}.matrixSum", f"{joint}.offsetParentMatrix")
        current = cmds.createNode("translationFromMatrix", name=f"{side}_cornerLipDrag_TFM", ss=True)
        original = cmds.createNode("translationFromMatrix", name=f"{side}_cornerLipBase_TFM", ss=True)
        cmds.connectAttr(f"{corner_joint}.worldMatrix[0]", f"{current}.input")
        cmds.connectAttr(f"{baseline}.matrixSum", f"{original}.input")
        delta = cmds.createNode("plusMinusAverage", name=f"{side}_cornerLipDrag_PMA", ss=True)
        cmds.setAttr(f"{delta}.operation", 2)
        cmds.connectAttr(f"{current}.output", f"{delta}.input3D[0]")
        cmds.connectAttr(f"{original}.output", f"{delta}.input3D[1]")
        return joint, f"{delta}.output3D"

    @staticmethod
    def _add_corner_drag(name, frame, delta, weight):
        """Add the same weighted world displacement to paired lip stations."""
        scale = cmds.createNode("multiplyDivide", name=name + "CornerDrag_MDV", ss=True)
        cmds.connectAttr(delta, scale + ".input1")
        cmds.setAttr(scale + ".input2", weight, weight, weight)
        translate = cmds.createNode("composeMatrix", name=name + "CornerDrag_CMX", ss=True)
        cmds.connectAttr(scale + ".output", translate + ".inputTranslate")
        result = cmds.createNode("multMatrix", name=name + "CornerDrag_MMX", ss=True)
        cmds.connectAttr(frame, result + ".matrixIn[0]")
        cmds.connectAttr(translate + ".outputMatrix", result + ".matrixIn[1]")
        return result + ".matrixSum"

    @staticmethod
    def _add_corner_rotation(name, frame, corner, pivot, weight, basis=None):
        """Rotate a lip station about its corner, fading to the mouth center.

        Use the jaw-follow pivot in the module's deformation space; head and
        main-mouth transforms are applied downstream. Blend the local rotation
        before changing basis so mirrored controls and rotateOrder work without
        scaling or shifting the pivot.
        """
        if weight <= 0.0:
            return frame
        if basis is None:
            rotation = cmds.createNode("pickMatrix", name=name + "CornerRotation_PCM", ss=True)
            cmds.connectAttr(corner + ".matrix", rotation + ".inputMatrix")
            for component in ("Translate", "Scale", "Shear"):
                cmds.setAttr(rotation + ".use" + component, 0)
            inverse = cmds.createNode("inverseMatrix", name=name + "CornerPivot_IMX", ss=True)
            cmds.connectAttr(pivot, inverse + ".inputMatrix")
            basis = (rotation + ".outputMatrix", inverse + ".outputMatrix", {})
        rotations = basis[2] if len(basis) > 2 else {}
        if weight not in rotations:
            blend = cmds.createNode("blendMatrix", name=name + "CornerRotation_BMX", ss=True)
            cmds.connectAttr(basis[0], blend + ".target[0].targetMatrix")
            cmds.setAttr(blend + ".target[0].weight", weight)
            rotations[weight] = blend + ".outputMatrix"
        result = cmds.createNode("multMatrix", name=name + "CornerRotation_MMX", ss=True)
        for index, plug in enumerate((frame, basis[1],
                                      rotations[weight], pivot)):
            cmds.connectAttr(plug, result + f".matrixIn[{index}]")
        return result + ".matrixSum"

    def _sticky_meeting_frames(self, frames, mouth_height_rev):
        """Preserve matching layouts; interpolate opposing stations for unequal lips."""
        def sample(part, position, name):
            row = frames[part]
            offset = position*(len(row)-1)
            lo = int(offset)
            hi = min(lo+1, len(row)-1)
            weight = offset-lo
            if lo == hi or weight < 1e-10:
                return row[lo]
            node = cmds.createNode('blendMatrix', name=name+'_BMX', ss=True)
            cmds.connectAttr(row[lo], node+'.inputMatrix')
            cmds.connectAttr(row[hi], node+'.target[0].targetMatrix')
            cmds.setAttr(node+'.target[0].weight', weight)
            return node+'.outputMatrix'
        matching = len(frames['upper']) == len(frames['lower'])
        result = {}
        for part in (('upper',) if matching else ('upper', 'lower')):
            plugs = []
            count = len(frames[part])
            for i in range(count):
                name = ('C_lipsZipMeet' if matching else 'C_'+part+'LipsZipMeet')+str(i).zfill(2)
                u = i/float(max(1, count-1))
                upper = frames['upper'][i] if part == 'upper' else sample('upper', u, name+'Upper')
                lower = frames['lower'][i] if part == 'lower' or matching else sample('lower', u, name+'Lower')
                meet = cmds.createNode('wtAddMatrix', name=name+'_WAM', ss=True)
                cmds.connectAttr(upper, meet+'.wtMatrix[0].matrixIn')
                cmds.connectAttr(lower, meet+'.wtMatrix[1].matrixIn')
                cmds.connectAttr(self.jaw_ctl+'.mouthHeight', meet+'.wtMatrix[0].weightIn')
                cmds.connectAttr(mouth_height_rev+'.outputX', meet+'.wtMatrix[1].weightIn')
                plugs.append(meet+'.matrixSum')
            result[part] = plugs
        if matching:
            result['lower'] = result['upper']
        return result

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
        # Narrow modifies projection inputs; the shared surface stays unchanged.
        # Project each lip control once onto this single guide-derived surface.

        # Create a bbox
        bbox = cmds.exactWorldBoundingBox(self.sphere)
        
        center = [
            (bbox[0] + bbox[3]) / 2,
            (bbox[1] + bbox[4]) / 2,
            (bbox[2] + bbox[5]) / 2
        ]
        self.mouth_center = center

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
        self.lips_controllers_grp = lips_controllers_grp
        main_lips_controllers = cmds.createNode("transform", name="C_primaryLipsControllers_GRP", ss=True, p=lips_controllers_grp)

        # Grupo propio para los joints de LABIO (separado de los del jaw), para que
        # el main de boca pueda mover solo los labios.
        self.lips_skinning_grp = cmds.createNode("transform", name="C_lipsSkinning_GRP", ss=True, p=self.skeleton_grp)

        # Create upper controller
        upper_lip_nodes, upper_lip_ctl = curve_tool.create_controller("C_upperLip", offset=["GRP", "OFF"], parent=main_lips_controllers)
        curve_tool.lock_attributes(upper_lip_ctl, ["v"])
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
        curve_tool.lock_attributes(lower_lip_ctl, ["v"])
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
        corner_drags = {}
        corner_pivots = {}
        corner_offsets = {}
        corner_local_matrices = {}

        # Create corner controllers
        for side in ["L", "R"]:
            
            # Create corner controller and place them
            aim_vector = (0, 0, -1)

            corner_nodes, corner_ctl = curve_tool.create_controller(f"{side}_lipCorner", offset=["GRP", "OFF"], parent=main_lips_controllers)
            curve_tool.lock_attributes(corner_ctl, ["sx", "sy", "sz", "v"])
            mtp_corner_lip = cmds.createNode("motionPath", name=f"{side}_lipCorner_MTP", ss=True)
            cmds.connectAttr(f"{self.upper_linear_lip_curve}.worldSpace[0]", f"{mtp_corner_lip}.geometryPath")
            corner_nodes_ctls.append(corner_nodes[0])
            corner_controllers.append(corner_ctl)
            corner_offsets[side] = corner_nodes[1]

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

            parent_matrix_blender = cmds.createNode("parentMatrix", name=f"{side}_lipCorner_PMX", ss=True)
            cmds.connectAttr(f"{aim_matrix_corner}.outputMatrix", f"{parent_matrix_blender}.inputMatrix")
            cmds.connectAttr(f"{self.mult_matrix_jaw_local}.matrixSum", f"{parent_matrix_blender}.target[0].targetMatrix")
            cmds.connectAttr(f"{self.mult_matrix_upper_jaw_local}.matrixSum", f"{parent_matrix_blender}.target[1].targetMatrix")
            reverse_blender = cmds.createNode("reverse", name=f"{side}_lipCorner_REV", ss=True)
            cmds.connectAttr(f"{corner_ctl}.Height", f"{reverse_blender}.inputX")
            cmds.connectAttr(f"{reverse_blender}.outputX", f"{parent_matrix_blender}.target[0].weight")
            cmds.connectAttr(f"{corner_ctl}.Height", f"{parent_matrix_blender}.target[1].weight")
            cmds.connectAttr(f"{parent_matrix_blender}.outputMatrix", f"{corner_nodes[0]}.offsetParentMatrix")
            corner_pivots[side] = f"{parent_matrix_blender}.outputMatrix"

            cmds.setAttr(f"{parent_matrix_blender}.target[0].offsetMatrix", self.get_offset_matrix(f"{aim_matrix_corner}.outputMatrix", f"{self.mult_matrix_jaw_local}.matrixSum"), type="matrix")
            cmds.setAttr(f"{parent_matrix_blender}.target[1].offsetMatrix", self.get_offset_matrix(f"{aim_matrix_corner}.outputMatrix", f"{self.mult_matrix_upper_jaw_local}.matrixSum"), type="matrix")
            

            local_jnt = cmds.createNode("joint", name=f"{side}_cornerLip_JNT", ss=True, p=self.module_trn)
            mmx_local = cmds.createNode("multMatrix", name=f"{side}_lowerLipLocal_MMT", ss=True)
            corner_local_matrices[side] = mmx_local
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

            base_corner, corner_drags[side] = self._corner_drag_driver(
                side, local_jnt, wta_local, self.module_trn)
            # Keep the ellipse profile for central/jaw opening. Animator corner
            # translation is added separately, with a wider shared falloff.
            upper_local_jnts.append(base_corner)
            lower_local_jnts.append(base_corner)
            if side == "L":
                upper_local_jnts.append(upper_local_jnt)
                lower_local_jnts.append(lower_local_jnt)


        # Signed local X drives independent, default-on corrective intensities.
        # Capture the neutral axes once; jaw/head following cannot activate them.
        start_pos = om.MVector(*cmds.xform(corner_controllers[0], q=True, ws=True, t=True))
        end_pos = om.MVector(*cmds.xform(corner_controllers[1], q=True, ws=True, t=True))
        rest_dist = (end_pos - start_pos).length() or 1.0

        half = rest_dist / 2.0
        corner_pos = {c.split("_")[0]: om.MVector(*cmds.xform(c, q=True, ws=True, t=True))
                      for c in corner_controllers}
        narrow_drivers, wide_inputs = {}, {}
        for ctl in corner_controllers:
            side = ctl.split("_")[0]
            # Measure all three neutral axes to construct a purely lateral inward
            # offset on mirrored/rotated controls. Only local X drives activation;
            # its projected magnitude sets a scale-relative response distance.
            p0 = corner_pos[side]
            other = corner_pos["R" if side == "L" else "L"]
            outdir = (p0 - other).normal()
            jac = []
            for ax in "XYZ":
                cmds.setAttr(f"{ctl}.translate{ax}", 1.0)
                p1 = om.MVector(*cmds.xform(ctl, q=True, ws=True, t=True))
                cmds.setAttr(f"{ctl}.translate{ax}", 0.0)
                jac.append(((p1 - p0) * outdir) / half)
            narrow_drivers[side], wide_inputs[side] = self._corner_auto_narrow(
                ctl, corner_offsets[side], corner_local_matrices[side], jac)
        # Central narrowing needs both sides; a single side leaves the center
        # and the opposite half untouched.
        in_min = cmds.createNode("condition", name="C_lipNarrowMin_COND", ss=True)
        cmds.setAttr(f"{in_min}.operation", 4)  # Less Than
        cmds.connectAttr(narrow_drivers["L"], f"{in_min}.firstTerm")
        cmds.connectAttr(narrow_drivers["R"], f"{in_min}.secondTerm")
        cmds.connectAttr(narrow_drivers["L"], f"{in_min}.colorIfTrueR")
        cmds.connectAttr(narrow_drivers["R"], f"{in_min}.colorIfFalseR")
        in_center = f"{in_min}.outColorR"

        # Corners already project their effective, inward-offset local matrix.
        # Pulling them toward the center again doubles Narrow, pinching the low
        # head mesh and changing the raised U. Only central inputs need a pull.
        def _narrow_pull(name, rfm, cps, in_plug):
            f_sub = cmds.createNode("subtract", name=f"{name}PullF_SUB", ss=True)
            cmds.setAttr(f"{f_sub}.input1", 1.0)
            f_mul = cmds.createNode("multiply", name=f"{name}PullF_MUL", ss=True)
            cmds.connectAttr(in_plug, f"{f_mul}.input[0]")
            cmds.setAttr(f"{f_mul}.input[1]", 0.5)  # ponytail: pull max 50% hacia el centro
            cmds.connectAttr(f"{f_mul}.output", f"{f_sub}.input2")
            rel = cmds.createNode("plusMinusAverage", name=f"{name}PullRel_PMA", ss=True)
            cmds.setAttr(f"{rel}.operation", 2)
            for i, ax in enumerate("XYZ"):
                cmds.connectAttr(f"{rfm}.output{ax}", f"{rel}.input3D[0].input3D{ax.lower()}")
            cmds.setAttr(f"{rel}.input3D[1]", *self.mouth_center, type="double3")
            sc = cmds.createNode("multiplyDivide", name=f"{name}PullScl_MUL", ss=True)
            cmds.connectAttr(f"{rel}.output3D", f"{sc}.input1")
            for ax in "XYZ":
                cmds.connectAttr(f"{f_sub}.output", f"{sc}.input2{ax}")
            add = cmds.createNode("plusMinusAverage", name=f"{name}Pull_PMA", ss=True)
            cmds.connectAttr(f"{sc}.output", f"{add}.input3D[0]")
            cmds.setAttr(f"{add}.input3D[1]", *self.mouth_center, type="double3")
            for ax in "XYZ":
                cmds.connectAttr(f"{add}.output3D.output3D{ax.lower()}", f"{cps}.inPosition{ax}", force=True)
        _narrow_pull("C_upperLip", rfm_upper_local, cps_upper_local, in_center)
        _narrow_pull("C_lowerLip", rfm_lower_local, cps_lower_local, in_center)

        # Keep the shared projection surface fixed. C_mainMouth applies mouth
        # following downstream, without moving the opposite lip's projection target.

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
        center_drags = {}
        for part, joint in [("upper", upper_local_jnt), ("lower", lower_local_jnt)]:
            _, center_drags[part] = self._corner_drag_driver(
                f"C_{part}Center", joint, f"C_{part}LipLocal_PMX.outputMatrix", self.module_trn)
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
        all_secondary_display_frames = {}
        all_secondary_controls = {}
        all_secondary_control_frames = {}
        all_secondary_stations = {}
        display_offsets = {"upper": [], "lower": []}
        corner_rotation_bases = {}
        corner_aim_axes = {}
        for corner in corner_controllers:
            side = corner.split("_")[0]
            rotation = cmds.createNode("pickMatrix", name=side + "_lipCornerRotation_PCM", ss=True)
            cmds.connectAttr(corner + ".matrix", rotation + ".inputMatrix")
            for component in ("Translate", "Scale", "Shear"):
                cmds.setAttr(rotation + ".use" + component, 0)
            inverse = cmds.createNode("inverseMatrix", name=side + "_lipCornerPivot_IMX", ss=True)
            cmds.connectAttr(corner_pivots[side], inverse + ".inputMatrix")
            corner_rotation_bases[side] = (rotation + ".outputMatrix", inverse + ".outputMatrix", {})
            corner_aim_axes[side] = []
            for label, axis in (("Y", (0, 1, 0)), ("X", (1, 0, 0)), ("Z", (0, 0, 1))):
                node = cmds.createNode("vectorProduct", name=side + "_lipCorner" + label + "_VPR", ss=True)
                cmds.setAttr(node + ".operation", 3)
                cmds.setAttr(node + ".input1", *axis)
                cmds.setAttr(node + ".normalizeOutput", 1)
                cmds.connectAttr(corner + ".worldMatrix[0]", node + ".matrix")
                corner_aim_axes[side].append(node + ".output")

        for part, nurbs in (["upper", self.upper_lip_nurbs], ["lower", self.lower_lip_nurbs]):

            curve = self.upper_rebuild_lip_curve if part == "upper" else self.lower_rebuild_lip_curve
            mid_point = rebuilded_cvs // 2

            cv_parameters = self._curve_cv_parameters(curve)
            secondary_grps = []
            secondary_ctls = []
            secondary_local_joints_mmx = []
            secondary_display_frames = []
            secondary_base_frames = []
            secondary_control_frames = []
            display_corrections = self._central_profile_correction(
                curve, f"C_{part}Lip_SKIN", f"C_{part}Lip_JNT", cv_parameters)

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
                curve_tool.lock_attributes(secondary_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])

                secondary_local_joint = cmds.createNode(
                    "joint", name=f"{ctl_name}Driver_JNT", ss=True, parent=self.module_trn
                )


                rebuilded_cv = cmds.ls(f"{curve}.cv[{index}]", flatten=True)[0]
                pos_rebuilded_cv = cmds.xform(rebuilded_cv, query=True, worldSpace=True, translation=True)
                real_param = cv_parameters[index]

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

                drag_side = "R" if real_param <= 0.5 else "L"
                corner = next(c for c in corner_controllers if c.startswith(drag_side + "_"))
                base_frame = self._add_corner_rotation(
                    ctl_name, f"{fbf}.output", corner, corner_pivots[drag_side],
                    self._corner_drag_weight(2.0 * min(real_param, 1.0 - real_param)),
                    basis=corner_rotation_bases[drag_side])
                display_frame, offset = self._lip_offset_frame(
                    ctl_name + "Display", base_frame,
                    [(corner_drags[drag_side], self._corner_drag_weight(2.0 * min(real_param, 1.0 - real_param))),
                     (center_drags[part], display_corrections[index])])
                display_offsets[part].append(offset)
                cmds.connectAttr(display_frame, f"{secondary_nodes[0]}.offsetParentMatrix")

                mult_matrix_secondary_local = cmds.createNode(
                    "multMatrix", name=f"{ctl_name}Local_MMX", ss=True
                )
                cmds.connectAttr(f"{secondary_ctl}.matrix", f"{mult_matrix_secondary_local}.matrixIn[0]")
                cmds.connectAttr(base_frame, f"{mult_matrix_secondary_local}.matrixIn[1]")
                cmds.connectAttr(
                    f"{mult_matrix_secondary_local}.matrixSum",
                    f"{secondary_local_joint}.offsetParentMatrix"
                )

                secondary_grps.append(secondary_nodes[0])
                secondary_ctls.append(secondary_ctl)
                secondary_local_joints_mmx.append(mult_matrix_secondary_local)
                all_secondary_joints[part].append(secondary_local_joint)
                secondary_display_frames.append(display_frame)
                secondary_base_frames.append(base_frame)

            # Targets use pre-aim frames, as in the matrix reference: no
            # controller world matrices enter this graph (no feedback cycle).
            display_positions = []
            for index, frame in enumerate(secondary_display_frames):
                position = cmds.createNode("translationFromMatrix", name=secondary_ctls[index][:-4] + "Neighbor_TFM", ss=True)
                cmds.connectAttr(frame, position + ".input")
                display_positions.append(position + ".output")
            for index, ctl in enumerate(secondary_ctls):
                name = ctl.rsplit("_CTL", 1)[0]
                target_index = index + 1 if index + 1 < len(secondary_ctls) else index - 1
                aimed = self._neighbor_lip_aim(name, secondary_display_frames[index],
                                               secondary_display_frames[target_index],
                                               index == len(secondary_ctls) - 1,
                                               positions=(display_positions[index], display_positions[target_index]))
                cmds.connectAttr(aimed, secondary_grps[index] + ".offsetParentMatrix", force=True)
                secondary_control_frames.append(aimed)
                rotation = cmds.createNode("pickMatrix", name=name + "NeighborRotation_PCM", ss=True)
                cmds.connectAttr(aimed, rotation + ".inputMatrix")
                cmds.setAttr(rotation + ".useTranslate", 0)
                inverse = cmds.createNode("inverseMatrix", name=name + "NeighborBaseInverse_IMX", ss=True)
                cmds.connectAttr(secondary_base_frames[index], inverse + ".inputMatrix")
                basis = cmds.createNode("multMatrix", name=name + "NeighborBasis_MMX", ss=True)
                cmds.connectAttr(rotation + ".outputMatrix", basis + ".matrixIn[0]")
                cmds.connectAttr(inverse + ".outputMatrix", basis + ".matrixIn[1]")
                vector = cmds.createNode("vectorProduct", name=name + "NeighborTranslate_VPR", ss=True)
                cmds.setAttr(vector + ".operation", 3)
                cmds.connectAttr(ctl + ".translate", vector + ".input1")
                cmds.connectAttr(basis + ".matrixSum", vector + ".matrix")
                local = cmds.createNode("composeMatrix", name=name + "NeighborLocal_CMX", ss=True)
                cmds.connectAttr(vector + ".output", local + ".inputTranslate")
                # Only remap animator translation. Rotating the ribbon's bind
                # frames would alter its neutral CV offsets and previous profiles.
                cmds.connectAttr(local + ".outputMatrix", secondary_local_joints_mmx[index] + ".matrixIn[0]", force=True)

            all_secondary_display_frames[part] = secondary_display_frames
            all_secondary_controls[part] = secondary_ctls
            all_secondary_control_frames[part] = secondary_control_frames
            all_secondary_stations[part] = cv_parameters
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
            # Each ribbon row follows its matching secondary driver. Closest-joint
            # binding mixes neighbouring rows differently across V and pinches corners.
            for row, joint in enumerate(all_secondary_joints[part]):
                cmds.skinPercent(skin_cluster, f"{nurbs}.cv[{row}][*]",
                                 transformValue=[(joint, 1.0)], zeroRemainingInfluences=True)

        lateral = (corner_pos["L"] - corner_pos["R"]).normal()
        forward = lateral ^ om.MVector(0, 1, 0)
        if forward.length() < 1e-8:
            forward = om.MVector(0, 0, 1)
        forward.normalize()
        # Orient depth away from the face using the authored lip arch.
        arch = om.MVector(*cmds.pointPosition(f"{self.upper_linear_lip_curve}.cv[{len(up_cvs) // 2}]", world=True))
        arch -= (corner_pos["L"] + corner_pos["R"]) * .5
        if forward * arch < 0:
            forward *= -1
        auto_wide_drivers = self._lip_auto_wide_drivers(
            all_secondary_controls, all_secondary_control_frames, half, lateral, wide_inputs)

        # Correct the displayed frames only. Output pins receive their own corner
        # correction once; warping ribbon drivers here would apply it twice.
        rounded_display, _ = self._round_raised_lip_frames(
            "C_lipRoundedRibbon", all_secondary_display_frames, corner_drags, half,
            stations=self._curve_cv_parameters(self.upper_rebuild_lip_curve), offsets=display_offsets)
        self._auto_wide_lip_frames(
            "C_lipAutoWideDisplay", rounded_display, auto_wide_drivers,
            forward, stations=all_secondary_stations, offsets=display_offsets)
        for part in ("upper", "lower"):
            self._finish_lip_offsets(display_offsets[part])

        output_joints = { "upper": [], "lower": [] }
        non_rotate_output_joints = { "upper": [], "lower": [] }
        aim_matrices = { "upper": [], "lower": [] }
        orient_plugs = { "upper": [], "lower": [] }
        pick_matrices = { "upper": [], "lower": [] }
        output_stations = {}
        output_offsets = {"upper": [], "lower": []}

        for part, nurbs in (["upper", self.upper_lip_nurbs], ["lower", self.lower_lip_nurbs]):
            
            _skin_curve = self.upper_rebuild_lip_curve if part == "upper" else self.lower_rebuild_lip_curve
            linear_curve = self.upper_linear_lip_curve if part == "upper" else self.lower_linear_lip_curve
            linear_curve_cvs = len(cmds.ls(f"{linear_curve}.cv[*]", flatten=True))
            driver_joints = all_secondary_joints[part]
            mid_point = linear_curve_cvs // 2
            offset_curve = self._lip_up_curve(_skin_curve, f"C_{part}LipOffset_CRV")
            offset_skin = cmds.skinCluster(driver_joints, offset_curve, toSelectedBones=True, bindMethod=0, skinMethod=0, normalizeWeights=1, name=f"C_{part}LipOffset_SKIN")[0]
            for row, joint in enumerate(driver_joints):
                cmds.skinPercent(offset_skin, f"{offset_curve}.cv[{row}]", transformValue=[(joint, 1.0)], zeroRemainingInfluences=True)

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

            

            # El closestPoint sobre la NURB puede caer en el pliegue de la
            # esquina (CVs cruzados en los guides) y devolver el u de la propia
            # esquina (0 o 1) para puntos interiores -> joint clavada en la
            # comisura y desgarro al abrir la jaw. Pre-calcular todos los u y
            # reparar los no monotonicos interpolando los vecinos.
            u_list = []
            for i in range(0, linear_curve_cvs):
                pos = cmds.xform(f"{linear_curve}.cv[{i}]", query=True, worldSpace=True, translation=True)
                u_i, _ = matrix_manager.getClosestParamsToPositionSurface(nurbs, pos)
                u_list.append(u_i)
            u_list = self._ordered_lip_parameters(u_list)
            # Output corner drag uses normalized joint stations. Auto Wide uses
            # those same stations rather than the repaired surface projection U.
            output_stations[part] = [i / float(linear_curve_cvs - 1) for i in range(linear_curve_cvs)]
            center_corrections = self._central_profile_correction(
                self.upper_rebuild_lip_curve if part == "upper" else self.lower_rebuild_lip_curve,
                f"C_{part}Lip_SKIN", f"C_{part}Lip_JNT", u_list)

            for i in range(0, linear_curve_cvs):

                curve_cv = f"{linear_curve}.cv[{i}]"

                if i < mid_point:
                    side = "R"
                    name_index = i  # Empieza en 0 y suma (0, 1, 2...)

                elif i == mid_point:
                    side = "C"
                    name_index = 0  # El centro siempre será 0

                else:
                    side = "L"
                    name_index = (linear_curve_cvs - 1) - i

                u_param = u_list[i]
                vertex_cv_pos = cmds.xform(curve_cv, query=True, worldSpace=True, translation=True)
 
                cmds.setAttr(f"{uv_pin_nurbs}.coordinate[{i}].coordinateU", u_param)
                cmds.setAttr(f"{uv_pin_nurbs}.coordinate[{i}].coordinateV", 0.5)
                # Identical knots and paired CV weights make U identical.
                cmds.setAttr(f"{uv_pin_up}.coordinate[{i}].coordinateU", u_param)
                cmds.setAttr(f"{uv_pin_up}.coordinate[{i}].coordinateV", 0.5)
                corner = next(c for c in corner_controllers if c.startswith("R_" if i <= mid_point else "L_"))
                aim_matrix_vector, frame = self._stable_lip_aim(
                    f"{side}_{part}Lip{name_index:02d}",
                    f"{uv_pin_nurbs}.outputMatrix[{i}]", f"{uv_pin_up}.outputMatrix[{i}]",
                    f"{corner}.worldMatrix[0]", vertex_cv_pos,
                    preserve_up_direction=True,
                    corner_axes=corner_aim_axes["R" if i <= mid_point else "L"])
                frame, offset = self._lip_offset_frame(
                    f"{side}_{part}Lip{name_index:02d}", frame,
                    [(corner_drags["R" if i <= mid_point else "L"],
                      self._corner_drag_weight(min(i, linear_curve_cvs - 1 - i) / float(mid_point))),
                     (center_drags[part], center_corrections[i])])
                output_offsets[part].append(offset)

                out_joint = cmds.createNode("joint", name=f"{side}_{part}Lip{name_index:02d}_JNT", ss=True, parent=self.lips_skinning_grp)
                cmds.connectAttr(frame, f"{out_joint}.offsetParentMatrix")

                aim_matrices[part].append(aim_matrix_vector)
                orient_plugs[part].append(frame)
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

                non_rot_out_joint = cmds.createNode("joint", name=f"{side}_{part}Lip{name_index:02d}NonRot_JNT", ss=True, parent=self.lips_skinning_grp)
                pick_matrix_non_rot = cmds.createNode("pickMatrix", name=f"{side}_{part}Lip{name_index:02d}NonRot_PCM", ss=True)
                cmds.setAttr(f"{pick_matrix_non_rot}.useRotate", 0)
                cmds.connectAttr(orient_plugs[part][i], f"{pick_matrix_non_rot}.inputMatrix")
                cmds.connectAttr(f"{pick_matrix_non_rot}.outputMatrix", f"{non_rot_out_joint}.offsetParentMatrix")
                non_rotate_output_joints[part].append(non_rot_out_joint)
                pick_matrices[part].append(pick_matrix_non_rot)
        


        orient_plugs, _ = self._round_raised_lip_frames(
            "C_lipRoundedOutput", orient_plugs, corner_drags, half, offsets=output_offsets)
        orient_plugs = self._auto_wide_lip_frames(
            "C_lipAutoWideOutput", orient_plugs, auto_wide_drivers,
            forward, stations=output_stations, offsets=output_offsets)
        for part in ("upper", "lower"):
            self._finish_lip_offsets(output_offsets[part])
            for index, frame in enumerate(orient_plugs[part]):
                for destination in (output_joints[part][index] + ".offsetParentMatrix",
                                    pick_matrices[part][index] + ".inputMatrix"):
                    if not cmds.isConnected(frame, destination):
                        cmds.connectAttr(frame, destination, force=True)

        # ----- ANTI-PINCH DE ESQUINAS -----
        # Upper/lower share the control's rest-compensated corner orientation.
        # Smoothstep fades this frame into the interior without changing position.
        corner_frames = {}
        for part in ("upper", "lower"):
            n_out = len(output_joints[part])
            corner_blend = min(6, n_out // 2)
            for corner_idx in (0, n_out-1):
                corner_side = "R" if corner_idx == 0 else "L"
                for k in range(corner_blend):
                    idx = corner_idx+k if corner_idx == 0 else corner_idx-k
                    t = k/float(max(1, corner_blend-1))
                    w = 1.0-t*t*(3.0-2.0*t)
                    if w <= 1e-12:
                        continue
                    key = corner_side
                    if key not in corner_frames:
                        corner = next(c for c in corner_controllers if c.startswith(corner_side+"_"))
                        avg = cmds.createNode("multMatrix", name=f"C_lipCorner{idx:02d}Frame_MMX", ss=True)
                        rest_corner = om.MMatrix(cmds.getAttr(corner+".worldMatrix[0]"))
                        cmds.setAttr(avg+".matrixIn[0]", list(rest_corner.inverse()), type="matrix")
                        cmds.connectAttr(corner+".worldMatrix[0]", avg+".matrixIn[1]")
                        corner_frames[key] = avg
                    avg = corner_frames[key]
                    own = orient_plugs[part][idx]
                    jb = cmds.createNode("blendMatrix", name=f"C_{part}LipCorner{idx:02d}Blend_BMX", ss=True)
                    cmds.connectAttr(own, jb+".inputMatrix")
                    cmds.connectAttr(avg+".matrixSum", jb+".target[0].targetMatrix")
                    cmds.setAttr(jb+".target[0].translateWeight", 0)
                    cmds.setAttr(jb+".target[0].rotateWeight", w)
                    cmds.setAttr(jb+".target[0].scaleWeight", 0)
                    cmds.setAttr(jb+".target[0].shearWeight", 0)
                    orient_plugs[part][idx] = jb+".outputMatrix"
                    cmds.connectAttr(jb+".outputMatrix", output_joints[part][idx]+".offsetParentMatrix", force=True)

        # ----- MANUAL STICKY LIPS (jaw_module_matrix setup) -----
        # Close corners first, then center. Independent of jaw rotation.
        cmds.addAttr(self.jaw_ctl, longName="mouthHeight", attributeType="float", min=0, max=1, defaultValue=0.5, keyable=True)
        cmds.addAttr(self.jaw_ctl, longName="stickyLips", niceName="Sticky Lips", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)
        cmds.addAttr(self.jaw_ctl, longName="stickyFalloff", niceName="Sticky Falloff", attributeType="float", min=0.001, max=1, defaultValue=0.2, keyable=True)
        mouth_height_rev = cmds.createNode("reverse", name="C_lipsMouthHeight_REV", ss=True)
        cmds.connectAttr(f"{self.jaw_ctl}.mouthHeight", f"{mouth_height_rev}.inputX")

        # Reference weights: upper * mouthHeight + lower * (1-mouthHeight).
        meeting_plugs = self._sticky_meeting_frames(orient_plugs, mouth_height_rev)
        sticky_weights = {}

        for part in ["upper", "lower"]:

            roll_controller = upper_lip_ctl if part == "upper" else lower_lip_ctl
            roll_rx_deg = cmds.createNode("multiply", name=f"C_{part}LipRollRxDeg_MUL", ss=True)
            cmds.connectAttr(roll_controller + ".rotateX", roll_rx_deg + ".input[0]")
            cmds.setAttr(roll_rx_deg + ".input[1]", 1.0)
            roll_drive = cmds.createNode("plusMinusAverage", name=f"C_{part}LipRollDrive_PMA", ss=True)
            cmds.connectAttr(roll_rx_deg + ".output", roll_drive + ".input1D[0]")
            cmds.connectAttr(roll_controller + ".Roll", roll_drive + ".input1D[1]")

            for i, (non_rot_joint, out_joint) in enumerate(zip(non_rotate_output_joints[part], output_joints[part])):

                real_index = i if i <= mid_point else (linear_curve_cvs - 1) - i

                side = non_rot_joint.split("_")[0]

                # Same falloff as the matrix module: inputMin stays at zero,
                # inputMax = normalized distance from corner * .7 + falloff.
                t_stick = float(real_index) / float(mid_point) if mid_point else 0.0
                if t_stick not in sticky_weights:
                    prefix = f"C_lipsSticky{len(sticky_weights):02d}"
                    sticky_rmv = cmds.createNode("remapValue", name=prefix + "_RMV", ss=True)
                    cmds.connectAttr(f"{self.jaw_ctl}.stickyLips", f"{sticky_rmv}.inputValue")
                    falloff_sum = cmds.createNode("sum", name=prefix + "Falloff_SUM", ss=True)
                    cmds.setAttr(f"{falloff_sum}.input[0]", t_stick * 0.7)
                    cmds.connectAttr(f"{self.jaw_ctl}.stickyFalloff", f"{falloff_sum}.input[1]")
                    cmds.connectAttr(f"{falloff_sum}.output", f"{sticky_rmv}.inputMax")
                    cmds.setAttr(f"{sticky_rmv}.outputMin", 0)
                    cmds.setAttr(f"{sticky_rmv}.outputMax", 1)
                    sticky_weights[t_stick] = f"{sticky_rmv}.outValue"
                sticky_weight = sticky_weights[t_stick]

                # Conexión del blendMatrix sticky a la joint de salida.
                blend_matrix_sticky_rot = cmds.createNode("blendMatrix", name=f"{out_joint}Sticky_BMX", ss=True)
                cmds.connectAttr(orient_plugs[part][i], f"{blend_matrix_sticky_rot}.inputMatrix")
                cmds.connectAttr(meeting_plugs[part][i], f"{blend_matrix_sticky_rot}.target[0].targetMatrix")
                cmds.connectAttr(sticky_weight, f"{blend_matrix_sticky_rot}.target[0].weight")
                # Match reference rotation blend; keep scale/shear out of
                # the weighted matrix average to avoid shrinking the lip frame.
                cmds.setAttr(f"{blend_matrix_sticky_rot}.target[0].scaleWeight", 0)
                cmds.setAttr(f"{blend_matrix_sticky_rot}.target[0].shearWeight", 0)
                cmds.connectAttr(f"{blend_matrix_sticky_rot}.outputMatrix", f"{out_joint}.offsetParentMatrix", f=True)

                # Non Rotate shares the solved sticky position and strips rotation.
                # Roll stays on the Rotate joint's local channel downstream.
                cmds.connectAttr(blend_matrix_sticky_rot + ".outputMatrix",
                                 pick_matrices[part][i] + ".inputMatrix", force=True)
                destination = non_rot_joint + ".offsetParentMatrix"
                if not cmds.isConnected(pick_matrices[part][i] + ".outputMatrix", destination):
                    cmds.connectAttr(pick_matrices[part][i] + ".outputMatrix", destination, force=True)

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
        Controlador main que mueve TODOS los controladores de la boca (mandíbula,
        labios, esquinas y secundarios) y su deformación como un único bloque
        rígido, encima del rig existente.

        El rig deforma con matrices locales rest-relativas (cancelan el movimiento
        del grupo padre), así que SIMPLEMENTE emparentar los controles bajo un main
        los movería en viewport pero NO movería los joints. En su lugar se calcula
        el delta rígido del main (identidad en reposo, independiente de la cara) y se
        inyecta en dos únicos puntos (SOLO labios, la mandíbula NO se mueve):
            - lips_controllers_grp.offsetParentMatrix -> todos los controles de labio siguen en viewport
            - lips_skinning_grp.offsetParentMatrix    -> todos los joints de labio deforman
        """

        main_mouth_nodes, main_mouth_ctl = curve_tool.create_controller(
            "C_mainMouth",
            offset=["GRP", "OFF"],
            parent=self.face_controls_parent
        )
        self.main_mouth_ctl = main_mouth_ctl
        curve_tool.lock_attributes(main_mouth_ctl, ["sx", "sy", "sz", "v"])

        # Colocar en el centro de la boca, eje-alineado (igual que las guías del jaw).
        place = [1, 0, 0, 0,
                 0, 1, 0, 0,
                 0, 0, 1, 0,
                 self.mouth_center[0], self.mouth_center[1], self.mouth_center[2], 1]
        # Sigue a la cabeza: offsetParentMatrix driveado por head.worldMatrix (place
        # guardado en local de la cabeza). El delta se calcula en local del grupo
        # -> identidad cuando solo se mueve la cabeza -> sin doble transformación.
        place_local = list(om.MMatrix(place) * om.MMatrix(cmds.getAttr(f"{self.head_ctl}.worldMatrix[0]")).inverse())
        follow_mmx = cmds.createNode("multMatrix", name="C_mainMouthFollow_MMX", ss=True)
        cmds.setAttr(f"{follow_mmx}.matrixIn[0]", place_local, type="matrix")
        cmds.connectAttr(f"{self.head_ctl}.worldMatrix[0]", f"{follow_mmx}.matrixIn[1]")
        cmds.connectAttr(f"{follow_mmx}.matrixSum", f"{main_mouth_nodes[0]}.offsetParentMatrix")
        # normalizar el grupo (solo offsetParentMatrix manda) ANTES de capturar el reposo
        cmds.xform(main_mouth_nodes[0], m=om.MMatrix.kIdentity)
        cmds.setAttr(f"{main_mouth_nodes[0]}.inheritsTransform", 0)

        # delta LOCAL al grupo (worldInverse EN VIVO): el grupo sigue la cabeza, así que
        # la cabeza se cancela en el delta -> a los labios solo llega lo que el animador
        # mueva el ctl (identidad si solo se mueve la cabeza; sin doble transformación).
        grp_rest = cmds.getAttr(f"{main_mouth_nodes[0]}.worldMatrix[0]")
        local_mmx = cmds.createNode("multMatrix", name="C_mainMouthLocal_MMX", ss=True)
        cmds.connectAttr(f"{main_mouth_ctl}.worldMatrix[0]", f"{local_mmx}.matrixIn[0]")
        cmds.connectAttr(f"{main_mouth_nodes[0]}.worldInverseMatrix[0]", f"{local_mmx}.matrixIn[1]")
        cmds.setAttr(f"{local_mmx}.matrixIn[2]", grp_rest, type="matrix")
        delta_mmx = cmds.createNode("multMatrix", name="C_mainMouthDelta_MMX", ss=True)
        cmds.setAttr(f"{delta_mmx}.matrixIn[0]", list(om.MMatrix(grp_rest).inverse()), type="matrix")
        cmds.connectAttr(f"{local_mmx}.matrixSum", f"{delta_mmx}.matrixIn[1]")

        cmds.connectAttr(f"{delta_mmx}.matrixSum", f"{self.lips_controllers_grp}.offsetParentMatrix", force=True)
        cmds.connectAttr(f"{delta_mmx}.matrixSum", f"{self.lips_skinning_grp}.offsetParentMatrix", force=True)

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
