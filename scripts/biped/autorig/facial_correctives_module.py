"""
Correctivas FACIALES por joints — una por cada shape/expresión del set esculpido
(pueden ser más o menos; ver .claude/skills/corrective-joints/references/faciales.md).

Crea leaf joints correctivas colgadas de las skinning joints de los módulos faciales
(jaw/lips, cheekbone, eyebrow, eyelid), driveadas por los controles canónicos de la cara
(en facial el control ES la pose: no hay dualidad FK/IK). Usa las primitivas de
utils/correctives.py; los amounts son atributos tunables en C_face_CTL bajo el separador
CORRECTIVES_SEP (persistibles vía character_extras del .build) y proporcionales al tamaño
de la cara (distancia interocular), así que son escala-independientes.

Set v1 (cada bloque se salta con un warning si su driver o su joint base no existen):
  - Jaw open  : chin (mentalis), mejillas L/R, papada/garganta.  Driver: C_jaw_CTL.rotateX
                con el signo de apertura medido (reutiliza el del auto-sticky).
  - Smile     : cheek raise L/R + nasolabial fold L/R.  Driver: lipCorner ty > 0.
  - Frown     : comisuras L/R hacia abajo/adentro.      Driver: lipCorner ty < 0.
  - Ceño      : bulge de la glabella (procerus).        Driver: eyebrowIn tx L+R.
  - Blink     : párpado superior envuelve la córnea L/R. Driver: eyeDirect Upper_Blink.
  - Pucker    : labios se proyectan en +Z.              Driver: lipNarrow L+R (0-1).
  - Brow raise: frente L/R rueda hacia arriba.          Driver: eyebrowMain ty.

Las direcciones de empuje se definen en MUNDO (personaje mirando +Z, L en +X) y se
convierten al espacio local de cada joint padre en build -> funcionan aunque las skinning
joints tengan cualquier orientación. Naming {L|R|C}_xxxCorrective_JNT -> skeleton_hierarchy
las cuelga automáticamente del _ENV de su padre en el esqueleto de export.
"""

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


def _out(side):
    """Vector 'hacia fuera' del lado (L = +X, R = -X)."""
    return (1.0, 0.0, 0.0) if side == "L" else (-1.0, 0.0, 0.0)


