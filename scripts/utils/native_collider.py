"""
native_collider — colisión de falda contra las piernas SOLO con nodos nativos de Maya
(sin plugin). Prototipo para evaluar si el empuje por-joint da calidad suficiente.

Idea: cada joint de la falda parte de una posición de REPOSO (anillo que cuelga de la
cintura) y se EMPUJA fuera de la "cápsula" de cada pierna (segmentos hip->knee->ankle)
usando matemática vectorial en nodos:
    closest point en el segmento -> distancia -> si < radio, mover a (closest + dir*radio).

Todo con nodos nativos (plusMinusAverage, vectorProduct, multiplyDivide, clamp,
distanceBetween, condition, decomposeMatrix) -> deformador determinista, portable, sin
dependencias. Se aplican los segmentos en cadena (sale de uno y luego del siguiente).
"""

import math
import maya.cmds as cmds
import maya.api.OpenMaya as om


def _set_or_connect(plug, value):
    if isinstance(value, str):
        cmds.connectAttr(value, plug)
    else:
        cmds.setAttr(plug, value)


def _n(node_type, name):
    return cmds.createNode(node_type, name=name, ss=True)


def push_out_segment(name, P, A, B, radius):
    """
    Empuja el punto `P` (plug vector) fuera del segmento [A,B] (plugs vector) si está a
    menos de `radius`. Devuelve el plug vector de la posición resultante (condition.outColor).
    Si no penetra, devuelve P sin cambios.
    """
    # AB = B - A ;  AP = P - A
    ab = _n("plusMinusAverage", name + "_AB"); cmds.setAttr(ab + ".operation", 2)
    cmds.connectAttr(B, ab + ".input3D[0]"); cmds.connectAttr(A, ab + ".input3D[1]")
    ap = _n("plusMinusAverage", name + "_AP"); cmds.setAttr(ap + ".operation", 2)
    cmds.connectAttr(P, ap + ".input3D[0]"); cmds.connectAttr(A, ap + ".input3D[1]")

    # t = dot(AP,AB) / dot(AB,AB), clamp 0..1
    d1 = _n("vectorProduct", name + "_dotAPAB"); cmds.setAttr(d1 + ".operation", 1)
    cmds.connectAttr(ap + ".output3D", d1 + ".input1"); cmds.connectAttr(ab + ".output3D", d1 + ".input2")
    d2 = _n("vectorProduct", name + "_dotABAB"); cmds.setAttr(d2 + ".operation", 1)
    cmds.connectAttr(ab + ".output3D", d2 + ".input1"); cmds.connectAttr(ab + ".output3D", d2 + ".input2")
    tdiv = _n("multiplyDivide", name + "_t"); cmds.setAttr(tdiv + ".operation", 2)
    cmds.connectAttr(d1 + ".outputX", tdiv + ".input1X"); cmds.connectAttr(d2 + ".outputX", tdiv + ".input2X")
    tc = _n("clamp", name + "_tc"); cmds.setAttr(tc + ".minR", 0); cmds.setAttr(tc + ".maxR", 1)
    cmds.connectAttr(tdiv + ".outputX", tc + ".inputR")

    # closest = A + AB*t
    sab = _n("multiplyDivide", name + "_scaledAB"); cmds.setAttr(sab + ".operation", 1)
    cmds.connectAttr(ab + ".output3D", sab + ".input1")
    for ax in "XYZ":
        cmds.connectAttr(tc + ".outputR", sab + ".input2" + ax)
    cl = _n("plusMinusAverage", name + "_closest"); cmds.setAttr(cl + ".operation", 1)
    cmds.connectAttr(A, cl + ".input3D[0]"); cmds.connectAttr(sab + ".output", cl + ".input3D[1]")

    # dvec = P - closest ; dist ; dir = normalize(dvec)
    dv = _n("plusMinusAverage", name + "_dvec"); cmds.setAttr(dv + ".operation", 2)
    cmds.connectAttr(P, dv + ".input3D[0]"); cmds.connectAttr(cl + ".output3D", dv + ".input3D[1]")
    dist = _n("distanceBetween", name + "_dist")
    cmds.connectAttr(P, dist + ".point1"); cmds.connectAttr(cl + ".output3D", dist + ".point2")
    dirn = _n("vectorProduct", name + "_dir"); cmds.setAttr(dirn + ".operation", 0); cmds.setAttr(dirn + ".normalizeOutput", 1)
    cmds.connectAttr(dv + ".output3D", dirn + ".input1")

    # pushed = closest + dir*radius
    dr = _n("multiplyDivide", name + "_dirR"); cmds.setAttr(dr + ".operation", 1)
    cmds.connectAttr(dirn + ".output", dr + ".input1")
    for ax in "XYZ":
        _set_or_connect(dr + ".input2" + ax, radius)
    pushed = _n("plusMinusAverage", name + "_pushed"); cmds.setAttr(pushed + ".operation", 1)
    cmds.connectAttr(cl + ".output3D", pushed + ".input3D[0]"); cmds.connectAttr(dr + ".output", pushed + ".input3D[1]")

    # if dist < radius -> pushed else P
    cond = _n("condition", name + "_cond"); cmds.setAttr(cond + ".operation", 4)  # 4 = Less Than
    cmds.connectAttr(dist + ".distance", cond + ".firstTerm"); _set_or_connect(cond + ".secondTerm", radius)
    cmds.connectAttr(pushed + ".output3D", cond + ".colorIfTrue")
    cmds.connectAttr(P, cond + ".colorIfFalse")
    return cond + ".outColor"


