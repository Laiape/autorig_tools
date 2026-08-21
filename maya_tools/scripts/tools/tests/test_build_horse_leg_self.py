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
        check(f"{base}: linea del Pv", cmds.objExists(f"{base}Pv_CRV"))
        # el master del pie es el ctl del fetlock; ni AnkleIk ni ctl a
        # mitad de pierna deben existir
        ankle = f"{base}FetlockIk_CTL"
        check(f"{base}: sin AnkleIk", not cmds.objExists(f"{base}AnkleIk_CTL"))
        mid = "Hock" if prefix == "backLeg" else "Carpus"
        check(f"{base}: sin ctl IK en el {mid}", not cmds.objExists(f"{base}{mid}Ik_CTL"))
        check(f"{base}: ctl Foot", cmds.objExists(f"{base}Foot_CTL"))
        check(f"{base}: ctl PasternIk", cmds.objExists(f"{base}PasternIk_CTL"))
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

# plano del IK: TODA la cadena sobre las guias en reposo, no solo el fetlock
# (un pole vector en el lado malo gira el plano y el fetlock ni se entera)
import maya.api.OpenMaya as om
CHAINS = (("backLeg", ("Hip", "Stifle", "Hock", "Fetlock")),
          ("frontLeg", ("Shoulder", "Elbow", "Carpus", "Fetlock")))

def _worst(base, fmt, joints):
    return max((om.MVector(cmds.xform(fmt.format(base=base, n=n), q=True, ws=True, t=True))
                - om.MVector(cmds.xform(f"{base}{n}_JNT", q=True, ws=True, t=True))).length()
               for n in joints)

for side in ("L", "R"):
    for prefix, joints in CHAINS:
        base = f"{side}_{prefix}"
        worst = _worst(base, "{base}{n}Ik_JNT", joints)
        check(f"{base}: cadena IK entera en reposo", worst < 0.2, "worst=%.3f" % worst)
        # FK en reposo: la cascada debe reproducir las guias exactas
        sw = f"{base}Settings_CTL.switchIkFk"
        cmds.setAttr(sw, 1)
        worst = _worst(base, "{base}{n}Fk_CTL", joints)
        cmds.setAttr(sw, 0)
        check(f"{base}: cascada FK sobre las guias", worst < 1e-3, "worst=%.4f" % worst)

# controles: canales congelados a 0 (la colocacion vive en el opm) y el ball
# IK orientado a MUNDO (point matrix)
for side in ("L", "R"):
    for prefix, joints in CHAINS:
        base = f"{side}_{prefix}"
        dirty = []
        for t in cmds.ls(f"{base}*_GRP", f"{base}*_OFF", f"{base}*_ANM", f"{base}*_CTL", type="transform"):
            for at, default in (("translate", (0, 0, 0)), ("rotate", (0, 0, 0)), ("scale", (1, 1, 1))):
                v = cmds.getAttr(f"{t}.{at}")[0]
                if any(abs(a - b) > 1e-4 for a, b in zip(v, default)):
                    dirty.append(f"{t}.{at}")
        check(f"{base}: canales de controles congelados", not dirty, str(dirty[:3]))
        bm = om.MMatrix(cmds.getAttr(f"{base}FetlockIk_CTL.worldMatrix[0]"))
        gp = cmds.xform(f"{base}Fetlock_JNT", q=True, ws=True, t=True)
        sx = 1 if side == "L" else -1  # en R el ball va espejado (X a -1)
        ws_rot = abs(bm[0] - sx) < 1e-4 and all(abs(bm[k] - 1) < 1e-4 for k in (5, 10))
        ws_pos = all(abs(bm[12 + i] - gp[i]) < 1e-3 for i in range(3))
        check(f"{base}: ball IK en world space sobre su guia", ws_rot and ws_pos)

# ESPEJO L/R por comportamiento: el mismo valor de canal en L y R produce el
# movimiento espejo (x opuesta, y/z iguales) en la salida
def _wpos(n):
    return om.MVector(cmds.xform(n, q=True, ws=True, t=True))

def _probe(ctl_suffix, attr, value, probe_suffix, prefix="backLeg"):
    res = {}
    for side in ("L", "R"):
        ctl = f"{side}_{prefix}{ctl_suffix}"
        pr = f"{side}_{prefix}{probe_suffix}"
        p0 = _wpos(pr)
        cmds.setAttr(f"{ctl}.{attr}", value)
        p1 = _wpos(pr)
        cmds.setAttr(f"{ctl}.{attr}", 0)
        res[side] = p1 - p0
    dL, dR = res["L"], res["R"]
    return abs(dL.x + dR.x) < 0.05 and abs(dL.y - dR.y) < 0.05 and abs(dL.z - dR.z) < 0.05, dL, dR

