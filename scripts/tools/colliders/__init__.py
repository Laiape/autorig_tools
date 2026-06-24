"""
colliders — bell / skirt collider deformers para Maya (SIN UI).

Fork de funcionalidad de https://github.com/azagoruyko/colliders (Apache 2.0,
Sergey Azagoruyko). Se ha quitado toda la UI; solo quedan las funciones que crean
y cablean los nodos. Los nodos de colisión (`bellCollider`, `skirtBellCollider`,
`planeCollider`) están en C++ (plugin compilado en plugins/<version>/colliders.mll);
`load_plugin()` lo carga automáticamente según la versión de Maya.

Uso (cuando hay una "falta"/interpenetración, p.ej. en anne):
    from tools.colliders import load_plugin, createBellCollider, createSkirtBellCollider
    load_plugin()
    node, bell, rings, curve = createBellCollider(numRings=1, prefix="anne_")

Para recompilar el plugin (p.ej. Maya 2026 si el .mll de 2025 no carga), usar
sources/ + CMakeLists.txt (ver UPSTREAM_README.md).
"""

import os
import math
import maya.cmds as cmds

BELL_NODE_TYPE = "bellCollider"
SKIRT_NODE_TYPE = "skirtBellCollider"

_PLUGIN_DIR = os.path.join(os.path.dirname(__file__), "plugins")
_PLUGIN_LOADED = False


# ---------------------------------------------------------------------------
# Carga del plugin C++ (según versión de Maya, con fallback)
# ---------------------------------------------------------------------------

def load_plugin(force=False):
    """
    Carga el plugin `colliders` (.mll) que registra los nodos de colisión.
    Busca plugins/<versionMaya>/colliders.mll; si no existe para esta versión,
    prueba las disponibles (la más alta primero) como fallback.

    Returns:
        bool: True si el plugin queda cargado.
    """
    global _PLUGIN_LOADED
    if _PLUGIN_LOADED and not force:
        return True

    # ¿ya cargado?
    try:
        if cmds.pluginInfo("colliders", query=True, loaded=True):
            _PLUGIN_LOADED = True
            return True
    except Exception:
        pass

    if not os.path.isdir(_PLUGIN_DIR):
        cmds.warning(f"colliders: no existe el directorio de plugins '{_PLUGIN_DIR}'.")
        return False

    ver = str(cmds.about(version=True)).split()[0].split(".")[0]
    candidates = []
    exact = os.path.join(_PLUGIN_DIR, ver, "colliders.mll")
    if os.path.exists(exact):
        candidates.append(exact)
    # fallback: el resto de versiones disponibles, de mayor a menor
    avail = sorted((d for d in os.listdir(_PLUGIN_DIR) if d.isdigit()), key=int, reverse=True)
    for d in avail:
        p = os.path.join(_PLUGIN_DIR, d, "colliders.mll")
        if os.path.exists(p) and p not in candidates:
            candidates.append(p)

    for p in candidates:
        try:
            cmds.loadPlugin(p, quiet=True)
            _PLUGIN_LOADED = True
            if os.path.dirname(p) != os.path.dirname(exact):
                cmds.warning(f"colliders: usando plugin de fallback '{os.path.basename(os.path.dirname(p))}' "
                             f"(no hay build para Maya {ver}; compila desde sources/ si da problemas).")
            return True
        except Exception:
            continue

    cmds.warning(f"colliders: no se pudo cargar el plugin para Maya {ver}. "
                 f"Compílalo desde sources/ (CMake) y mete el .mll en plugins/{ver}/.")
    return False


def _ensure_plugin():
    if not load_plugin():
        raise RuntimeError("colliders: el plugin C++ no está cargado (load_plugin() falló).")


# ---------------------------------------------------------------------------
# Funcionalidad (sin UI) — de azagoruyko/colliders
# ---------------------------------------------------------------------------

def createBellCollider(numRings=1, prefix=""):
    """
    Auto-create a bell locator + numRings ring locators, wire them
    into a new bellCollider node. All parameters use node defaults.
    """
    _ensure_plugin()
    bellLoc = cmds.spaceLocator(name=f"{prefix}skirt_bell_locator")[0]

    ringLocs = []
    for i in range(numRings):
        loc = cmds.spaceLocator(name=f"{prefix}skirt_ring_locator{i + 1}")[0]
        cmds.setAttr(loc + ".s", 0.4, 1.5, 0.4)
        ringLocs.append(loc)

    node = cmds.createNode(BELL_NODE_TYPE, name=f"{prefix}bellCollider")
    nodeXform = cmds.listRelatives(node, parent=True, type="transform")[0]
    cmds.rename(nodeXform, f"{prefix}bellCollider_transform")
    cmds.connectAttr(f"{bellLoc}.worldMatrix[0]", f"{node}.bellMatrix", force=True)
    for idx, rl in enumerate(ringLocs):
        cmds.connectAttr(f"{rl}.worldMatrix[0]", f"{node}.ringMatrix[{idx}]", force=True)

    # Lock t/r/s on the bellCollider's parent transform
    nodeXform = cmds.listRelatives(node, parent=True)[0]
    for attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
        cmds.setAttr(f"{nodeXform}.{attr}", lock=True)

    # Create a curve and connect outputCurve so it's visible in the viewport
    curveXform = cmds.createNode("transform", name=f"{prefix}bellCurve")
    curveShape = cmds.createNode("nurbsCurve", name=f"{prefix}bellCurveShape", parent=curveXform)
    cmds.connectAttr(f"{node}.outputCurve", f"{curveShape}.create", force=True)

    cmds.select(node)
    return node, bellLoc, ringLocs, curveXform