def _world_t(jnt):
    """Plug vector con la traslación mundo de un joint."""
    d = _n("decomposeMatrix", jnt.split("|")[-1] + "_DCM")
    cmds.connectAttr(jnt + ".worldMatrix[0]", d + ".inputMatrix")
    return d + ".outputTranslate"


def build_skirt_ring(prefix, waist, legs, count=12, height=20.0, ring_radius=18.0):
    """
    Prototipo: crea un anillo de `count` joints que cuelga de `waist` (reposo) y se empuja
    fuera de las piernas. `legs` = lista de dicts {hip,knee,ankle,radius} (joints _ENV).
    Devuelve (grp, joints).
    """
    grp = cmds.createNode("transform", name=prefix + "nativeSkirt_GRP")
    waistT = _world_t(waist)

    segs = []  # (A, B, radius)
    for leg in legs:
        a, m, b = _world_t(leg["hip"]), _world_t(leg["knee"]), _world_t(leg["ankle"])
        r = leg.get("radius", 8.0)
        segs.append((a, m, r))
        segs.append((m, b, r))

    joints = []
    for i in range(count):
        th = 2.0 * math.pi * i / count
        off = (ring_radius * math.cos(th), -height, ring_radius * math.sin(th))
        rest = _n("plusMinusAverage", f"{prefix}skirt{i:02d}_rest"); cmds.setAttr(rest + ".operation", 1)
        cmds.connectAttr(waistT, rest + ".input3D[0]")
        cmds.setAttr(rest + ".input3D[1]", off[0], off[1], off[2], type="double3")
        P = rest + ".output3D"
        for s, (A, B, r) in enumerate(segs):
            P = push_out_segment(f"{prefix}skirt{i:02d}_seg{s}", P, A, B, r)
        cmds.select(clear=True)
        jnt = cmds.joint(name=f"{prefix}skirt{i:02d}_JNT")
        cmds.parent(jnt, grp)
        cmds.connectAttr(P, jnt + ".translate")
        joints.append(jnt)
    return grp, joints


def _drive_joint_world(name, parent, pos_plug):
    """Crea un joint hijo de `parent` cuya posición mundo = `pos_plug` (color/vector),
    con rotación identidad, vía offsetParentMatrix negando al padre (sirve en cadena)."""
    cmds.select(clear=True)
    jnt = cmds.joint(name=name)
    cmds.parent(jnt, parent)
    inv = cmds.listConnections(f"{jnt}.inverseScale", destination=False, source=True, plugs=True)
    if inv:
        cmds.disconnectAttr(inv[0], f"{jnt}.inverseScale")
    four = _n("fourByFourMatrix", name + "_4x4")
    cmds.connectAttr(pos_plug + "R", four + ".in30")
    cmds.connectAttr(pos_plug + "G", four + ".in31")
    cmds.connectAttr(pos_plug + "B", four + ".in32")
    mmx = _n("multMatrix", name + "_OPM")
    cmds.connectAttr(four + ".output", mmx + ".matrixIn[0]")
    cmds.connectAttr(parent + ".worldInverseMatrix[0]", mmx + ".matrixIn[1]")
    cmds.connectAttr(mmx + ".matrixSum", jnt + ".offsetParentMatrix")
    cmds.setAttr(jnt + ".translate", 0, 0, 0)
    cmds.setAttr(jnt + ".jointOrient", 0, 0, 0)
    cmds.setAttr(jnt + ".radius", 0.5)
    return jnt


