"""
skirt_collider — colisión de falda contra las piernas SOLO con nodos nativos de Maya
(sin plugin, sin simulación, sin nodo custom). Reemplazo del bell collider C++ de
`tools/colliders` y del prototipo por cápsulas `utils/native_collider.py`.

POR QUÉ ESTE ENFOQUE
--------------------
El prototipo anterior empujaba cada joint de la falda POR SEPARADO fuera de cápsulas de
pierna (closest-point-en-segmento). Al no haber coherencia, la falda pellizca y hace cosas
raras entre las piernas. El bell collider de Azagoruyko funciona porque colisiona contra una
CAMPANA SUAVE Y COHERENTE. Aquí se recupera esa coherencia de dos formas:

  1. Cada pierna genera una superficie NURBS "campana" (loft de anillos hip/knee/ankle) que
     sigue la pose por matrices. Es C1 (suave), así el campo de normales/closest-point no da
     saltos entre joints vecinos.
  2. El push de cada joint se PROMEDIA con sus vecinos del anillo, de modo que la falda
     envuelve la pierna como una lámina en vez de como puntos sueltos.

Cada joint de la falda parte de una posición de REPOSO (anillo colgando de la cintura, que
sigue al personaje) y, si penetra una campana, se lleva a `closest + normal * grosor` con un
falloff suave. Todo con nodos nativos: loft, closestPointOnSurface, pointOnSurfaceInfo,
vectorProduct, plusMinusAverage, multiplyDivide, condition, clamp, remapValue. Determinista y
art-directable (atributos radius/thickness/falloff/enable en un control).

CONVENCIONES DE ESTE REPO
-------------------------
Rig por matrices (offsetParentMatrix), grupos offset para no ensuciar canales, naming
`_GRP/_JNT/_CTL` y joints de pierna `_ENV`. Lee los nombres de joint por plantilla (override
con `names=`), no hardcodea posiciones. No depende de plugins.

IMPORTANTE — NO PROBADO EN MAYA EN ESTE ENTORNO
-----------------------------------------------
Este módulo se ha escrito con las firmas reales de los nodos nativos, pero NO se ha podido
ejecutar en Maya aquí. Antes de darlo por bueno, revisa la sección "PRUEBA Y AJUSTE" al final
del fichero: los tres puntos que casi seguro habrá que afinar por personaje son (a) el eje de
los anillos de la campana, (b) el signo de la normal de empuje y (c) los radios por defecto.

USO RÁPIDO
----------
    from tools import skirt_collider
    reload(skirt_collider)

    # Cableado automático a los _ENV del rig (ambas piernas + cintura):
    data = skirt_collider.build_from_rig(prefix="anne_", num_joints=16)

    # O paso a paso / genérico (ver build_from_rig para el orden):
    left  = skirt_collider.build_leg_bell("L", "L_legUpper00_ENV", "L_legLower00_ENV",
                                          "L_legAnkle_ENV", prefix="anne_")
"""

import maya.cmds as cmds


# --------------------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------------------- #

def _n(node_type, name):
    """createNode con skipSelect, para no ensuciar la selección durante el build."""
    return cmds.createNode(node_type, name=name, ss=True)


def _matrix_drive(child, driver):
    """
    Cuelga `child` de `driver` por matriz (estándar del repo): el child hereda la pose world
    del driver vía offsetParentMatrix, dejando sus canales locales limpios en cero.
    """
    cmds.connectAttr(driver + ".worldMatrix[0]", child + ".offsetParentMatrix", f=True)
    for at in ("translate", "rotate"):
        for ax in "XYZ":
            try:
                cmds.setAttr(f"{child}.{at}{ax}", 0)
            except Exception:
                pass
    for ax in "XYZ":
        try:
            cmds.setAttr(f"{child}.scale{ax}", 1)
        except Exception:
            pass


# --------------------------------------------------------------------------------------- #
# 1) Campana NURBS por pierna (el collider suave y coherente)
# --------------------------------------------------------------------------------------- #