def _findAxis(startObj, endObj):
    if not startObj or not endObj:
        return 1
    pwm = cmds.xform(startObj, query=True, worldSpace=True, matrix=True)
    p1 = cmds.xform(startObj, query=True, worldSpace=True, translation=True)
    p2 = cmds.xform(endObj, query=True, worldSpace=True, translation=True)

    vx = p2[0] - p1[0]
    vy = p2[1] - p1[1]
    vz = p2[2] - p1[2]
    l = math.sqrt(vx * vx + vy * vy + vz * vz)
    if l < 1e-5:
        return 1
    vx /= l
    vy /= l
    vz /= l

    px = (pwm[0], pwm[1], pwm[2])
    py = (pwm[4], pwm[5], pwm[6])
    pz = (pwm[8], pwm[9], pwm[10])

    dx = vx * px[0] + vy * px[1] + vz * px[2]
    dy = vx * py[0] + vy * py[1] + vz * py[2]
    dz = vx * pz[0] + vy * pz[1] + vz * pz[2]

    axes = [(0, dx), (1, dy), (2, dz), (3, -dx), (4, -dy), (5, -dz)]
    axes.sort(key=lambda x: x[1], reverse=True)
    return axes[0][0]


def createSkirtBellCollider(
    prefix="",
    leftHipObj=None,
    leftKneeObj=None,
    leftHeelObj=None,
    rightHipObj=None,
    rightKneeObj=None,
    rightHeelObj=None,
    waistObj=None,
    skirtType=1,
):
    """Create a SkirtBellCollider. Bell locator is placed at the midpoint
    between the two hip objects (world space)."""
    _ensure_plugin()

    lp = cmds.xform(leftHipObj, query=True, worldSpace=True, translation=True)
    rp = cmds.xform(rightHipObj, query=True, worldSpace=True, translation=True)
    mid = [(lp[i] + rp[i]) * 0.5 for i in range(3)]

    dist = math.sqrt((lp[0] - rp[0]) ** 2 + (lp[1] - rp[1]) ** 2 + (lp[2] - rp[2]) ** 2)
    if dist < 1e-4:
        dist = 1.0

    bellLoc = cmds.spaceLocator(name=f"{prefix}skirt_locator")[0]
    cmds.xform(bellLoc, worldSpace=True, translation=mid)
    cmds.xform(bellLoc, worldSpace=True, rotation=(180, 0, 0))

    if waistObj:
        cmds.parentConstraint(waistObj, bellLoc, maintainOffset=True)

    node = cmds.createNode(SKIRT_NODE_TYPE, name=f"{prefix}skirtBellCollider")
    nodeXform = cmds.listRelatives(node, parent=True, type="transform")[0]
    cmds.rename(nodeXform, f"{prefix}skirtBellCollider_transform")

    cmds.setAttr(f"{node}.skirtType", skirtType)
    cmds.setAttr(f"{node}.bellScale", dist, 1.0, dist, type="double3")
    cmds.setAttr(f"{node}.ringScale", dist / 2.0, 1.0, dist / 2.0, type="double3")

    cmds.setAttr(f"{node}.leftRingAxis", _findAxis(leftHipObj, leftKneeObj))
    cmds.setAttr(f"{node}.rightRingAxis", _findAxis(rightHipObj, rightKneeObj))
    cmds.setAttr(f"{node}.bellAxis", 1)  # We set rotation to (180,0,0), so Y is down

    jointPairs = [
        (bellLoc, "bellMatrix"),
        (leftHipObj, "leftHipMatrix"),
        (leftKneeObj, "leftKneeMatrix"),
        (leftHeelObj, "leftHeelMatrix"),
        (rightHipObj, "rightHipMatrix"),
        (rightKneeObj, "rightKneeMatrix"),
        (rightHeelObj, "rightHeelMatrix"),
    ]
    for obj, attr in jointPairs:
        if obj:
            cmds.connectAttr(f"{obj}.worldMatrix[0]", f"{node}.{attr}", force=True)

    # Lock t/r/s on the skirtBellCollider's parent transform
    nodeXform = cmds.listRelatives(node, parent=True)[0]
    for attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
        cmds.setAttr(f"{nodeXform}.{attr}", lock=True)

    # Rebuild the surface with history
    surfXform = cmds.createNode("transform", name=f"{prefix}skirt_surface")
    surfShape = cmds.createNode("nurbsSurface", name=f"{prefix}skirt_surfaceShape", parent=surfXform)

    rebuildNode = cmds.createNode("rebuildSurface")
    cmds.setAttr(f"{rebuildNode}.direction", 1)  # 0=U, 1=V, 2=U and V
    cmds.setAttr(f"{rebuildNode}.spansU", 1)
    cmds.setAttr(f"{rebuildNode}.spansV", 4)

    cmds.connectAttr(f"{node}.outputSurface", f"{rebuildNode}.inputSurface", force=True)
    cmds.connectAttr(f"{rebuildNode}.outputSurface", f"{surfShape}.create", force=True)
    cmds.sets(surfShape, edit=True, forceElement="initialShadingGroup")

    cmds.select(node)
    return node, bellLoc, surfXform