def build_native_skirt(prefix, waist, legs, rings=4, count=12,
                       top_radius=10.0, bottom_radius=22.0, height=40.0,
                       skinning_parent=None, make_env=True, waist_env=None):
    """
    Falda completa con colisión, SOLO nodos nativos (sin plugin).

    - Reposo en CAMPANA que sigue a la cintura `waist` (offset en su espacio local, así
      acompaña rotación+traslación): `rings` anillos hacia abajo, radio de `top_radius`
      (arriba) a `bottom_radius` (bajo), cayendo hasta `height`.
    - Cada joint se EMPUJA fuera de las cápsulas de las piernas (`legs`: dicts
      {hip,knee,ankle,radius}), por segmentos hip->knee->ankle.
    - Joints en CADENAS verticales (una por vuelta), driveados por offsetParentMatrix.
    - Si make_env: crea sus `_ENV` espejando las cadenas, colgando de `waist_env`
      (para el esqueleto de export / skeleton_hierarchy).

    Returns: (grp, columns)  columns = lista de cadenas (cada una lista de joints).
    """
    grp = cmds.createNode("transform", name=f"{prefix}skirtSkinning_GRP")
    if skinning_parent and cmds.objExists(skinning_parent):
        cmds.parent(grp, skinning_parent)

    wm = om.MMatrix(cmds.getAttr(waist + ".worldMatrix[0]"))
    w_inv = wm.inverse()
    wp = cmds.xform(waist, q=True, ws=True, t=True)

    segs = []  # (A, B, radius)
    for leg in legs:
        a, m, b = _world_t(leg["hip"]), _world_t(leg["knee"]), _world_t(leg["ankle"])
        r = leg.get("radius", 8.0)
        segs.append((a, m, r)); segs.append((m, b, r))

    columns = []
    for c in range(count):
        th = 2.0 * math.pi * c / count
        prev = grp
        chain = []
        for ri in range(rings):
            t_down = ri / float(max(1, rings - 1))          # 0..1 (radio)
            radius = top_radius + (bottom_radius - top_radius) * t_down
            h = height * (ri + 1) / float(rings)            # caída
            # punto de campana en MUNDO -> a espacio local de la cintura (sigue su pose)
            world_pt = om.MPoint(wp[0] + radius * math.cos(th), wp[1] - h, wp[2] + radius * math.sin(th))
            loc = world_pt * w_inv
            # reposo siguiendo la cintura: punto local x worldMatrix (vectorProduct op4 = point-matrix)
            pmm = _n("vectorProduct", f"{prefix}skirt{c:02d}_{ri:02d}_rest")
            cmds.setAttr(pmm + ".operation", 4)
            cmds.setAttr(pmm + ".input1", loc.x, loc.y, loc.z, type="double3")
            cmds.connectAttr(waist + ".worldMatrix[0]", pmm + ".matrix")
            P = pmm + ".output"
            for s, (A, B, r) in enumerate(segs):
                P = push_out_segment(f"{prefix}skirt{c:02d}_{ri:02d}_seg{s}", P, A, B, r)
            jnt = _drive_joint_world(f"{prefix}skirt{c:02d}_{ri:02d}_JNT", prev, P)
            chain.append(jnt)
            prev = jnt
        columns.append(chain)

    if make_env and waist_env and cmds.objExists(waist_env):
        for chain in columns:
            prev_env = waist_env
            for jnt in chain:
                env_name = jnt.split("|")[-1].replace("_JNT", "_ENV")
                env = cmds.createNode("joint", name=env_name, parent=prev_env)
                inv = cmds.listConnections(f"{env}.inverseScale", destination=False, source=True, plugs=True)
                if inv:
                    cmds.disconnectAttr(inv[0], f"{env}.inverseScale")
                mmx = _n("multMatrix", env_name + "Env_MMX")
                cmds.connectAttr(jnt + ".worldMatrix[0]", mmx + ".matrixIn[0]")
                cmds.connectAttr(prev_env + ".worldInverseMatrix[0]", mmx + ".matrixIn[1]")
                cmds.connectAttr(mmx + ".matrixSum", env + ".offsetParentMatrix")
                cmds.setAttr(env + ".jointOrient", 0, 0, 0)
                prev_env = env

    return grp, columns