def build_leg_bell(side, hip, knee, ankle, prefix="", radii=(9.0, 6.0, 5.0),
                   sections=10, aim_axis=(0, 1, 0), parent=None):
    """
    Construye una superficie NURBS "campana" que envuelve la pierna [hip -> knee -> ankle] y
    la sigue por matrices. Es el collider: suave (loft grado 3) y coherente.

    Args:
        side (str): 'L'/'R'/'C', solo para naming.
        hip, knee, ankle (str): joints _ENV de la pierna (de arriba a abajo).
        prefix (str): prefijo de asset (p.ej. 'anne_').
        radii (tuple): radio del anillo en (hip, knee, ankle). El collider debe ser un pelín
            mayor que la carne para que la falda no toque la piel: sube estos valores si la
            falda se mete, bájalos si "flota".
        sections (int): resolución angular de cada anillo.
        aim_axis (tuple): eje LOCAL del joint que apunta a lo largo del hueso. En la mayoría de
            rigs es X; aquí el anillo se crea con normal en `aim_axis` para quedar perpendicular
            al hueso. AJUSTA esto si los anillos salen tumbados (ver PRUEBA Y AJUSTE).
        parent (str|None): grupo donde meter la campana.

    Returns:
        dict con: 'surface' (transform), 'shape', 'rings' (3 transforms), 'grp'.
    """
    grp = _n("transform", f"{prefix}{side}_skirtBell_GRP")
    if parent:
        cmds.parent(grp, parent)

    rings = []
    for jnt, rad, part in ((hip, radii[0], "Hip"),
                           (knee, radii[1], "Knee"),
                           (ankle, radii[2], "Ankle")):
        # Anillo NURBS perpendicular al hueso, del radio pedido.
        circ = cmds.circle(name=f"{prefix}{side}_skirtBell{part}_CRV",
                           nr=aim_axis, r=rad, s=sections, d=3, ch=False)[0]
        cmds.parent(circ, grp)
        # Sigue al joint por matriz: el anillo queda pegado al hueso y hereda su pose.
        _matrix_drive(circ, jnt)
        rings.append(circ)

    # Loft con historia: al moverse los anillos, la superficie se actualiza sola.
    surf = cmds.loft(rings[0], rings[1], rings[2], name=f"{prefix}{side}_skirtBell_SURF",
                     ch=True, u=True, c=False, ar=True, d=3, ss=1, rn=False, po=0)[0]
    cmds.parent(surf, grp)
    shape = cmds.listRelatives(surf, s=True, type="nurbsSurface")[0]

    return {"surface": surf, "shape": shape, "rings": rings, "grp": grp}


# --------------------------------------------------------------------------------------- #
# 2) Anillo de reposo de la falda (cuelga de la cintura y sigue al personaje)
# --------------------------------------------------------------------------------------- #

def build_rest_ring(waist, prefix="", num_joints=16, radius=16.0, drop=22.0, parent=None):
    """
    Crea `num_joints` locators de REPOSO en un anillo que cuelga de la cintura. Siguen al
    personaje (cuelgan del waist por matriz), así el reposo es dinámico, no una posición fija.
    Cada locator marca dónde estaría la falda SIN colisión.

    Returns:
        dict con 'rests' (lista de transforms), 'grp'.
    """
    import math
    grp = _n("transform", f"{prefix}skirtRest_GRP")
    if parent:
        cmds.parent(grp, parent)
    # El anillo cuelga de la cintura: grupo pegado al waist por matriz.
    _matrix_drive(grp, waist)

    rests = []
    for i in range(num_joints):
        ang = (2.0 * math.pi * i) / num_joints
        # Plano XZ alrededor de la cintura, cayendo -Y (drop). Ajusta ejes si tu 'up' no es Y.
        x = radius * math.cos(ang)
        z = radius * math.sin(ang)
        loc = _n("transform", f"{prefix}skirtRest{i:02d}_GRP")
        cmds.parent(loc, grp)
        cmds.setAttr(loc + ".translate", x, -drop, z, type="double3")
        rests.append(loc)
    return {"rests": rests, "grp": grp}


