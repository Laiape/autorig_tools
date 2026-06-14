import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
from importlib import reload
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


class LegModule(object):

    """
    Pierna de cuadrúpedo basada en el leg del bípedo:
        - Guías (anatomía equina): {side}_{LEG_PREFIX}Hip_JNT -> Knee -> Ankle
          -> Fetlock -> Pastern -> Tip. La cadena puede tener más o menos huesos
          intermedios; el módulo es genérico por índice. El Tip es el pivote de
          la punta del casco. El módulo detecta la longitud automáticamente.
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
    ROOT_JOINT = "Hip"  # joint raíz de la cadena (front lo sobreescribe a "Shoulder")
    # Índice de la articulación apex del pole vector (desde la que se proyecta).
    # Es la gran articulación que dobla hacia ATRÁS: el corvejón (hock) en la
    # trasera y el carpo (la "rodilla" del caballo) en la delantera — ambos en
    # el índice 2 con la cadena estándar de 6 joints. Si la cadena tiene otra
    # cuenta, se cae al knee (índice 1).
    PV_APEX_INDEX = 2
    STANDARD_JOINT_COUNT = 6
    SIDE_AXIS = (1, 0, 0)  # eje lateral del personaje (guías en orientación canónica)
    # La delantera es casi recta (carpo) y el spring no sabe doblar -> hay que
    # sembrarle la dirección de flexión. La trasera tiene el corvejón doblado y
    # captura bien el preferredAngle: NO se toca. Front lo pone a True.
    SEED_STRAIGHT_BEND = False
    FORWARD_AXIS = (0, 0, 1)  # hacia dónde mira el personaje; la PV apunta aquí
                              # para que el apex (carpo/corvejón) doble hacia atrás

    def __init__(self):

        self.modules = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side, solver="spring", skinning_jnts=5, bendys=True, primaryInputAxis=(1, 0, 0), secondaryInputAxis=(0, 1, 0)):

        """
        Args:
            side (str): 'L' o 'R'.
            solver (str): "spring" o "rp".
            skinning_jnts (int): joints de skinning por segmento bendy.
            bendys (bool): controles bendy + ribbons por segmento; si es False,
                las guías importadas se quedan como cadena de skinning simple.
            primaryInputAxis (tuple): eje que apunta a la siguiente guía.
            secondaryInputAxis (tuple): eje secundario (up).
        """

        if solver not in ("spring", "rp"):
            cmds.error(f"Solver '{solver}' no soportado: usa 'spring' o 'rp'.")

        self.side = side
        self.solver = solver
        self.skinning_jnts = skinning_jnts
        self.bendys = bendys
        self.primary_axis = primaryInputAxis if side == "L" else tuple(-x for x in primaryInputAxis)
        self.secondary_axis = secondaryInputAxis if side == "L" else tuple(-x for x in secondaryInputAxis)
        # Eje lateral por lado: +X en L, -X en R, para que la R sea MIRROR de la
        # L (frames, root y controles reflejados) en vez de world-consistente.
        self.side_vec = om.MVector(*self.SIDE_AXIS) * (1 if side == "L" else -1)

        self.module_name = f"{self.side}_{self.LEG_PREFIX}"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_chains()
        self.controllers_creation()
        self.ik_setup()
        self.ik_stretch_soft()
        self.ik_calibration()
        self.foot_attributes()
        self.fk_stretch()
        if self.bendys:
            self.bendys_setup()
        self.skinning_setup()

        data_manager.DataExportBiped().append_data(f"{self.LEG_PREFIX}_module",
                            {
                                f"{self.side}_hip_JNT": self.leg_joints[0],
                                f"{self.side}_legIk": self.ik_controllers[0],
                                f"{self.side}_hipFk": self.fk_controllers[0],
                                f"{self.side}_legPv": self.pv_ctl,
                                f"{self.side}_rootIk": self.root_ik_ctl,
                                f"{self.side}_ikFkSwitch": self.settings_ctl,
                                f"{self.side}_bendy_ctls": getattr(self, "bendy_ctls", []),
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

        self.leg_chain = guides_manager.get_guides(f"{self.side}_{self.LEG_PREFIX}{self.ROOT_JOINT}_JNT")
        cmds.parent(self.leg_chain[0], self.module_trn)
        self._setup_chain()

    def _setup_chain(self):

        """
        Indices y matrices de la cadena. Cadena esperada (anatomía equina,
        genérica en número de huesos): Hip -> Knee -> Ankle -> Fetlock ->
        Pastern -> Tip. El IK principal va de Hip al Fetlock; el Pastern es la
        pisada y el Tip el pivote de la punta del casco.
        """
        self.leg_joints = self.leg_chain[:-1]  # todo menos el Tip
        self.tip_joint = self.leg_chain[-1]
        self.plant_index = len(self.leg_chain) - 2          # Pastern (pisada)
        self.leg_end_index = max(2, len(self.leg_chain) - 3)  # Fetlock (fin del IK principal)

        # Articulación apex del pole vector: el PV sale de ESTA joint (carpo en
        # delantera / corvejón en trasera = índice 2; knee si la cadena no es
        # estándar). Se usa tanto para colocar el PV como para la línea guía.
        self.pv_apex_index = self.PV_APEX_INDEX if len(self.leg_chain) == self.STANDARD_JOINT_COUNT else 1
        self.pv_apex_index = max(1, min(self.pv_apex_index, self.leg_end_index - 1))

        # Posiciones world de las guías (de los joints importados tal cual)
        self.guide_positions = [om.MVector(cmds.xform(j, q=True, ws=True, t=True)) for j in self.leg_chain]

        # Frames de la cadena (lo que pide el setup, ver foto):
        #   X = aim al siguiente joint (baja por el hueso)
        #   Z = eje lateral del personaje (side_vec, world) → eje de flexión,
        #       IGUAL en toda la cadena (eje del mundo como referencia FIJA, no la
        #       normal del plano de la pata, inestable en patas rectas).
        #   Y = perpendicular en el plano (delante/atrás)
        side_ref = self.side_vec  # +X en L, -X en R (mirror)
        hip_p, knee_p = self.guide_positions[0], self.guide_positions[1]
        ankle_p = self.guide_positions[self.leg_end_index]
        self.plane_normal = (knee_p - hip_p) ^ (ankle_p - hip_p)
        self.plane_normal = self.plane_normal.normal() if self.plane_normal.length() > 1e-4 else om.MVector(side_ref)

        # Dirección de la PV (hacia DELANTE, plano sagital). El spring dobla el
        # apex en sentido opuesto, así que el corvejón/carpo dobla hacia ATRÁS.
        root_p, end_p = self.guide_positions[0], self.guide_positions[self.leg_end_index]
        line = end_p - root_p
        self.leg_line_len = line.length()
        line_dir = line.normal() if self.leg_line_len > 1e-6 else om.MVector(0.0, 0.0, 1.0)
        bend_dir = side_ref ^ line_dir
        if bend_dir.length() < 1e-4:
            bend_dir = self.plane_normal ^ line_dir
        bend_dir.normalize()
        if (bend_dir * om.MVector(*self.FORWARD_AXIS)) < 0:
            bend_dir = -bend_dir
        self.bend_dir = bend_dir

        # Cadena IK: en patas casi rectas (delantera) se PRE-DOBLAN los joints
        # intermedios hacia atrás (-bend_dir) para que el spring tenga un bulto
        # real (como el corvejón) y doble hacia atrás limpio, sin depender de
        # seeds que pelean con la PV. La trasera no se pre-dobla (ya tiene su
        # zigzag). La calibración corrige el reposo a las guías; los FK usan las
        # posiciones originales.
        ik_positions = list(self.guide_positions)
        if self.SEED_STRAIGHT_BEND:
            bulge = bend_dir * (-self.leg_line_len * 0.1)  # bulto sagital (limpio, sin lateral)
            for i in range(1, self.leg_end_index):
                ik_positions[i] = self.guide_positions[i] + bulge

        self.ik_frames = self._build_frames(ik_positions, side_ref)
        self.guides_matrices = [list(f) for f in self._build_frames(self.guide_positions, side_ref)]

    def _roll_cv(self, blend_plug, aim_target_plug, name):
        """
        Frame anti-flip para alimentar el ribbon: aim al siguiente joint con el
        eje lateral ALINEADO al lado del personaje (estable, no se retuerce) +
        el twist LIMPIO del joint real extraído por swing-twist (cuaternión, sin
        flip, neutralizado a 0 en reposo). Devuelve el multMatrix (.matrixSum).
        """
        nonroll = cmds.createNode("aimMatrix", name=f"{name}NonRoll_AMX", ss=True)
        cmds.connectAttr(blend_plug, f"{nonroll}.inputMatrix")
        cmds.connectAttr(aim_target_plug, f"{nonroll}.primary.primaryTargetMatrix")
        cmds.setAttr(f"{nonroll}.primaryInputAxis", *self.primary_axis, type="double3")
        cmds.setAttr(f"{nonroll}.secondaryInputAxis", 0, 0, 1, type="double3")  # local Z = lateral
        cmds.setAttr(f"{nonroll}.secondaryMode", 2)  # alinear al vector
        cmds.setAttr(f"{nonroll}.secondaryTargetVector", self.side_vec.x, self.side_vec.y, self.side_vec.z, type="double3")

        twist_qn = matrix_manager.extract_twist(blend_plug, f"{nonroll}.outputMatrix", axis="x", name=name, return_quat=True)
        cmp = cmds.createNode("composeMatrix", name=f"{name}RollTwist_CMP", ss=True)
        cmds.setAttr(f"{cmp}.useEulerRotation", 0)
        cmds.connectAttr(f"{twist_qn}.outputQuat", f"{cmp}.inputQuat")
        roll = cmds.createNode("multMatrix", name=f"{name}Roll_MMX", ss=True)
        cmds.connectAttr(f"{cmp}.outputMatrix", f"{roll}.matrixIn[0]")
        cmds.connectAttr(f"{nonroll}.outputMatrix", f"{roll}.matrixIn[1]")
        return roll

    def _build_frames(self, positions, side_ref):
        """Frames X=aim, Z=lateral(side_ref), Y=delante/atrás para una lista de posiciones."""
        frames = []
        x_axis = om.MVector(1.0, 0.0, 0.0)
        for i, pos in enumerate(positions):
            if i < len(positions) - 1:
                x_axis = (positions[i + 1] - pos).normal()
            y_axis = (side_ref ^ x_axis).normal()
            z_axis = (x_axis ^ y_axis).normal()
            frames.append(om.MMatrix([
                x_axis.x, x_axis.y, x_axis.z, 0.0,
                y_axis.x, y_axis.y, y_axis.z, 0.0,
                z_axis.x, z_axis.y, z_axis.z, 0.0,
                pos.x, pos.y, pos.z, 1.0,
            ]))
        return frames

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

        # Cadena IK: usa los frames planares ya calculados en _setup_chain
        # (X aim, Z = eje lateral consistente, Y en el plano) — misma
        # orientación que los controles FK.
        self.ik_chain = []
        for joint, frame in zip(self.leg_chain, self.ik_frames):
            cmds.select(clear=True)
            ik_joint = cmds.joint(name=joint.replace("_JNT", "Ik_JNT"))
            cmds.xform(ik_joint, ws=True, m=list(frame))
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

        # Pie reverso: ankleIk (en el Ankle, orientado a mundo, como el bípedo)
        # -> toeIk (punta) -> ballIk (pisada)
        ankle_rest = self._translation_matrix(self.guide_positions[self.leg_end_index])
        if self.side == "R":
            ankle_rest = self._mirror_matrix(ankle_rest)

        rest_matrices = {
            "ankleIk": ankle_rest,
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

        # El frame planar del root IK no coincide con la matriz del root ctl:
        # offset horneado (frame0 * ctl_rest^-1) para que la cadena conserve
        # sus frames al seguir al control
        root_follow_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}IkRootFollow_MMX", ss=True)
        root_offset = self.ik_frames[0] * om.MMatrix(self.guides_matrices[0]).inverse()
        cmds.setAttr(f"{root_follow_mmx}.matrixIn[0]", list(root_offset), type="matrix")
        cmds.connectAttr(f"{self.root_ik_ctl}.worldMatrix[0]", f"{root_follow_mmx}.matrixIn[1]")
        cmds.connectAttr(f"{root_follow_mmx}.matrixSum", f"{self.ik_chain[0]}.offsetParentMatrix")
        for attr in ["translate", "rotate", "jointOrient"]:
            for axis in ["X", "Y", "Z"]:
                cmds.setAttr(f"{self.ik_chain[0]}.{attr}{axis}", 0)
                cmds.setAttr(f"{self.leg_joints[0]}.{attr}{axis}", 0)

        # Pole vector: el control se crea aquí, pero su posición de reposo se
        # hornea en ik_setup desde el poleVector automático del handle (es la
        # única dirección que preserva el reposo del spring; verificado).
        self.pv_nodes, self.pv_ctl = curve_tool.create_controller(name=f"{self.module_name}Pv", offset=["GRP", "ANM"])
        self.lock_attributes(self.pv_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])

        cmds.addAttr(self.pv_ctl, longName="extraAttr", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{self.pv_ctl}.extraAttr", channelBox=True, lock=True)
        cmds.addAttr(self.pv_ctl, longName="pvOrientation", niceName="Pv Orientation", attributeType="float", defaultValue=0, minValue=0, maxValue=1, keyable=True)

        # pvOrientation (TFG): 0 = orientado a mundo, 1 = Z apuntando a la rodilla
        self.pv_orient_blm = cmds.createNode("blendMatrix", name=f"{self.module_name}PvOrient_BLM", ss=True)
        cmds.connectAttr(f"{self.pv_ctl}.pvOrientation", f"{self.pv_orient_blm}.target[0].weight")
        cmds.connectAttr(f"{self.pv_orient_blm}.outputMatrix", f"{self.pv_nodes[0]}.offsetParentMatrix")

        cmds.parent(self.pv_nodes[0], ik_controllers_trn)
        cmds.xform(self.pv_nodes[0], m=om.MMatrix.kIdentity)

        # Línea que apunta del apex (carpo/corvejón) al PV
        crv_point_pv = cmds.curve(d=1, p=[(0, 0, 1), (0, 1, 0)], n=f"{self.module_name}Pv_CRV")
        row_knee = cmds.createNode("rowFromMatrix", name=f"{self.module_name}Pv_RFM", ss=True)
        row_ctl = cmds.createNode("rowFromMatrix", name=f"{self.module_name}PvCtl_RFM", ss=True)
        cmds.setAttr(f"{row_knee}.input", 3)
        cmds.setAttr(f"{row_ctl}.input", 3)
        cmds.connectAttr(f"{self.pv_ctl}.worldMatrix[0]", f"{row_ctl}.matrix")
        cmds.connectAttr(f"{self.ik_chain[self.pv_apex_index]}.worldMatrix[0]", f"{row_knee}.matrix")
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

        # Sin preferred angles el spring no codifica el zigzag de reposo y las
        # rodillas saltan al pasar a IK (verificado: drift ~10u -> 0 con spa)
        cmds.joint(self.ik_chain[0], e=True, setPreferredAngles=True, children=True)

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

        # Colocación del PV — geométrica en WORLD, en el plano sagital de la pata.
        # bend_dir (calculado en _setup_chain) apunta hacia DELANTE; el spring
        # dobla el apex en sentido opuesto, así que el corvejón/carpo dobla hacia
        # ATRÁS. El reposo del solve lo corrige ik_calibration(), así que la
        # posición del PV es libre geométricamente.
        apex_index = self.pv_apex_index
        apex_p = self.guide_positions[apex_index]
        bend_dir = self.bend_dir
        distance = self.leg_line_len * 0.5
        pv_pos = apex_p + bend_dir * distance

        # Orientación del control (pvOrientation): Z hacia el apex
        apex_x_axis = om.MVector(self.guides_matrices[apex_index][0], self.guides_matrices[apex_index][1], self.guides_matrices[apex_index][2])
        cmds.setAttr(f"{self.pv_orient_blm}.inputMatrix", self._translation_matrix(pv_pos), type="matrix")
        pv_aimed = guides_manager._aim_matrix(pv_pos, apex_p, pv_pos + apex_x_axis, (0, 0, 1), (1, 0, 0))
        cmds.setAttr(f"{self.pv_orient_blm}.target[0].targetMatrix", list(pv_aimed), type="matrix")

        # poleVectorConstraint clásico: con los preferred angles puestos y el
        # PV sobre la dirección automática, preserva el reposo exacto
        # (verificado: cualquier conexión manual del poleVector lo rompe)
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

    def ik_calibration(self):

        """
        El spring (y el RP multi-hueso) redistribuye el bend a su manera y la
        pose de reposo del solve no coincide exactamente con las guías. Aquí se
        mide el reposo real de cada joint IK y se hornea la corrección LOCAL
        constante (guía × reposo⁻¹, premultiplicada: gira con el joint) en la
        entrada del blend FK/IK. Resultado: en IK la pierna reposa EXACTA sobre
        las guías, sea cual sea el solver, y en movimiento la corrección viaja
        como un offset de hueso.
        """
        cmds.dgdirty(allPlugs=True)

        for i, joint in enumerate(self.leg_joints):

            ik_joint = self.ik_chain[i]
            solved_rest = om.MMatrix(cmds.getAttr(f"{ik_joint}.worldMatrix[0]"))
            target = om.MMatrix(self.guides_matrices[i])
            correction = target * solved_rest.inverse()

            if correction.isEquivalent(om.MMatrix.kIdentity, 1e-5):
                continue  # fk_blend ya conectó el worldMatrix tal cual

            calibration_mmx = cmds.createNode("multMatrix", name=joint.replace("_JNT", "IkCalibration_MMX"), ss=True)
            cmds.setAttr(f"{calibration_mmx}.matrixIn[0]", list(correction), type="matrix")
            cmds.connectAttr(f"{ik_joint}.worldMatrix[0]", f"{calibration_mmx}.matrixIn[1]")
            cmds.connectAttr(f"{calibration_mmx}.matrixSum", f"{self.blend_matrices[i][0]}.inputMatrix", force=True)

    def foot_attributes(self):

        foot_ctl = self.ik_controllers[0]
        toe_sdk = self.ik_sdk_nodes[1]
        ball_sdk = self.ik_sdk_nodes[2]
        foot_sdk = self.ik_sdk_nodes[0]

        cmds.addAttr(foot_ctl, longName="EXTRA_ATTRIBUTES", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{foot_ctl}.EXTRA_ATTRIBUTES", keyable=False, channelBox=True, lock=True)

        for attr in ["Ankle_Twist", "Ball_Twist", "Toe_Twist", "Roll"]:
            cmds.addAttr(foot_ctl, longName=attr, attributeType="float", defaultValue=0, keyable=True)
        cmds.addAttr(foot_ctl, longName="Roll_Break_Angle", attributeType="float", defaultValue=45, keyable=True)
        cmds.addAttr(foot_ctl, longName="Roll_Straight_Angle", attributeType="float", defaultValue=90, keyable=True)

        cmds.connectAttr(f"{foot_ctl}.Ankle_Twist", f"{foot_sdk}.rotateY")
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

    def bendys_setup(self):

        """
        Bendys estilo TFG: un control por segmento del IK principal (a mitad
        del hueso, siguiendo el blend FK/IK) y un ribbon de Boor por tramo
        [inicio, bendy, fin] que genera las joints de skinning. El twist viaja
        solo: los up del ribbon salen de las matrices blendeadas de cada
        extremo. El tramo Fetlock->Pastern y el Tip se cubren con joints directas.
        """
        segment_count = self.main_end_index
        if segment_count == 2:
            segment_names = ["Upper", "Lower"]
        elif segment_count == 3:
            segment_names = ["Upper", "Middle", "Lower"]
        else:
            segment_names = [f"Segment0{i}" for i in range(segment_count)]

        blend_wm = [f"{bm[0]}.outputMatrix" for bm in self.blend_matrices]
        cv_nodes = [bm[0] for bm in self.blend_matrices]

        # Non-roll del primer segmento (pairblends del TFG): la cadera blendeada
        # se realinea contra una referencia sin twist (root IK o GRP del primer
        # FK según el switch) y se re-aima a la rodilla. Evita el flip de twist
        # del hip en el ribbon del primer bendy.
        non_roll_space = cmds.createNode("blendMatrix", name=f"{self.module_name}NonRollSpace_BLM", ss=True)
        cmds.connectAttr(f"{self.root_ik_nodes[0]}.worldMatrix[0]", f"{non_roll_space}.inputMatrix")
        cmds.connectAttr(f"{self.fk_nodes[0]}.worldMatrix[0]", f"{non_roll_space}.target[0].targetMatrix")
        cmds.connectAttr(f"{self.settings_ctl}.Ik_Fk", f"{non_roll_space}.target[0].weight")

        non_roll_align = cmds.createNode("blendMatrix", name=f"{self.module_name}NonRollAlign_BLM", ss=True)
        cmds.connectAttr(blend_wm[0], f"{non_roll_align}.inputMatrix")
        cmds.connectAttr(f"{non_roll_space}.outputMatrix", f"{non_roll_align}.target[0].targetMatrix")
        cmds.setAttr(f"{non_roll_align}.target[0].translateWeight", 0)
        cmds.setAttr(f"{non_roll_align}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{non_roll_align}.target[0].shearWeight", 0)

        non_roll_aim = cmds.createNode("aimMatrix", name=f"{self.module_name}NonRollAim_AMX", ss=True)
        cmds.connectAttr(f"{non_roll_align}.outputMatrix", f"{non_roll_aim}.inputMatrix")
        cmds.connectAttr(blend_wm[1], f"{non_roll_aim}.primary.primaryTargetMatrix")
        cmds.setAttr(f"{non_roll_aim}.primaryInputAxis", *self.primary_axis, type="double3")

        self.raw_hip_blend = blend_wm[0]  # con twist, para el bendy ctl
        blend_wm[0] = f"{non_roll_aim}.outputMatrix"
        cv_nodes[0] = non_roll_aim

        # Roll anti-flip en el RESTO de joints del IK principal (igual que el
        # bípedo): cada CV del ribbon recibe un frame con el eje lateral estable
        # + el twist limpio (swing-twist), en vez del blend crudo que flippea.
        # roll_wm guarda el plug de cada frame (para el ribbon y el bendy ctl).
        roll_wm = list(blend_wm)
        roll_wm[0] = f"{non_roll_aim}.outputMatrix"
        for i in range(1, self.main_end_index + 1):
            aim_target = blend_wm[i + 1] if i + 1 < len(blend_wm) else blend_wm[i]
            cv_nodes[i] = self._roll_cv(blend_wm[i], aim_target, f"{self.module_name}Roll0{i}")
            roll_wm[i] = f"{cv_nodes[i]}.matrixSum"

        bendy_grp = cmds.createNode("transform", name=f"{self.module_name}BendyControllers_GRP", ss=True, p=self.controllers_grp)
        cmds.setAttr(f"{bendy_grp}.inheritsTransform", 0)

        aim_axis = "x" if self.side == "L" else "-x"

        # Up estable para las joints de skinning: alineamos su Z lateral al eje X
        # del masterwalk (referencia que NO se pliega) en vez de derivar la Z del
        # cross aim×up del de Boor (que la inclinaba en los acodamientos, p.ej. el
        # gaskin). Resultado: X=hueso, Y=delante/atrás, Z=lateral limpio en toda la
        # cadena, sin flip y consistente con el chain. up_object_vector = lado
        # (+X en L, -X en R) para que la Z mire al lateral correcto.
        up_object_vector = (self.side_vec.x, self.side_vec.y, self.side_vec.z)

        # El último joint de cada tramo se queda a 0.95 para no solaparse con
        # el primero del tramo siguiente (mismo truco que el TFG)
        params = [i / (self.skinning_jnts - 1) for i in range(self.skinning_jnts)]
        params[-1] = 0.95

        self.bendy_ctls = []
        for i in range(segment_count):

            name = f"{self.module_name}{segment_names[i]}Bendy"

            mid_blm = cmds.createNode("blendMatrix", name=f"{name}_BLM", ss=True)
            # Rotación desde los frames ROLL limpios (anti-flip), no el blend crudo
            cmds.connectAttr(self.raw_hip_blend if i == 0 else roll_wm[i], f"{mid_blm}.inputMatrix")
            cmds.connectAttr(roll_wm[i + 1], f"{mid_blm}.target[0].targetMatrix")
            cmds.setAttr(f"{mid_blm}.target[0].translateWeight", 0.5)
            cmds.setAttr(f"{mid_blm}.target[0].rotateWeight", 0)
            cmds.setAttr(f"{mid_blm}.target[0].scaleWeight", 0)
            cmds.setAttr(f"{mid_blm}.target[0].shearWeight", 0)

            if i == 0:
                # Medio twist en el bendy de la cadera (TFG): blend de rotación
                # 0.5 entre la cadera con twist y la versión non-roll
                cmds.connectAttr(roll_wm[0], f"{mid_blm}.target[1].targetMatrix")
                cmds.setAttr(f"{mid_blm}.target[1].translateWeight", 0)
                cmds.setAttr(f"{mid_blm}.target[1].rotateWeight", 0.5)
                cmds.setAttr(f"{mid_blm}.target[1].scaleWeight", 0)
                cmds.setAttr(f"{mid_blm}.target[1].shearWeight", 0)

            bendy_nodes, bendy_ctl = curve_tool.create_controller(name=name, offset=["GRP", "ANM"], parent=bendy_grp)
            self.lock_attributes(bendy_ctl, ["sx", "sy", "sz", "v"])
            cmds.connectAttr(f"{mid_blm}.outputMatrix", f"{bendy_nodes[0]}.offsetParentMatrix")
            self.bendy_ctls.append(bendy_ctl)

            segment_jnts, temp = ribbon.de_boor_ribbon(
                cvs=(cv_nodes[i], bendy_ctl, cv_nodes[i + 1]),
                aim_axis=aim_axis, up_axis="z", num_joints=self.skinning_jnts,
                skeleton_grp=self.skeleton_grp, name=name, custom_parameter=params,
                up_object=self.masterwalk_ctl, up_object_vector=up_object_vector,
            )
            for t in temp:
                cmds.delete(t)

        # Fetlock, Pastern y Tip (el tramo del pie no lleva bendy)
        fetlock_skinning = cmds.createNode("joint", name=f"{self.module_name}FetlockSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(blend_wm[self.main_end_index], f"{fetlock_skinning}.offsetParentMatrix")

        pastern_skinning = cmds.createNode("joint", name=f"{self.module_name}PasternSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(blend_wm[self.plant_index], f"{pastern_skinning}.offsetParentMatrix")

        tip_offset = om.MMatrix(self.guides_matrices[-1]) * om.MMatrix(self.guides_matrices[self.plant_index]).inverse()
        tip_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}TipSkinning_MMX", ss=True)
        cmds.setAttr(f"{tip_mmx}.matrixIn[0]", list(tip_offset), type="matrix")
        cmds.connectAttr(blend_wm[self.plant_index], f"{tip_mmx}.matrixIn[1]")
        tip_skinning = cmds.createNode("joint", name=f"{self.module_name}TipSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{tip_mmx}.matrixSum", f"{tip_skinning}.offsetParentMatrix")

    def skinning_setup(self):

        """
        Sin bendys: las guías importadas (ya dirigidas por los blend FK/IK) se
        quedan como cadena de skinning con el sufijo Skinning bajo el grupo de
        esqueleto. Con bendys, el skinning son los ribbons + ankle/ball/tip y
        la cadena guía se queda oculta como esqueleto de blend del módulo.
        """
        if self.bendys:
            cmds.setAttr(f"{self.leg_chain[0]}.visibility", 0)
            return

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
    Pierna delantera (anatomía equina): {side}_scapula_JNT -> Shoulder -> Elbow
    -> Ankle -> Fetlock -> Pastern -> Tip. Misma construcción que la trasera (el
    PV se calcula del plano real de la cadena, así que el bend invertido del
    carpo sale solo) más la escápula (master + escápula aimada al root de la
    pierna + end con space switch), portada del dragon_leg del TFG.
    """

    LEG_PREFIX = "frontLeg"
    ROOT_JOINT = "Shoulder"  # la delantera arranca en el shoulder (no hip)
    SEED_STRAIGHT_BEND = True  # delantera casi recta: hay que sembrar el bend
    # PV desde el carpo (la "rodilla" equina = índice 2). Hereda PV_APEX_INDEX = 2.

    def make(self, side, solver="spring", skinning_jnts=5, bendys=True, primaryInputAxis=(1, 0, 0), secondaryInputAxis=(0, 1, 0)):
        super().make(side, solver=solver, skinning_jnts=skinning_jnts, bendys=bendys,
                     primaryInputAxis=primaryInputAxis, secondaryInputAxis=secondaryInputAxis)
        self.scapula_setup()

    def load_guides(self):

        """
        La cadena delantera cuelga de la escápula: {side}_scapula_JNT ->
        Shoulder -> ... -> Tip. Se importa todo desde la escápula, se separa la
        pierna y la guía de escápula se hornea (posición) y se borra.
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