# Plantillas de los joints _ENV del rig (skeletonHierarchy). {side} -> "L"/"R".
RIG_ENV_LEGS = {
    "hip":   "{side}_legUpper00_ENV",
    "knee":  "{side}_legLower00_ENV",
    "ankle": "{side}_legAnkle_ENV",
    "waist": "C_localHip_ENV",
}


def build_native_skirt_from_rig(prefix="", rings=5, count=16,
                                skinning_parent="skel_GRP", names=None):
    """
    Conveniencia: monta la falda nativa resolviendo los joints _ENV del rig y la escala
    automáticamente (radios/altura desde la longitud del muslo). `names` permite override.
    Returns: (grp, columns) o None si faltan joints.
    """
    tpl = dict(RIG_ENV_LEGS)
    if names:
        tpl.update(names)
    waist = tpl["waist"]
    if not cmds.objExists(waist):
        cmds.warning(f"native skirt: no existe la cintura '{waist}'.")
        return None

    legs = []
    for s in ("L", "R"):
        hip, knee, ankle = (tpl["hip"].format(side=s), tpl["knee"].format(side=s), tpl["ankle"].format(side=s))
        if not all(cmds.objExists(x) for x in (hip, knee, ankle)):
            cmds.warning(f"native skirt: faltan joints _ENV de pierna {s} ({hip}/{knee}/{ankle}).")
            return None
        legs.append({"hip": hip, "knee": knee, "ankle": ankle})

    def Wv(n):
        return om.MVector(*cmds.xform(n, q=True, ws=True, t=True))
    thigh = (Wv(legs[0]["knee"]) - Wv(legs[0]["hip"])).length() or 30.0
    leg_r = round(thigh * 0.18, 2)
    hipoff = (Wv(waist) - Wv(legs[0]["hip"])).length()
    for leg in legs:
        leg["radius"] = leg_r

    return build_native_skirt(
        prefix, waist, legs, rings=rings, count=count,
        top_radius=round(hipoff + leg_r, 2),
        bottom_radius=round(hipoff + thigh * 0.5, 2),
        height=round(thigh * 1.1, 2),
        skinning_parent=skinning_parent, make_env=True, waist_env=waist,
    )


# ===========================================================================
# Versión con SUPERFICIE: la colisión drive los CV de una NURBS surface y las
# joints de skinning van SOBRE la superficie (pointOnSurfaceInfo) -> la superficie
# interpola y la deformación sale LIMPIA (da la continuidad de tela).
# ===========================================================================

def _legs_segments(legs):
    segs = []
    for leg in legs:
        a, m, b = _world_t(leg["hip"]), _world_t(leg["knee"]), _world_t(leg["ankle"])
        r = leg.get("radius", 8.0)
        segs.append((a, m, r)); segs.append((m, b, r))
    return segs


def make_leg_surface(name, hip, knee, ankle, thigh_r_plug, calf_r_plug, parent=None):
    """
    Crea una NURBS surface (tubo) que envuelve la pierna: círculos en hip/knee/ankle
    (driveados por los joints, radio = plugs tunables) lofteados. Devuelve la shape.
    """
    def circ(jnt, rad_plug, cname):
        tr, mk = cmds.circle(name=cname, normal=(1, 0, 0), constructionHistory=True)
        _set_or_connect(mk + ".radius", rad_plug)
        if parent:
            tr = cmds.parent(tr, parent)[0]
        pinv = (cmds.listRelatives(tr, parent=True, fullPath=True) or [None])[0]
        mmx = _n("multMatrix", cname + "_MMX")
        cmds.connectAttr(jnt + ".worldMatrix[0]", mmx + ".matrixIn[0]")
        if pinv:
            cmds.connectAttr(pinv + ".worldInverseMatrix[0]", mmx + ".matrixIn[1]")
        cmds.connectAttr(mmx + ".matrixSum", tr + ".offsetParentMatrix")
        for at in ("translate", "rotate"):
            cmds.setAttr(tr + "." + at, 0, 0, 0)
        return tr
    ch = circ(hip, thigh_r_plug, f"{name}_hipCIR")
    ck = circ(knee, thigh_r_plug, f"{name}_kneeCIR")
    ca = circ(ankle, calf_r_plug, f"{name}_ankleCIR")
    surfT = cmds.loft(ch, ck, ca, ch=True, u=True, c=False, ar=False, d=3, ss=1, po=0)[0]
    surfT = cmds.rename(surfT, name)
    if parent:
        surfT = cmds.parent(surfT, parent)[0]
    return cmds.listRelatives(surfT, shapes=True, fullPath=True)[0]


