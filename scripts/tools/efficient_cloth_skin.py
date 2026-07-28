"""
efficient_cloth_skin — skin de ropa lo MÁS EFICIENTE posible (runtime), sin copy skin weights.

IDEA (método `bakeDeformer` del catálogo, Familia 1)
----------------------------------------------------
En vez de copiar pesos del cuerpo a la prenda (que hereda los errores del bind del cuerpo y
sigue siendo rígido), se hace lo contrario del habitual:

    1. Riggeas la prenda de forma RICA y barata de autoría: un proximityWrap al cuerpo. La
       prenda sigue la SUPERFICIE ya deformada (skin + AdonisFX) del cuerpo, capturando la
       deformación real, no solo los joints.
    2. HORNEAS esa deformación a un único skinCluster LINEAL con `bakeDeformer`, resolviendo
       por mínimos cuadrados los pesos que mejor la reproducen, con un tope de influencias
       (maxInfluences 4 -> game-ready).
    3. Optimizas el resultado: prune de pesos minúsculos, clamp de influencias, normalizado.

Resultado: la prenda deforma como si tuviera un wrap caro, pero en runtime es UN skinCluster
lineal con pocas influencias -> lo más eficiente posible de evaluar y portable a motor. El wrap
solo se usa para hornear; se borra después.

Por qué es "más eficiente" que el copy skin: el copy skin ya es un skinCluster, sí, pero hereda
pesos sucios del cuerpo (muchas influencias, cruces entre partes). bakeDeformer RESUELVE pesos
nuevos, limpios y acotados que aproximan la deformación objetivo -> menos influencias por
vértice, sin cruces, y de una superficie de referencia mejor.

CONVENCIONES DE ESTE REPO
-------------------------
Se apoya en tu tooling (SkinManager para versionar el .skc horneado), naming del repo, y no
depende de plugins. `bakeDeformer` y `proximityWrap` son NATIVOS de Maya.

IMPORTANTE — NO PROBADO EN MAYA EN ESTE ENTORNO
-----------------------------------------------
Firmas de comando verificadas contra la doc, pero sin ejecutar en Maya aquí. Los dos puntos a
validar (ver "PRUEBA Y AJUSTE" al final): (a) los plugs del proximityWrap por versión, y (b)
que `bakeDeformer` muestrea bien la pose/rango (conviene tener poses representativas).

USO RÁPIDO
----------
    from tools import efficient_cloth_skin as ecs
    reload(ecs)

    # Pipeline completo: wrap al cuerpo -> bake a skin lineal -> optimizar
    res = ecs.build_efficient_cloth_skin(
        cloth="anne_dress_GEO",
        body="anne_body_GEO",
        skeleton_root="C_root_JNT",     # raíz del esqueleto del cuerpo
        max_influences=4)
    print(res["report"])                 # influencias/vértice antes vs después

    # Si ya tienes la prenda deformada de forma rica por tu cuenta (correctivos, transfer+deltaMush...):
    sc = ecs.bake_to_efficient_skin("anne_dress_rich_GEO", "anne_dress_GEO",
                                    "C_root_JNT", max_influences=4)
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma


# --------------------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------------------- #

def _shape(mesh):
    """Shape de deformación (no intermediate) de un transform de malla."""
    if cmds.nodeType(mesh) == "mesh":
        return mesh
    shapes = cmds.listRelatives(mesh, s=True, ni=True, type="mesh") or []
    if not shapes:
        raise RuntimeError(f"[efficient_cloth_skin] '{mesh}' no tiene shape de malla.")
    return shapes[0]


def _skincluster(mesh):
    """Devuelve el skinCluster que deforma `mesh`, o None."""
    scs = [n for n in (cmds.listHistory(mesh, pdo=True) or [])
           if cmds.nodeType(n) == "skinCluster"]
    return scs[0] if scs else None


def skin_report(mesh, sc=None, threshold=1e-4, sample=None):
    """
    Informe de EFICIENCIA de un skin: nº de joints, y máx/medio de influencias por vértice
    (lo que de verdad cuesta en runtime). Usa OpenMaya para leer los pesos de golpe.

    Args:
        sample (int|None): si se da, muestrea ese nº de vértices (rápido en mallas densas).

    Returns:
        dict con influences_total, max_per_vertex, avg_per_vertex, verts.
    """
    sc = sc or _skincluster(mesh)
    if not sc:
        return {"error": f"'{mesh}' no tiene skinCluster."}

    sel = om.MSelectionList()
    sel.add(sc)
    skfn = oma.MFnSkinCluster(sel.getDependNode(0))

    msel = om.MSelectionList()
    msel.add(_shape(mesh))
    dag = msel.getDagPath(0)

    fn_mesh = om.MFnMesh(dag)
    n_verts = fn_mesh.numVertices
    infl = skfn.influenceObjects()
    n_infl = len(infl)

    comp_fn = om.MFnSingleIndexedComponent()
    comp = comp_fn.create(om.MFn.kMeshVertComponent)
    idxs = range(n_verts) if not sample else range(0, n_verts, max(1, n_verts // sample))
    idxs = list(idxs)
    comp_fn.addElements(idxs)

    weights, n_w = skfn.getWeights(dag, comp)
    # weights es plano: [v0_i0, v0_i1, ..., v1_i0, ...]; n_w = nº de influencias
    max_pv, total_pv = 0, 0
    for vi in range(len(idxs)):
        c = 0
        base = vi * n_w
        for j in range(n_w):
            if weights[base + j] > threshold:
                c += 1
        max_pv = max(max_pv, c)
        total_pv += c
    avg_pv = total_pv / float(len(idxs)) if idxs else 0.0

    return {"skinCluster": sc, "influences_total": n_infl,
            "max_per_vertex": max_pv, "avg_per_vertex": round(avg_pv, 2),
            "verts": len(idxs)}


# --------------------------------------------------------------------------------------- #
# 1) Fuente rica: proximityWrap de la prenda al cuerpo
# --------------------------------------------------------------------------------------- #

def create_proximity_wrap(target, driver, falloff=0.1, name=None):
    """
    Crea un proximityWrap NATIVO en `target` (prenda) manejado por `driver` (cuerpo). Así la
    prenda sigue la superficie ya deformada del cuerpo (captura la deformación real), que es la
    fuente rica que luego horneamos.

    OJO: los plugs del proximityWrap varían algo entre versiones de Maya; verifícalos en la tuya
    (Node Editor) si el driver no engancha. Firma general (Maya 2018+):
        drivers[i].driverGeometry      <- driver worldMesh (vivo)
        drivers[i].driverBindGeometry  <- driver malla en bind (estático)
    """
    name = name or f"{target}_prox_WRAP"
    wrap = cmds.deformer(target, type="proximityWrap", name=name)[0]

    drv_shape = _shape(driver)
    # Malla de bind estática: duplicado del driver en la pose actual (referencia de reposo).
    bind_dup = cmds.duplicate(driver, name=f"{driver}_wrapBind")[0]
    bind_shape = _shape(bind_dup)
    cmds.setAttr(bind_dup + ".visibility", 0)

    try:
        cmds.connectAttr(drv_shape + ".worldMesh[0]", wrap + ".drivers[0].driverGeometry", f=True)
        cmds.connectAttr(bind_shape + ".outMesh", wrap + ".drivers[0].driverBindGeometry", f=True)
    except Exception as exc:
        cmds.warning(f"[efficient_cloth_skin] no pude cablear el proximityWrap "
                     f"(verifica los plugs en tu versión): {exc}")

    for at, val in (("wrapMode", 1), ("falloffScale", falloff), ("maxDrivers", 1)):
        if cmds.attributeQuery(at, node=wrap, exists=True):
            try:
                cmds.setAttr(f"{wrap}.{at}", val)
            except Exception:
                pass
    return {"wrap": wrap, "bind_dup": bind_dup}


# --------------------------------------------------------------------------------------- #
# 2) Núcleo: hornear a un skinCluster lineal eficiente + optimizar
# --------------------------------------------------------------------------------------- #

def bake_to_efficient_skin(src_mesh, dst_mesh, skeleton_root, max_influences=4,
                           prune=0.005, dual_quaternion=False, dst_skeleton_root=None):
    """
    Hornea la deformación de `src_mesh` (rica: wrap/correctivos/transfer+deltaMush) a un
    skinCluster LINEAL sobre `dst_mesh`, con `bakeDeformer` (mínimos cuadrados, tope de
    influencias). Luego optimiza: prune + normalizado + método de skinning.

    src_mesh y dst_mesh deben tener la MISMA topología (típicamente dst es un duplicado limpio
    de la prenda; src es esa misma prenda deformada por el wrap).

    Returns: dict con 'skinCluster', 'report_before', 'report_after'.
    """
    dst_root = dst_skeleton_root or skeleton_root
    for m in (src_mesh, dst_mesh):
        if not cmds.objExists(m):
            raise RuntimeError(f"[efficient_cloth_skin] no existe la malla '{m}'.")
    for j in (skeleton_root, dst_root):
        if not cmds.objExists(j):
            raise RuntimeError(f"[efficient_cloth_skin] no existe la raíz de esqueleto '{j}'.")

    # bakeDeformer: resuelve el skin lineal que aproxima la deformación de src, bind sobre dst.
    #   (firma verificada: srcMeshName/dstMeshName/srcSkeletonName/dstSkeletonName/maxInfluences)
    cmds.bakeDeformer(srcMeshName=src_mesh, dstMeshName=dst_mesh,
                      srcSkeletonName=skeleton_root, dstSkeletonName=dst_root,
                      maxInfluences=max_influences)

    sc = _skincluster(dst_mesh)
    if not sc:
        raise RuntimeError("[efficient_cloth_skin] bakeDeformer no dejó skinCluster en el destino.")

    # Optimización: prune de pesos minúsculos + clamp de influencias + normalizado forzado.
    cmds.skinPercent(sc, dst_mesh, pruneWeights=prune, normalize=True)
    cmds.setAttr(sc + ".maxInfluences", max_influences)
    cmds.setAttr(sc + ".maintainMaxInfluences", True)
    cmds.setAttr(sc + ".skinningMethod", 1 if dual_quaternion else 0)  # 0 lineal / 1 DQ
    try:
        cmds.skinCluster(sc, e=True, forceNormalizeWeights=True)
    except Exception:
        pass

    return {"skinCluster": sc,
            "report_after": skin_report(dst_mesh, sc=sc)}


# --------------------------------------------------------------------------------------- #
# 3) Orquestador: prenda + cuerpo -> skin eficiente
# --------------------------------------------------------------------------------------- #

def build_efficient_cloth_skin(cloth, body, skeleton_root, max_influences=4,
                               prune=0.005, dual_quaternion=False,
                               source_mesh=None, cleanup=True):
    """
    Pipeline completo: (wrap de la prenda al cuerpo) -> bakeDeformer a skin lineal -> optimizar.

    Args:
        cloth (str): malla de la prenda (queda skinneada eficientemente al final).
        body (str): malla del cuerpo ya deformada (skin + AdonisFX). Manda la deformación real.
        skeleton_root (str): raíz del esqueleto del cuerpo (a la que se bindeará la prenda).
        max_influences (int): tope de influencias por vértice (4 = game-ready).
        source_mesh (str|None): si YA tienes la prenda deformada de forma rica por tu cuenta,
            pásala aquí y NO se crea wrap (se hornea directamente desde ella).
        cleanup (bool): borra el wrap/duplicados temporales tras hornear.

    Returns:
        dict con 'cloth', 'skinCluster', 'report', y nodos temporales creados.
    """
    if source_mesh is None:
        # La prenda ORIGINAL será el destino limpio; el wrap va sobre un DUPLICADO (la fuente rica).
        src = cmds.duplicate(cloth, name=f"{cloth}_richSrc")[0]
        wrap_info = create_proximity_wrap(src, body)
        temp = [src, wrap_info["wrap"], wrap_info["bind_dup"]]
    else:
        src = source_mesh
        temp = []

    baked = bake_to_efficient_skin(src, cloth, skeleton_root,
                                   max_influences=max_influences, prune=prune,
                                   dual_quaternion=dual_quaternion)

    if cleanup and temp:
        for n in temp:
            if cmds.objExists(n):
                try:
                    cmds.delete(n)
                except Exception:
                    pass

    return {"cloth": cloth, "skinCluster": baked["skinCluster"],
            "report": baked["report_after"], "temp": ([] if cleanup else temp)}


# ======================================================================================= #
# PRUEBA Y AJUSTE (leer antes de darlo por bueno en Maya)
# ======================================================================================= #
#
# No he podido ejecutar esto en Maya. Puntos a validar, por orden:
#
# 1) MUESTREO DE bakeDeformer. bakeDeformer aprende los pesos observando cómo deforma la fuente
#    al MOVER el esqueleto. Para un buen resultado, ten poses representativas del rango (o deja
#    que muestree la pose de bind + algunas poses clave). Si la prenda solo se ve bien en la pose
#    de bind, mueve las piernas/torso a poses extremas ANTES de hornear. Comprueba el resultado
#    escrubbeando: la prenda horneada debe seguir de cerca a la del wrap.
#
# 2) PLUGS DEL proximityWrap. `drivers[0].driverGeometry` / `driverBindGeometry` son los de Maya
#    2018+. Si en tu versión el driver no engancha, míralos en el Node Editor sobre un
#    proximityWrap creado por UI (Deform > Proximity Wrap) y ajusta create_proximity_wrap.
#    Alternativa sin riesgo: genera la fuente rica como quieras (tu auto_skin_transfer +
#    `cmds.deltaMush`, o correctivos) y pásala con source_mesh=...; el núcleo (bakeDeformer +
#    optimizar) se reutiliza igual.
#
# 3) TOPOLOGÍA. src y dst deben compartir topología (dst es la prenda original; src su duplicado
#    deformado). bakeDeformer empareja por índice de vértice.
#
# 4) VERIFICA LA EFICIENCIA. skin_report(cloth) te da max/medio de influencias por vértice. El
#    objetivo es max_per_vertex <= max_influences y un avg bajo. Compáralo con el copy skin del
#    cuerpo (que suele tener más influencias y cruces).
#
# INTEGRACIÓN CON TU PIPELINE (siguiente paso natural):
# - Versiona el skin horneado con tu SkinManager:
#       from tools.skin_manager_api import SkinManager
#       SkinManager().export_skins()          # guarda el .skc del resultado
# - Mételo en un clothing_module.py que lea la prenda/cuerpo del build (data_manager) en vez de
#   nombres a mano, y valida con model_checker (normalizado, maxInfluences, sin joints sueltos).
# - Para juego: con skinningMethod lineal (0) y maxInfluences 4 ya es exportable a FBX directo.
