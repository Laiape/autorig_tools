import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
from importlib import reload
import math

from utils import data_manager
from utils import guides_manager
from utils import curve_tool
from utils import matrix_manager

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)


class LegModule(object):

    """
    Pierna de cuadrúpedo basada en el leg del bípedo:
        - Guías: {side}_{LEG_PREFIX}Hip_JNT -> Knee -> Ankle [-> Ball] -> Tip.
          La cadena de pierna puede ser de 4 joints (Hip/Knee/Ankle/Ball, 3
          huesos) o de 3 (Hip/Knee/Ankle, 2 huesos); el Tip es el pivote de la
          punta del casco. El módulo detecta la longitud automáticamente.
        - solver: "spring" (ikSpringSolver, reparte el bend entre los 3 huesos)
          o "rp" (ikRPsolver hip->ankle + SC para el resto, estilo bípedo).
          Con cadena de 2 huesos siempre se usa RP (spring no aporta nada).
        - FK/IK switch con fk_blend (sin cadena FK de joints), pie reverso
          (foot -> toe -> ball), pole vector calculado del plano real de la
          cadena, stretch FK y atributos de roll/twist en el control del pie.
        - Las guías importadas se quedan como cadena de skinning (renombradas
          a *Skinning_JNT) y las matrices de guía van horneadas (grupos
          freezeados, sin transforms muertos).
    """

    LEG_PREFIX = "backLeg"

    def __init__(self):

        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side, solver="spring", primaryInputAxis=(1, 0, 0), secondaryInputAxis=(0, 1, 0)):

        """
        Args:
            side (str): 'L' o 'R'.
            solver (str): "spring" o "rp".
            primaryInputAxis (tuple): eje que apunta a la siguiente guía.
            secondaryInputAxis (tuple): eje secundario (up).
        """

        if solver not in ("spring", "rp"):
            cmds.error(f"Solver '{solver}' no soportado: usa 'spring' o 'rp'.")

        self.side = side
        self.solver = solver
        self.primary_axis = primaryInputAxis if side == "L" else tuple(-x for x in primaryInputAxis)
        self.secondary_axis = secondaryInputAxis if side == "L" else tuple(-x for x in secondaryInputAxis)

        self.module_name = f"{self.side}_{self.LEG_PREFIX}"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_chains()
        self.controllers_creation()
        self.ik_setup()
        self.ik_stretch_soft()
        self.foot_attributes()
        self.fk_stretch()
        self.skinning_setup()

        data_manager.DataExportBiped().append_data(f"{self.LEG_PREFIX}_module",
                            {
                                f"{self.side}_hip_JNT": self.leg_joints[0],
                                f"{self.side}_legIk": self.ik_controllers[0],
                                f"{self.side}_hipFk": self.fk_controllers[0],
                                f"{self.side}_legPv": self.pv_ctl,
                                f"{self.side}_rootIk": self.root_ik_ctl,
                            })

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    def lock_attributes(self, ctl, attrs):
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)

    def _translation_matrix(self, pos):
        return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, pos.x, pos.y, pos.z, 1]

    def _mirror_matrix(self, matrix_value):
        """Misma matriz de espejo que matrix_manager.mirror_controllers (R side)."""
        cmx = cmds.createNode("composeMatrix", ss=True)
        if abs(self.secondary_axis[0]) == 1:
            cmds.setAttr(f"{cmx}.inputScaleX", -1)
            cmds.setAttr(f"{cmx}.inputRotateX", 180)
        elif abs(self.secondary_axis[2]) == 1:
            cmds.setAttr(f"{cmx}.inputScaleY", -1)
            cmds.setAttr(f"{cmx}.inputRotateZ", 180)
        else:
            cmds.setAttr(f"{cmx}.inputScaleZ", -1)
            cmds.setAttr(f"{cmx}.inputRotateY", 180)
        mirror = om.MMatrix(cmds.getAttr(f"{cmx}.outputMatrix"))
        cmds.delete(cmx)
        return list(mirror * om.MMatrix(matrix_value))

    # ─────────────────────────────────────────────────────────────────────────
    # Build
    # ─────────────────────────────────────────────────────────────────────────
    def load_guides(self):

        self.leg_chain = guides_manager.get_guides(f"{self.side}_{self.LEG_PREFIX}Hip_JNT")
        cmds.parent(self.leg_chain[0], self.module_trn)
        self._setup_chain()

    def _setup_chain(self):

        """
        Indices y matrices de la cadena. Cadena esperada (genérica en número de
        huesos de pierna): Hip [-> FrontKnee -> BackKnee | -> Knee] -> Ankle ->
        Ball -> Tip. El IK principal va de Hip a Ankle; Ball es la pisada y Tip
        el pivote de la punta.
        """
        self.leg_joints = self.leg_chain[:-1]  # todo menos el Tip
        self.tip_joint = self.leg_chain[-1]
        self.plant_index = len(self.leg_chain) - 2          # Ball
        self.leg_end_index = max(2, len(self.leg_chain) - 3)  # Ankle (fin del IK principal)

        # Matrices horneadas (X a la siguiente guía, secondary hacia la previa)
        self.guides_matrices, self.guides_points = guides_manager.orient_guides(
            guides=self.leg_chain, primaryInputAxis=self.primary_axis, secondaryInputAxis=self.secondary_axis
        )
        self.guides_matrices = [cmds.getAttr(attr) for attr in self.guides_matrices]
        self.guide_positions = [om.MVector(m[12], m[13], m[14]) for m in self.guides_matrices]

        # La red de orient_guides ya no hace falta: los valores están horneados
        net = self.guides_points[0].split(".")[0]
        if cmds.objExists(net):
            cmds.delete(net)

    def create_chains(self):

        # Settings ctl junto al pie, desplazado hacia fuera
        leg_length = (self.guide_positions[self.plant_index] - self.guide_positions[0]).length()
        offset = leg_length * 0.25 * (1 if self.side == "L" else -1)
        settings_pos = self.guide_positions[self.plant_index] + om.MVector(offset, 0.0, 0.0)

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.module_name}Settings", offset=["GRP"])
        self.lock_attributes(self.settings_ctl, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v", "rotateOrder"])
        cmds.setAttr(f"{self.settings_node[0]}.offsetParentMatrix", self._translation_matrix(settings_pos), type="matrix")
        cmds.addAttr(self.settings_ctl, longName="Ik_Fk", niceName="Switch IK --> FK", attributeType="float", defaultValue=0, minValue=0, maxValue=1, keyable=True)
        cmds.parent(self.settings_node[0], self.controllers_grp)

        # Cadena IK (no hay cadena FK: los controles FK alimentan el blend)
        self.ik_chain = []
        for joint in self.leg_chain:
            cmds.select(clear=True)
            ik_joint = cmds.joint(name=joint.replace("_JNT", "Ik_JNT"))
            cmds.matchTransform(ik_joint, joint, pos=True, rot=True)
            cmds.makeIdentity(ik_joint, apply=True, translate=True, rotate=True, scale=True, normal=False)
            if self.ik_chain:
                cmds.parent(ik_joint, self.ik_chain[-1])
            self.ik_chain.append(ik_joint)
        cmds.parent(self.ik_chain[0], self.module_trn)

    def controllers_creation(self):

        # ----- FK -----
        self.fk_nodes = []
        self.fk_controllers = []
        self.blend_matrices = []

        fk_controllers_trn = cmds.createNode("transform", name=f"{self.module_name}FkControllers_GRP", ss=True, p=self.controllers_grp)

        for i, joint in enumerate(self.leg_joints):

            fk_node, fk_ctl = curve_tool.create_controller(name=joint.replace("_JNT", "Fk"), offset=["GRP", "ANM"])
            self.lock_attributes(fk_ctl, ["tx", "ty", "tz", "sx", "sy", "sz", "v"])

            if i == 0:
                cmds.setAttr(f"{fk_node[0]}.offsetParentMatrix", self.guides_matrices[0], type="matrix")
            else:
                # opm relativo al FK anterior (grupos freezeados): primero se
                # parenta y después se limpia el local que compensa cmds.parent
                cmds.parent(fk_node[0], self.fk_controllers[-1])
                relative = om.MMatrix(self.guides_matrices[i]) * om.MMatrix(self.guides_matrices[i - 1]).inverse()
                cmds.setAttr(f"{fk_node[0]}.offsetParentMatrix", list(relative), type="matrix")
            cmds.xform(fk_node[0], m=om.MMatrix.kIdentity)

            self.fk_nodes.append(fk_node[0])
            self.fk_controllers.append(fk_ctl)

            ik_joint = self.ik_chain[i]
            prev = self.leg_joints[i - 1] if i > 0 else None
            self.blend_matrices.append(matrix_manager.fk_blend(joint, ik_joint, fk_ctl, prev, self.settings_ctl))

        cmds.parent(self.fk_nodes[0], fk_controllers_trn)

        # ----- IK -----
        ik_controllers_trn = cmds.createNode("transform", name=f"{self.module_name}IkControllers_GRP", ss=True, p=self.controllers_grp)
        reverse_node = cmds.createNode("reverse", name=f"{self.module_name}IkFk_REV", ss=True)
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{reverse_node}.inputX")
        cmds.connectAttr(f"{reverse_node}.outputX", f"{ik_controllers_trn}.visibility")
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{fk_controllers_trn}.visibility")

        plant_matrix = self.guides_matrices[self.plant_index]
        tip_matrix = self.guides_matrices[-1]

        # Pie reverso: footIk (plantado en el suelo) -> toeIk (punta) -> ballIk
        foot_rest = self._translation_matrix(self.guide_positions[self.plant_index])
        if self.side == "R":
            foot_rest = self._mirror_matrix(foot_rest)

        rest_matrices = {
            "footIk": foot_rest,
            "toeIk": tip_matrix,
            "ballIk": plant_matrix,
        }

        self.ik_nodes = []
        self.ik_sdk_nodes = []
        self.ik_controllers = []

        previous_rest = None
        for name, rest in rest_matrices.items():
            ik_node, ik_ctl = curve_tool.create_controller(name=f"{self.module_name}{name[0].upper()}{name[1:]}", offset=["GRP", "SDK"])
            self.lock_attributes(ik_ctl, ["sx", "sy", "sz", "v"])

            if previous_rest is None:
                cmds.setAttr(f"{ik_node[0]}.offsetParentMatrix", rest, type="matrix")
            else:
                # mismo orden que en FK: parentar, opm relativo y freezear
                cmds.parent(ik_node[0], self.ik_controllers[-1])
                relative = om.MMatrix(rest) * om.MMatrix(previous_rest).inverse()
                cmds.setAttr(f"{ik_node[0]}.offsetParentMatrix", list(relative), type="matrix")
            cmds.xform(ik_node[0], m=om.MMatrix.kIdentity)

            previous_rest = rest
            self.ik_nodes.append(ik_node[0])
            self.ik_sdk_nodes.append(ik_node[1])
            self.ik_controllers.append(ik_ctl)

        cmds.parent(self.ik_nodes[0], ik_controllers_trn)

        # Root IK
        self.root_ik_nodes, self.root_ik_ctl = curve_tool.create_controller(name=f"{self.module_name}RootIk", offset=["GRP", "ANM"])
        self.lock_attributes(self.root_ik_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])
        cmds.setAttr(f"{self.root_ik_nodes[0]}.offsetParentMatrix", self.guides_matrices[0], type="matrix")
        cmds.parent(self.root_ik_nodes[0], ik_controllers_trn)
        cmds.xform(self.root_ik_nodes[0], m=om.MMatrix.kIdentity)

        cmds.connectAttr(f"{self.root_ik_ctl}.worldMatrix[0]", f"{self.ik_chain[0]}.offsetParentMatrix")
        for attr in ["translate", "rotate", "jointOrient"]:
            for axis in ["X", "Y", "Z"]:
                cmds.setAttr(f"{self.ik_chain[0]}.{attr}{axis}", 0)
                cmds.setAttr(f"{self.leg_joints[0]}.{attr}{axis}", 0)

        # Pole vector: posición analítica desde el plano real de la cadena
        root_p = self.guide_positions[0]
        knee_p = self.guide_positions[1]
        end_p = self.guide_positions[self.leg_end_index]
        line = (end_p - root_p).normalize()
        projection = root_p + line * ((knee_p - root_p) * line)
        bend_dir = knee_p - projection
        if bend_dir.length() < 1e-4:
            bend_dir = om.MVector(0.0, 0.0, 1.0)  # cadena recta: fallback hacia delante
        bend_dir.normalize()
        leg_length = (end_p - root_p).length()
        pv_pos = knee_p + bend_dir * (leg_length * 0.5)

        self.pv_nodes, self.pv_ctl = curve_tool.create_controller(name=f"{self.module_name}Pv", offset=["GRP", "ANM"])
        self.lock_attributes(self.pv_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])
        cmds.setAttr(f"{self.pv_nodes[0]}.offsetParentMatrix", self._translation_matrix(pv_pos), type="matrix")
        cmds.parent(self.pv_nodes[0], ik_controllers_trn)
        cmds.xform(self.pv_nodes[0], m=om.MMatrix.kIdentity)

        # Línea que apunta del knee al PV
        crv_point_pv = cmds.curve(d=1, p=[(0, 0, 1), (0, 1, 0)], n=f"{self.module_name}Pv_CRV")
        row_knee = cmds.createNode("rowFromMatrix", name=f"{self.module_name}Pv_RFM", ss=True)
        row_ctl = cmds.createNode("rowFromMatrix", name=f"{self.module_name}PvCtl_RFM", ss=True)
        cmds.setAttr(f"{row_knee}.input", 3)
        cmds.setAttr(f"{row_ctl}.input", 3)
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{row_ctl}.matrix")
        cmds.connectAttr(f"{self.ik_chain[1]}.worldMatrix[0]", f"{row_knee}.matrix")
        for axis, value in zip("XYZ", ("xValue", "yValue", "zValue")):
            cmds.connectAttr(f"{row_knee}.output{axis}", f"{crv_point_pv}.controlPoints[0].{value}")
            cmds.connectAttr(f"{row_ctl}.output{axis}", f"{crv_point_pv}.controlPoints[1].{value}")
        cmds.setAttr(f"{crv_point_pv}.inheritsTransform", 0)
        cmds.setAttr(f"{crv_point_pv}.overrideEnabled", 1)
        cmds.setAttr(f"{crv_point_pv}.overrideDisplayType", 1)
        cmds.setAttr(f"{crv_point_pv}.hiddenInOutliner", 1)
        cmds.parent(crv_point_pv, self.pv_ctl)

    def ik_setup(self):

        """
        ikHandles nativos: el IK principal (spring o RP según el argumento) va
        de la cadera al Ankle — genérico en número de huesos — y el pie se
        resuelve con SC: Ankle -> Ball y Ball -> Tip. Con 2 huesos el spring no
        aporta nada y se cae a RP.
        """
        foot_ctl, toe_ctl, ball_ctl = self.ik_controllers
        handles = []

        ankle_index = self.leg_end_index
        self.main_end_index = ankle_index

        use_spring = self.solver == "spring" and ankle_index >= 3
        solver_name = "ikRPsolver"
        if use_spring:
            cmds.loadPlugin("ikSpringSolver", quiet=True)
            if not cmds.objExists("ikSpringSolver"):
                mel.eval("ikSpringSolver;")
            solver_name = "ikSpringSolver"

        self.ik_handle = cmds.ikHandle(name=f"{self.module_name}Ik_HDL", startJoint=self.ik_chain[0],
                                       endEffector=self.ik_chain[ankle_index], solver=solver_name)[0]
        handles.append(self.ik_handle)

        if ankle_index < self.plant_index:
            # El ankle viaja con el ballIk manteniendo su offset de reposo
            ankle_offset = om.MMatrix(self.guides_matrices[ankle_index]) * om.MMatrix(self.guides_matrices[self.plant_index]).inverse()
            ankle_follow_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}AnkleFollow_MMX", ss=True)
            cmds.setAttr(f"{ankle_follow_mmx}.matrixIn[0]", list(ankle_offset), type="matrix")
            cmds.connectAttr(f"{ball_ctl}.worldMatrix[0]", f"{ankle_follow_mmx}.matrixIn[1]")
            cmds.connectAttr(f"{ankle_follow_mmx}.matrixSum", f"{self.ik_handle}.offsetParentMatrix")
            self.ik_handle_target = f"{ankle_follow_mmx}.matrixSum"

            ball_handle = cmds.ikHandle(name=f"{self.module_name}BallIk_HDL", startJoint=self.ik_chain[ankle_index],
                                        endEffector=self.ik_chain[self.plant_index], solver="ikSCsolver")[0]
            cmds.connectAttr(f"{ball_ctl}.worldMatrix[0]", f"{ball_handle}.offsetParentMatrix")
            handles.append(ball_handle)
        else:
            # Sin Ball separado: el IK principal acaba en la pisada
            cmds.connectAttr(f"{ball_ctl}.worldMatrix[0]", f"{self.ik_handle}.offsetParentMatrix")
            self.ik_handle_target = f"{ball_ctl}.worldMatrix[0]"

        toe_handle = cmds.ikHandle(name=f"{self.module_name}ToeIk_HDL", startJoint=self.ik_chain[self.plant_index],
                                   endEffector=self.ik_chain[-1], solver="ikSCsolver")[0]
        cmds.connectAttr(f"{toe_ctl}.worldMatrix[0]", f"{toe_handle}.offsetParentMatrix")
        handles.append(toe_handle)

        freeze_float_constant = cmds.createNode("floatConstant", name=f"{self.module_name}Freeze_FCN", ss=True)
        cmds.setAttr(f"{freeze_float_constant}.inFloat", 0)
        for handle in handles:
            cmds.parent(handle, self.module_trn)
            cmds.setAttr(f"{handle}.visibility", 0)
            for attr in ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"]:
                cmds.connectAttr(f"{freeze_float_constant}.outFloat", f"{handle}.{attr}")

        cmds.poleVectorConstraint(self.pv_ctl, self.ik_handle)

    def ik_stretch_soft(self):

        """
        Stretch y soft IK sobre los handles nativos, genérico para 2 o 3
        segmentos: el stretch escala el translateX de los joints IK con el
        ratio distancia/longitud (normalizado por globalScale, estilo del
        stretch del bípedo) y el soft amortigua la posición del handle con la
        curva exponencial clásica, recolocándolo con composeMatrix * aimMatrix.
        """
        foot_ctl = self.ik_controllers[0]
        segment_count = self.main_end_index
        rest_lengths = [
            (self.guide_positions[i + 1] - self.guide_positions[i]).length()
            for i in range(segment_count)
        ]

        if segment_count == 2:
            mult_names = ["upperLengthMult", "lowerLengthMult"]
        elif segment_count == 3:
            mult_names = ["upperLengthMult", "middleLengthMult", "lowerLengthMult"]
        else:
            mult_names = [f"segment0{i}LengthMult" for i in range(segment_count)]

        cmds.addAttr(foot_ctl, longName="STRETCHY", niceName="STRETCHY ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{foot_ctl}.STRETCHY", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(foot_ctl, longName="Stretch", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)
        for name in mult_names:
            cmds.addAttr(foot_ctl, longName=name, attributeType="float", minValue=0.001, defaultValue=1, keyable=True)

        cmds.addAttr(foot_ctl, longName="SOFT", niceName="SOFT ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{foot_ctl}.SOFT", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(foot_ctl, longName="Soft", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)
        cmds.addAttr(foot_ctl, longName="Soft_Start", attributeType="float", minValue=0.001, maxValue=1, defaultValue=0.8, keyable=True)

        # ----- Distancia actual normalizada por globalScale -----
        current_dbt = cmds.createNode("distanceBetween", name=f"{self.module_name}CurrentLength_DBT", ss=True)
        cmds.connectAttr(f"{self.root_ik_ctl}.worldMatrix[0]", f"{current_dbt}.inMatrix1")
        cmds.connectAttr(self.ik_handle_target, f"{current_dbt}.inMatrix2")

        distance_div = cmds.createNode("divide", name=f"{self.module_name}GlobalScale_DIV", ss=True)
        cmds.connectAttr(f"{current_dbt}.distance", f"{distance_div}.input1")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{distance_div}.input2")
        distance_plug = f"{distance_div}.output"

        # ----- Longitud total viva (con los length mults) -----
        length_sum = cmds.createNode("sum", name=f"{self.module_name}TotalLength_SUM", ss=True)
        for i, (rest, mult_name) in enumerate(zip(rest_lengths, mult_names)):
            segment_mul = cmds.createNode("multiply", name=f"{self.module_name}Segment0{i}Length_MUL", ss=True)
            cmds.setAttr(f"{segment_mul}.input[0]", rest)
            cmds.connectAttr(f"{foot_ctl}.{mult_name}", f"{segment_mul}.input[1]")
            cmds.connectAttr(f"{segment_mul}.output", f"{length_sum}.input[{i}]")
        length_plug = f"{length_sum}.output"

        # ----- Stretch: factor = lerp(1, max(1, d/L), Stretch) -----
        ratio_div = cmds.createNode("divide", name=f"{self.module_name}LengthRatio_DIV", ss=True)
        cmds.connectAttr(distance_plug, f"{ratio_div}.input1")
        cmds.connectAttr(length_plug, f"{ratio_div}.input2")

        ratio_max = cmds.createNode("max", name=f"{self.module_name}LengthRatio_MAX", ss=True)
        cmds.setAttr(f"{ratio_max}.input[0]", 1)
        cmds.connectAttr(f"{ratio_div}.output", f"{ratio_max}.input[1]")

        stretch_remap = cmds.createNode("remapValue", name=f"{self.module_name}Stretch_RMV", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Stretch", f"{stretch_remap}.inputValue")
        cmds.setAttr(f"{stretch_remap}.outputMin", 1)
        cmds.connectAttr(f"{ratio_max}.output", f"{stretch_remap}.outputMax")

        for i in range(1, segment_count + 1):
            rest_tx = cmds.getAttr(f"{self.ik_chain[i]}.translateX")
            joint_mul = cmds.createNode("multiply", name=f"{self.module_name}Stretch0{i}_MUL", ss=True)
            cmds.setAttr(f"{joint_mul}.input[0]", rest_tx)
            cmds.connectAttr(f"{stretch_remap}.outValue", f"{joint_mul}.input[1]")
            cmds.connectAttr(f"{foot_ctl}.{mult_names[i - 1]}", f"{joint_mul}.input[2]")
            cmds.connectAttr(f"{joint_mul}.output", f"{self.ik_chain[i]}.translateX")

        # ----- Soft: d' = dStart + range * (1 - e^(-(d - dStart) / range)) -----
        soft_start_mul = cmds.createNode("multiply", name=f"{self.module_name}SoftStart_MUL", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Soft_Start", f"{soft_start_mul}.input[0]")
        cmds.connectAttr(length_plug, f"{soft_start_mul}.input[1]")

        soft_range_sub = cmds.createNode("subtract", name=f"{self.module_name}SoftRange_SUB", ss=True)
        cmds.connectAttr(length_plug, f"{soft_range_sub}.input1")
        cmds.connectAttr(f"{soft_start_mul}.output", f"{soft_range_sub}.input2")

        soft_delta_sub = cmds.createNode("subtract", name=f"{self.module_name}SoftDelta_SUB", ss=True)
        cmds.connectAttr(distance_plug, f"{soft_delta_sub}.input1")
        cmds.connectAttr(f"{soft_start_mul}.output", f"{soft_delta_sub}.input2")

        soft_exponent_div = cmds.createNode("divide", name=f"{self.module_name}SoftExponent_DIV", ss=True)
        cmds.connectAttr(f"{soft_delta_sub}.output", f"{soft_exponent_div}.input1")
        cmds.connectAttr(f"{soft_range_sub}.output", f"{soft_exponent_div}.input2")

        soft_exponent_neg = cmds.createNode("negate", name=f"{self.module_name}SoftExponent_NEG", ss=True)
        cmds.connectAttr(f"{soft_exponent_div}.output", f"{soft_exponent_neg}.input")

        soft_exp_pow = cmds.createNode("power", name=f"{self.module_name}SoftExp_POW", ss=True)
        cmds.setAttr(f"{soft_exp_pow}.input", math.e)
        cmds.connectAttr(f"{soft_exponent_neg}.output", f"{soft_exp_pow}.exponent")

        soft_one_minus = cmds.createNode("subtract", name=f"{self.module_name}SoftOneMinusExp_SUB", ss=True)
        cmds.setAttr(f"{soft_one_minus}.input1", 1)
        cmds.connectAttr(f"{soft_exp_pow}.output", f"{soft_one_minus}.input2")

        soft_falloff_mul = cmds.createNode("multiply", name=f"{self.module_name}SoftFalloff_MUL", ss=True)
        cmds.connectAttr(f"{soft_range_sub}.output", f"{soft_falloff_mul}.input[0]")
        cmds.connectAttr(f"{soft_one_minus}.output", f"{soft_falloff_mul}.input[1]")

        soft_distance_sum = cmds.createNode("sum", name=f"{self.module_name}SoftDistance_SUM", ss=True)
        cmds.connectAttr(f"{soft_start_mul}.output", f"{soft_distance_sum}.input[0]")
        cmds.connectAttr(f"{soft_falloff_mul}.output", f"{soft_distance_sum}.input[1]")

        # Solo amortigua pasado el inicio del soft (condition: d > dStart)
        soft_condition = cmds.createNode("condition", name=f"{self.module_name}Soft_CON", ss=True)
        cmds.setAttr(f"{soft_condition}.operation", 2)  # Greater than
        cmds.connectAttr(distance_plug, f"{soft_condition}.firstTerm")
        cmds.connectAttr(f"{soft_start_mul}.output", f"{soft_condition}.secondTerm")
        cmds.connectAttr(f"{soft_distance_sum}.output", f"{soft_condition}.colorIfTrueR")
        cmds.connectAttr(distance_plug, f"{soft_condition}.colorIfFalseR")

        soft_blend = cmds.createNode("blendTwoAttr", name=f"{self.module_name}Soft_B2A", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Soft", f"{soft_blend}.attributesBlender")
        cmds.connectAttr(distance_plug, f"{soft_blend}.input[0]")
        cmds.connectAttr(f"{soft_condition}.outColorR", f"{soft_blend}.input[1]")

        # De vuelta a unidades world (la distancia iba normalizada)
        soft_world_mul = cmds.createNode("multiply", name=f"{self.module_name}SoftWorld_MUL", ss=True)
        cmds.connectAttr(f"{soft_blend}.output", f"{soft_world_mul}.input[0]")
        cmds.connectAttr(f"{self.masterwalk_ctl}.globalScale", f"{soft_world_mul}.input[1]")

        # Recolocación del handle: composeMatrix(tx) * aimMatrix (sin DAG)
        absolute_primary = tuple(abs(x) for x in self.primary_axis)
        soft_aim = cmds.createNode("aimMatrix", name=f"{self.module_name}Soft_AIM", ss=True)
        cmds.connectAttr(f"{self.root_ik_ctl}.worldMatrix[0]", f"{soft_aim}.inputMatrix")
        cmds.connectAttr(self.ik_handle_target, f"{soft_aim}.primary.primaryTargetMatrix")
        cmds.setAttr(f"{soft_aim}.primaryInputAxis", *absolute_primary, type="double3")
        cmds.setAttr(f"{soft_aim}.secondaryInputAxis", *self.secondary_axis, type="double3")
        cmds.setAttr(f"{soft_aim}.primaryMode", 1)

        soft_cmx = cmds.createNode("composeMatrix", name=f"{self.module_name}Soft_CMX", ss=True)
        cmds.connectAttr(f"{soft_world_mul}.output", f"{soft_cmx}.inputTranslateX")

        soft_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}Soft_MMX", ss=True)
        cmds.connectAttr(f"{soft_cmx}.outputMatrix", f"{soft_mmx}.matrixIn[0]")
        cmds.connectAttr(f"{soft_aim}.outputMatrix", f"{soft_mmx}.matrixIn[1]")

        cmds.connectAttr(f"{soft_mmx}.matrixSum", f"{self.ik_handle}.offsetParentMatrix", force=True)

    def foot_attributes(self):

        foot_ctl = self.ik_controllers[0]
        toe_sdk = self.ik_sdk_nodes[1]
        ball_sdk = self.ik_sdk_nodes[2]
        foot_sdk = self.ik_sdk_nodes[0]

        cmds.addAttr(foot_ctl, longName="EXTRA_ATTRIBUTES", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{foot_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)

        for attr in ["Foot_Twist", "Ball_Twist", "Toe_Twist", "Roll"]:
            cmds.addAttr(foot_ctl, longName=attr, attributeType="float", defaultValue=0, keyable=True)
        cmds.addAttr(foot_ctl, longName="Roll_Break_Angle", attributeType="float", defaultValue=45, keyable=True)
        cmds.addAttr(foot_ctl, longName="Roll_Straight_Angle", attributeType="float", defaultValue=90, keyable=True)

        cmds.connectAttr(f"{foot_ctl}.Foot_Twist", f"{foot_sdk}.rotateY")
        cmds.connectAttr(f"{foot_ctl}.Ball_Twist", f"{ball_sdk}.rotateY")
        cmds.connectAttr(f"{foot_ctl}.Toe_Twist", f"{toe_sdk}.rotateY")

        # Roll: hasta el break angle levanta el ball; de ahí al straight angle
        # pasa el peso a la punta (igual que el bípedo)
        roll_straight_angle = cmds.createNode("remapValue", name=f"{self.module_name}RollStraightAngle_RMV", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Roll", f"{roll_straight_angle}.inputValue")
        cmds.connectAttr(f"{foot_ctl}.Roll_Straight_Angle", f"{roll_straight_angle}.inputMax")
        cmds.connectAttr(f"{foot_ctl}.Roll_Break_Angle", f"{roll_straight_angle}.inputMin")
        cmds.setAttr(f"{roll_straight_angle}.outputMin", 0)
        cmds.setAttr(f"{roll_straight_angle}.outputMax", 1)

        multiply_node = cmds.createNode("multiply", name=f"{self.module_name}RollStraightAngle_MUL", ss=True)
        cmds.connectAttr(f"{roll_straight_angle}.outValue", f"{multiply_node}.input[0]")
        cmds.connectAttr(f"{foot_ctl}.Roll", f"{multiply_node}.input[1]")
        negate_roll_straight = cmds.createNode("negate", name=f"{self.module_name}RollStraight_NEG", ss=True)
        cmds.connectAttr(f"{multiply_node}.output", f"{negate_roll_straight}.input")
        cmds.connectAttr(f"{negate_roll_straight}.output", f"{toe_sdk}.rotateZ")

        roll_break_angle = cmds.createNode("remapValue", name=f"{self.module_name}RollBreakAngle_RMV", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Roll", f"{roll_break_angle}.inputValue")
        cmds.connectAttr(f"{foot_ctl}.Roll_Break_Angle", f"{roll_break_angle}.inputMax")
        cmds.setAttr(f"{roll_break_angle}.outputMin", 0)
        cmds.setAttr(f"{roll_break_angle}.outputMax", 1)

        reverse = cmds.createNode("reverse", name=f"{self.module_name}RollBreakAngle_REV", ss=True)
        cmds.connectAttr(f"{roll_straight_angle}.outValue", f"{reverse}.inputX")

        roll_angle_enable_mul = cmds.createNode("multiply", name=f"{self.module_name}RollAngleEnable_MUL", ss=True)
        cmds.connectAttr(f"{reverse}.outputX", f"{roll_angle_enable_mul}.input[0]")
        cmds.connectAttr(f"{foot_ctl}.Roll", f"{roll_angle_enable_mul}.input[1]")

        roll_lift_angle_mul = cmds.createNode("multiply", name=f"{self.module_name}RollLiftAngle_MUL", ss=True)
        cmds.connectAttr(f"{roll_break_angle}.outValue", f"{roll_lift_angle_mul}.input[0]")
        cmds.connectAttr(f"{roll_angle_enable_mul}.output", f"{roll_lift_angle_mul}.input[1]")
        negate_roll_lift = cmds.createNode("negate", name=f"{self.module_name}RollLift_NEG", ss=True)
        cmds.connectAttr(f"{roll_lift_angle_mul}.output", f"{negate_roll_lift}.input")
        cmds.connectAttr(f"{negate_roll_lift}.output", f"{ball_sdk}.rotateZ")

    def fk_stretch(self):

        """FK stretch por segmento (igual que el bípedo, con matrices horneadas)."""

        for i, ctl in enumerate(self.fk_controllers[:-1]):

            cmds.addAttr(ctl, longName="STRETCHY", niceName="STRETCHY ------", attributeType="enum", enumName="------")
            cmds.setAttr(f"{ctl}.STRETCHY", keyable=False, channelBox=True, lock=True)
            cmds.addAttr(ctl, shortName="Stretch", minValue=0, defaultValue=1, keyable=True)

            rest_length = (self.guide_positions[i + 1] - self.guide_positions[i]).length()
            if self.side == "R":
                rest_length *= -1

            label = ctl.split("_")[1]
            mult_node = cmds.createNode("multiply", n=f"{self.module_name}{label}Stretch_MUL", ss=True)
            cmds.connectAttr(f"{ctl}.Stretch", f"{mult_node}.input[0]")
            cmds.setAttr(f"{mult_node}.input[1]", rest_length)

            # El opm del siguiente FK es un valor horneado: se reconstruye con un
            # fourByFour fijando las filas y dirigiendo solo la traslación X
            target_node = self.fk_nodes[i + 1]
            relative = cmds.getAttr(f"{target_node}.offsetParentMatrix")

            fbf = cmds.createNode("fourByFourMatrix", name=f"{self.module_name}{label}Stretch_FBF", ss=True)
            for row in range(4):
                for col in range(3):
                    cmds.setAttr(f"{fbf}.in{row}{col}", relative[row * 4 + col])
            cmds.connectAttr(f"{mult_node}.output", f"{fbf}.in30", force=True)
            cmds.connectAttr(f"{fbf}.output", f"{target_node}.offsetParentMatrix", force=True)

    def skinning_setup(self):

        """
        Las guías importadas (ya dirigidas por los blend FK/IK) se quedan como
        cadena de skinning con el sufijo Skinning, bajo el grupo de esqueleto.
        """
        cmds.parent(self.leg_chain[0], self.skeleton_grp)

        renamed = []
        for joint in self.leg_chain:
            renamed.append(cmds.rename(joint, joint.replace("_JNT", "Skinning_JNT")))

        self.leg_chain = renamed
        self.leg_joints = renamed[:-1]
        self.tip_joint = renamed[-1]


class BackLegModule(LegModule):

    """Pierna trasera: {side}_backLegHip_JNT -> ... -> Tip."""

    LEG_PREFIX = "backLeg"


class FrontLegModule(LegModule):

    """
    Pierna delantera: {side}_frontLegHip_JNT -> ... -> Tip.
    Misma construcción que la trasera (el PV se calcula del plano real de la
    cadena, así que el bend invertido del carpo sale solo) más la escápula
    (master + escápula aimada al root de la pierna + end con space switch),
    portada del dragon_leg del TFG. Necesita la guía {side}_frontLegScapula_JNT.
    """

    LEG_PREFIX = "frontLeg"

    def make(self, side, solver="spring", primaryInputAxis=(1, 0, 0), secondaryInputAxis=(0, 1, 0)):
        super().make(side, solver=solver, primaryInputAxis=primaryInputAxis, secondaryInputAxis=secondaryInputAxis)
        self.scapula_setup()

    def load_guides(self):

        """
        La cadena delantera cuelga de la escápula: {side}_scapula_JNT ->
        frontLegHip -> ... -> Tip. Se importa todo desde la escápula, se separa
        la pierna y la guía de escápula se hornea (posición) y se borra.
        """
        chain = guides_manager.get_guides(f"{self.side}_scapula_JNT")
        if not chain:
            # Asset sin escápula: cadena directa desde el hip
            super().load_guides()
            return
        cmds.parent(chain[0], self.module_trn)

        self.scapula_guide_pos = om.MVector(cmds.xform(chain[0], q=True, ws=True, t=True))

        cmds.parent(chain[1], self.module_trn)  # separa la pierna de la escápula
        cmds.delete(chain[0])

        self.leg_chain = chain[1:]
        self._setup_chain()

    def scapula_setup(self):

        """
        Escápula estilo TFG con matrices: master en el root de la pierna
        (orientado a mundo), escápula en su guía aimada al root siguiendo al
        master, y end en el root con space switch translate/rotate entre la
        escápula y el masterwalk. Dos joints de skinning.
        """
        if not hasattr(self, "scapula_guide_pos"):
            cmds.warning(f"{self.side}_scapula_JNT no existe: se omite la escápula.")
            return

        scapula_pos = self.scapula_guide_pos

        root_pos = self.guide_positions[0]
        masterwalk_rest = om.MMatrix(cmds.getAttr(f"{self.masterwalk_ctl}.worldMatrix[0]"))

        # Orientación de la escápula: X apunta al root de la pierna, Y arriba
        scapula_rest = guides_manager._aim_matrix(
            scapula_pos, root_pos, scapula_pos + om.MVector(0.0, 1.0, 0.0),
            self.primary_axis, self.secondary_axis
        )
        master_rest = om.MMatrix(self._translation_matrix(root_pos))
        root_point_rest = om.MMatrix(self._translation_matrix(root_pos))

        # Master: en el root de la pierna, orientado a mundo
        master_nodes, self.scapula_master_ctl = curve_tool.create_controller(name=f"{self.module_name}ScapulaMaster", offset=["GRP", "ANM"], parent=self.controllers_grp)
        self.lock_attributes(self.scapula_master_ctl, ["sx", "sy", "sz", "v"])
        cmds.setAttr(f"{master_nodes[0]}.offsetParentMatrix", list(master_rest), type="matrix")

        # Escápula: en su guía, siguiendo al master con offset horneado
        scapula_nodes, self.scapula_ctl = curve_tool.create_controller(name=f"{self.module_name}Scapula", offset=["GRP", "ANM"], parent=self.controllers_grp)
        self.lock_attributes(self.scapula_ctl, ["sx", "sy", "sz", "v"])
        cmds.setAttr(f"{scapula_nodes[0]}.inheritsTransform", 0)

        scapula_offset_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}Scapula_MMX", ss=True)
        cmds.setAttr(f"{scapula_offset_mmx}.matrixIn[0]", list(scapula_rest * master_rest.inverse()), type="matrix")
        cmds.connectAttr(f"{self.scapula_master_ctl}.worldMatrix[0]", f"{scapula_offset_mmx}.matrixIn[1]")
        cmds.connectAttr(f"{scapula_offset_mmx}.matrixSum", f"{scapula_nodes[0]}.offsetParentMatrix")

        # End: en el root de la pierna, con space switch entre escápula y masterwalk
        end_nodes, self.scapula_end_ctl = curve_tool.create_controller(name=f"{self.module_name}ScapulaEnd", offset=["GRP", "ANM"], parent=self.controllers_grp)
        self.lock_attributes(self.scapula_end_ctl, ["sx", "sy", "sz", "v"])
        cmds.setAttr(f"{end_nodes[0]}.inheritsTransform", 0)

        cmds.addAttr(self.scapula_ctl, longName="SpaceSwitchSep", niceName="SPACE SWITCHES ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.scapula_ctl}.SpaceSwitchSep", channelBox=True, lock=True)
        cmds.addAttr(self.scapula_ctl, longName="TranslateValue", attributeType="float", min=0, max=1, defaultValue=0.5, keyable=True)
        cmds.addAttr(self.scapula_ctl, longName="RotateValue", attributeType="float", min=0, max=1, defaultValue=0.5, keyable=True)

        end_masterwalk_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}ScapulaEndWorld_MMX", ss=True)
        cmds.setAttr(f"{end_masterwalk_mmx}.matrixIn[0]", list(root_point_rest * masterwalk_rest.inverse()), type="matrix")
        cmds.connectAttr(f"{self.masterwalk_ctl}.worldMatrix[0]", f"{end_masterwalk_mmx}.matrixIn[1]")

        end_scapula_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}ScapulaEndLocal_MMX", ss=True)
        cmds.setAttr(f"{end_scapula_mmx}.matrixIn[0]", list(root_point_rest * scapula_rest.inverse()), type="matrix")
        cmds.connectAttr(f"{self.scapula_ctl}.worldMatrix[0]", f"{end_scapula_mmx}.matrixIn[1]")

        end_space_blm = cmds.createNode("blendMatrix", name=f"{self.module_name}ScapulaEndSpace_BLM", ss=True)
        cmds.connectAttr(f"{end_masterwalk_mmx}.matrixSum", f"{end_space_blm}.inputMatrix")
        cmds.connectAttr(f"{end_scapula_mmx}.matrixSum", f"{end_space_blm}.target[0].targetMatrix")
        cmds.connectAttr(f"{self.scapula_ctl}.TranslateValue", f"{end_space_blm}.target[0].translateWeight")
        cmds.connectAttr(f"{self.scapula_ctl}.RotateValue", f"{end_space_blm}.target[0].rotateWeight")
        cmds.setAttr(f"{end_space_blm}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{end_space_blm}.target[0].shearWeight", 0)
        cmds.connectAttr(f"{end_space_blm}.outputMatrix", f"{end_nodes[0]}.offsetParentMatrix")

        # Skinning joints de la escápula
        scapula_skinning = cmds.createNode("joint", name=f"{self.module_name}ScapulaSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{self.scapula_ctl}.worldMatrix[0]", f"{scapula_skinning}.offsetParentMatrix")
        scapula_end_skinning = cmds.createNode("joint", name=f"{self.module_name}ScapulaEndSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{self.scapula_end_ctl}.worldMatrix[0]", f"{scapula_end_skinning}.offsetParentMatrix")

        data_manager.DataExportBiped().append_data(f"{self.LEG_PREFIX}_module",
                            {
                                f"{self.side}_scapula_ctl": self.scapula_ctl,
                                f"{self.side}_scapula_master_ctl": self.scapula_master_ctl,
                                f"{self.side}_scapula_end_ctl": self.scapula_end_ctl,
                            })