def push_out_surface(name, P, surf_shape, offset):
    """
    Empuja el punto `P` (plug vector) fuera de la NURBS `surf_shape` si está DENTRO:
    closestPointOnSurface -> punto+normal; si P está por detrás de la normal (dentro),
    lo lleva al punto de superficie + normal*offset. Devuelve plug vector resultante.
    """
    cps = _n("closestPointOnSurface", name + "_CPS")
    cmds.connectAttr(surf_shape + ".worldSpace[0]", cps + ".inputSurface")
    cmds.connectAttr(P, cps + ".inPosition")
    # la normal se saca con pointOnSurfaceInfo en el parámetro del punto más cercano
    posi = _n("pointOnSurfaceInfo", name + "_POSI")
    cmds.connectAttr(surf_shape + ".worldSpace[0]", posi + ".inputSurface")
    cmds.connectAttr(cps + ".parameterU", posi + ".parameterU")
    cmds.connectAttr(cps + ".parameterV", posi + ".parameterV")
    Ps = posi + ".position"
    nrm = _n("vectorProduct", name + "_N"); cmds.setAttr(nrm + ".operation", 0); cmds.setAttr(nrm + ".normalizeOutput", 1)
    cmds.connectAttr(posi + ".normal", nrm + ".input1")
    N = nrm + ".output"
    # vec = P - Ps ; side = dot(vec, N)  (<0 = dentro)
    vec = _n("plusMinusAverage", name + "_vec"); cmds.setAttr(vec + ".operation", 2)
    cmds.connectAttr(P, vec + ".input3D[0]"); cmds.connectAttr(Ps, vec + ".input3D[1]")
    side = _n("vectorProduct", name + "_side"); cmds.setAttr(side + ".operation", 1)
    cmds.connectAttr(vec + ".output3D", side + ".input1"); cmds.connectAttr(N, side + ".input2")
    # pushed = Ps + N*offset
    no = _n("multiplyDivide", name + "_No"); cmds.setAttr(no + ".operation", 1)
    cmds.connectAttr(N, no + ".input1")
    for ax in "XYZ":
        _set_or_connect(no + ".input2" + ax, offset)
    pushed = _n("plusMinusAverage", name + "_pushed"); cmds.setAttr(pushed + ".operation", 1)
    cmds.connectAttr(Ps, pushed + ".input3D[0]"); cmds.connectAttr(no + ".output", pushed + ".input3D[1]")
    # si dentro (side<0) -> pushed, si no -> P
    cond = _n("condition", name + "_cond"); cmds.setAttr(cond + ".operation", 4)  # less than
    cmds.connectAttr(side + ".outputX", cond + ".firstTerm"); cmds.setAttr(cond + ".secondTerm", 0)
    cmds.connectAttr(pushed + ".output3D", cond + ".colorIfTrue"); cmds.connectAttr(P, cond + ".colorIfFalse")
    return cond + ".outColor"


def _push_out_surfaces(name, P, surfs, offset, passes=2):
    """Empuja P fuera de todas las `surfs` (lista de shapes), `passes` veces (converge
    cuando empuja entre dos piernas)."""
    for it in range(passes):
        for k, sh in enumerate(surfs):
            P = push_out_surface(f"{name}_p{it}s{k}", P, sh, offset)
    return P


def _push_out_segs(name, P, segs, passes=1):
    """Empuja P fuera de las cápsulas `segs` = [(A,B,radius),...] (fiable para interiores),
    `passes` veces."""
    for it in range(passes):
        for s, (A, B, r) in enumerate(segs):
            P = push_out_segment(f"{name}_p{it}s{s}", P, A, B, r)
    return P