class FacialCorrectivesModule(object):

    def __init__(self):
        dm = data_manager.DataExportBiped()
        self.face_ctl = dm.get_data("neck_module", "face_ctl")

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
        """Joint del medio de un patrón ls (p.ej. '{side}_cheekbone*Skinning_JNT')."""
        found = sorted(cmds.ls(pattern, type="joint") or [])
        return found[len(found) // 2] if found else None

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

        # Separador en el channel box (patrón CORRECTIVES_SEP del arm module)
        if not cmds.attributeQuery("CORRECTIVES_SEP", node=self.host, exists=True):
            cmds.addAttr(self.host, longName="CORRECTIVES_SEP", niceName="CORRECTIVES",
                         attributeType="enum", enumName="____", keyable=False)
            cmds.setAttr(f"{self.host}.CORRECTIVES_SEP", channelBox=True, lock=True)

        # Escala de la cara (interocular; fallback: boca; fallback: 10) -> defaults
        # de amount proporcionales al personaje, independientes de su tamaño.
        if self._exists("L_eyeSkinning_JNT", "R_eyeSkinning_JNT"):
            fs = (self._world_pos("L_eyeSkinning_JNT") - self._world_pos("R_eyeSkinning_JNT")).length()
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

        # --- Chin / mentalis: nace en la barbilla y empuja ADELANTE al abrir (la
        # barbilla se estira y aplana; la correctiva le devuelve el volumen).
        if upper_mid and lower_mid:
            lo = self._world_pos(lower_mid)
            chin_w = lo + (lo - self._world_pos(upper_mid))  # proyección bajo el labio
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
            self._skip("chin/throat correctives", "C_upper/lowerLip*_JNT")

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

        smile_rng = self._attr("SmileRange", 2.0)    # lipCorner ty a sonrisa completa
        frown_rng = self._attr("FrownRange", -2.0)   # lipCorner ty a mueca completa
        fs = self.face_scale

        for side in "LR":
            corner_ctl = f"{side}_lipCorner_CTL"
            if not self._exists(corner_ctl):
                self._skip(f"{side} smile/frown correctives", corner_ctl)
                continue
            driver = f"{corner_ctl}.translateY"

            # --- Cheek raise: el pómulo empuja la carne ARRIBA y contra el hueso
            # (no inflar como globo). Acompaña AU6+AU12.
            cheek_base = self._mid(f"{side}_cheekbone*Skinning_JNT")
            if cheek_base:
                en, am = self._enable_amount(f"SmileCheek{side}", 0.10 * fs)
                d = om.MVector(*_out(side)) * 0.3 + om.MVector(*_UP) * 0.9
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
            # oris); cuelga del jaw skinning para acompañar a la mandíbula.
            if self._exists("C_jawSkinning_JNT"):
                corner_w = self._world_pos(corner_ctl) + om.MVector(0, -0.05 * fs, 0)
                en, am = self._enable_amount(f"FrownCorner{side}", 0.06 * fs)
                d = om.MVector(*_out(side)) * -0.5 + om.MVector(0, -0.86, 0)
                jnt = correctives.corrective_offset_push(
                    f"{side}_frownCornerCorrective", "C_jawSkinning_JNT", driver, 0, frown_rng,
                    self._local_point("C_jawSkinning_JNT", corner_w),
                    self._local_dir("C_jawSkinning_JNT", (d.x, d.y, d.z)), am, enable_attr=en)
                self.created.append(jnt)

    # ------------------------------------------------------------------ ceño / brow raise

    def brow_setup(self):
        """Glabella bulge (ceño, AU4) y frente que rueda arriba (brow raise, AU1+2)."""

        fs = self.face_scale

        # --- Glabella: procerus/corrugator empujan volumen ENTRE las cejas al
        # fruncir; el skinning junta las cejas pero no crea el bulge -> push +Z.
        # Driver = media de los dos ceños (eyebrowIn tx), cada lado con su rango
        # por si el control R está espejado (rangos tunables en el host).
        glab_base = "C_eyebrowMidSkinning_JNT"
        if self._exists(glab_base, "L_eyebrowIn_CTL", "R_eyebrowIn_CTL"):
            rng_l = self._attr("GlabellaRangeL", -1.8)  # tx del ceño L a fruncido total
            rng_r = self._attr("GlabellaRangeR", -1.8)
            w_l = correctives._remap01("C_glabellaL", "L_eyebrowIn_CTL.translateX", 0, rng_l)
            w_r = correctives._remap01("C_glabellaR", "R_eyebrowIn_CTL.translateX", 0, rng_r)
            driver = self._average("C_glabellaAvg", w_l, w_r)
            en, am = self._enable_amount("Glabella", 0.08 * fs)
            jnt = correctives.corrective_push(
                "C_glabellaCorrective", glab_base, driver, 0, 1,
                self._local_dir(glab_base, _FWD), am, enable_attr=en)
            self.created.append(jnt)
        else:
            self._skip("glabella corrective", f"{glab_base} / eyebrowIn ctls")

        # --- Brow raise: la piel de la frente rueda ARRIBA (y algo adelante) al
        # subir la ceja; sin esto la frente queda plana.
        raise_rng = self._attr("BrowRaiseRange", 1.0)
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
        """El párpado superior envuelve la córnea al cerrar (evita el clipping/bulge):
        empuja ADELANTE (se separa del globo) a partir del ~20% del cierre."""

        for side in "LR":
            lid_base = self._mid(f"{side}_upperEyelid0*Skinning_JNT")
            direct_ctl = f"{side}_eyeDirect_CTL"
            if not (lid_base and self._exists(direct_ctl)):
                self._skip(f"{side} blink corrective", f"{side}_upperEyelid0*/{direct_ctl}")
                continue
            en, am = self._enable_amount(f"BlinkLid{side}", 0.05 * self.face_scale)
            jnt = correctives.corrective_push(
                f"{side}_blinkLidCorrective", lid_base, f"{direct_ctl}.Upper_Blink",
                0.2, 1.0, self._local_dir(lid_base, _FWD), am, enable_attr=en)
            self.created.append(jnt)

    # ------------------------------------------------------------------ pucker

    def pucker_setup(self):
        """Los labios se fruncen Y SE PROYECTAN adelante (orbicularis oris): el
        skinning los junta pero no los saca en 3D. Driver = media de los narrow
        L/R (ya normalizados 0-1 por el jaw module)."""

        lip_base = "C_upperLip00_JNT" if cmds.objExists("C_upperLip00_JNT") else None
        if not (lip_base and self._exists("L_lipNarrow_CLM", "R_lipNarrow_CLM")):
            self._skip("pucker corrective", "C_upperLip*_JNT / lipNarrow_CLMs")
            return
        driver = self._average("C_puckerAvg", "L_lipNarrow_CLM.outputR", "R_lipNarrow_CLM.outputR")
        en, am = self._enable_amount("Pucker", 0.15 * self.face_scale)
        jnt = correctives.corrective_push(
            "C_puckerCorrective", lip_base, driver, 0, 1,
            self._local_dir(lip_base, _FWD), am, enable_attr=en)
        self.created.append(jnt)
