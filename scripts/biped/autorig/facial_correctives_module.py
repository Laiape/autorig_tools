"""
Correctivas FACIALES por joints — una por cada shape/expresión del set esculpido
(pueden ser más o menos; ver .claude/skills/corrective-joints/references/faciales.md).

Crea leaf joints correctivas colgadas de las skinning joints de los módulos faciales
(jaw/lips, cheekbone, eyebrow, eyelid), driveadas por los controles canónicos de la cara
(en facial el control ES la pose: no hay dualidad FK/IK). Usa las primitivas de
utils/correctives.py; los amounts Y los rangos de activación son atributos tunables en
C_face_CTL bajo el separador CORRECTIVES_SEP (persistibles vía character_extras del
.build) con defaults proporcionales al tamaño de la cara -> escala-independientes.

Set v1 (cada bloque se salta con un warning si su driver o su joint base no existen):
  - Jaw open  : chin (mentalis), mejillas L/R, papada/garganta.  Driver: C_jaw_CTL.rotateX
                con el signo de apertura medido (reutiliza el del auto-sticky).
  - Smile     : cheek raise L/R + nasolabial fold L/R.  Driver: lipCorner ty > 0.
  - Frown     : comisuras L/R hacia abajo/adentro.      Driver: lipCorner ty < 0.
  - Ceño      : bulge de la glabella (procerus).        Driver: DISTANCIA entre los dos
                eyebrowIn (fruncir = juntarse), normalizada por globalScale — inmune a la
                orientación de los ctls de ceja (van alineados a la curva, no al mundo).
  - Blink     : párpado superior envuelve la córnea L/R (perfil en campana: pica a mitad
                de cierre, casi 0 con el ojo cerrado). Driver: eyeDirect Upper_Blink.
                En personajes con eyelid surface=True el párpado ya se proyecta sobre el
                globo: bajar el Amount o apagar el Enable vía character_extras.
  - Pucker    : labios se proyectan en +Z. Driver: C_lipNarrowMin_COND (mínimo L/R — solo
                pucker real, sin cross-talk; convención del jaw module).
  - Brow raise: frente L/R rueda hacia arriba.          Driver: eyebrowMain ty.

Las direcciones de empuje se definen en MUNDO (personaje mirando +Z, L en +X — se
comprueba empíricamente en build y se aborta con warning si no se cumple) y se convierten
al espacio local de cada joint padre -> funcionan con cualquier orientación de joints.
make() es re-ejecutable: borra el set anterior antes de reconstruir. Naming
{L|R|C}_xxxCorrective_JNT -> skeleton_hierarchy las cuelga del _ENV de su padre en export.
"""

import re

import maya.cmds as cmds
import maya.api.OpenMaya as om
from importlib import reload

from utils import data_manager
from utils import correctives

reload(data_manager)
reload(correctives)

# Direcciones mundo (convención del repo: personaje mira +Z, lado L en +X)
_FWD = (0.0, 0.0, 1.0)
_UP = (0.0, 1.0, 0.0)

# Bases de nombre creadas por este módulo (joints + sus redes _MUL/_RMV/_SUM y los
# nodos de driver propios) — se usan para el cleanup de re-ejecución.
_NAME_BASES = (
    ["C_chinCorrective", "C_throatCorrective", "C_glabellaCorrective",
     "C_puckerCorrective", "C_jawOpenCorrective", "C_glabellaKnit", "C_glabella",
     "C_puckerAvg"]
    + [f"{s}_{b}" for s in "LR" for b in
       ["jawCheekCorrective", "smileCheekCorrective", "nasolabialCorrective",
        "frownCornerCorrective", "browRaiseCorrective", "blinkLidCorrective"]]
)


def _out(side):
    """Vector 'hacia fuera' del lado (L = +X, R = -X)."""
    return (1.0, 0.0, 0.0) if side == "L" else (-1.0, 0.0, 0.0)