def build_native_skirt_surface(prefix, waist, legs, rings=6, count=16,
                               top_radius=10.0, bottom_radius=22.0, height=40.0,
                               skin_around=20, skin_v=6, thigh_radius=12.0, calf_radius=9.0,
                               hip_offset=10.0,
                               module_parent=None, skinning_parent=None,
                               make_env=True, waist_env=None):
    """
    Falda con colisión via SUPERFICIE (sin plugin):
      colisión -> CV de una curva por anillo -> loft -> NURBS surface -> joints sobre
      la superficie (pointOnSurfaceInfo). La superficie interpola -> deformación limpia.

    El RADIO de colisión (grosor de pierna) es TUNABLE EN VIVO: se crean atributos
    `ThighRadius` y `CalfRadius` en el module_grp -> súbelos hasta que la falda envuelva
    la pierna y deje de atravesar (el mesh de pierna suele ser más grueso que el eje).

    Devuelve (module_grp, surface, skin_grp, joints).
    """
    mod = cmds.createNode("transform", name=f"{prefix}skirtModule_GRP")
    if module_parent and cmds.objExists(module_parent):
        cmds.parent(mod, module_parent)

    # atributos tunables: grosor de pierna (radio de las leg-surfaces) + margen de tela
    cmds.addAttr(mod, longName="ThighRadius", attributeType="float", defaultValue=thigh_radius, minValue=0, keyable=True)
    cmds.addAttr(mod, longName="CalfRadius", attributeType="float", defaultValue=calf_radius, minValue=0, keyable=True)
    cmds.addAttr(mod, longName="SkinOffset", attributeType="float", defaultValue=1.0, minValue=0, keyable=True)
    thigh_r_plug, calf_r_plug, offset_plug = f"{mod}.ThighRadius", f"{mod}.CalfRadius", f"{mod}.SkinOffset"

    # radio efectivo de colisión = radio de pierna + margen de tela (para empujar la falda)
    def _eff(rplug, nm):
        s = _n("plusMinusAverage", nm); cmds.setAttr(s + ".operation", 1)
        cmds.connectAttr(rplug, s + ".input1D[0]"); cmds.connectAttr(offset_plug, s + ".input1D[1]")
        return s + ".output1D"
    thigh_eff, calf_eff = _eff(thigh_r_plug, prefix + "thighEff"), _eff(calf_r_plug, prefix + "calfEff")

    wm = om.MMatrix(cmds.getAttr(waist + ".worldMatrix[0]")); w_inv = wm.inverse()
    wp = cmds.xform(waist, q=True, ws=True, t=True)

    # ---- DOS leg-surfaces (una por pierna): VISUAL del collider (mismo radio) ----
    leg_surfs = []
    for i, leg in enumerate(legs):
        make_leg_surface(f"{prefix}legCollider{i}", leg["hip"], leg["knee"], leg["ankle"],
                         thigh_r_plug, calf_r_plug, parent=mod)
    # ---- colisión por CÁPSULA (eje + radio efectivo): fiable para interiores ----
    segs = []
    for leg in legs:
        a, m, b = _world_t(leg["hip"]), _world_t(leg["knee"]), _world_t(leg["ankle"])
        segs.append((a, m, thigh_eff)); segs.append((m, b, calf_eff))

    # direcciones (horizontal y abajo) en espacio LOCAL de la cintura (constantes)
    down_local = om.MVector(0.0, -1.0, 0.0) * w_inv
    # El radio del cono SIGUE EN VIVO a ThighRadius para envolver SIEMPRE las dos piernas:
    #   radius_live(ring) = hip_offset + ThighRadius * flare(ring)   (flare crece al bajar)
    ring_curves = []
    for ri in range(rings):
        t_down = ri / float(max(1, rings - 1))
        flare = 1.4 + 0.9 * t_down          # margen sobre el tubo + ensanche hacia abajo
        h = height * (ri + 1) / float(rings)
        radius0 = hip_offset + thigh_radius * flare   # estimación para la curva inicial
        pts = [(wp[0] + radius0 * math.cos(2.0 * math.pi * (c % count) / count),
                wp[1] - h,
                wp[2] + radius0 * math.sin(2.0 * math.pi * (c % count) / count)) for c in range(count + 1)]
        crv = cmds.curve(d=3, p=pts, name=f"{prefix}skirtRing{ri:02d}_CRV")
        crv = cmds.parent(crv, mod)[0]
        shp = cmds.listRelatives(crv, shapes=True, fullPath=True)[0]
        # radio vivo del anillo = hip_offset + ThighRadius * flare
        rmul = _n("multiplyDivide", f"{prefix}r{ri:02d}_rmul"); cmds.setAttr(rmul + ".operation", 1)
        cmds.connectAttr(thigh_r_plug, rmul + ".input1X"); cmds.setAttr(rmul + ".input2X", flare)
        radd = _n("plusMinusAverage", f"{prefix}r{ri:02d}_radd"); cmds.setAttr(radd + ".operation", 1)
        cmds.connectAttr(rmul + ".outputX", radd + ".input1D[0]"); cmds.setAttr(radd + ".input1D[1]", hip_offset)
        rlive = radd + ".output1D"
        down_off = (down_local.x * h, down_local.y * h, down_local.z * h)
        for c in range(count + 1):
            th = 2.0 * math.pi * (c % count) / count
            ldir = om.MVector(math.cos(th), 0.0, math.sin(th)) * w_inv   # dir horizontal en local
            # restLocal = ldir * radius_live + down*h
            ds = _n("multiplyDivide", f"{prefix}r{ri:02d}c{c:02d}_ds"); cmds.setAttr(ds + ".operation", 1)
            cmds.setAttr(ds + ".input1", ldir.x, ldir.y, ldir.z, type="double3")
            for ax in "XYZ":
                cmds.connectAttr(rlive, ds + ".input2" + ax)
            rl = _n("plusMinusAverage", f"{prefix}r{ri:02d}c{c:02d}_rl"); cmds.setAttr(rl + ".operation", 1)
            cmds.connectAttr(ds + ".output", rl + ".input3D[0]")
            cmds.setAttr(rl + ".input3D[1]", down_off[0], down_off[1], down_off[2], type="double3")
            # restWorld = restLocal x waist.worldMatrix  (point-matrix)
            pmm = _n("vectorProduct", f"{prefix}r{ri:02d}c{c:02d}_rest"); cmds.setAttr(pmm + ".operation", 4)
            cmds.connectAttr(rl + ".output3D", pmm + ".input1"); cmds.connectAttr(waist + ".worldMatrix[0]", pmm + ".matrix")
            P = _push_out_segs(f"{prefix}r{ri:02d}c{c:02d}", pmm + ".output", segs, passes=2)
            cmds.connectAttr(P + "R", f"{shp}.controlPoints[{c}].xValue", force=True)
            cmds.connectAttr(P + "G", f"{shp}.controlPoints[{c}].yValue", force=True)
            cmds.connectAttr(P + "B", f"{shp}.controlPoints[{c}].zValue", force=True)
        ring_curves.append(crv)

    # ---- loft -> superficie ----
    surfT = cmds.loft(*ring_curves, ch=True, u=True, c=False, ar=False, d=3, ss=1, rn=False, po=0)[0]
    surfT = cmds.rename(surfT, f"{prefix}skirt_surface")
    cmds.parent(surfT, mod)
    surfShape = cmds.listRelatives(surfT, shapes=True, fullPath=True)[0]

    # ---- joints sobre la superficie (pointOnSurfaceInfo) ----
    skin_grp = cmds.createNode("transform", name=f"{prefix}skirtSkinning_GRP")
    if skinning_parent and cmds.objExists(skinning_parent):
        cmds.parent(skin_grp, skinning_parent)
    minU, maxU = cmds.getAttr(surfShape + ".minValueU"), cmds.getAttr(surfShape + ".maxValueU")
    minV, maxV = cmds.getAttr(surfShape + ".minValueV"), cmds.getAttr(surfShape + ".maxValueV")

    joints = []
    for iu in range(skin_around):
        u = minU + (maxU - minU) * (iu / float(skin_around))         # alrededor [0,1)
        for iv in range(skin_v):
            v = minV + (maxV - minV) * (iv / float(max(1, skin_v - 1)))  # abajo [0,1]
            posi = _n("pointOnSurfaceInfo", f"{prefix}skin{iu:02d}_{iv:02d}_posi")
            cmds.connectAttr(surfShape + ".worldSpace[0]", posi + ".inputSurface")
            cmds.setAttr(posi + ".parameterU", u); cmds.setAttr(posi + ".parameterV", v)
            # base suave = posición sobre la superficie; + EMPUJE FINAL fuera de las
            # leg-surfaces (2 pasadas) -> ningún joint penetra nunca.
            P = _push_out_segs(f"{prefix}skin{iu:02d}_{iv:02d}", posi + ".position", segs, passes=2)
            jnt = _drive_joint_world(f"{prefix}skin{iu:02d}_{iv:02d}_JNT", skin_grp, P)
            joints.append(jnt)

    # ---- _ENV (export) negando la cintura ----
    if make_env and waist_env and cmds.objExists(waist_env):
        for jnt in joints:
            env_name = jnt.split("|")[-1].replace("_JNT", "_ENV")
            env = cmds.createNode("joint", name=env_name, parent=waist_env)
            inv = cmds.listConnections(f"{env}.inverseScale", destination=False, source=True, plugs=True)
            if inv:
                cmds.disconnectAttr(inv[0], f"{env}.inverseScale")
            mmx = _n("multMatrix", env_name + "Env_MMX")
            cmds.connectAttr(jnt + ".worldMatrix[0]", mmx + ".matrixIn[0]")
            cmds.connectAttr(waist_env + ".worldInverseMatrix[0]", mmx + ".matrixIn[1]")
            cmds.connectAttr(mmx + ".matrixSum", env + ".offsetParentMatrix")
            cmds.setAttr(env + ".jointOrient", 0, 0, 0)

    return mod, surfT, skin_grp, joints


