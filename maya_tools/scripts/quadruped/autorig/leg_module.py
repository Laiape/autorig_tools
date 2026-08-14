import maya.cmds as cmds
import maya.mel as mel
import maya.api.OpenMaya as om
from importlib import reload
import math

from maya_tools.scripts.utils import data_manager
from maya_tools.scripts.utils import guides_manager
from maya_tools.scripts.utils import curve_tool
from maya_tools.scripts.utils import matrix_manager
from maya_tools.scripts.utils import ribbon

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)
reload(ribbon)


# Ejes canónicos: las guías solo dan POSICIÓN; la orientación se construye con
# estas variables (nunca hardcodeadas), así un cambio de convención se propaga.
_AXIS_VECTORS = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}


def _axis_letter(vec):
    """Letra del eje ('x'/'y'/'z') de un vector tipo (1,0,0), ignorando el signo."""
    a = tuple(round(abs(c)) for c in vec)
    for letter, v in _AXIS_VECTORS.items():
        if a == tuple(int(c) for c in v):
            return letter
    return "x"


def _third_axis_letter(a, b):
    """La letra de eje restante dadas otras dos (p.ej. 'x','y' -> 'z')."""
    return ({"x", "y", "z"} - {a, b}).pop()


def _axis_letter_signed(vec):
    """Letra con signo ('x'/'-x'/'z'...) de un vector tipo (-1,0,0)."""
    letter = _axis_letter(vec)
    idx = {"x": 0, "y": 1, "z": 2}[letter]
    return ("-" + letter) if vec[idx] < 0 else letter


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
    ROOT_JOINT = "Hip"
    PV_APEX_INDEX = 2
    STANDARD_JOINT_COUNT = 6
    SIDE_AXIS = (1, 0, 0)
    SEED_STRAIGHT_BEND = False
    FORWARD_AXIS = (0, 0, -1)
    PV_SIGN = 1
    REPOSITION_IK_TO_GUIDES = False
    # Aparato recíproco: solo el miembro POSTERIOR lo tiene (la delantera no).
    RECIPROCAL_FK = False
    # Ratio corvejón/babilla del acoplamiento en FK. MEDIDO del propio spring de
    # esta cadena (headless, ballIk.ty 5→40): -1.092 → -1.088, estable <0.5% en
    # todo el rango de flexión. O sea: el acoplamiento lineal REPRODUCE lo que el
    # spring ya hace por construcción, no lo aproxima. Signo negativo = el zigzag
    # (la babilla abre cranial y el corvejón caudal). Recalibrar si cambian las guías.
    RECIPROCAL_RATIO = -1.09

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
        self.aim_letter = _axis_letter(primaryInputAxis)
        self.fb_letter = _axis_letter(secondaryInputAxis)
        self.up_letter = _third_axis_letter(self.aim_letter, self.fb_letter)
        self.up_axis = _AXIS_VECTORS[self.up_letter]
        self.aim_axis_str = _axis_letter_signed(self.primary_axis)
        self.side_vec = om.MVector(*self.SIDE_AXIS) * (1 if side == "L" else -1)
        self.lateral_ref = self.side_vec * -1

        self.module_name = f"{self.side}_{self.LEG_PREFIX}"
        self.module_trn = cmds.createNode("transform", name=f"{self.module_name}Module_GRP", ss=True, p=self.modules)
        self.skeleton_grp = cmds.createNode("transform", name=f"{self.module_name}Skinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}Controllers_GRP", ss=True, p=self.masterwalk_ctl)

        self.load_guides()
        self.create_chains()
        self.controllers_creation()
        self.ik_setup()
        self.ik_stretch_soft()
        self._bend_bias(self.ik_ctl["ankleIk"])  # tras stretch/soft: fija el orden del channel box
        self.ik_calibration()
        self.foot_attributes()
        self.fk_stretch()
        if self.RECIPROCAL_FK:
            self.reciprocal_fk_coupling()
        if self.bendys:
            self.bendys_setup()
        self.skinning_setup()
        self.foot_offset_setup()

        data_manager.DataExportBiped().append_data(f"{self.LEG_PREFIX}_module",
                            {
                                f"{self.side}_hip_JNT": self.leg_joints[0],
                                f"{self.side}_legIk": self.ik_controllers[0],
                                f"{self.side}_hipFk": self.fk_controllers[0],
                                f"{self.side}_legPv": self.pv_ctl,
                                f"{self.side}_rootIk": self.root_ik_ctl,
                                f"{self.side}_ikFkSwitch": self.settings_ctl,
                                f"{self.side}_bendy_ctls": getattr(self, "bendy_ctls", []),
                                f"{self.side}_footOffset": getattr(self, "foot_offset_ctl", None),
                                # Articulación metacarpo/metatarsofalángica (el "menudillo" del
                                # équido). Es el MISMO hueso en el ungulado y en el digitígrado:
                                # el caballo tiene un solo dedo a partir de aquí y el perro
                                # cuatro. digits_module cuelga los dedos de este joint.
                                f"{self.side}_mtp_JNT": self.foot_skin_drivers[0][0] if getattr(self, "foot_skin_drivers", None) else None,
                            })

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
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

        self.pv_apex_index = self.PV_APEX_INDEX if len(self.leg_chain) == self.STANDARD_JOINT_COUNT else 1
        self.pv_apex_index = max(1, min(self.pv_apex_index, self.leg_end_index - 1))

        # Posiciones world de las guías (de los joints importados tal cual)
        self.guide_positions = [om.MVector(cmds.xform(j, q=True, ws=True, t=True)) for j in self.leg_chain]
        side_ref = self.lateral_ref  # lateral de orientación (Y hacia delante)
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

        ik_positions = list(self.guide_positions)
        if self.SEED_STRAIGHT_BEND:
            bulge = bend_dir * (-self.leg_line_len * 0.1)
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
        cmds.setAttr(f"{nonroll}.secondaryInputAxis", *self.up_axis, type="double3")  # eje lateral local
        cmds.setAttr(f"{nonroll}.secondaryMode", 2)  # alinear al vector
        cmds.setAttr(f"{nonroll}.secondaryTargetVector", self.lateral_ref.x, self.lateral_ref.y, self.lateral_ref.z, type="double3")

        twist_qn = matrix_manager.extract_twist(blend_plug, f"{nonroll}.outputMatrix", axis=self.aim_letter, name=name, return_quat=True)
        cmp = cmds.createNode("composeMatrix", name=f"{name}RollTwist_CMP", ss=True)
        cmds.setAttr(f"{cmp}.useEulerRotation", 0)
        cmds.connectAttr(f"{twist_qn}.outputQuat", f"{cmp}.inputQuat")
        roll = cmds.createNode("multMatrix", name=f"{name}Roll_MMX", ss=True)
        cmds.connectAttr(f"{cmp}.outputMatrix", f"{roll}.matrixIn[0]")
        cmds.connectAttr(f"{nonroll}.outputMatrix", f"{roll}.matrixIn[1]")
        return roll

    def _build_frames(self, positions, lateral_ref):
        """
        Frames a partir de POSICIONES + la convención de ejes del módulo: aim
        (aim_letter) baja por el hueso, lateral (up_letter) se alinea a
        lateral_ref, y delante/atrás (fb_letter) sale del cruz. Las tres se
        colocan en las filas X/Y/Z según sus letras (sin hardcodear ejes).
        """
        frames = []
        aim = om.MVector(*_AXIS_VECTORS[self.aim_letter])
        for i, pos in enumerate(positions):
            if i < len(positions) - 1:
                aim = (positions[i + 1] - pos).normal()
            fb = (lateral_ref ^ aim).normal()
            lateral = (aim ^ fb).normal()
            rows = {self.aim_letter: aim, self.fb_letter: fb, self.up_letter: lateral}
            rx, ry, rz = rows["x"], rows["y"], rows["z"]
            frames.append(om.MMatrix([
                rx.x, rx.y, rx.z, 0.0,
                ry.x, ry.y, ry.z, 0.0,
                rz.x, rz.y, rz.z, 0.0,
                pos.x, pos.y, pos.z, 1.0,
            ]))
        return frames

    def create_chains(self):

        # Settings ctl junto al pie, desplazado hacia fuera
        leg_length = (self.guide_positions[self.plant_index] - self.guide_positions[0]).length()
        offset = leg_length * 0.25 * (1 if self.side == "L" else -1)
        settings_pos = self.guide_positions[self.plant_index] + om.MVector(offset, 0.0, 0.0)

        self.settings_node, self.settings_ctl = curve_tool.create_controller(name=f"{self.module_name}Settings", offset=["GRP"])
        curve_tool.lock_attributes(self.settings_ctl, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v", "rotateOrder"])
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
            curve_tool.lock_attributes(fk_ctl, ["tx", "ty", "tz", "sx", "sy", "sz", "v"])

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
        # -> heelIk (talón) -> toeIk (punta) -> ballIk (pisada)
        ankle_rest = self._translation_matrix(self.guide_positions[self.leg_end_index])
        if self.side == "R":
            ankle_rest = self._mirror_matrix(ankle_rest)

        # Talón del casco. El caballo apoya SOLO el casco, así que sus pivotes son
        # la punta (breakover) y el talón — la planta/talón del bípedo no aplican.
        # No hay guía de talón, así que se deriva de las que hay: el casco va de la
        # punta (Tip, en el suelo) a los talones, que caen bajo la cuartilla, o sea
        # el Pastern (pisada) proyectado al suelo. Y "el suelo" es la única
        # referencia de contacto que dan las guías: la altura del Tip (el repo no
        # tiene noción de suelo, y esto no la inventa). Medido en horse_v001: da un
        # casco de punta a talón de ~9.5u ≈ 13 cm a la escala del asset, que es la
        # longitud real de un casco -> la derivación se sostiene.
        # Lleva el frame del Tip para que su rotateZ sea la MISMA flexión sagital
        # que el roll de punta/ball, solo que con otro pivote.
        heel_pos = om.MVector(self.guide_positions[self.plant_index])
        heel_pos.y = self.guide_positions[-1].y  # Y = arriba (misma convención que la escápula)
        heel_matrix = list(tip_matrix[:12]) + [heel_pos.x, heel_pos.y, heel_pos.z, 1.0]

        rest_matrices = {
            "ankleIk": ankle_rest,
            "heelIk": heel_matrix,
            "toeIk": tip_matrix,
            "ballIk": plant_matrix,
        }

        self.ik_nodes = []
        self.ik_sdk_nodes = []
        self.ik_controllers = []

        previous_rest = None
        for name, rest in rest_matrices.items():
            ik_node, ik_ctl = curve_tool.create_controller(name=f"{self.module_name}{name[0].upper()}{name[1:]}", offset=["GRP", "SDK"])
            curve_tool.lock_attributes(ik_ctl, ["sx", "sy", "sz", "v"])

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

        # Acceso por nombre: el pie reverso ya tiene cuatro pivotes y los índices
        # posicionales se rompen en cuanto se inserta uno nuevo en la cadena.
        self.ik_ctl = dict(zip(rest_matrices, self.ik_controllers))
        self.ik_sdk = dict(zip(rest_matrices, self.ik_sdk_nodes))

        # Root IK
        self.root_ik_nodes, self.root_ik_ctl = curve_tool.create_controller(name=f"{self.module_name}RootIk", offset=["GRP", "ANM"])
        curve_tool.lock_attributes(self.root_ik_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])
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
        self.pv_nodes, self.pv_ctl, self.pv_orient_blm = self._create_pv_control(
            f"{self.module_name}Pv", self.pv_apex_index, ik_controllers_trn)

    def _create_pv_control(self, name, apex_index, parent_trn):

        """
        Crea un control de pole vector (con su grupo, el blendMatrix de
        orientación pvOrientation y la línea apex->PV). Devuelve
        (nodes, ctl, orient_blm). La posición de reposo se hornea luego en
        ik_setup/_place_pv desde el PV automático del handle.
        """
        pv_nodes, pv_ctl = curve_tool.create_controller(name=name, offset=["GRP", "ANM"])
        curve_tool.lock_attributes(pv_ctl, ["rx", "ry", "rz", "sx", "sy", "sz", "v"])

        cmds.addAttr(pv_ctl, longName="extraAttr", niceName="EXTRA ATTRIBUTES ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{pv_ctl}.extraAttr", channelBox=True, lock=True)
        cmds.addAttr(pv_ctl, longName="pvOrientation", niceName="Pv Orientation", attributeType="float", defaultValue=0, minValue=0, maxValue=1, keyable=True)

        # pvOrientation (TFG): 0 = orientado a mundo, 1 = Z apuntando al apex
        pv_orient_blm = cmds.createNode("blendMatrix", name=f"{name}Orient_BLM", ss=True)
        cmds.connectAttr(f"{pv_ctl}.pvOrientation", f"{pv_orient_blm}.target[0].weight")
        cmds.connectAttr(f"{pv_orient_blm}.outputMatrix", f"{pv_nodes[0]}.offsetParentMatrix")

        cmds.parent(pv_nodes[0], parent_trn)
        cmds.xform(pv_nodes[0], m=om.MMatrix.kIdentity)

        # Línea que apunta del apex (carpo/corvejón) al PV
        crv_point_pv = cmds.curve(d=1, p=[(0, 0, 1), (0, 1, 0)], n=f"{name}_CRV")
        row_apex = cmds.createNode("rowFromMatrix", name=f"{name}_RFM", ss=True)
        row_ctl = cmds.createNode("rowFromMatrix", name=f"{name}Ctl_RFM", ss=True)
        cmds.setAttr(f"{row_apex}.input", 3)
        cmds.setAttr(f"{row_ctl}.input", 3)
        cmds.connectAttr(f"{pv_ctl}.worldMatrix[0]", f"{row_ctl}.matrix")
        cmds.connectAttr(f"{self.ik_chain[apex_index]}.worldMatrix[0]", f"{row_apex}.matrix")
        for axis, value in zip("XYZ", ("xValue", "yValue", "zValue")):
            cmds.connectAttr(f"{row_apex}.output{axis}", f"{crv_point_pv}.controlPoints[0].{value}")
            cmds.connectAttr(f"{row_ctl}.output{axis}", f"{crv_point_pv}.controlPoints[1].{value}")
        cmds.setAttr(f"{crv_point_pv}.inheritsTransform", 0)
        cmds.setAttr(f"{crv_point_pv}.overrideEnabled", 1)
        cmds.setAttr(f"{crv_point_pv}.overrideDisplayType", 1)
        cmds.setAttr(f"{crv_point_pv}.hiddenInOutliner", 1)
        cmds.parent(crv_point_pv, pv_ctl)
        return pv_nodes, pv_ctl, pv_orient_blm

    def _place_pv(self, ik_handle, pv_ctl, pv_orient_blm, apex_index):

        """
        Coloca un PV geométricamente en WORLD, en el plano sagital de la pata:
        apex + bend_dir * media-longitud * PV_SIGN. Orienta el blendMatrix
        (up al apex, aim alineado al aim del apex) y aplica el
        poleVectorConstraint. El reposo del solve lo corrige ik_calibration, así
        que la posición es libre geométricamente.
        """
        apex_p = self.guide_positions[apex_index]
        distance = self.leg_line_len * 0.5
        pv_pos = apex_p + self.bend_dir * distance * self.PV_SIGN

        aim_row = {"x": 0, "y": 1, "z": 2}[self.aim_letter] * 4
        m = self.guides_matrices[apex_index]
        apex_aim_axis = om.MVector(m[aim_row], m[aim_row + 1], m[aim_row + 2])
        cmds.setAttr(f"{pv_orient_blm}.inputMatrix", self._translation_matrix(pv_pos), type="matrix")
        pv_aimed = guides_manager._aim_matrix(pv_pos, apex_p, pv_pos + apex_aim_axis,
                                              self.up_axis, _AXIS_VECTORS[self.aim_letter])
        cmds.setAttr(f"{pv_orient_blm}.target[0].targetMatrix", list(pv_aimed), type="matrix")

        # poleVectorConstraint clásico: con los preferred angles puestos y el
        # PV sobre la dirección automática, preserva el reposo exacto.
        cmds.poleVectorConstraint(pv_ctl, ik_handle)

    def ik_setup(self):

        """
        ikHandles nativos: el IK principal (spring o RP según el argumento) va
        de la cadera al Ankle — genérico en número de huesos — y el pie se
        resuelve con SC: Ankle -> Ball y Ball -> Tip. Con 2 huesos el spring no
        aporta nada y se cae a RP.
        """
        foot_ctl, toe_ctl, ball_ctl = self.ik_ctl["ankleIk"], self.ik_ctl["toeIk"], self.ik_ctl["ballIk"]
        handles = []

        self.main_end_index = self.leg_end_index

        # Sin preferred angles el spring no codifica el zigzag de reposo y las
        # rodillas saltan al pasar a IK (verificado: drift ~10u -> 0 con spa)
        cmds.joint(self.ik_chain[0], e=True, setPreferredAngles=True, children=True)

        # El preferredAngle ya quedó capturado del pre-bend. Si el módulo lo pide,
        # reposicionamos la cadena IK EXACTAMENTE sobre las guías: las joints del
        # solver reposan en su sitio (nada desplazado) y, como el reposo del solve
        # coincide con las guías, la calibración queda en identidad y el fold sigue
        # la dirección del DOBLEZ DE LA GUÍA. Lo activan las DOS subclases concretas
        # (BackLegModule:1314 y FrontLegModule:1336); el False de LegModule es solo
        # el defecto de la clase base, que ninguna pata construida llega a usar.
        if self.REPOSITION_IK_TO_GUIDES:
            for i, ik_joint in enumerate(self.ik_chain):
                cmds.xform(ik_joint, ws=True, m=list(self.guides_matrices[i]))

        self._ik_setup_single(foot_ctl, toe_ctl, ball_ctl, handles)

        freeze_float_constant = cmds.createNode("floatConstant", name=f"{self.module_name}Freeze_FCN", ss=True)
        cmds.setAttr(f"{freeze_float_constant}.inFloat", 0)
        for handle in handles:
            cmds.parent(handle, self.module_trn)
            cmds.setAttr(f"{handle}.visibility", 0)
            for attr in ["translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"]:
                cmds.connectAttr(f"{freeze_float_constant}.outFloat", f"{handle}.{attr}")

        self._place_pv(self.ik_handle, self.pv_ctl, self.pv_orient_blm, self.pv_apex_index)

    def _ik_setup_single(self, foot_ctl, toe_ctl, ball_ctl, handles):

        """IK clásico de una capa: spring/RP Hip->Fetlock + pie SC."""
        ankle_index = self.leg_end_index

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
            self.fetlock_follow_mmx = ankle_follow_mmx  # foot_attributes le inyecta el muelle

            ball_handle = cmds.ikHandle(name=f"{self.module_name}BallIk_HDL", startJoint=self.ik_chain[ankle_index],
                                        endEffector=self.ik_chain[self.plant_index], solver="ikSCsolver")[0]
            cmds.connectAttr(f"{ball_ctl}.worldMatrix[0]", f"{ball_handle}.offsetParentMatrix")
            handles.append(ball_handle)
        else:
            # Sin Ball separado: el IK principal acaba en la pisada. Sin hueso de
            # cuartilla no hay ángulo menudillo-cuartilla que hundir: no hay muelle.
            cmds.connectAttr(f"{ball_ctl}.worldMatrix[0]", f"{self.ik_handle}.offsetParentMatrix")
            self.ik_handle_target = f"{ball_ctl}.worldMatrix[0]"
            self.fetlock_follow_mmx = None

        toe_handle = cmds.ikHandle(name=f"{self.module_name}ToeIk_HDL", startJoint=self.ik_chain[self.plant_index],
                                   endEffector=self.ik_chain[-1], solver="ikSCsolver")[0]
        cmds.connectAttr(f"{toe_ctl}.worldMatrix[0]", f"{toe_handle}.offsetParentMatrix")
        handles.append(toe_handle)
        # _bend_bias se llama desde make() DESPUÉS de ik_stretch_soft para que el orden
        # del channel box sea stretchy, soft, bias, ... (el bias es no-op sin spring).

    def _bend_bias(self, foot_ctl):

        """
        Reparto del doblez entre las articulaciones REALES del spring. Una cadena de
        3 huesos con la raíz y el pie clavados tiene exactamente UN grado de libertad
        redundante: qué parte del plegado se lleva el codo y qué parte el carpo. Ese
        DOF es lo que el animador quiere tocar para marcar el galope, y el
        `springAngleBias` del propio ikSpringSolver ya lo expone — no hace falta ni un
        control extra ni un joint más.

        Un solo atributo porque el DOF es uno: subirlo carga el doblez arriba (codo),
        bajarlo lo carga abajo (carpo). Los dos slots del bias van complementarios
        (b, 1-b): el bias UNIFORME es un no-op medido (0.0/0.25/0.5/0.75/1.0 en los
        dos slots -> codo 81.74° y carpo 95.45° en las cinco), lo que mueve el reparto
        es la RAZÓN entre slots.

        Medido headless (delantera, plegado recogido de galope, pie ty=25 tz=-8):
        bias 0.0 -> codo 105.9°/carpo 75.8° · 0.5 -> 81.7°/95.5° (defecto, el reparto
        natural del solver) · 1.0 -> 70.4°/126.9°. O sea ~35° de autoridad en el codo
        y ~51° en el carpo, monótono y sin saltos. Defecto 0.5 = el reparto que ya
        daba el solver, así que el reposo y el match FK/IK no se mueven.
        """
        idx = cmds.getAttr(f"{self.ik_handle}.springAngleBias", multiIndices=True) or []
        if len(idx) < 2:
            return

        cmds.addAttr(foot_ctl, longName="BEND", niceName="BEND ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{foot_ctl}.BEND", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(foot_ctl, longName="Bend_Bias", attributeType="float", minValue=0, maxValue=1, defaultValue=0.5, keyable=True)

        bias_rev = cmds.createNode("reverse", name=f"{self.module_name}BendBias_REV", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Bend_Bias", f"{bias_rev}.inputX")
        cmds.connectAttr(f"{foot_ctl}.Bend_Bias", f"{self.ik_handle}.springAngleBias[{idx[0]}].springAngleBias_FloatValue")
        cmds.connectAttr(f"{bias_rev}.outputX", f"{self.ik_handle}.springAngleBias[{idx[-1]}].springAngleBias_FloatValue")

    def ik_stretch_soft(self):

        """
        Stretch y soft IK sobre los handles nativos, genérico para 2 o 3
        segmentos: el stretch escala el translateX de los joints IK con el
        ratio distancia/longitud (normalizado por globalScale, estilo del
        stretch del bípedo) y el soft amortigua la posición del handle con la
        curva exponencial clásica, recolocándolo con composeMatrix * aimMatrix.
        """
        foot_ctl = self.ik_ctl["ankleIk"]
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

        foot_ctl = self.ik_ctl["ankleIk"]
        foot_sdk = self.ik_sdk["ankleIk"]
        heel_sdk = self.ik_sdk["heelIk"]
        toe_sdk = self.ik_sdk["toeIk"]
        ball_sdk = self.ik_sdk["ballIk"]

        # Fetlock antes que los extras: fija el orden del channel box (…bias, fetlock, extras).
        self._fetlock_spring(foot_ctl)

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

        # Signo del roll por lado: los frames del pie de la R son MIRROR de los de la
        # L (Z lateral invertida), así que el mismo rotateZ local gira en sentidos
        # opuestos en mundo. Para que la L salga mirror exacto de la R, el roll va con
        # signo +1 en L y -1 en R, TANTO en la punta como en el ball. (Antes se negaba
        # igual en ambos: en la L el toe-roll caía en el sentido MUERTO del SC
        # Pastern->Tip —la punta no rodaba— y el ball rodaba hacia el lado contrario.
        # Verificado headless: con este signo dTip de la L == X-mirror de la R, err 0.)
        roll_sign = 1 if self.side == "L" else -1

        # Roll NEGATIVO: pivote del talón. Antes era un no-op verificado (el
        # roll_break_angle tiene inputMin=0, así que Roll<0 clampaba a 0 y el
        # roll_lift multiplicaba por 0: no movía nada). El `min` aísla el tramo
        # negativo, así que el positivo (ball -> punta) sigue exactamente igual.
        # Signo INVERTIDO respecto al roll positivo, y no por convención de frames:
        # bascular hacia atrás sobre el talón es el giro CONTRARIO a rodar hacia
        # delante sobre la punta. Medido headless: con el mismo signo la punta se
        # hundía bajo el suelo (tip.y 0.43 -> -4.33 con Roll=-30); con este, sube.
        # Límite medido: bascular sobre el talón ALEJA el menudillo de la cadera y la
        # trasera ya reposa al 94.1% de extensión, así que a partir de ~-25° la cadena
        # no llega y el casco deja de girar rígido (-2.3% a -30°). No es del talón: es
        # alcance. Con Stretch=1 el pivote vuelve a ser rígido exacto hasta -40°.
        heel_roll = cmds.createNode("min", name=f"{self.module_name}RollHeel_MIN", ss=True)
        cmds.setAttr(f"{heel_roll}.input[0]", 0)
        cmds.connectAttr(f"{foot_ctl}.Roll", f"{heel_roll}.input[1]")
        heel_roll_sign = cmds.createNode("multiply", name=f"{self.module_name}RollHeel_MUL", ss=True)
        cmds.connectAttr(f"{heel_roll}.output", f"{heel_roll_sign}.input[0]")
        cmds.setAttr(f"{heel_roll_sign}.input[1]", -roll_sign)
        cmds.connectAttr(f"{heel_roll_sign}.output", f"{heel_sdk}.rotateZ")

        multiply_node = cmds.createNode("multiply", name=f"{self.module_name}RollStraightAngle_MUL", ss=True)
        cmds.connectAttr(f"{roll_straight_angle}.outValue", f"{multiply_node}.input[0]")
        cmds.connectAttr(f"{foot_ctl}.Roll", f"{multiply_node}.input[1]")
        toe_roll_sign = cmds.createNode("multiply", name=f"{self.module_name}RollStraight_NEG", ss=True)
        cmds.connectAttr(f"{multiply_node}.output", f"{toe_roll_sign}.input[0]")
        cmds.setAttr(f"{toe_roll_sign}.input[1]", roll_sign)
        cmds.connectAttr(f"{toe_roll_sign}.output", f"{toe_sdk}.rotateZ")

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
        lift_roll_sign = cmds.createNode("multiply", name=f"{self.module_name}RollLift_NEG", ss=True)
        cmds.connectAttr(f"{roll_lift_angle_mul}.output", f"{lift_roll_sign}.input[0]")
        cmds.setAttr(f"{lift_roll_sign}.input[1]", roll_sign)
        cmds.connectAttr(f"{lift_roll_sign}.output", f"{ball_sdk}.rotateZ")

    def _fetlock_spring(self, foot_ctl):

        """
        Muelle del menudillo. El menudillo se hunde por CARGA, no por rotación
        activa: el SDFT se estira y devuelve el 93% del trabajo. Antes era rígido —
        `ankle_offset` era una constante horneada y el handle principal y el SC
        Fetlock->Pastern colgaban los dos del MISMO ball_ctl, así que el ángulo
        menudillo-cuartilla no cambiaba nunca.

        Se inyecta una rotación en el follow del menudillo: opm = offset * C * ball.
        C queda con el pivote en el ball_ctl, o sea en la CUARTILLA (Pastern), que es
        el punto correcto: el casco está plantado y la cuartilla va rígida con él,
        así que el menudillo baja girando alrededor de la cuartilla y el ángulo MCP
        se abre solo. El SC Fetlock->Pastern sigue colgando del ball_ctl y la
        distancia menudillo-cuartilla se conserva (C es un giro puro sobre ese
        pivote), así que el pie no se descoloca.

        ponytail: es un driver MANUAL — el animador dice cuánta carga hay. No hay
        detección de contacto con el suelo (el repo no tiene noción de suelo) ni
        histéresis carga/retorno (el 93% del SDFT), que es lo que separaría la
        bajada del rebote. Techo conocido: para que se hunda solo al pisar hace
        falta contacto real, y eso es un sistema aparte, no un atributo.
        """
        if not getattr(self, "fetlock_follow_mmx", None):
            return

        cmds.addAttr(foot_ctl, longName="FETLOCK", niceName="FETLOCK ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{foot_ctl}.FETLOCK", keyable=False, channelBox=True, lock=True)
        # Default 0: el muelle es una característica del ÉQUIDO (aparato de estay), no
        # del cuadrúpedo genérico — un digitígrado no lo tiene. Además, con carga en
        # reposo la cadena queda en su tope de alcance y el ball-roll se aplasta:
        # medido, el menudillo sube 7.45u con carga 0 y solo 2.25u con carga 1.
        cmds.addAttr(foot_ctl, longName="Fetlock_Load", attributeType="float", minValue=0, maxValue=1, defaultValue=0, keyable=True)
        # Recorrido a carga máxima. Por defecto 22° = la excursión MEDIDA del ángulo
        # MCP de paso a galope (~218° -> ~240°), que es el rango que se anima. El ROM
        # total del menudillo es 62°±7°, así que el atributo admite más si hace falta
        # un extremo; es el knob de calibración contra referencia.
        cmds.addAttr(foot_ctl, longName="Fetlock_Load_Angle", attributeType="float", defaultValue=22, keyable=True)

        load_rmv = cmds.createNode("remapValue", name=f"{self.module_name}FetlockLoad_RMV", ss=True)
        cmds.connectAttr(f"{foot_ctl}.Fetlock_Load", f"{load_rmv}.inputValue")
        cmds.setAttr(f"{load_rmv}.outputMin", 0)
        cmds.connectAttr(f"{foot_ctl}.Fetlock_Load_Angle", f"{load_rmv}.outputMax")
        # Curva NO lineal: el aparato suspensor es un muelle que ENDURECE al cargarse
        # (al principio se hunde fácil, luego se resiste), así que la respuesta a la
        # carga es cóncava, no una rampa. Los datos de marcha calibran el RANGO
        # (los 22°), no la forma; la forma la pone el muelle.
        # Validación headless de la trasera (ángulo MCP palmar real medido en la
        # cadena, reposo del rig = 207.6°): carga 0.25 -> 216.5° · 0.5 -> 226.7° ·
        # 1.0 -> 235.2°. Contra lo publicado (paso ~218, trote ~226, galope ~240):
        # el trote cae a 0.65° y el paso a 1.5°; el galope se queda 4.8° corto porque
        # el reposo del rig ya está por debajo del paso. Para un plano de galope,
        # subir Fetlock_Load_Angle a ~26 (eso es el knob, no una constante nueva).
        #
        # La DELANTERA también lo lleva desde que se quitó el DOUBLE_BEND: antes su
        # tramo bajo colgaba del carpus_ctl con 0.95u de holgura (96.1% de extensión)
        # y cargar el menudillo despegaba el casco, así que había una guarda. Ahora el
        # tramo lo alimenta el spring entero desde el hombro: 2.32u de holgura (2.4×),
        # y el muelle CABE. Medido (reposo 224.2°): carga 0.25 -> 233.5° con el casco
        # clavado (tip.y 1.2271, error 0). Con el cuerpo FIJO y Stretch=0 el casco se
        # despega 0.07u a 0.5 y 0.33u a 1.0 (la cadena topa contra su alcance); con
        # Stretch=1 se queda clavado a TODAS las cargas (1.2271 exacto, 0.5 -> 245.3°,
        # 1.0 -> 252.2°). ponytail: el tope es alcance con la raíz clavada, no el
        # muelle — en un galope real el cuerpo BAJA justo cuando el menudillo se hunde
        # y la holgura vuelve sola. Techo: con el cuerpo fijo y Stretch=0, carga >0.4
        # despega el casco unos milímetros; el escape ya existe (Stretch), como en el
        # pivote del talón. Upgrade si molesta: autostretch por carga, no otra guarda.
        for i, (position, value) in enumerate(((0.0, 0.0), (0.5, 0.7), (1.0, 1.0))):
            cmds.setAttr(f"{load_rmv}.value[{i}].value_Position", position)
            cmds.setAttr(f"{load_rmv}.value[{i}].value_FloatValue", value)
            cmds.setAttr(f"{load_rmv}.value[{i}].value_Interp", 3)  # spline

        # Signo por lado, igual que el roll: los frames del pie de la R son mirror.
        load_sign = cmds.createNode("multiply", name=f"{self.module_name}FetlockLoad_MUL", ss=True)
        cmds.connectAttr(f"{load_rmv}.outValue", f"{load_sign}.input[0]")
        cmds.setAttr(f"{load_sign}.input[1]", 1 if self.side == "L" else -1)

        load_cmp = cmds.createNode("composeMatrix", name=f"{self.module_name}FetlockLoad_CMP", ss=True)
        cmds.connectAttr(f"{load_sign}.output", f"{load_cmp}.inputRotateZ")

        # Se inserta C entre el offset horneado y el ball_ctl: matrixIn[1] pasa a [2].
        follow = self.fetlock_follow_mmx
        ball_plug = cmds.listConnections(f"{follow}.matrixIn[1]", plugs=True, source=True, destination=False)[0]
        cmds.disconnectAttr(ball_plug, f"{follow}.matrixIn[1]")
        cmds.connectAttr(f"{load_cmp}.outputMatrix", f"{follow}.matrixIn[1]")
        cmds.connectAttr(ball_plug, f"{follow}.matrixIn[2]")

    def fk_stretch(self):

        """FK stretch por segmento (igual que el bípedo, con matrices horneadas)."""

        for i, ctl in enumerate(self.fk_controllers[:-1]):

            cmds.addAttr(ctl, longName="STRETCHY", niceName="STRETCHY ------", attributeType="enum", enumName="------")
            cmds.setAttr(f"{ctl}.STRETCHY", keyable=False, channelBox=True, lock=True)
            cmds.addAttr(ctl, shortName="Stretch", minValue=0, defaultValue=1, keyable=True)

            # El opm del siguiente FK es un valor horneado: se reconstruye con un
            # fourByFour fijando las filas y dirigiendo solo la traslación X
            target_node = self.fk_nodes[i + 1]
            relative = cmds.getAttr(f"{target_node}.offsetParentMatrix")

            # El reposo sale del PROPIO opm que se reconstruye (relative[12] = in30 = X
            # local del hijo = longitud del hueso), no de una cuenta aparte: así
            # Stretch=1 devuelve el reposo por construcción, no porque dos cuentas
            # coincidan. Antes se recalculaba de las guías y se NEGABA en la R, asumiendo
            # que sus frames llevan el aim invertido. NO lo llevan: _build_frames pone el
            # aim (dirección al hijo) en la fila X en AMBOS lados —usa aim_letter, que va
            # sin signo—; el espejo de la R vive en lateral_ref, o sea en las filas Y/Z.
            # Por eso el roll_sign de foot_attributes (rotateZ) sí necesita signo por
            # lado y esta traslación no. Dejaba la R con cada hueso del revés: medido
            # headless en reposo, al conmutar a FK el menudillo saltaba 175.21 (trasera)
            # y 150.17 (delantera) —el primer salto, 58.998, era 2× el primer hueso
            # clavado— con la L a 0.0. Ahora los dos lados corren el MISMO código: 0.0.
            # ponytail: in30 y relative[12] asumen aim = ±X (el único eje con el que se
            # llama). Al salir valor y slot de la MISMA celda, el reposo aguanta
            # cualquier convención; lo que se quedaría sin efecto es el stretch. Upgrade:
            # aim_col = {"x": 0, "y": 1, "z": 2}[self.aim_letter], y usarlo en los dos.
            rest_length = relative[12]

            label = ctl.split("_")[1]
            mult_node = cmds.createNode("multiply", n=f"{self.module_name}{label}Stretch_MUL", ss=True)
            cmds.connectAttr(f"{ctl}.Stretch", f"{mult_node}.input[0]")
            cmds.setAttr(f"{mult_node}.input[1]", rest_length)

            fbf = cmds.createNode("fourByFourMatrix", name=f"{self.module_name}{label}Stretch_FBF", ss=True)
            for row in range(4):
                for col in range(3):
                    cmds.setAttr(f"{fbf}.in{row}{col}", relative[row * 4 + col])
            cmds.connectAttr(f"{mult_node}.output", f"{fbf}.in30", force=True)
            cmds.connectAttr(f"{fbf}.output", f"{target_node}.offsetParentMatrix", force=True)

    def reciprocal_fk_coupling(self):

        """
        Aparato recíproco (peroneo tercero + flexor digital superficial): babilla
        y corvejón flexionan y extienden JUNTOS, obligatoriamente — no es una
        preferencia de pose, es una atadura mecánica del miembro posterior. En IK
        el spring ya lo impone por construcción (Hip->Fetlock sobre tres huesos);
        en FK cada ctl rotaba libre y se podían posar ángulos que el animal no
        puede hacer. Aquí el corvejón hereda la flexión de la babilla × ratio.

        El par sale por índice: el apex del bend del spring ES el corvejón y el
        hueso anterior la babilla (el mismo apex que usa el PV). Nada hardcodeado.

        Va DESPUÉS de fk_stretch porque este reescribe el offsetParentMatrix del
        FK con su fourByFour: se reengancha lo que haya conectado, no se asume.

        opm = C * R (C = rotación acoplada, R = reposo/stretch). C queda a la
        IZQUIERDA de R, o sea en el frame local del corvejón y con su mismo
        pivote: exactamente donde rota su propio ctl. Consecuencias: el ctl del
        corvejón sigue siendo un offset ENCIMA del acoplamiento (el animador
        puede matizar sin pelearse con él) y en reposo C = identidad, así que ni
        la pose de reposo ni el match FK/IK se mueven.
        """
        hock_index = self.pv_apex_index
        stifle_ctl = self.fk_controllers[hock_index - 1]
        hock_node = self.fk_nodes[hock_index]
        axis = self.up_letter.upper()  # eje lateral = el de la flexión sagital

        cmds.addAttr(stifle_ctl, longName="RECIPROCAL", niceName="RECIPROCAL ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{stifle_ctl}.RECIPROCAL", keyable=False, channelBox=True, lock=True)
        # 1 = atadura anatómica; 0 = corvejón libre (el comportamiento de antes).
        # El animador lo baja solo para poses no anatómicas a sabiendas.
        cmds.addAttr(stifle_ctl, longName="Reciprocal", attributeType="float", minValue=0, maxValue=1, defaultValue=1, keyable=True)

        ratio_mul = cmds.createNode("multiply", name=f"{self.module_name}Reciprocal_MUL", ss=True)
        cmds.connectAttr(f"{stifle_ctl}.rotate{axis}", f"{ratio_mul}.input[0]")
        cmds.setAttr(f"{ratio_mul}.input[1]", self.RECIPROCAL_RATIO)
        cmds.connectAttr(f"{stifle_ctl}.Reciprocal", f"{ratio_mul}.input[2]")

        coupling_cmp = cmds.createNode("composeMatrix", name=f"{self.module_name}Reciprocal_CMP", ss=True)
        cmds.connectAttr(f"{ratio_mul}.output", f"{coupling_cmp}.inputRotate{axis}")

        coupling_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}Reciprocal_MMX", ss=True)
        cmds.connectAttr(f"{coupling_cmp}.outputMatrix", f"{coupling_mmx}.matrixIn[0]")
        rest_source = cmds.listConnections(f"{hock_node}.offsetParentMatrix", plugs=True, source=True, destination=False)
        if rest_source:
            cmds.connectAttr(rest_source[0], f"{coupling_mmx}.matrixIn[1]")
        else:
            cmds.setAttr(f"{coupling_mmx}.matrixIn[1]", cmds.getAttr(f"{hock_node}.offsetParentMatrix"), type="matrix")
        cmds.connectAttr(f"{coupling_mmx}.matrixSum", f"{hock_node}.offsetParentMatrix", force=True)

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
        cmds.setAttr(f"{non_roll_aim}.secondaryInputAxis", *self.up_axis, type="double3")
        cmds.setAttr(f"{non_roll_aim}.secondaryMode", 2)
        cmds.setAttr(f"{non_roll_aim}.secondaryTargetVector", self.lateral_ref.x, self.lateral_ref.y, self.lateral_ref.z, type="double3")

        self.raw_hip_blend = blend_wm[0]  # con twist, para el bendy ctl
        blend_wm[0] = f"{non_roll_aim}.outputMatrix"
        cv_nodes[0] = non_roll_aim

        roll_wm = list(blend_wm)
        roll_wm[0] = f"{non_roll_aim}.outputMatrix"
        for i in range(1, self.main_end_index + 1):
            aim_target = blend_wm[i + 1] if i + 1 < len(blend_wm) else blend_wm[i]
            cv_nodes[i] = self._roll_cv(blend_wm[i], aim_target, f"{self.module_name}Roll0{i}")
            roll_wm[i] = f"{cv_nodes[i]}.matrixSum"

        bendy_grp = cmds.createNode("transform", name=f"{self.module_name}BendyControllers_GRP", ss=True, p=self.controllers_grp)
        cmds.setAttr(f"{bendy_grp}.inheritsTransform", 0)

        aim_axis = self.aim_axis_str

        up_object_vector = (self.lateral_ref.x, self.lateral_ref.y, self.lateral_ref.z)
        params = [i / (self.skinning_jnts - 1) for i in range(self.skinning_jnts)]
        params[-1] = 0.95
        hip_ctl_roll = f"{self._roll_cv(self.raw_hip_blend, blend_wm[1], f'{self.module_name}HipCtl')}.matrixSum"

        # Add attribute in self.settings_ctl to control the bendy controllers visibility
        cmds.addAttr(self.settings_ctl, longName="Bendy_Controllers", niceName="Bendy_Controllers", attributeType="bool", defaultValue=True, keyable=True)
        cmds.setAttr(f"{self.settings_ctl}.Bendy_Controllers", lock=False, keyable=False, channelBox=True)

        self.bendy_ctls = []
        for i in range(segment_count):

            name = f"{self.module_name}{segment_names[i]}Bendy"

            mid_blm = cmds.createNode("blendMatrix", name=f"{name}_BLM", ss=True)
            cmds.connectAttr(hip_ctl_roll if i == 0 else roll_wm[i], f"{mid_blm}.inputMatrix")
            cmds.connectAttr(roll_wm[i + 1], f"{mid_blm}.target[0].targetMatrix")
            cmds.setAttr(f"{mid_blm}.target[0].translateWeight", 0.5)
            cmds.setAttr(f"{mid_blm}.target[0].rotateWeight", 0)
            cmds.setAttr(f"{mid_blm}.target[0].scaleWeight", 0)
            cmds.setAttr(f"{mid_blm}.target[0].shearWeight", 0)

            if i == 0:
                cmds.connectAttr(roll_wm[0], f"{mid_blm}.target[1].targetMatrix")
                cmds.setAttr(f"{mid_blm}.target[1].translateWeight", 0)
                cmds.setAttr(f"{mid_blm}.target[1].rotateWeight", 0.5)
                cmds.setAttr(f"{mid_blm}.target[1].scaleWeight", 0)
                cmds.setAttr(f"{mid_blm}.target[1].shearWeight", 0)

            bendy_nodes, bendy_ctl = curve_tool.create_controller(name=name, offset=["GRP", "ANM"], parent=bendy_grp)
            cmds.connectAttr(f"{self.settings_ctl}.Bendy_Controllers", f"{bendy_nodes[0]}.visibility")
            curve_tool.lock_attributes(bendy_ctl, ["sx", "sy", "sz", "v"])
            cmds.connectAttr(f"{mid_blm}.outputMatrix", f"{bendy_nodes[0]}.offsetParentMatrix")
            self.bendy_ctls.append(bendy_ctl)

            segment_jnts, temp = ribbon.de_boor_ribbon(
                cvs=(cv_nodes[i], bendy_ctl, cv_nodes[i + 1]),
                aim_axis=aim_axis, up_axis=self.up_letter, num_joints=self.skinning_jnts,
                skeleton_grp=self.skeleton_grp, name=name, custom_parameter=params,
                up_object=self.masterwalk_ctl, up_object_vector=up_object_vector,
            )
            for t in temp:
                cmds.delete(t)

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

        self.foot_skin_drivers = [
            (fetlock_skinning, blend_wm[self.main_end_index]),
            (pastern_skinning, blend_wm[self.plant_index]),
            (tip_skinning, f"{tip_mmx}.matrixSum"),
        ]

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

        self.foot_skin_drivers = [
            (renamed[self.leg_end_index], f"{self.blend_matrices[self.leg_end_index][0]}.outputMatrix"),
            (renamed[self.plant_index], f"{self.blend_matrices[self.plant_index][0]}.outputMatrix"),
        ]

    def foot_offset_setup(self):

        """
        Control EXTRA del pie en el menudillo (Fetlock). Mueve/rota/escala SOLO los
        joints de DEFORMACIÓN del pie —menudillo, cuartilla y casco— sin arrastrar la
        pierna: es un ajuste/secundaria del casco montado sobre el pie ya animado.

        Va montado sobre la POSICIÓN del pie animado: el GRP sigue el punto del
        menudillo (blend FK/IK del Fetlock: IK, spring, roll y twist mueven ese punto)
        pero se mantiene ORIENTADO A MUNDO, así que el manipulador se traslada con el
        pie y sus ejes son siempre los del mundo. El animador solo AÑADE su offset
        encima. En reposo (control en identidad) es un no-op EXACTO en cualquier pose.

        Mecánica (matrices, sin constraints): el delta del animador es
            Δ = P⁻¹ · CTL.world = P⁻¹ · T · P          (T = TRS local del control)
        con P = solo la POSICIÓN del menudillo (traslación pura, orientada a mundo).
        En reposo (T = I -> CTL.world = P) es la identidad SEA CUAL SEA la animación
        del pie: no hay doble transform al rodar/cargar. Como P no lleva rotación, Δ
        aplica T en ejes de MUNDO con el pivote en el menudillo (rotación/escala en
        world space). Se POSMULTIPLICA en el world de cada joint del pie:
            world' = world · Δ
        y como los tres joints son hojas (hermanos bajo skeleton_grp), el pie entero
        se mueve RÍGIDO alrededor del menudillo y nada más se entera.

        Deliberadamente NO alimenta el ikHandle de la pierna ni los pivotes del reverse
        foot: por eso mueve el pie y NO la pierna. Consecuencia aceptada: en poses
        extremas el casco se separa visualmente de la caña (la caña la sigue marcando
        el blend del menudillo, que no se toca). Es intencionado; no se reconecta.

        ponytail: offset RÍGIDO del pie completo alrededor del menudillo, sin
        deformación/blend de transición hacia la caña. Es lo pedido (control de ajuste).
        Techo: si se quisiera suavizar el corte caña/casco haría falta un blend de
        pesos en la malla, que es otro sistema, no este control.
        """
        self.foot_offset_ctl = None
        if not getattr(self, "foot_skin_drivers", None):
            return

        foot_frame = f"{self.blend_matrices[self.leg_end_index][0]}.outputMatrix"

        nodes, ctl = curve_tool.create_controller(
            name=f"{self.module_name}FootOffset", offset=["GRP", "ANM"], parent=self.controllers_grp)
        curve_tool.lock_attributes(ctl, ["v"])  # translate + rotate + scale libres (TRS)
        self.foot_offset_ctl = ctl

        # Rotación/escala en WORLD SPACE: el control se coloca en la POSICIÓN del
        # menudillo pero con los ejes del MUNDO, no los del hueso. pickMatrix se queda
        # solo con la traslación de foot_frame (descarta rotación y escala).
        foot_pos = cmds.createNode("pickMatrix", name=f"{self.module_name}FootOffsetPos_PMX", ss=True)
        cmds.connectAttr(foot_frame, f"{foot_pos}.inputMatrix")
        for attr in ("useRotate", "useScale", "useShear"):
            cmds.setAttr(f"{foot_pos}.{attr}", 0)

        # El GRP cabalga la POSICIÓN del menudillo animado (orientado a mundo).
        # inheritsTransform=0 porque foot_pos ya es world (incluye masterwalk/globalScale).
        cmds.setAttr(f"{nodes[0]}.inheritsTransform", 0)
        cmds.connectAttr(f"{foot_pos}.outputMatrix", f"{nodes[0]}.offsetParentMatrix")

        # Δ = P⁻¹ · CTL.world = P⁻¹ · T · P  (identidad en reposo; T en ejes de MUNDO,
        # pivote en la posición del menudillo, porque P es traslación pura).
        foot_inv = cmds.createNode("inverseMatrix", name=f"{self.module_name}FootOffsetFrame_INV", ss=True)
        cmds.connectAttr(f"{foot_pos}.outputMatrix", f"{foot_inv}.inputMatrix")
        delta_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}FootOffsetDelta_MMX", ss=True)
        cmds.connectAttr(f"{foot_inv}.outputMatrix", f"{delta_mmx}.matrixIn[0]")
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{delta_mmx}.matrixIn[1]")

        # world' = world · Δ en cada joint de deformación del pie (hojas: sin la pierna).
        # inheritsTransform=0 -> world = offsetParentMatrix (el plug ya es world absoluto).
        for joint, world_plug in self.foot_skin_drivers:
            off_mmx = cmds.createNode("multMatrix", name=joint.replace("_JNT", "Offset_MMX"), ss=True)
            cmds.connectAttr(world_plug, f"{off_mmx}.matrixIn[0]")
            cmds.connectAttr(f"{delta_mmx}.matrixSum", f"{off_mmx}.matrixIn[1]")
            cmds.setAttr(f"{joint}.inheritsTransform", 0)
            cmds.connectAttr(f"{off_mmx}.matrixSum", f"{joint}.offsetParentMatrix", force=True)