def _natural_key(name):
    """Orden natural: 'x010' después de 'x02' (los ribbons nombran 0{i} sin padding)."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


class FacialCorrectivesModule(object):

    def __init__(self):
        dm = data_manager.DataExportBiped()
        self.face_ctl = dm.get_data("neck_module", "face_ctl")
        self.masterwalk = dm.get_data("basic_structure", "masterwalk_ctl")

    # ------------------------------------------------------------------ helpers

    def _exists(self, *nodes):
        return all(n and cmds.objExists(n) for n in nodes)

    def _skip(self, what, missing):
        om.MGlobal.displayInfo(f"facial_correctives: skip {what} (falta {missing})")

    def _world_pos(self, node):
        return om.MVector(*cmds.xform(node, q=True, ws=True, t=True))

    def _parent_inverse(self, parent):
        return om.MMatrix(cmds.getAttr(f"{parent}.worldInverseMatrix[0]"))

    def _local_dir(self, parent, world_dir):
        """Dirección mundo -> espacio local del padre (solo rotación/escala)."""
        v = om.MVector(*world_dir) * self._parent_inverse(parent)
        if v.length() > 1e-9:
            v.normalize()
        return (v.x, v.y, v.z)

    def _local_point(self, parent, world_point):
        """Punto mundo -> translate local bajo el padre (para rest_offset)."""
        p = om.MPoint(world_point.x, world_point.y, world_point.z) * self._parent_inverse(parent)
        return (p.x, p.y, p.z)

    def _attr(self, name, dv, minv=None, maxv=None, attr_type="float"):
        """Crea (si no existe) un attr keyable en el host y devuelve su plug."""
        if not cmds.attributeQuery(name, node=self.host, exists=True):
            kwargs = {"longName": name, "attributeType": attr_type, "defaultValue": dv, "keyable": True}
            if minv is not None:
                kwargs["minValue"] = minv
            if maxv is not None:
                kwargs["maxValue"] = maxv
            cmds.addAttr(self.host, **kwargs)
        return f"{self.host}.{name}"

    def _enable_amount(self, prefix, amount_dv):
        """Par {prefix}Enable / {prefix}Amount en el host (patrón arc_attrs de arm)."""
        en = self._attr(f"{prefix}Enable", 1, attr_type="bool")
        am = self._attr(f"{prefix}Amount", round(amount_dv, 2))
        return en, am

    def _mid(self, pattern):
        """Joint del medio de un patrón ls, en orden NATURAL (aguanta índices >9)."""
        found = sorted(cmds.ls(pattern, type="joint") or [], key=_natural_key)
        return found[len(found) // 2] if found else None

    def _closest_joint(self, patterns, world_pos):
        """Joint (no NonRot) más cercana a un punto mundo, entre varios patrones ls."""
        best, best_d = None, None
        for pat in patterns:
            for j in cmds.ls(pat, type="joint") or []:
                if "NonRot" in j:
                    continue
                d = (self._world_pos(j) - world_pos).length()
                if best_d is None or d < best_d:
                    best, best_d = j, d
        return best

    def _cleanup(self):
        """Borra el set anterior (joints + redes) -> make() re-ejecutable sin duplicar."""
        stale = []
        for base in _NAME_BASES:
            stale += cmds.ls(f"{base}*") or []
        if stale:
            cmds.delete(list(set(stale)))
            om.MGlobal.displayInfo(f"facial_correctives: limpiado set anterior ({len(stale)} nodos)")

    def _check_world_convention(self):
        """Comprueba empíricamente mira-+Z / L-en-+X; si no se cumple, mejor no
        construir nada (todos los empujes saldrían invertidos en silencio)."""
        if self._exists("L_eyeSkinning_JNT", "R_eyeSkinning_JNT"):
            if self._world_pos("L_eyeSkinning_JNT").x <= self._world_pos("R_eyeSkinning_JNT").x:
                om.MGlobal.displayWarning(
                    "facial_correctives: L_eye no está en +X (convención L=+X rota) — skip")
                return False
        if self._exists("C_upperLip00_JNT", "C_jawSkinning_JNT"):
            if self._world_pos("C_upperLip00_JNT").z <= self._world_pos("C_jawSkinning_JNT").z:
                om.MGlobal.displayWarning(
                    "facial_correctives: los labios no están en +Z del jaw (¿personaje mirando -Z?) — skip")
                return False
        return True

    # ------------------------------------------------------------------ drivers

    def _jaw_open_driver(self):
        """
        Plug en GRADOS DE APERTURA (positivo al abrir), FK-agnóstico dentro de la cara:
        C_jaw_CTL.rotateX es la mandíbula RELATIVA a la cabeza (control local), así que
        inclinar la cabeza no lo contamina. El signo de apertura se reutiliza del que
        midió empíricamente el auto-sticky del jaw module; si no existe, se mide igual
        (probe: rotar 10 grados y ver si el labio inferior baja).
        """
        sticky_mul = "C_lipsAutoStickyOpen_MUL"
        if cmds.objExists(sticky_mul):
            sign = cmds.getAttr(f"{sticky_mul}.input[1]")
        else:
            probe = "C_lowerLip00_JNT" if cmds.objExists("C_lowerLip00_JNT") else "C_jawSkinning_JNT"
            y0 = cmds.xform(probe, q=True, ws=True, t=True)[1]
            cmds.setAttr("C_jaw_CTL.rotateX", 10)
            y1 = cmds.xform(probe, q=True, ws=True, t=True)[1]
            cmds.setAttr("C_jaw_CTL.rotateX", 0)
            sign = 1.0 if y1 < y0 else -1.0
        mul = cmds.createNode("multiply", name="C_jawOpenCorrective_MUL", ss=True)
        cmds.connectAttr("C_jaw_CTL.rotateX", f"{mul}.input[0]")
        cmds.setAttr(f"{mul}.input[1]", float(sign))
        return f"{mul}.output"

    def _average(self, name, plug_a, plug_b):
        """(a + b) / 2 -> plug."""
        s = cmds.createNode("sum", name=f"{name}_SUM", ss=True)
        cmds.connectAttr(plug_a, f"{s}.input[0]")
        cmds.connectAttr(plug_b, f"{s}.input[1]")
        mul = cmds.createNode("multiply", name=f"{name}_MUL", ss=True)
        cmds.connectAttr(f"{s}.output", f"{mul}.input[0]")
        cmds.setAttr(f"{mul}.input[1]", 0.5)
        return f"{mul}.output"

    # ------------------------------------------------------------------ make

    def make(self):

        if not self._exists(self.face_ctl):
            self._skip("facial correctives", "neck_module/face_ctl")
            return

        self.host = self.face_ctl
        self.created = []

        self._cleanup()
        if not self._check_world_convention():
            return

        # Separador en el channel box (patrón CORRECTIVES_SEP del arm module)
        if not cmds.attributeQuery("CORRECTIVES_SEP", node=self.host, exists=True):
            cmds.addAttr(self.host, longName="CORRECTIVES_SEP", niceName="CORRECTIVES",
                         attributeType="enum", enumName="____", keyable=False)
            cmds.setAttr(f"{self.host}.CORRECTIVES_SEP", channelBox=True, lock=True)

        # Escala de la cara -> defaults de amounts Y rangos proporcionales al personaje.
        # Base: interocular; en caras de ojos laterales (cuadrúpedos) la interocular se
        # dispara, así que se capa con la distancia ojos->mandíbula.
        if self._exists("L_eyeSkinning_JNT", "R_eyeSkinning_JNT"):
            l_eye, r_eye = self._world_pos("L_eyeSkinning_JNT"), self._world_pos("R_eyeSkinning_JNT")
            fs = (l_eye - r_eye).length()
            if self._exists("C_jawSkinning_JNT"):
                fs = min(fs, ((l_eye + r_eye) * 0.5 - self._world_pos("C_jawSkinning_JNT")).length())
        elif self._exists("L_lipCorner_CTL", "R_lipCorner_CTL"):
            fs = (self._world_pos("L_lipCorner_CTL") - self._world_pos("R_lipCorner_CTL")).length() * 1.2
        else:
            fs = 10.0
        self.face_scale = fs

        self.jaw_open_setup()
        self.smile_frown_setup()
        self.brow_setup()
        self.blink_setup()
        self.pucker_setup()

        data_manager.DataExportBiped().append_data(
            "facial_correctives", {"host": self.host, "joints": self.created})
        om.MGlobal.displayInfo(
            f"facial_correctives: {len(self.created)} joints correctivas creadas")

    # ------------------------------------------------------------------ jaw open

    def jaw_open_setup(self):
        """Chin (mentalis) + mejillas + papada, driveados por la apertura de la jaw."""

        if not self._exists("C_jaw_CTL", "C_jawSkinning_JNT"):
            self._skip("jaw open correctives", "C_jaw_CTL / C_jawSkinning_JNT")
            return

        driver = self._jaw_open_driver()
        rng = self._attr("JawOpenRange", 25.0, minv=1.0)  # grados a apertura "completa"
        fs = self.face_scale
        jaw = "C_jawSkinning_JNT"

        # Joints centrales de los labios (nombres exactos: el patrón con * matchearía
        # también las NonRot y la local del módulo)
        upper_mid = "C_upperLip00_JNT" if cmds.objExists("C_upperLip00_JNT") else None
        lower_mid = "C_lowerLip00_JNT" if cmds.objExists("C_lowerLip00_JNT") else None

        # --- Chin / mentalis: nace en la ALMOHADILLA del mentón (bajo el surco
        # labiomental) y empuja ADELANTE al abrir (la barbilla se estira y aplana;
        # la correctiva le devuelve el volumen).
        if upper_mid and lower_mid:
            lo = self._world_pos(lower_mid)
            chin_w = lo + (lo - self._world_pos(upper_mid)) + om.MVector(0, -0.10 * fs, 0)
            en, am = self._enable_amount("JawChin", 0.12 * fs)
            jnt = correctives.corrective_offset_push(
                "C_chinCorrective", jaw, driver, 0, rng,
                self._local_point(jaw, chin_w), self._local_dir(jaw, _FWD), am,
                enable_attr=en)
            self.created.append(jnt)

            # --- Papada / garganta: bajo la barbilla, al abrir tira ABAJO/ATRÁS
            # (platysma tensándose). C_jaw_CTL.rotateX ya es jaw-vs-cabeza.
            throat_w = chin_w + om.MVector(0, -0.20 * fs, -0.15 * fs)
            en, am = self._enable_amount("JawThroat", 0.10 * fs)
            jnt = correctives.corrective_offset_push(
                "C_throatCorrective", jaw, driver, 0, rng,
                self._local_point(jaw, throat_w),
                self._local_dir(jaw, (0.0, -0.7, -0.7)), am, enable_attr=en)
            self.created.append(jnt)
        else:
            self._skip("chin/throat correctives", "C_upper/lowerLip00_JNT")

        # --- Mejillas: al abrir, la carne se tensa hacia abajo y se hunde; la
        # correctiva sostiene el volumen empujando hacia FUERA.
        for side in "LR":
            cheek_base = self._mid(f"{side}_cheekbone*Skinning_JNT")
            if not cheek_base:
                self._skip(f"{side} jaw cheek corrective", f"{side}_cheekbone*Skinning_JNT")
                continue
            base_w = self._world_pos(cheek_base) + om.MVector(0, -0.15 * self.face_scale, 0)
            en, am = self._enable_amount(f"JawCheek{side}", 0.08 * self.face_scale)
            jnt = correctives.corrective_offset_push(
                f"{side}_jawCheekCorrective", cheek_base, driver, 0, rng,
                self._local_point(cheek_base, base_w),
                self._local_dir(cheek_base, _out(side)), am, enable_attr=en)
            self.created.append(jnt)

    # ------------------------------------------------------------------ smile / frown

    def smile_frown_setup(self):
        """Cheek raise + nasolabial (smile) y comisuras abajo (frown), por lado."""

        fs = self.face_scale
        # Rangos proporcionales a la cara (~2.0 con la interocular de los assets de
        # referencia): el travel de un ctl facial escala con el personaje.
        smile_rng = self._attr("SmileRange", round(0.4 * fs, 2))
        frown_rng = self._attr("FrownRange", round(-0.4 * fs, 2))

        for side in "LR":
            corner_ctl = f"{side}_lipCorner_CTL"
            if not self._exists(corner_ctl):
                self._skip(f"{side} smile/frown correctives", corner_ctl)
                continue
            driver = f"{corner_ctl}.translateY"

            # --- Cheek raise: el "pad malar" sube y va HACIA DELANTE formando la
            # manzana de la mejilla bajo el ojo (empujar contra el hueso, no
            # ensanchar la cara). Acompaña AU6+AU12.
            cheek_base = self._mid(f"{side}_cheekbone*Skinning_JNT")
            if cheek_base:
                en, am = self._enable_amount(f"SmileCheek{side}", 0.10 * fs)
                d = (om.MVector(*_out(side)) * 0.2 + om.MVector(*_UP) * 0.7
                     + om.MVector(*_FWD) * 0.6)
                jnt = correctives.corrective_push(
                    f"{side}_smileCheekCorrective", cheek_base, driver, 0, smile_rng,
                    self._local_dir(cheek_base, (d.x, d.y, d.z)), am, enable_attr=en)
                self.created.append(jnt)
            else:
                self._skip(f"{side} smile cheek corrective", f"{side}_cheekbone*Skinning_JNT")

            # --- Nasolabial fold: joint EN la línea del pliegue (ala de la nariz ->
            # comisura) que se hunde (-Z) y sube, tallando el fold que el skinning
            # no marca. Cuelga del cheek si existe (sigue a la mejilla animada).
            nostril = f"{side}_nosetrilSkinning_JNT"
            naso_base = f"{side}_cheekSkinning_JNT" if self._exists(f"{side}_cheekSkinning_JNT") else cheek_base
            if naso_base and self._exists(nostril):
                fold_w = (self._world_pos(nostril) + self._world_pos(corner_ctl)) * 0.5
                en, am = self._enable_amount(f"Nasolabial{side}", 0.08 * fs)
                jnt = correctives.corrective_offset_push(
                    f"{side}_nasolabialCorrective", naso_base, driver, 0, smile_rng,
                    self._local_point(naso_base, fold_w),
                    self._local_dir(naso_base, (0.0, 0.55, -0.84)), am, enable_attr=en)
                self.created.append(jnt)
            else:
                self._skip(f"{side} nasolabial corrective", f"{nostril} / cheek base")

            # --- Frown: la comisura baja y va hacia el centro (depressor anguli
            # oris). Cuelga del joint de labio MÁS CERCANO a la comisura (que sigue
            # el blend jaw/upperJaw real del corner; colgarla del jaw skinning
            # doblaría la caída con la boca abierta).
            corner_w = self._world_pos(corner_ctl)
            frown_base = self._closest_joint(
                [f"{side}_upperLip*_JNT", f"{side}_lowerLip*_JNT"], corner_w)
            if frown_base:
                en, am = self._enable_amount(f"FrownCorner{side}", 0.06 * fs)
                d = om.MVector(*_out(side)) * -0.5 + om.MVector(0, -0.86, 0)
                jnt = correctives.corrective_offset_push(
                    f"{side}_frownCornerCorrective", frown_base, driver, 0, frown_rng,
                    self._local_point(frown_base, corner_w + om.MVector(0, -0.05 * fs, 0)),
                    self._local_dir(frown_base, (d.x, d.y, d.z)), am, enable_attr=en)
                self.created.append(jnt)
            else:
                self._skip(f"{side} frown corrective", f"{side}_*Lip*_JNT")

    # ------------------------------------------------------------------ ceño / brow raise

    def brow_setup(self):
        """Glabella bulge (ceño, AU4) y frente que rueda arriba (brow raise, AU1+2)."""

        fs = self.face_scale

        # --- Glabella: procerus/corrugator empujan volumen ENTRE las cejas al
        # fruncir -> push +Z. Driver = DISTANCIA entre los dos eyebrowIn: fruncir es
        # juntarse, da igual la orientación local de los ctls (van alineados a la
        # curva de la ceja, su translateX NO es "hacia la línea media") y no hay
        # signo que adivinar en R. Se normaliza por globalScale porque los drivers
        # por distancia SÍ escalan con el masterwalk.
        glab_base = "C_eyebrowMidSkinning_JNT"
        if self._exists(glab_base, "L_eyebrowIn_CTL", "R_eyebrowIn_CTL"):
            rest_d = (self._world_pos("L_eyebrowIn_CTL") - self._world_pos("R_eyebrowIn_CTL")).length()
            dbt = cmds.createNode("distanceBetween", name="C_glabellaKnit_DBT", ss=True)
            cmds.connectAttr("L_eyebrowIn_CTL.worldMatrix[0]", f"{dbt}.inMatrix1")
            cmds.connectAttr("R_eyebrowIn_CTL.worldMatrix[0]", f"{dbt}.inMatrix2")
            d_plug = f"{dbt}.distance"
            if self._exists(self.masterwalk) and cmds.attributeQuery(
                    "globalScale", node=self.masterwalk, exists=True):
                div = cmds.createNode("divide", name="C_glabellaKnit_DIV", ss=True)
                cmds.connectAttr(d_plug, f"{div}.input1")
                cmds.connectAttr(f"{self.masterwalk}.globalScale", f"{div}.input2")
                d_plug = f"{div}.output"
            # fracción de la distancia de reposo a la que el fruncido es "total"
            knit = self._attr("GlabellaKnit", 0.55, minv=0.05, maxv=0.95)
            in_max = cmds.createNode("multiply", name="C_glabellaKnitMax_MUL", ss=True)
            cmds.connectAttr(knit, f"{in_max}.input[0]")
            cmds.setAttr(f"{in_max}.input[1]", rest_d)
            driver = correctives._remap01("C_glabella", d_plug, rest_d, f"{in_max}.output")
            en, am = self._enable_amount("Glabella", 0.08 * fs)
            jnt = correctives.corrective_push(
                "C_glabellaCorrective", glab_base, driver, 0, 1,
                self._local_dir(glab_base, _FWD), am, enable_attr=en)
            self.created.append(jnt)
        else:
            self._skip("glabella corrective", f"{glab_base} / eyebrowIn ctls")

        # --- Brow raise: la piel de la frente rueda ARRIBA (y algo adelante) al
        # subir la ceja; sin esto la frente queda plana.
        raise_rng = self._attr("BrowRaiseRange", round(0.2 * fs, 2))
        for side in "LR":
            brow_base = self._mid(f"{side}_eyebrowSkinning*_JNT")
            main_ctl = f"{side}_eyebrowMain_CTL"
            if not (brow_base and self._exists(main_ctl)):
                self._skip(f"{side} brow raise corrective", f"{side}_eyebrowSkinning*/{main_ctl}")
                continue
            en, am = self._enable_amount(f"BrowRaise{side}", 0.06 * fs)
            jnt = correctives.corrective_push(
                f"{side}_browRaiseCorrective", brow_base, f"{main_ctl}.translateY",
                0, raise_rng, self._local_dir(brow_base, (0.0, 0.8, 0.6)), am,
                enable_attr=en)
            self.created.append(jnt)

    # ------------------------------------------------------------------ blink

    def blink_setup(self):
        """El párpado superior envuelve la córnea al cerrar. El error de cuerda del
        LBS es máximo a MITAD de blink y casi nulo cerrado -> perfil en campana en
        el remap (0 -> 1 a medio cierre -> 0.15 cerrado). La dirección 'fuera del
        globo' se saca del eje Z del eye joint (en cuadrúpedos el ojo mira de lado,
        el +Z mundo sería tangente al globo)."""

        for side in "LR":
            lid_base = self._mid(f"{side}_upperEyelid0*Skinning_JNT")
            direct_ctl = f"{side}_eyeDirect_CTL"
            if not (lid_base and self._exists(direct_ctl)):
                self._skip(f"{side} blink corrective", f"{side}_upperEyelid0*/{direct_ctl}")
                continue

            eye_jnt = f"{side}_eyeSkinning_JNT"
            if cmds.objExists(eye_jnt):
                m = cmds.getAttr(f"{eye_jnt}.worldMatrix[0]")
                fwd_w = om.MVector(m[8], m[9], m[10])  # eje Z del ojo = mirada
                if fwd_w.length() > 1e-9:
                    fwd_w.normalize()
                fwd_w = (fwd_w.x, fwd_w.y, fwd_w.z)
            else:
                fwd_w = _FWD

            en, am = self._enable_amount(f"BlinkLid{side}", 0.05 * self.face_scale)
            jnt = correctives.corrective_push(
                f"{side}_blinkLidCorrective", lid_base, f"{direct_ctl}.Upper_Blink",
                0.0, 1.0, self._local_dir(lid_base, fwd_w), am, enable_attr=en)
            self.created.append(jnt)

            # Campana sobre el remap creado por corrective_push
            rmv = f"{side}_blinkLidCorrective_RMV"
            if cmds.objExists(rmv):
                for i, (pos, val) in enumerate([(0.0, 0.0), (0.5, 1.0), (1.0, 0.15)]):
                    cmds.setAttr(f"{rmv}.value[{i}].value_Position", pos)
                    cmds.setAttr(f"{rmv}.value[{i}].value_FloatValue", val)
                    cmds.setAttr(f"{rmv}.value[{i}].value_Interp", 2)  # smooth

    # ------------------------------------------------------------------ pucker

    def pucker_setup(self):
        """Los labios se fruncen Y SE PROYECTAN adelante (orbicularis oris): el
        skinning los junta pero no los saca en 3D. Driver = MÍNIMO de los narrow
        L/R (C_lipNarrowMin_COND, convención del jaw module: solo actúa cuando LOS
        DOS corners van hacia dentro = pucker real, sin cross-talk L<->R)."""

        lip_base = "C_upperLip00_JNT" if cmds.objExists("C_upperLip00_JNT") else None
        if not lip_base:
            self._skip("pucker corrective", "C_upperLip00_JNT")
            return
        if cmds.objExists("C_lipNarrowMin_COND"):
            driver = "C_lipNarrowMin_COND.outColorR"
        elif self._exists("L_lipNarrow_CLM", "R_lipNarrow_CLM"):
            driver = self._average("C_puckerAvg", "L_lipNarrow_CLM.outputR", "R_lipNarrow_CLM.outputR")
        else:
            self._skip("pucker corrective", "C_lipNarrowMin_COND / lipNarrow_CLMs")
            return
        en, am = self._enable_amount("Pucker", 0.15 * self.face_scale)
        jnt = correctives.corrective_push(
            "C_puckerCorrective", lip_base, driver, 0, 1,
            self._local_dir(lip_base, _FWD), am, enable_attr=en)
        self.created.append(jnt)