def build_native_skirt_surface_from_rig(prefix="", rings=6, count=16, skin_around=20, skin_v=6,
                                        module_parent=None, skinning_parent="skel_GRP", names=None):
    """Como build_native_skirt_from_rig pero con SUPERFICIE intermedia (deformación limpia)."""
    tpl = dict(RIG_ENV_LEGS)
    if names:
        tpl.update(names)
    waist = tpl["waist"]
    if not cmds.objExists(waist):
        cmds.warning(f"native skirt surface: no existe la cintura '{waist}'."); return None
    legs = []
    for s in ("L", "R"):
        hip, knee, ankle = (tpl["hip"].format(side=s), tpl["knee"].format(side=s), tpl["ankle"].format(side=s))
        if not all(cmds.objExists(x) for x in (hip, knee, ankle)):
            cmds.warning(f"native skirt surface: faltan _ENV pierna {s}."); return None
        legs.append({"hip": hip, "knee": knee, "ankle": ankle})

    def Wv(n):
        return om.MVector(*cmds.xform(n, q=True, ws=True, t=True))
    thigh = (Wv(legs[0]["knee"]) - Wv(legs[0]["hip"])).length() or 30.0
    hipoff = (Wv(waist) - Wv(legs[0]["hip"])).length()
    # radios por defecto generosos (el mesh de pierna es más grueso que el eje); tunables en vivo.
    thigh_radius = round(thigh * 0.30, 2)
    calf_radius = round(thigh * 0.24, 2)

    return build_native_skirt_surface(
        prefix, waist, legs, rings=rings, count=count, skin_around=skin_around, skin_v=skin_v,
        thigh_radius=thigh_radius, calf_radius=calf_radius, hip_offset=round(hipoff, 2),
        height=round(thigh * 1.1, 2),
        module_parent=module_parent, skinning_parent=skinning_parent,
        make_env=True, waist_env=waist,
    )