for label, args in (
    ("HipFk rz30", ("HipFk_CTL", "rotateZ", 30, "StifleFk_CTL")),
    ("HipFk ry30", ("HipFk_CTL", "rotateY", 30, "StifleFk_CTL")),
    ("StifleFk rz-40", ("StifleFk_CTL", "rotateZ", -40, "HockFk_CTL")),
    ("FetlockIk tz10", ("FetlockIk_CTL", "translateZ", 10, "StifleIk_JNT")),
    ("FetlockIk tx5", ("FetlockIk_CTL", "translateX", 5, "StifleIk_JNT")),
    ("FetlockIk ry30", ("FetlockIk_CTL", "rotateY", 30, "TipSkinning_JNT")),
    ("Foot rx25", ("Foot_CTL", "rotateX", 25, "TipSkinning_JNT")),
    ("Roll -20", ("FetlockIk_CTL", "Roll", -20, "TipSkinning_JNT")),
    ("Bank 20", ("FetlockIk_CTL", "Bank", 20, "TipSkinning_JNT")),
    ("HipIk ty5", ("HipIk_CTL", "translateY", 5, "StifleIk_JNT")),
    ("ElbowFk rz30 (front)", ("ElbowFk_CTL", "rotateZ", 30, "CarpusFk_CTL", "frontLeg")),
):
    ok, dL, dR = _probe(*args)
    check(f"espejo L/R: {label}", ok, "L=%s R=%s" % ([round(v, 2) for v in dL], [round(v, 2) for v in dR]))
check("espejo L/R: FetlockIk R con X a -1", abs(cmds.getAttr("R_backLegFetlockIk_CTL.worldMatrix[0]")[0] + 1) < 1e-4)

# bendys y joints de skinning del ribbon ORIENTADOS como la cadena original
def _axes(m):
    m = om.MMatrix(m)
    return [om.MVector(m[0], m[1], m[2]), om.MVector(m[4], m[5], m[6]), om.MVector(m[8], m[9], m[10])]

for side in ("L", "R"):
    for prefix, joints in CHAINS:
        base = f"{side}_{prefix}"
        worst = 1.0
        for i, seg in enumerate(("Upper", "Middle", "Lower")):
            ga = _axes(cmds.getAttr(f"{base}{joints[i]}Blend_BLM.outputMatrix"))
            for node in [f"{base}{seg}Bendy_CTL"] + cmds.ls(f"{base}{seg}0?_ENV") + cmds.ls(f"{base}{seg}0?Skinning_JNT"):
                na = _axes(cmds.getAttr(f"{node}.worldMatrix[0]"))
                worst = min(worst, na[0] * ga[0], na[1] * ga[1], na[2] * ga[2])
        check(f"{base}: bendys y ribbon orientados como la cadena", worst > 0.98, "dot=%.3f" % worst)

# Bend_Bias (spring): redistribuye el doblez sin mover el pie; 0.5 = reposo
for side in ("L",):
    ankle = f"{side}_backLegFetlockIk_CTL"
    if not cmds.attributeQuery("Bend_Bias", node=ankle, exists=True):
        check("bias spring: attr Bend_Bias", False)
    else:
        # en pose PLEGADA: en reposo cualquier reparto da la misma solucion
        cmds.setAttr(f"{ankle}.translateY", 15)
        stifle0 = _wpos(f"{side}_backLegStifleIk_JNT")
        foot0 = _wpos(f"{side}_backLegFetlockIk_JNT")
        cmds.setAttr(f"{ankle}.Bend_Bias", 1)
        d_stifle = (_wpos(f"{side}_backLegStifleIk_JNT") - stifle0).length()
        d_foot = (_wpos(f"{side}_backLegFetlockIk_JNT") - foot0).length()
        cmds.setAttr(f"{ankle}.Bend_Bias", 0.5)
        d_back = (_wpos(f"{side}_backLegStifleIk_JNT") - stifle0).length()
        cmds.setAttr(f"{ankle}.translateY", 0)
        check("bias spring: redistribuye (babilla se mueve)", d_stifle > 0.5, "d=%.2f" % d_stifle)
        check("bias spring: el pie no se mueve", d_foot < 0.05, "d=%.3f" % d_foot)
        check("bias spring: 0.5 vuelve al reparto natural", d_back < 1e-3, "d=%.4f" % d_back)