class BackLegModule(LegModule):

    """Pierna trasera: {side}_backLegHip_JNT -> ... -> Tip."""

    LEG_PREFIX = "backLeg"
    # Dobla hacia ATRÁS (corvejón caudal): el fold sigue al PRE-BEND, así que se
    # siembra hacia caudal (FORWARD_AXIS = +Z -> pre-bend -Z). El PV se mantiene en
    # el lado caudal (PV_SIGN = -1) aunque doble hacia atrás. Y se reposiciona la
    # cadena IK sobre las guías: nada desplazado (el corvejón ya marca el doblez).
    FORWARD_AXIS = (0, 0, 1)
    SEED_STRAIGHT_BEND = True
    PV_SIGN = -1
    REPOSITION_IK_TO_GUIDES = True
    # El aparato recíproco es exclusivo del posterior. En IK el spring ya lo impone
    # por construcción (Hip->Fetlock sobre los tres huesos); esto lo ata también en FK.
    RECIPROCAL_FK = True


class FrontLegModule(LegModule):

    """
    Pierna delantera (anatomía equina): {side}_scapula_JNT -> Shoulder -> Elbow
    -> Ankle -> Fetlock -> Pastern -> Tip. Misma construcción que la trasera (el
    PV se calcula del plano real de la cadena, así que el bend invertido del
    carpo sale solo) más la escápula (master + escápula aimada al root de la
    pierna + end con space switch), portada del dragon_leg del TFG.
    """

    LEG_PREFIX = "frontLeg"
    ROOT_JOINT = "Shoulder"
    # Doblez CRANIAL (carpo adelante). Para reposicionar sin desplazamiento, el PV
    # debe ir alineado con el doblez (lado cranial), igual que la trasera con su
    # corvejón: PV_SIGN = -1 lo lleva al lado del doblez.
    PV_SIGN = -1
    REPOSITION_IK_TO_GUIDES = True
    SEED_STRAIGHT_BEND = True
    # Galope: los dos ángulos de ~90° (el "double bend" de la delantera) los da el
    # spring Shoulder->Fetlock sobre los TRES huesos reales, sin nada añadido —
    # medido headless en el plegado recogido: codo 81.7° y CARPO 95.5°, cada uno en
    # su sentido anatómico (codo caudal, carpo cranial), suave hasta codo 50.8°/carpo
    # 59.3° sin flip. El reparto entre ambos lo mueve `Bend_Bias` (springAngleBias).
    # Hubo un flag DOUBLE_BEND que insertaba Elbow2/Ankle2 a media diáfisis para
    # forzar los dos ángulos: doblaba el RADIO y la CAÑA por la mitad del hueso
    # (huesos únicos y sólidos que no flexionan), y encima resolvía PEOR — el carpo se
    # quedaba en 165.3° (casi recto) mientras media caña doblaba 72.5°, y el codo
    # colapsaba a 0.03° (hueso sobre hueso). Borrado: el mecanismo sobraba y el
    # propósito ya lo cumplía el spring. No re-insertes joints intermedios.
    # Floating scapula: el omóplato se DESLIZA sobre una NURBS surface (el caballo
    # no tiene clavícula; la escápula flota sobre la caja torácica) para un
    # movimiento realista del hombro. Flag para activar/desactivar el setup.
    SCAPULA_FLOATING = True
    FLOATING_WIDTH_MULT = 3.0   # ancho de la superficie (U, fore/aft) ~ longitud escápula→root
    FLOATING_LENGTH_MULT = 2.0  # alto (V, up/down)

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
        curve_tool.lock_attributes(self.scapula_master_ctl, ["sx", "sy", "sz", "v"])
        cmds.setAttr(f"{master_nodes[0]}.offsetParentMatrix", list(master_rest), type="matrix")

        # Escápula: en su guía, siguiendo al master con offset horneado
        scapula_nodes, self.scapula_ctl = curve_tool.create_controller(name=f"{self.module_name}Scapula", offset=["GRP", "ANM"], parent=self.controllers_grp)
        curve_tool.lock_attributes(self.scapula_ctl, ["sx", "sy", "sz", "v"])
        cmds.setAttr(f"{scapula_nodes[0]}.inheritsTransform", 0)

        scapula_offset_mmx = cmds.createNode("multMatrix", name=f"{self.module_name}Scapula_MMX", ss=True)
        cmds.setAttr(f"{scapula_offset_mmx}.matrixIn[0]", list(scapula_rest * master_rest.inverse()), type="matrix")
        cmds.connectAttr(f"{self.scapula_master_ctl}.worldMatrix[0]", f"{scapula_offset_mmx}.matrixIn[1]")
        cmds.connectAttr(f"{scapula_offset_mmx}.matrixSum", f"{scapula_nodes[0]}.offsetParentMatrix")

        # End: en el root de la pierna, con space switch entre escápula y masterwalk
        end_nodes, self.scapula_end_ctl = curve_tool.create_controller(name=f"{self.module_name}ScapulaEnd", offset=["GRP", "ANM"], parent=self.controllers_grp)
        curve_tool.lock_attributes(self.scapula_end_ctl, ["sx", "sy", "sz", "v"])
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

        # Skinning joints de la escápula. Con floating, el omóplato no sigue
        # directamente al control sino su proyección sobre la NURBS surface.
        if self.SCAPULA_FLOATING:
            scapula_drive = self._scapula_floating_setup(scapula_nodes[0], scapula_rest, root_pos, scapula_pos)
        else:
            scapula_drive = f"{self.scapula_ctl}.worldMatrix[0]"

        scapula_skinning = cmds.createNode("joint", name=f"{self.module_name}ScapulaSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(scapula_drive, f"{scapula_skinning}.offsetParentMatrix")
        scapula_end_skinning = cmds.createNode("joint", name=f"{self.module_name}ScapulaEndSkinning_JNT", ss=True, p=self.skeleton_grp)
        cmds.connectAttr(f"{self.scapula_end_ctl}.worldMatrix[0]", f"{scapula_end_skinning}.offsetParentMatrix")

        data_manager.DataExportBiped().append_data(f"{self.LEG_PREFIX}_module",
                            {
                                f"{self.side}_scapula_ctl": self.scapula_ctl,
                                f"{self.side}_scapula_master_ctl": self.scapula_master_ctl,
                                f"{self.side}_scapula_end_ctl": self.scapula_end_ctl,
                            })

    def _scapula_floating_setup(self, grp, scapula_rest, root_pos, scapula_pos):

        """
        Floating scapula ("floating shoulder"): el omóplato se desliza sobre una
        MEDIA ESFERA (NURBS) que aproxima la caja torácica, para un movimiento
        realista. La cúpula **pasa por la escápula (reposo) y por el shoulder**
        (radio = distancia escápula→shoulder; centro de curvatura entre ambos,
        hundido hacia dentro del cuerpo). El control proyecta su posición sobre la
        esfera (closestPointOnSurface) y el omóplato sigue el punto proyectado,
        conservando la rotación del control. El atributo Floating (0-1) mezcla
        entre el comportamiento directo y el flotante.

        Toda la proyección se hace en el ESPACIO DEL GRP del control (vía
        `worldInverseMatrix`), así que es independiente del cuerpo y no hay offset
        horneado: en reposo el control está en el origen del GRP, que está SOBRE la
        esfera → el punto proyectado es él mismo → sin desplazamiento. La superficie
        se PARENTA EN `modules` (no en controles) y sigue al cuerpo conectando su
        `offsetParentMatrix` al worldMatrix del GRP.

        Returns:
            str: el plug de matriz (worldMatrix) que dirige el joint de skinning.
        """
        radius = (root_pos - scapula_pos).length() or 10.0
        scapula_rest_mtx = om.MMatrix(scapula_rest)

        # --- Cúpula (media esfera) en el espacio del GRP -----------------------
        # La escápula (origen del GRP) va en el BORDE/corte y el shoulder en la
        # parte REDONDA: el ápice de la cúpula apunta hacia el shoulder y el borde
        # (rim) pasa por la escápula. Esfera equidistante de escápula y shoulder
        # (pasa por ambos), centro hundido en -Z (lateral interno).
        root_local = om.MPoint(root_pos.x, root_pos.y, root_pos.z) * scapula_rest_mtx.inverse()
        mid_x = root_local.x * 0.5
        center_z = -math.sqrt(max(radius * radius - mid_x * mid_x, 0.0))
        center = om.MVector(mid_x, 0.0, center_z)

        scap_dir = (om.MVector(0.0, 0.0, 0.0) - center).normal()           # escápula desde el centro
        sho_dir = (om.MVector(root_local.x, 0.0, 0.0) - center).normal()   # shoulder desde el centro
        plane_n = (scap_dir ^ sho_dir).normal()                            # normal del plano escápula-shoulder
        apex_dir = (plane_n ^ scap_dir).normal()                           # 90° desde la escápula hacia el shoulder
        # el shoulder (~60° de la escápula) cae DENTRO de la cúpula (90°) -> redondo;
        # la escápula a 90° del ápice -> en el borde/corte (sin desplazamiento).

        # Perfil: arco de 90° del ápice (sobre el eje, hacia el shoulder) al borde
        # (la escápula). Revolve 360° alrededor del eje del ápice -> cúpula. Los CVs
        # quedan ya en espacio GRP (se construye en world sin transform).
        profile_pts = []
        for i in range(7):
            a = math.radians(90.0 * i / 6.0)
            p = center + radius * (apex_dir * math.cos(a) + scap_dir * math.sin(a))
            profile_pts.append((p.x, p.y, p.z))
        profile = cmds.curve(d=3, p=profile_pts, name=f"{self.module_name}ScapulaFloatingProfile_CRV")
        surf_tf = cmds.revolve(profile, axis=(apex_dir.x, apex_dir.y, apex_dir.z),
                               pivot=(center.x, center.y, center.z), startSweep=0, endSweep=360,
                               sections=16, degree=3, name=f"{self.module_name}ScapulaFloating_NRB")[0]
        cmds.delete(profile)
        cmds.delete(surf_tf, ch=True)  # sin historia: CVs editables (el rigger esculpe la curvatura del torso)
        cmds.makeIdentity(surf_tf, apply=True, t=1, r=1, s=1, n=0)  # CVs en espacio GRP, transform identidad
        cmds.parent(surf_tf, self.module_trn, relative=True)
        cmds.setAttr(f"{surf_tf}.inheritsTransform", 0)
        cmds.xform(surf_tf, matrix=list(om.MMatrix.kIdentity))
        cmds.connectAttr(f"{grp}.worldMatrix[0]", f"{surf_tf}.offsetParentMatrix")
        cmds.setAttr(f"{surf_tf}.overrideEnabled", 1)
        cmds.setAttr(f"{surf_tf}.overrideDisplayType", 2)  # reference: visible para esculpir, no seleccionable
        cmds.setAttr(f"{surf_tf}.visibility", 0)
        curve_tool.lock_attributes(surf_tf, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])
        self.scapula_floating_surface = surf_tf
        surf_shape = cmds.listRelatives(surf_tf, shapes=True)[0]

        ctl = self.scapula_ctl

        # Control en el espacio del GRP (independiente del cuerpo)
        ctl_in_grp = cmds.createNode("multMatrix", name=f"{self.module_name}ScapulaFloatingLocal_MMX", ss=True)
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{ctl_in_grp}.matrixIn[0]")
        cmds.connectAttr(f"{grp}.worldInverseMatrix[0]", f"{ctl_in_grp}.matrixIn[1]")

        rfm = cmds.createNode("rowFromMatrix", name=f"{self.module_name}ScapulaFloatingPos_RFM", ss=True)
        cmds.setAttr(f"{rfm}.input", 3)
        cmds.connectAttr(f"{ctl_in_grp}.matrixSum", f"{rfm}.matrix")

        # Punto más cercano sobre la esfera, en espacio objeto (= espacio GRP)
        cps = cmds.createNode("closestPointOnSurface", name=f"{self.module_name}ScapulaFloating_CPS", ss=True)
        cmds.connectAttr(f"{surf_shape}.local", f"{cps}.inputSurface")
        for axis in "XYZ":
            cmds.connectAttr(f"{rfm}.output{axis}", f"{cps}.inPosition{axis}")

        posi = cmds.createNode("pointOnSurfaceInfo", name=f"{self.module_name}ScapulaFloating_POSI", ss=True)
        cmds.connectAttr(f"{surf_shape}.local", f"{posi}.inputSurface")
        cmds.connectAttr(f"{cps}.parameterU", f"{posi}.parameterU")
        cmds.connectAttr(f"{cps}.parameterV", f"{posi}.parameterV")

        # Frame de la superficie en el punto proyectado (espacio GRP): tangentes
        # + normal (rotación) + posición.
        surf_frame = cmds.createNode("fourByFourMatrix", name=f"{self.module_name}ScapulaFloatingSurf_FBF", ss=True)
        for row, attr in ((0, "normalizedTangentU"), (1, "normalizedTangentV"), (2, "normalizedNormal")):
            for col, axis in enumerate("XYZ"):
                cmds.connectAttr(f"{posi}.{attr}{axis}", f"{surf_frame}.in{row}{col}")
        for col, axis in enumerate("XYZ"):
            cmds.connectAttr(f"{posi}.position{axis}", f"{surf_frame}.in3{col}")

        # Traslación proyectada (posición sobre la cúpula)
        surf_pos = cmds.createNode("pickMatrix", name=f"{self.module_name}ScapulaFloatingPos_PMX", ss=True)
        cmds.connectAttr(f"{surf_frame}.output", f"{surf_pos}.inputMatrix")
        cmds.setAttr(f"{surf_pos}.useRotate", 0)
        cmds.setAttr(f"{surf_pos}.useScale", 0)
        cmds.setAttr(f"{surf_pos}.useShear", 0)

        # --- Atributos ---
        cmds.addAttr(ctl, longName="FLOATING_SEP", niceName="FLOATING ------", attributeType="enum", enumName="------", keyable=True)
        cmds.setAttr(f"{ctl}.FLOATING_SEP", keyable=False, channelBox=True, lock=True)
        cmds.addAttr(ctl, longName="Floating", attributeType="float", min=0, max=1, defaultValue=1, keyable=True)
        cmds.addAttr(ctl, longName="Auto_Orient", attributeType="float", min=0, max=1, defaultValue=0, keyable=True)

        # Auto-orient: el omóplato se inclina siguiendo la rotación del frame de la
        # cúpula al deslizar. surf_rot = rotación del frame de superficie; S0inv
        # (constante, horneado del reposo) la cancela en reposo -> el delta es
        # identidad en reposo (sin desplazamiento sea cual sea Auto_Orient).
        surf_rot = cmds.createNode("pickMatrix", name=f"{self.module_name}ScapulaFloatingSurfRot_PMX", ss=True)
        cmds.connectAttr(f"{surf_frame}.output", f"{surf_rot}.inputMatrix")
        cmds.setAttr(f"{surf_rot}.useTranslate", 0)
        cmds.setAttr(f"{surf_rot}.useScale", 0)
        cmds.setAttr(f"{surf_rot}.useShear", 0)

        cmds.dgdirty(allPlugs=True)
        s0_inv = list(om.MMatrix(cmds.getAttr(f"{surf_rot}.outputMatrix")).inverse())
        surf_delta = cmds.createNode("multMatrix", name=f"{self.module_name}ScapulaFloatingSurfDelta_MMX", ss=True)
        cmds.setAttr(f"{surf_delta}.matrixIn[0]", s0_inv, type="matrix")
        cmds.connectAttr(f"{surf_rot}.outputMatrix", f"{surf_delta}.matrixIn[1]")

        # Mezcla del delta por Auto_Orient (0 = conserva la orientación del control,
        # 1 = sigue la normal/tangentes de la cúpula)
        orient_blend = cmds.createNode("blendMatrix", name=f"{self.module_name}ScapulaFloatingOrient_BLM", ss=True)
        cmds.connectAttr(f"{surf_delta}.matrixSum", f"{orient_blend}.target[0].targetMatrix")
        cmds.connectAttr(f"{ctl}.Auto_Orient", f"{orient_blend}.target[0].weight")
        cmds.setAttr(f"{orient_blend}.target[0].translateWeight", 0)
        cmds.setAttr(f"{orient_blend}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{orient_blend}.target[0].shearWeight", 0)

        # Rotación del control (espacio GRP)
        pick_rot = cmds.createNode("pickMatrix", name=f"{self.module_name}ScapulaFloatingRot_PMX", ss=True)
        cmds.connectAttr(f"{ctl_in_grp}.matrixSum", f"{pick_rot}.inputMatrix")
        cmds.setAttr(f"{pick_rot}.useTranslate", 0)
        cmds.setAttr(f"{pick_rot}.useScale", 0)
        cmds.setAttr(f"{pick_rot}.useShear", 0)

        # orient = rotación_control * delta_superficie (en reposo = rotación_control)
        orient = cmds.createNode("multMatrix", name=f"{self.module_name}ScapulaFloatingOrient_MMX", ss=True)
        cmds.connectAttr(f"{pick_rot}.outputMatrix", f"{orient}.matrixIn[0]")
        cmds.connectAttr(f"{orient_blend}.outputMatrix", f"{orient}.matrixIn[1]")

        # bone_grp = orient * traslación_proyectada ; bone_world = bone_grp * GRP.world
        bone_grp = cmds.createNode("multMatrix", name=f"{self.module_name}ScapulaFloatingBone_MMX", ss=True)
        cmds.connectAttr(f"{orient}.matrixSum", f"{bone_grp}.matrixIn[0]")
        cmds.connectAttr(f"{surf_pos}.outputMatrix", f"{bone_grp}.matrixIn[1]")

        bone_world = cmds.createNode("multMatrix", name=f"{self.module_name}ScapulaFloatingWorld_MMX", ss=True)
        cmds.connectAttr(f"{bone_grp}.matrixSum", f"{bone_world}.matrixIn[0]")
        cmds.connectAttr(f"{grp}.worldMatrix[0]", f"{bone_world}.matrixIn[1]")

        # Floating (0-1): mezcla directo <-> flotante
        blend = cmds.createNode("blendMatrix", name=f"{self.module_name}ScapulaFloating_BLM", ss=True)
        cmds.connectAttr(f"{ctl}.worldMatrix[0]", f"{blend}.inputMatrix")
        cmds.connectAttr(f"{bone_world}.matrixSum", f"{blend}.target[0].targetMatrix")
        cmds.connectAttr(f"{ctl}.Floating", f"{blend}.target[0].weight")
        cmds.setAttr(f"{blend}.target[0].scaleWeight", 0)
        cmds.setAttr(f"{blend}.target[0].shearWeight", 0)

        return f"{blend}.outputMatrix"