def attachJointsToSurface(surface, u_num, v_num, prefix=""):
    """Creates a grid of joints attached to the given NURBS surface using pointOnSurfaceInfo and fourByFourMatrix."""
    shapes = cmds.listRelatives(surface, shapes=True, path=True)
    if not shapes:
        cmds.warning(f"No shape found for surface {surface}")
        return []
    surfShape = shapes[0]

    joints = []

    # Group all attachments under a single transform for neatness
    grp = cmds.createNode('transform', name=f"{prefix}attachedJoints_group")

    min_u = cmds.getAttr(f"{surfShape}.minValueU")
    max_u = cmds.getAttr(f"{surfShape}.maxValueU")
    min_v = cmds.getAttr(f"{surfShape}.minValueV")
    max_v = cmds.getAttr(f"{surfShape}.maxValueV")

    for i in range(u_num):
        # Periodic in U, so [0, 1) to avoid overlap at seam
        u_ratio = i / float(u_num) if u_num > 0 else 0.5
        u_val = min_u + u_ratio * (max_u - min_u)
        for j in range(v_num):
            # Open in V, so [0, 1] exactly
            v_ratio = j / float(max(1, v_num - 1)) if v_num > 1 else 0.5
            v_val = min_v + v_ratio * (max_v - min_v)

            # PointOnSurfaceInfo
            posi = cmds.createNode('pointOnSurfaceInfo', name=f"{prefix}skirt_{i}_{j}_posi")
            cmds.connectAttr(f"{surfShape}.worldSpace[0]", f"{posi}.inputSurface", force=True)
            cmds.setAttr(f"{posi}.parameterU", u_val)
            cmds.setAttr(f"{posi}.parameterV", v_val)

            # Nodes for matrix assembly
            fourByFour = cmds.createNode("fourByFourMatrix", name=f"{prefix}skirt_{i}_{j}_fourByFourMatrix")
            decompose = cmds.createNode("decomposeMatrix", name=f"{prefix}skirt_{i}_{j}_decomposeMatrix")
            inv = cmds.createNode("multMatrix", name=f"{prefix}skirt_{i}_{j}_multMatrix")

            # Transform to hold the joint
            jntGrp = cmds.createNode('transform', name=f"{prefix}skirt_{i}_{j}_transform", parent=grp)

            # Feed posi vectors into fourByFourMatrix
            cmds.connectAttr(f"{posi}.positionX", f"{fourByFour}.in30", force=True)
            cmds.connectAttr(f"{posi}.positionY", f"{fourByFour}.in31", force=True)
            cmds.connectAttr(f"{posi}.positionZ", f"{fourByFour}.in32", force=True)

            cmds.connectAttr(f"{posi}.normalX", f"{fourByFour}.in00", force=True)
            cmds.connectAttr(f"{posi}.normalY", f"{fourByFour}.in01", force=True)
            cmds.connectAttr(f"{posi}.normalZ", f"{fourByFour}.in02", force=True)

            cmds.connectAttr(f"{posi}.tangentUx", f"{fourByFour}.in10", force=True)
            cmds.connectAttr(f"{posi}.tangentUy", f"{fourByFour}.in11", force=True)
            cmds.connectAttr(f"{posi}.tangentUz", f"{fourByFour}.in12", force=True)

            cmds.connectAttr(f"{posi}.tangentVx", f"{fourByFour}.in20", force=True)
            cmds.connectAttr(f"{posi}.tangentVy", f"{fourByFour}.in21", force=True)
            cmds.connectAttr(f"{posi}.tangentVz", f"{fourByFour}.in22", force=True)

            # Multiply world matrix by parentInverseMatrix to get local
            cmds.connectAttr(f"{fourByFour}.output", f"{inv}.matrixIn[0]", force=True)
            cmds.connectAttr(f"{jntGrp}.parentInverseMatrix[0]", f"{inv}.matrixIn[1]", force=True)
            cmds.connectAttr(f"{inv}.matrixSum", f"{decompose}.inputMatrix", force=True)

            # Drive the transform
            cmds.connectAttr(f"{decompose}.outputTranslate", f"{jntGrp}.translate", force=True)
            cmds.connectAttr(f"{decompose}.outputRotate", f"{jntGrp}.rotate", force=True)

            # Actual joint
            cmds.select(clear=True)
            jnt = cmds.joint(name=f"{prefix}skirt_{i}_{j}_joint")
            cmds.parent(jnt, jntGrp, relative=True)
            cmds.setAttr(f"{jnt}.radius", 0.5)
            joints.append(jnt)

    return joints