# ===========================================================================
# Proxy skin de prueba: vestido -> joints de la falda por CLOSEST JOINT, para que
# la tela SIGA a los joints empujados (si no, atraviesa aunque los joints no penetren).
# ===========================================================================

def proxy_skin_to_skirt(mesh, joints=None, extra=("C_localHip_ENV",),
                        max_influences=3, prefix=""):
    """
    Binde `mesh` (el vestido) a los joints _ENV de la falda por CLOSEST JOINT
    (bindMethod=0), para un test de skinning: cada vértice sigue a su joint más cercano
    (el empujado por la colisión) -> la tela no se mete en la pierna.

    Si `joints` es None, busca los `{prefix}skin*_ENV` de la falda. `extra` añade la
    cintura para la parte alta. `max_influences` bajo = más rígido (menos arrastre).
    Devuelve el skinCluster.
    """
    if joints is None:
        joints = cmds.ls(f"{prefix}skin*_ENV", type="joint") or cmds.ls("*skin*_ENV", type="joint") or []
    infs = list(joints) + [e for e in extra if cmds.objExists(e)]
    if not infs:
        cmds.warning("proxy_skin_to_skirt: no se encontraron joints de falda _ENV.")
        return None
    if not cmds.objExists(mesh):
        cmds.warning(f"proxy_skin_to_skirt: no existe el mesh '{mesh}'.")
        return None
    # quitar skin previo en el mesh (para el test)
    shapes = cmds.listRelatives(mesh, shapes=True, ni=True, fullPath=True) or [mesh]
    for sh in shapes:
        for sc in (cmds.listConnections(sh, type="skinCluster") or []):
            try:
                cmds.skinCluster(sc, edit=True, unbind=True)
            except Exception:
                pass
    skc = cmds.skinCluster(infs, mesh, toSelectedBones=True, bindMethod=0, skinMethod=0,
                           normalizeWeights=1, maximumInfluences=max_influences,
                           obeyMaxInfluences=True, dropoffRate=4.0,
                           name=f"{prefix}skirtProxy_SKC")[0]
    cmds.inViewMessage(amg=f"proxy skin: <hl>{mesh}</hl> -> {len(infs)} joints (closest).",
                       pos="midCenter", fade=True)
    return skc