# pie reverso FUNCIONAL, medido en los joints de skinning del pie (lo que
# deforma): roll negativo bascula sobre el talon -> la punta SUBE; roll pasado
# el break rueda sobre la punta -> la cuartilla SUBE; a 0 vuelve al reposo.
for side in ("L", "R"):
    ankle = f"{side}_backLegFetlockIk_CTL"
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

# Foot: rota SOLO el casco (fetlock hacia abajo) — el IK de la pierna no se mueve
for side in ("L", "R"):
    foot = f"{side}_backLegFoot_CTL"
    tip = f"{side}_backLegTipSkinning_JNT"
    fet = f"{side}_backLegFetlockIk_JNT"
    if not all(cmds.objExists(n) for n in (foot, tip, fet)):
        check(f"{side}: ctl Foot funcional (nodos presentes)", False)
        continue
    t0 = om.MVector(cmds.xform(tip, q=True, ws=True, t=True))
    f0 = om.MVector(cmds.xform(fet, q=True, ws=True, t=True))
    cmds.setAttr(f"{foot}.rotateX", 25)
    dt = (om.MVector(cmds.xform(tip, q=True, ws=True, t=True)) - t0).length()
    df = (om.MVector(cmds.xform(fet, q=True, ws=True, t=True)) - f0).length()
    cmds.setAttr(f"{foot}.rotateX", 0)
    check(f"{side}: Foot rota el casco", dt > 0.5, "d_tip=%.3f" % dt)
    check(f"{side}: Foot no mueve la pierna IK", df < 1e-3, "d_fet=%.5f" % df)

    # PasternIk: PIVOTE del IK en la cuartilla — rotarlo pivota el fetlock
    # (la pierna sigue) y el casco, con la cuartilla quieta
    pastern = f"{side}_backLegPasternIk_CTL"
    t0 = om.MVector(cmds.xform(tip, q=True, ws=True, t=True))
    f0 = om.MVector(cmds.xform(fet, q=True, ws=True, t=True))
    p0 = om.MVector(cmds.xform(pastern, q=True, ws=True, t=True))
    cmds.setAttr(f"{pastern}.rotateX", 25)
    dt = (om.MVector(cmds.xform(tip, q=True, ws=True, t=True)) - t0).length()
    df = (om.MVector(cmds.xform(fet, q=True, ws=True, t=True)) - f0).length()
    dp = (om.MVector(cmds.xform(pastern, q=True, ws=True, t=True)) - p0).length()
    cmds.setAttr(f"{pastern}.rotateX", 0)
    check(f"{side}: PasternIk rota el casco", dt > 0.5, "d_tip=%.3f" % dt)
    check(f"{side}: PasternIk pivota la pierna (fetlock orbita)", df > 0.5, "d_fet=%.3f" % df)
    check(f"{side}: PasternIk pivota sobre si mismo", dp < 1e-3, "d=%.5f" % dp)

# ── config de nodos (SELF MATH): reparto tipo spring + stretch/soft ──
cmds.file(new=True, force=True)
modules_grp = cmds.createNode("transform", name="modules_GRP")
skel_grp = cmds.createNode("transform", name="skel_GRP")
masterwalk = cmds.circle(name="C_masterwalk_CTL", ch=False)[0]
cmds.addAttr(masterwalk, longName="globalScale", attributeType="float", defaultValue=1, keyable=True)
dm = data_manager.DataExportBiped()
dm.new_build()
dm.append_data("basic_structure", {
    "modules_GRP": modules_grp,
    "skel_GRP": skel_grp,
    "masterwalk_ctl": masterwalk,
})
leg = lm.BackLegModule()
try:
    leg.make("L", solver="nodes", skinning_joints_number=5)
    check("nodes: build", True)
except Exception:
    traceback.print_exc()
    check("nodes: build", False, "excepcion")

base = "L_backLeg"
ankle = f"{base}FetlockIk_CTL"
check("nodes: sin ikHandles", not cmds.ls(type="ikHandle"))
check("nodes: attrs stretch/soft", all(cmds.attributeQuery(a, node=ankle, exists=True)
      for a in ("Stretch", "Soft", "Soft_Start")))

def _pt(i):
    m = cmds.getAttr(leg.nodes_ik_world[i])
    return om.MVector(m[12], m[13], m[14])

def _hock_angle():
    return math.degrees((_pt(1) - _pt(2)).angle(_pt(3) - _pt(2)))

import math
# referencia de reposo: los frames horneados de las guias (la cadena guia y la
# ik se borran en publish en la config de nodos)
def _gm(l, i):
    return om.MMatrix(cmds.getAttr(l.guides_matrices[i]))

