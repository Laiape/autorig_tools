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
        check(f"{base}: ctl IK Ball", cmds.objExists(f"{base}BALL_CTL"))
        ankle = f"{base}ANKLE_CTL"
        check(f"{base}: attrs stretch/soft", cmds.objExists(ankle)
              and cmds.attributeQuery("Stretch", node=ankle, exists=True)
              and cmds.attributeQuery("Soft", node=ankle, exists=True))
        check(f"{base}: blends", bool(cmds.ls(f"{base}*Blend_BLM", type="blendMatrix")))

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

maya.standalone.uninitialize()
print("RESULTADO:", "OK" if not fails else "FALLO %s" % fails)
sys.exit(1 if fails else 0)
