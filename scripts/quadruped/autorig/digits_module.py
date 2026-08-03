import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload

from utils import data_manager
from utils import guides_manager
from utils import curve_tool
from utils import matrix_manager

reload(data_manager)
reload(guides_manager)
reload(curve_tool)
reload(matrix_manager)


# Reparto del Spread por dedo. El eje funcional de la pata digitígrada cae ENTRE
# los dedos III y IV (a diferencia de la mano del bípedo, cuyo eje es el dedo
# medio), así que los dedos se abren en abanico simétrico respecto a ese eje: los
# externos (II y V) abren del todo y los centrales (III y IV) apenas. El espolón
# (dedo I) no entra: no apoya y lleva sus propios atributos.
_SPREAD_WEIGHTS = {
    "digitII":  -1.00,
    "digitIII": -0.33,
    "digitIV":   0.33,
    "digitV":    1.00,
}
_SPREAD_MAX_RY = 12  # grados a Spread=10 para los dedos externos


class DigitsModule(object):

    """
    Dedos de una pata DIGITÍGRADA (perro, gato), colgados de la articulación
    metacarpo/metatarsofalángica que publica el módulo de pierna.

    Por qué existe como módulo aparte y no como una rama dentro de LegModule:
    la pierna del cuadrúpedo es una CADENA LINEAL (LegModule indexa por posición
    — leg_end_index, plant_index —) y una pata digitígrada se BIFURCA en varios
    dedos a partir del MTP. Meter la bifurcación dentro del módulo de pierna
    obligaría a que todo el indexado entendiese de ramas, para un solo caso. En
    su lugar, la pierna se queda lineal (y por tanto idéntica en el ungulado y en
    el digitígrado: mismos tres segmentos funcionales, mismo spring IK) y los
    dedos se componen encima. Es el mismo patrón que fingers_module con la muñeca
    del bípedo.

    Anatómicamente el MTP es el MISMO hueso en las dos tipologías — lo que el
    équido llama menudillo. El ungulado apoya un único dedo (III, con el
    metacarpo fusionado en la caña); el digitígrado apoya II-V y conserva el I
    elevado como espolón. Esa es toda la diferencia, y es la que justifica que
    el pie sea intercambiable y la pierna no.

    Guías esperadas (las que no existan se omiten sin error):
        {side}_{legPrefix}{Digit}00_JNT -> 01 -> 02 [-> 03End]
    p. ej. L_frontLegDigitIII00_JNT. Nomenclatura romana II-V porque es la
    notación veterinaria estándar y evita el "index/middle/ring" del bípedo, que
    en un cánido sería anatómicamente falso.
    """

    # I = espolón (dewclaw, no apoya), II-V = dedos de apoyo.
    DIGIT_NAMES = ["digitI", "digitII", "digitIII", "digitIV", "digitV"]
    DEWCLAW = "digitI"

    def __init__(self):
        self.modules        = data_manager.DataExportBiped().get_data("basic_structure", "modules_GRP")
        self.skel_grp       = data_manager.DataExportBiped().get_data("basic_structure", "skel_GRP")
        self.masterwalk_ctl = data_manager.DataExportBiped().get_data("basic_structure", "masterwalk_ctl")

    def make(self, side, leg_prefix="frontLeg"):

        """
        Args:
            side (str): 'L' o 'R'.
            leg_prefix (str): 'frontLeg' o 'backLeg'. Debe coincidir con el
                LEG_PREFIX del módulo de pierna del que cuelgan los dedos.
        """
        self.side = side
        self.leg_prefix = leg_prefix
        self.module_name = f"{self.side}_{self.leg_prefix}"

        self.mtp_jnt = data_manager.DataExportBiped().get_data(f"{self.leg_prefix}_module", f"{self.side}_mtp_JNT")
        if not self.mtp_jnt or not cmds.objExists(self.mtp_jnt):
            cmds.warning(f"[digits] sin MTP publicado para {self.module_name}: construye antes la pierna.")
            return

        self.module_trn      = cmds.createNode("transform", name=f"{self.module_name}DigitsModule_GRP", ss=True, p=self.modules)
        self.skeleton_grp    = cmds.createNode("transform", name=f"{self.module_name}DigitsSkinning_GRP", ss=True, p=self.skel_grp)
        self.controllers_grp = cmds.createNode("transform", name=f"{self.module_name}DigitsControllers_GRP", ss=True, p=self.masterwalk_ctl)
        cmds.setAttr(f"{self.controllers_grp}.inheritsTransform", 0)

        self.load_guides()
        if not self.digits:
            cmds.warning(f"[digits] no se encontró ninguna guía de dedo para {self.module_name}.")
            return

        self.fk_digits()
        self.parent_digits_to_mtp()
        self.attributes_setup()

        data_manager.DataExportBiped().append_data(f"{self.leg_prefix}_digits_module",
                            {
                                f"{self.side}_digit_ctls": {n: self._ctl[n] for n in self.digit_names},
                                f"{self.side}_digitsAttributes": self.digit_attributes_ctl,
                                f"{self.side}_digitsSkinning": self.skinning_joints,
                            })

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    def _lock(self, ctl, attrs):
        for attr in attrs:
            cmds.setAttr(f"{ctl}.{attr}", lock=True, keyable=False, channelBox=False)

    def _guide_root(self, name):
        return f"{self.module_name}{name[0].upper()}{name[1:]}00_JNT"

    # ─────────────────────────────────────────────────────────────────────────
    # Build
    # ─────────────────────────────────────────────────────────────────────────
    def load_guides(self):

        """
        Carga solo los dedos cuya guía raíz exista. Un perro suele llevar espolón
        en las manos y no en los pies, y hay razas sin él: el módulo se adapta a
        lo que traiga el personaje en vez de exigir los cinco.
        """
        # El import va aquí dentro y no arriba: guides_manager ya depende de
        # rig_manager y rig_manager importa los módulos de rig, así que a nivel de
        # módulo sería un ciclo. Resuelto en tiempo de llamada.
        from utils import rig_manager

        character = rig_manager.get_character_name_from_build()

        self.digits = []
        self.digit_names = []
        for name in self.DIGIT_NAMES:
            root = self._guide_root(name)
            # La existencia se comprueba contra el .guides, NO contra la escena:
            # get_guides CREA los joints a partir del fichero, así que antes de
            # llamarlo no hay nada en escena que comprobar.
            if not guides_manager.read_guides_info(character, root):
                continue
            cmds.select(clear=True)
            guides = guides_manager.get_guides(root)
            if not guides:
                continue
            cmds.parent(guides[0], self.module_trn)
            self.digits.append(guides)
            self.digit_names.append(name)
        cmds.select(clear=True)

    def fk_digits(self):

        """
        Una cadena FK por dedo, con grupo SDK intermedio para que los atributos
        de Curl/Spread manejen el dedo sin pisar los canales del control (el
        animador conserva el control limpio encima del SDK).
        """
        self._ctl   = {n: [] for n in self.digit_names}
        self._nodes = {n: [] for n in self.digit_names}
        self._sdk   = {n: [] for n in self.digit_names}
        self.skinning_joints = {n: [] for n in self.digit_names}

        skin_trns = {
            name: cmds.createNode("transform", name=f"{self.module_name}{name[0].upper()}{name[1:]}Skinning_GRP", ss=True, p=self.skeleton_grp)
            for name in self.digit_names
        }

        for name, digit in zip(self.digit_names, self.digits):
            ctl_list, nodes_list, sdk_list = self._ctl[name], self._nodes[name], self._sdk[name]

            # Las guías importadas se convierten en la cadena de skinning; las
            # guías End solo marcan la punta y no llevan peso.
            chain = [jnt for jnt in digit if "End" not in jnt]
            end_joints = [jnt for jnt in digit if "End" in jnt]
            if end_joints:
                cmds.delete(end_joints)
            cmds.parent(chain[0], skin_trns[name])

            for i, joint in enumerate(chain):
                cmds.select(clear=True)
                fk_node, fk_ctl = curve_tool.create_controller(
                    name=joint.replace("_JNT", ""), offset=["GRP", "SDK"]
                )
                cmds.matchTransform(fk_node[0], joint, pos=True, rot=True)

                if ctl_list:
                    cmds.parent(fk_node[0], ctl_list[-1])

                ctl_list.append(fk_ctl)
                nodes_list.append(fk_node[0])
                sdk_list.append(fk_node[1])

                prev = chain[i - 1] if i > 0 else None
                matrix_manager.fk_constraint(joint, prev, False, None)

                self._lock(fk_ctl, ["sx", "sy", "sz", "v"])
                cmds.xform(joint, m=om.MMatrix.kIdentity)

            self.skinning_joints[name] = [
                cmds.rename(jnt, jnt.replace("_JNT", "Skinning_JNT")) for jnt in chain
            ]

        for name in self.digit_names:
            cmds.parent(self._nodes[name][0], self.controllers_grp)

        # Control de atributos, colocado sobre el primer dedo de apoyo que haya.
        anchor = next((n for n in self.digit_names if n != self.DEWCLAW), self.digit_names[0])
        self.digit_attributes_nodes, self.digit_attributes_ctl = curve_tool.create_controller(
            name=f"{self.module_name}DigitsAttributes", offset=["GRP"]
        )
        cmds.parent(self.digit_attributes_nodes[0], self.controllers_grp)
        cmds.matchTransform(self.digit_attributes_nodes[0], self._ctl[anchor][0], pos=True, rot=True)
        self._lock(self.digit_attributes_ctl, ["tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz", "v"])

    def parent_digits_to_mtp(self):

        """
        Los dedos siguen al MTP por parentMatrix con offset horneado, no por
        parenteo DAG: el MTP es un joint de skinning que ya viene dirigido por el
        blend FK/IK (y por el offset del pie), así que colgar de él por DAG
        heredaría su transform dos veces.
        """
        targets = [self._nodes[n][0] for n in self.digit_names] + [self.digit_attributes_nodes[0]]
        for node in targets:
            cmds.select(clear=True)
            temp_loc = cmds.spaceLocator(name=node.replace("GRP", "LOC"))[0]
            cmds.matchTransform(temp_loc, node, pos=True, rot=True)
            pm = cmds.createNode("parentMatrix", name=node.replace("GRP", "PM"), ss=True)
            cmds.connectAttr(f"{temp_loc}.worldMatrix[0]", f"{pm}.inputMatrix")
            cmds.connectAttr(f"{self.mtp_jnt}.worldMatrix[0]", f"{pm}.target[0].targetMatrix")
            cmds.setAttr(f"{pm}.target[0].offsetMatrix", matrix_manager.get_offset_matrix(node, self.mtp_jnt), type="matrix")
            cmds.connectAttr(f"{pm}.outputMatrix", f"{node}.offsetParentMatrix")
            cmds.xform(node, m=om.MMatrix.kIdentity)
            cmds.delete(temp_loc)

    # ─────────────────────────────────────────────────────────────────────────
    # Atributos
    # ─────────────────────────────────────────────────────────────────────────
    def attributes_setup(self):

        """
        Curl, Spread y Twist para los dedos de apoyo; el espolón va aparte porque
        no pisa y su rango es otro. No hay Cup: el cuenco es un gesto de mano
        prensil (oposición del pulgar) y una pata digitígrada no lo hace.
        """
        ctl = self.digit_attributes_ctl

        def sep(ln):
            cmds.addAttr(ctl, longName=ln, attributeType="enum", enumName="____")
            cmds.setAttr(f"{ctl}.{ln}", lock=True, keyable=False, channelBox=True)

        def flt(ln):
            cmds.addAttr(ctl, longName=ln, attributeType="float",
                         defaultValue=0, max=10, min=-10, keyable=True)

        support = [n for n in self.digit_names if n != self.DEWCLAW]

        if support:
            sep("DIGIT_ATTRIBUTES")
            flt("Curl"); flt("Spread"); flt("Twist")

        if self.DEWCLAW in self.digit_names:
            sep("DEWCLAW_ATTRIBUTES")
            flt("Dewclaw_Curl"); flt("Dewclaw_Twist")

        # Curl y Twist por falange: la proximal manda, las distales acompañan con
        # menos recorrido (el dedo se enrosca, no se parte por igual).
        phalanx_curl = [-70, 18, -55, 14, -45, 12]

        for name in support:
            sdk_list = self._sdk[name]
            spread_ry = _SPREAD_MAX_RY * _SPREAD_WEIGHTS.get(name, 0.0)

            for i, sdk in enumerate(sdk_list):
                pos, neg = phalanx_curl[min(i * 2, len(phalanx_curl) - 2):][:2]
                self._sdk_key(sdk, "rz", "Curl", pos, neg)
                self._sdk_key(sdk, "rx", "Twist", 15, -15)
                # El abanico sale de la falange PROXIMAL: abrir desde la punta
                # separaría las uñas sin mover el dedo.
                if i == 0:
                    self._sdk_key(sdk, "ry", "Spread", spread_ry, -spread_ry)

        if self.DEWCLAW in self.digit_names:
            for sdk in self._sdk[self.DEWCLAW]:
                self._sdk_key(sdk, "rz", "Dewclaw_Curl", -60, 15)
                self._sdk_key(sdk, "rx", "Dewclaw_Twist", 15, -15)

    def _sdk_key(self, node, attr, driver, pos, neg):
        ctl = self.digit_attributes_ctl
        cmds.select(node)
        cmds.setDrivenKeyframe(at=attr, dv=0,   cd=f"{ctl}.{driver}", v=0)
        cmds.setDrivenKeyframe(at=attr, dv=10,  cd=f"{ctl}.{driver}", v=pos)
        cmds.setDrivenKeyframe(at=attr, dv=-10, cd=f"{ctl}.{driver}", v=neg)
