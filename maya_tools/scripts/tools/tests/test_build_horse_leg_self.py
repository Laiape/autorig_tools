"""Build headless de las 4 patas de leg_module_self con las guias del caballo."""
import sys, traceback

import maya.standalone
maya.standalone.initialize(name="python")

import maya.cmds as cmds

fails = []

def check(label, ok, detail=""):
    print("%-56s %s %s" % (label, "OK " if ok else "MAL", detail))
    if not ok:
        fails.append(label)

# ── contexto de personaje + estructura minima que el modulo lee del cache ──
cmds.optionVar(sv=("currentAssetRigName", "horse"))
cmds.file(new=True, force=True)

modules_grp = cmds.createNode("transform", name="modules_GRP")
skel_grp = cmds.createNode("transform", name="skel_GRP")
masterwalk = cmds.circle(name="C_masterwalk_CTL", ch=False)[0]
cmds.addAttr(masterwalk, longName="globalScale", attributeType="float", defaultValue=1, keyable=True)

from maya_tools.scripts.utils import data_manager
dm = data_manager.DataExportBiped()
dm.new_build()
dm.append_data("basic_structure", {
    "modules_GRP": modules_grp,
    "skel_GRP": skel_grp,
    "masterwalk_ctl": masterwalk,
})

from maya_tools.scripts.quadruped.autorig import leg_module_self as lm

# ── build de las cuatro patas ──
for cls, sides in ((lm.BackLegModule, ("L", "R")), (lm.FrontLegModule, ("L", "R"))):
    for side in sides:
        label = f"{cls.__name__} {side}"
        try:
            # misma firma que usa rig_manager (el boton de BUILD RIG)
            cls().make(side, solver="spring", skinning_joints_number=5)
            check(f"build {label}", True)
        except Exception:
            traceback.print_exc()
            check(f"build {label}", False, "excepcion")

# ── sanity checks sobre la escena resultante ──
for side in ("L", "R"):
    for prefix, root in (("backLeg", "Hip"), ("frontLeg", "Shoulder")):
        base = f"{side}_{prefix}"
        check(f"{base}: cadena IK", cmds.objExists(f"{base}{root}Ik_JNT"))
        check(f"{base}: handle spring", bool(cmds.ls(f"{side}_*Ik_HDL", type="ikHandle")))
        check(f"{base}: settings ctl", cmds.objExists(f"{base}Settings_CTL"))
        check(f"{base}: ctl FK raiz", cmds.objExists(f"{base}{root}Fk_CTL"))
        # nombres de ctl IK derivados de la guia de su indice semantico
        check(f"{base}: ctl IK ball (FetlockIk)", cmds.objExists(f"{base}FetlockIk_CTL"))
        check(f"{base}: ctl Pv", cmds.objExists(f"{base}Pv_CTL"))
        ankle = f"{base}AnkleIk_CTL"
        check(f"{base}: attrs stretch/soft", cmds.objExists(ankle)
              and cmds.attributeQuery("Stretch", node=ankle, exists=True)
              and cmds.attributeQuery("Soft", node=ankle, exists=True))
        check(f"{base}: blends", bool(cmds.ls(f"{base}*Blend_BLM", type="blendMatrix")))
        # skinning: 3 segmentos x skinning_joints_number (ribbons) + 3 del pie
        skel = f"{base}Skinning_GRP"
        skel_jnts = cmds.listRelatives(skel, allDescendents=True, type="joint") or []
        check(f"{base}: joints de skinning (>=18)", len(skel_jnts) >= 18, f"n={len(skel_jnts)}")
        check(f"{base}: pie skinning", all(cmds.objExists(f"{base}{n}Skinning_JNT") for n in ("Fetlock", "Pastern", "Tip")))
        # pie reverso: pila de pivotes + atributos de roll en el ctl del tobillo
        check(f"{base}: pivotes reversos", all(cmds.objExists(f"{base}{p}_CTL")
              for p in ("BankOut", "BankIn", "Heel", "Toe", "Sole")))
        check(f"{base}: attrs de roll", cmds.objExists(ankle)
              and all(cmds.attributeQuery(a, node=ankle, exists=True)
                      for a in ("Roll", "Bank", "Roll_Break_Angle", "Roll_Straight_Angle")))

# reposo: el blend (peso 0 = IK) debe devolver la pose de guia -> los joints
# ik reposan sobre las guias originales
import maya.api.OpenMaya as om
probe = "L_backLegFetlockIk_JNT"
guide = "L_backLegFetlock_JNT"
if cmds.objExists(probe) and cmds.objExists(guide):
    p1 = om.MVector(cmds.xform(probe, q=True, ws=True, t=True))
    p2 = om.MVector(cmds.xform(guide, q=True, ws=True, t=True))
    check("reposo: IK fetlock sobre la guia", (p1 - p2).length() < 1e-3,
          "delta=%.5f" % (p1 - p2).length())

# pie reverso FUNCIONAL, medido en los joints de skinning del pie (lo que
# deforma): roll negativo bascula sobre el talon -> la punta SUBE; roll pasado
# el break rueda sobre la punta -> la cuartilla SUBE; a 0 vuelve al reposo.
for side in ("L", "R"):
    ankle = f"{side}_backLegAnkleIk_CTL"
    tip = f"{side}_backLegTipSkinning_JNT"
    pastern = f"{side}_backLegPasternSkinning_JNT"
    if not all(cmds.objExists(n) for n in (ankle, tip, pastern)):
        check(f"{side}: pie reverso funcional (nodos presentes)", False)
        continue
    tip_rest_y = cmds.xform(tip, q=True, ws=True, t=True)[1]
    pastern_rest_y = cmds.xform(pastern, q=True, ws=True, t=True)[1]

    cmds.setAttr(f"{ankle}.Roll", -20)
    dy = cmds.xform(tip, q=True, ws=True, t=True)[1] - tip_rest_y
    check(f"{side}: roll -20 punta sube (talon)", dy > 0.1, "dy=%.3f" % dy)

    cmds.setAttr(f"{ankle}.Roll", 60)
    dy = cmds.xform(pastern, q=True, ws=True, t=True)[1] - pastern_rest_y
    check(f"{side}: roll 60 cuartilla sube (punta)", dy > 0.1, "dy=%.3f" % dy)

    cmds.setAttr(f"{ankle}.Roll", 0)
    dy = cmds.xform(tip, q=True, ws=True, t=True)[1] - tip_rest_y
    check(f"{side}: roll 0 vuelve al reposo", abs(dy) < 1e-4, "dy=%.5f" % dy)

maya.standalone.uninitialize()
print("RESULTADO:", "OK" if not fails else "FALLO %s" % fails)
sys.exit(1 if fails else 0)