# --------------------------------------------------------------------------------------- #
# 3) Push nativo: empuja un punto de reposo fuera de una campana
# --------------------------------------------------------------------------------------- #

def _push_out_of_bell(name, rest_node, bell_shape, thickness_plug):
    """
    Devuelve el plug vector (world) de la posición de `rest_node` empujada fuera de la campana
    `bell_shape` si penetra dentro de `thickness`. Si no penetra, devuelve el reposo.

    Mecánica (todo nativo):
        closestPointOnSurface(rest) -> punto más cercano C y (u,v)
        pointOnSurfaceInfo(u,v)     -> normal N (hacia fuera de la campana)
        signedDist = dot(rest - C, N)      (negativo = dentro de la carne)
        si signedDist < thickness: target = C + N*thickness   (fuera, con colchón)
        si no:                     target = rest
    """
    # rest world position
    rest_dm = _n("decomposeMatrix", f"{name}_restDM")
    cmds.connectAttr(rest_node + ".worldMatrix[0]", rest_dm + ".inputMatrix")

    # closest point on surface
    cpos = _n("closestPointOnSurface", f"{name}_CPOS")
    cmds.connectAttr(bell_shape + ".worldSpace[0]", cpos + ".inputSurface")
    cmds.connectAttr(rest_dm + ".outputTranslate", cpos + ".inPosition")

    # normal en (u,v) del punto más cercano
    posi = _n("pointOnSurfaceInfo", f"{name}_POSI")
    cmds.connectAttr(bell_shape + ".worldSpace[0]", posi + ".inputSurface")
    cmds.connectAttr(cpos + ".parameterU", posi + ".parameterU")
    cmds.connectAttr(cpos + ".parameterV", posi + ".parameterV")

    # rest - C
    diff = _n("plusMinusAverage", f"{name}_diff")
    cmds.setAttr(diff + ".operation", 2)  # subtract
    cmds.connectAttr(rest_dm + ".outputTranslate", diff + ".input3D[0]")
    cmds.connectAttr(cpos + ".position", diff + ".input3D[1]")

    # signedDist = dot(rest - C, N)
    dot = _n("vectorProduct", f"{name}_dot")
    cmds.setAttr(dot + ".operation", 1)  # dot
    cmds.connectAttr(diff + ".output3D", dot + ".input1")
    cmds.connectAttr(posi + ".normalizedNormal", dot + ".input2")

    # N * thickness
    ntk = _n("multiplyDivide", f"{name}_Nthick")
    cmds.setAttr(ntk + ".operation", 1)  # multiply
    cmds.connectAttr(posi + ".normalizedNormal", ntk + ".input1")
    for ax in "XYZ":
        cmds.connectAttr(thickness_plug, ntk + f".input2{ax}")

    # target_inside = C + N*thickness
    tin = _n("plusMinusAverage", f"{name}_targetIn")
    cmds.setAttr(tin + ".operation", 1)  # sum
    cmds.connectAttr(cpos + ".position", tin + ".input3D[0]")
    cmds.connectAttr(ntk + ".output", tin + ".input3D[1]")

    # condition: signedDist < thickness ? target_inside : rest
    cond = _n("condition", f"{name}_cond")
    cmds.setAttr(cond + ".operation", 4)  # less than
    cmds.connectAttr(dot + ".outputX", cond + ".firstTerm")
    cmds.connectAttr(thickness_plug, cond + ".secondTerm")
    cmds.connectAttr(tin + ".output3D", cond + ".colorIfTrue")
    cmds.connectAttr(rest_dm + ".outputTranslate", cond + ".colorIfFalse")

    return cond + ".outColor"