worst = max((_pt(i) - om.MVector(_gm(leg, i)[12], _gm(leg, i)[13], _gm(leg, i)[14])).length()
            for i in range(5))
check("nodes: reposo de la red", worst < 1.7, "worst=%.3f" % worst)
check("nodes: linea del Pv", cmds.objExists(f"{base}Pv_CRV"))
check("nodes: cadenas ik y guia borradas", not cmds.objExists(f"{base}Hip_JNT") and not cmds.objExists(f"{base}HipIk_JNT"))

# frames de la red alineados con las guias (X e Y) - en las DOS patas
for cls2, base2, names2 in ((lm.FrontLegModule, "L_frontLeg", ("Shoulder", "Elbow", "Carpus")),):
    leg2 = cls2()
    leg2.make("L", solver="nodes", skinning_joints_number=5)
    worst_dot = 1.0
    for i, n_ in enumerate(names2):
        fm = om.MMatrix(cmds.getAttr(leg2.nodes_ik_world[i]))
        gm = _gm(leg2, i)
        worst_dot = min(worst_dot, fm[0]*gm[0]+fm[1]*gm[1]+fm[2]*gm[2], fm[4]*gm[4]+fm[5]*gm[5]+fm[6]*gm[6])
    check(f"nodes: frames {base2} sobre las guias", worst_dot > 0.98, "dot=%.3f" % worst_dot)
worst_dot = 1.0
for i, n_ in enumerate(("Hip", "Stifle", "Hock")):
    fm = om.MMatrix(cmds.getAttr(leg.nodes_ik_world[i]))
    gm = _gm(leg, i)
    worst_dot = min(worst_dot, fm[0]*gm[0]+fm[1]*gm[1]+fm[2]*gm[2], fm[4]*gm[4]+fm[5]*gm[5]+fm[6]*gm[6])
check(f"nodes: frames {base} sobre las guias", worst_dot > 0.98, "dot=%.3f" % worst_dot)

# reparto tipo spring: al plegar la pata el CORVEJON tambien dobla (con la
# cuerda fija quedaba congelado = RP+SC)
a0 = _hock_angle()
cmds.setAttr(f"{ankle}.translateY", 20)
a1 = _hock_angle()
cmds.setAttr(f"{ankle}.translateY", 0)
check("nodes: el corvejon dobla al plegar (spring)", abs(a1 - a0) > 5, "delta=%.1f grados" % (a1 - a0))

# stretch: con Stretch=1 y el objetivo fuera de alcance, el fetlock lo sigue
cmds.setAttr(f"{ankle}.Stretch", 1)
cmds.setAttr(f"{ankle}.translateY", -25)
target = om.MVector(cmds.xform(f"{base}Foot_CTL", q=True, ws=True, t=True))
d_reach = (_pt(3) - target).length()
cmds.setAttr(f"{ankle}.Stretch", 0)
d_noreach = (_pt(3) - target).length()
cmds.setAttr(f"{ankle}.translateY", 0)
check("nodes: stretch alcanza el objetivo", d_reach < 0.1, "d=%.3f" % d_reach)
check("nodes: sin stretch se queda corto", d_noreach > 1.0, "d=%.3f" % d_noreach)

# Bend_Bias (nodes): mismo dial sobre la cuerda, medido en pose plegada
if cmds.attributeQuery("Bend_Bias", node=ankle, exists=True):
    cmds.setAttr(f"{ankle}.translateY", 15)
    b0 = _pt(1)
    f0 = _pt(3)
    cmds.setAttr(f"{ankle}.Bend_Bias", 1)
    d_stifle = (_pt(1) - b0).length()
    d_foot = (_pt(3) - f0).length()
    cmds.setAttr(f"{ankle}.Bend_Bias", 0.5)
    d_back = (_pt(1) - b0).length()
    cmds.setAttr(f"{ankle}.translateY", 0)
    check("bias nodes: redistribuye (babilla se mueve)", d_stifle > 0.5, "d=%.2f" % d_stifle)
    check("bias nodes: el pie no se mueve", d_foot < 0.05, "d=%.3f" % d_foot)
    check("bias nodes: 0.5 vuelve al reparto natural", d_back < 1e-3, "d=%.4f" % d_back)
else:
    check("bias nodes: attr Bend_Bias", False)

maya.standalone.uninitialize()
print("RESULTADO:", "OK" if not fails else "FALLO %s" % fails)
sys.exit(1 if fails else 0)