# ---------------------------------------------------------------------------
# Integración con el rig (usa los joints _ENV del esqueleto de export)
# ---------------------------------------------------------------------------

# Plantillas de los joints _ENV del rig (skeletonHierarchy). {side} -> "L"/"R".
RIG_ENV = {
    "hip":   "{side}_legUpper00_ENV",   # cadera  (arriba del muslo)
    "knee":  "{side}_legLower00_ENV",   # rodilla (arriba de la pierna baja)
    "heel":  "{side}_legAnkle_ENV",     # tobillo / talón
    "waist": "C_localHip_ENV",          # cintura / pelvis
}


def _exists(node):
    return bool(node) and cmds.objExists(node)


def create_skirt_collider_from_rig(prefix="", with_heels=True, attach_joints=False,
                                   u_num=7, v_num=5, names=None):
    """
    Crea un skirtBellCollider cableado a los joints _ENV del rig:
        hip   = {side}_legUpper00_ENV
        knee  = {side}_legLower00_ENV
        heel  = {side}_legAnkle_ENV
        waist = C_localHip_ENV
    Así el collider sigue al esqueleto de export. `names` permite overridear las
    plantillas (dict con claves hip/knee/heel/waist). Si faltan los _ENV, avisa.

    Returns: (node, bellLoc, surface, joints) o None si faltan joints clave.
    """
    _ensure_plugin()
    tpl = dict(RIG_ENV)
    if names:
        tpl.update(names)

    def s(key, side):
        return tpl[key].format(side=side)

    required = {
        "L hip": s("hip", "L"), "L knee": s("knee", "L"),
        "R hip": s("hip", "R"), "R knee": s("knee", "R"),
    }
    missing = [f"{k} ({v})" for k, v in required.items() if not _exists(v)]
    if missing:
        cmds.warning("skirt collider: faltan joints _ENV -> " + ", ".join(missing))
        return None

    lh, rh = s("heel", "L"), s("heel", "R")
    heels = with_heels and _exists(lh) and _exists(rh)
    waist = s("waist", "C")
    node, bell, surf = createSkirtBellCollider(
        prefix=prefix,
        leftHipObj=s("hip", "L"), leftKneeObj=s("knee", "L"), leftHeelObj=(lh if heels else None),
        rightHipObj=s("hip", "R"), rightKneeObj=s("knee", "R"), rightHeelObj=(rh if heels else None),
        waistObj=(waist if _exists(waist) else None),
        skirtType=1 if heels else 0,
    )
    joints = attachJointsToSurface(surf, u_num, v_num, prefix=prefix) if attach_joints else []
    return node, bell, surf, joints


def create_bell_collider_on(env_joint, numRings=1, prefix="", follow=True):
    """
    Crea un bellCollider y coloca su locator sobre `env_joint` (un joint _ENV del rig);
    con follow=True el locator sigue al joint (parentConstraint) y los anillos cuelgan
    de él, así el collider acompaña a la pose. Para arreglar interpenetraciones
    puntuales ("faltas"). Si no se pasa prefix se deriva del nombre del joint.

    Returns: (node, bellLoc, ringLocs, curve) o None si el joint no existe.
    """
    _ensure_plugin()
    if not _exists(env_joint):
        cmds.warning(f"bell collider: no existe el joint '{env_joint}'.")
        return None
    if not prefix:
        prefix = env_joint.split("|")[-1].replace("_ENV", "_")

    node, bellLoc, ringLocs, curve = createBellCollider(numRings=numRings, prefix=prefix)
    cmds.matchTransform(bellLoc, env_joint, position=True, rotation=True)
    for rl in ringLocs:
        cmds.parent(rl, bellLoc)          # los anillos siguen a la campana
    if follow:
        cmds.parentConstraint(env_joint, bellLoc, maintainOffset=True)
    return node, bellLoc, ringLocs, curve