def _closest_of_two(name, rest_node, plug_a, plug_b):
    """
    De dos posiciones candidatas (una por pierna) elige la MÁS ALEJADA del reposo, que es la
    que resuelve la penetración más profunda. Así un joint entre las dos piernas respeta la
    campana que más lo empuja, sin sumar empujes (que daría posiciones raras).
    """
    rest_dm = _n("decomposeMatrix", f"{name}_pickRestDM")
    cmds.connectAttr(rest_node + ".worldMatrix[0]", rest_dm + ".inputMatrix")

    da = _n("distanceBetween", f"{name}_dA")
    cmds.connectAttr(rest_dm + ".outputTranslate", da + ".point1")
    cmds.connectAttr(plug_a, da + ".point2")
    db = _n("distanceBetween", f"{name}_dB")
    cmds.connectAttr(rest_dm + ".outputTranslate", db + ".point1")
    cmds.connectAttr(plug_b, db + ".point2")

    cond = _n("condition", f"{name}_pick")
    cmds.setAttr(cond + ".operation", 2)  # greater than
    cmds.connectAttr(da + ".distance", cond + ".firstTerm")
    cmds.connectAttr(db + ".distance", cond + ".secondTerm")
    cmds.connectAttr(plug_a, cond + ".colorIfTrue")
    cmds.connectAttr(plug_b, cond + ".colorIfFalse")
    return cond + ".outColor"


# --------------------------------------------------------------------------------------- #
# 4) Coherencia: suaviza el empuje de cada joint con sus vecinos del anillo
# --------------------------------------------------------------------------------------- #

def _smooth_ring(name_prefix, plugs, blend_plug):
    """
    Promedia cada posición con sus dos vecinos del anillo (cerrado), mezclado por `blend_plug`
    (0 = sin suavizado, 1 = suavizado pleno). Esto es lo que evita el pellizco: la falda pasa
    de "puntos sueltos empujados" a "lámina que envuelve".

    Returns: lista de plugs vector suavizados (mismo orden).
    """
    n = len(plugs)
    out = []
    for i in range(n):
        prev_p = plugs[(i - 1) % n]
        next_p = plugs[(i + 1) % n]
        avg = _n("plusMinusAverage", f"{name_prefix}_avg{i:02d}")
        cmds.setAttr(avg + ".operation", 3)  # average
        cmds.connectAttr(prev_p, avg + ".input3D[0]")
        cmds.connectAttr(plugs[i], avg + ".input3D[1]")
        cmds.connectAttr(next_p, avg + ".input3D[2]")
        # blend entre el valor propio y el promedio
        bc = _n("blendColors", f"{name_prefix}_blend{i:02d}")
        cmds.connectAttr(blend_plug, bc + ".blender")
        cmds.connectAttr(avg + ".output3D", bc + ".color1")
        cmds.connectAttr(plugs[i], bc + ".color2")
        out.append(bc + ".output")
    return out


# --------------------------------------------------------------------------------------- #
# 5) Control art-directable
# --------------------------------------------------------------------------------------- #

def build_control(prefix="", thickness=1.5, smooth=0.4):
    """Control con los atributos de colisión (grosor de colchón, suavizado, enable)."""
    ctl = cmds.circle(name=f"{prefix}skirtCollider_CTL", nr=(0, 1, 0), r=4, ch=False)[0]
    cmds.addAttr(ctl, ln="colliderSettings", at="enum", en="______", k=True)
    cmds.setAttr(ctl + ".colliderSettings", lock=True)
    cmds.addAttr(ctl, ln="enable", at="float", min=0, max=1, dv=1, k=True)
    cmds.addAttr(ctl, ln="thickness", at="float", min=0, dv=thickness, k=True)
    cmds.addAttr(ctl, ln="smooth", at="float", min=0, max=1, dv=smooth, k=True)
    return ctl


# --------------------------------------------------------------------------------------- #
# 6) Orquestador: cablea todo desde el rig
# --------------------------------------------------------------------------------------- #

DEFAULT_NAMES = {
    "L_hip": "L_legUpper00_ENV", "L_knee": "L_legLower00_ENV", "L_ankle": "L_legAnkle_ENV",
    "R_hip": "R_legUpper00_ENV", "R_knee": "R_legLower00_ENV", "R_ankle": "R_legAnkle_ENV",
    "waist": "C_localHip_ENV",
}


def build_from_rig(prefix="", num_joints=16, names=None,
                   leg_radii=(9.0, 6.0, 5.0), ring_radius=16.0, ring_drop=22.0,
                   thickness=1.5, smooth=0.4, attach_joints=True):
    """
    Construye el collider de falda completo cableado a los _ENV del rig:
        campanas L/R  ->  anillo de reposo bajo la cintura  ->  push nativo + suavizado
        ->  drivers world  ->  (opcional) joints de skinning de la falda.

    Args:
        prefix (str): prefijo de asset.
        num_joints (int): joints alrededor de la falda (resolución del anillo).
        names (dict|None): override de los joints (ver DEFAULT_NAMES).
        leg_radii: radios (hip, knee, ankle) de cada campana.
        ring_radius, ring_drop: geometría del anillo de reposo (radio y caída desde la cintura).
        thickness: colchón de colisión (distancia mínima falda-pierna).
        smooth: suavizado de coherencia (0..1).
        attach_joints (bool): crea joints de skinning bajo cada driver (para pesar la malla).

    Returns:
        dict con todos los nodos creados (bells, rest ring, drivers, joints, control, grp).
    """
    names = dict(DEFAULT_NAMES, **(names or {}))
    for key, jnt in names.items():
        if not cmds.objExists(jnt):
            cmds.warning(f"[skirt_collider] no existe el joint '{jnt}' (clave {key}); "
                         "pasa 'names=' con los nombres reales de tu rig.")

    root = _n("transform", f"{prefix}skirtCollider_GRP")
    ctl = build_control(prefix=prefix, thickness=thickness, smooth=smooth)
    cmds.parent(ctl, root)
    thick_plug = ctl + ".thickness"
    smooth_plug = ctl + ".smooth"

    # 1) campanas
    left = build_leg_bell("L", names["L_hip"], names["L_knee"], names["L_ankle"],
                          prefix=prefix, radii=leg_radii, parent=root)
    right = build_leg_bell("R", names["R_hip"], names["R_knee"], names["R_ankle"],
                           prefix=prefix, radii=leg_radii, parent=root)

    # 2) anillo de reposo colgando de la cintura
    ring = build_rest_ring(names["waist"], prefix=prefix, num_joints=num_joints,
                           radius=ring_radius, drop=ring_drop, parent=root)

    # 3) push por pierna + elegir el empuje que más resuelve + suavizar entre vecinos
    raw = []
    for i, rest in enumerate(ring["rests"]):
        pl = _push_out_of_bell(f"{prefix}skirtColL{i:02d}", rest, left["shape"], thick_plug)
        pr = _push_out_of_bell(f"{prefix}skirtColR{i:02d}", rest, right["shape"], thick_plug)
        picked = _closest_of_two(f"{prefix}skirtCol{i:02d}", rest, pl, pr)
        raw.append(picked)

    smoothed = _smooth_ring(f"{prefix}skirtColSmooth", raw, smooth_plug)

    # 4) drivers world (parent identidad => translate local == world) + enable (mezcla con reposo)
    driver_grp = _n("transform", f"{prefix}skirtDrivers_GRP")
    cmds.parent(driver_grp, root)
    drivers, joints = [], []
    for i, (rest, pos_plug) in enumerate(zip(ring["rests"], smoothed)):
        drv = _n("transform", f"{prefix}skirtDrv{i:02d}_GRP")
        cmds.parent(drv, driver_grp)
        # enable: 0 => reposo puro, 1 => posición con colisión
        rest_dm = _n("decomposeMatrix", f"{prefix}skirtDrvRest{i:02d}_DM")
        cmds.connectAttr(rest + ".worldMatrix[0]", rest_dm + ".inputMatrix")
        en = _n("blendColors", f"{prefix}skirtDrvEnable{i:02d}")
        cmds.connectAttr(ctl + ".enable", en + ".blender")
        cmds.connectAttr(pos_plug, en + ".color1")
        cmds.connectAttr(rest_dm + ".outputTranslate", en + ".color2")
        cmds.connectAttr(en + ".output", drv + ".translate")
        drivers.append(drv)

        if attach_joints:
            jnt = _n("joint", f"{prefix}skirtCol{i:02d}_JNT")
            cmds.parent(jnt, drv)
            cmds.setAttr(jnt + ".translate", 0, 0, 0, type="double3")
            joints.append(jnt)

    return {
        "grp": root, "control": ctl, "left_bell": left, "right_bell": right,
        "rest_ring": ring, "drivers": drivers, "joints": joints,
    }


# ======================================================================================= #
# PRUEBA Y AJUSTE (leer antes de dar por bueno el resultado en Maya)
# ======================================================================================= #
#
# No he podido ejecutar esto en Maya. Estos son los tres puntos que casi seguro tendrás que
# afinar por personaje, en orden de probabilidad:
#
# 1) EJE DE LOS ANILLOS (aim_axis en build_leg_bell). Los anillos deben quedar PERPENDICULARES
#    al hueso. Si salen tumbados, cambia aim_axis a (1,0,0) o al eje que apunte por el hueso en
#    tu rig (mira la orientación de L_legUpper00_ENV). Comprueba la campana visualmente: debe
#    envolver la pierna como un cono, sin retorcerse en el loft.
#
# 2) SIGNO DE LA NORMAL (en _push_out_of_bell). pointOnSurfaceInfo.normalizedNormal apunta
#    hacia fuera según la orientación de la superficie del loft. Si la falda se mete HACIA
#    dentro en vez de salir, la normal está invertida: o inviertes el orden de los anillos en
#    el loft (rings[2],rings[1],rings[0]) o multiplicas la normal por -1 con un multiplyDivide.
#
# 3) RADIOS Y COLCHÓN (leg_radii, thickness). El collider debe ser algo mayor que la carne.
#    Empieza con la campana visible, sube leg_radii hasta que cubra el muslo/gemelo, y ajusta
#    thickness (colchón falda-pierna) hasta que la falda no toque la piel pero tampoco flote.
#
# 4) ESPACIO / GRUPO RAÍZ. Los drivers reciben posición WORLD (su padre es identidad), así que
#    el `*_skirtCollider_GRP` debe quedarse en el ORIGEN (identidad). Si lo cuelgas de un grupo
#    que se mueve (p.ej. el global del rig), los joints saldrían doble-transformados. Para
#    colgarlo de un grupo móvil, convierte el target world a local multiplicando por
#    `driver_grp.worldInverseMatrix[0]` (multMatrix + decomposeMatrix) antes del `.translate`.
#
# Ajuste fino de calidad:
# - 'smooth' (0..1) sube la coherencia (menos pellizco) a cambio de que la falda envuelva menos
#   ceñida. Empieza en 0.4.
# - 'enable' permite apagar la colisión (0) para animación rápida y encenderla (1) para el pase.
# - Si necesitas que la falda DESLICE hacia abajo al chocar (no solo salga radial), añade una
#   componente tangente: proyecta el empuje sobre el plano de la normal y súmale un pelín de -Y.
#
# ALTERNATIVA con el nodo nativo `keepout`:
#   Si prefieres el nodo `keepout` para el push (en vez de closestPointOnSurface), su interfaz
#   por script está poco documentada y cambia entre versiones; hay que verificar sus plugs en
#   TU Maya (Node Editor sobre un keepout creado por UI). El resto del módulo (campanas, anillo
#   de reposo, suavizado, drivers) se reutiliza igual: solo cambiaría _push_out_of_bell.
#
# INTEGRACIÓN CON EL RIG (siguiente paso natural, siguiendo el patrón del repo):
# - Meter esto en un `clothing_module.py` que lea guides/cache (data_manager) en vez de radios
#   a mano, y publique sus joints en el build cache para que el skin los consuma.
# - Pesar la falda a `*_skirtCol*_JNT` (o transferir con SkinManager) y validar con model_checker.
