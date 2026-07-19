"""
proxy_skinning.py
=================
Proxy skinning del cuerpo con la cadena recomendada (skill body-proxy-skinning), SIN usar
auto_skin_transfer. Backend del botón "Proxy Skinning" (ui/proxy_skinning_UI.py).

CADENA
------
    1. BIND del proxy con Geodesic Voxel Binding (bindMethod=3) si aún no está skinneado, o
       usar su skinCluster existente (lo normal: pintas el proxy low-res).
       GVB mide por el VOLUMEN interior -> no cruza influencias entre partes próximas (el
       problema del closest-joint).
    2. BIND del high-res a los MISMOS joints (GVB) para tener un skinCluster destino, y
       TRANSFERIR los pesos del proxy con `copySkinWeights` (nativo). Por defecto asociación
       por -uvSpace (si hay UV coherente) o closestComponent, e influenceAssociation por label,
       que evitan el cruce. NO se usa auto_skin_transfer.
    3. Optimizar: prune + clamp de maxInfluences + normalizar (skin eficiente).
    4. REFINAR con Delta Mush (opcional).
    5. HORNEAR el Delta Mush a un skin lineal con bakeDeformer (opcional) -> deja el resultado
       en un único skinCluster barato y exportable.

Todo con comandos NATIVOS (skinCluster/geomBind, copySkinWeights, deltaMush, bakeDeformer).

USO (sin UI)
------------
    from tools import proxy_skinning
    reload(proxy_skinning)
    res = proxy_skinning.proxy_skin("body_proxy_GEO", "body_GEO", "C_root_JNT",
                                    max_influences=4, uv_space=False, delta_mush=True)
    print(res)

NOTA: no se ha podido ejecutar en Maya en este entorno; firmas de comando verificadas contra la
doc. Ver "PRUEBA Y AJUSTE" al final.
"""

import maya.cmds as cmds

try:
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    _HAS_OM = True
except Exception:
    _HAS_OM = False


# --------------------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------------------- #

def _skincluster(mesh):
    """skinCluster que deforma `mesh`, o None."""
    for n in (cmds.listHistory(mesh, pruneDagObjects=True) or []):
        if cmds.nodeType(n) == "skinCluster":
            return n
    return None


def _joint_chain(root):
    """root + todos sus joints descendientes (el esqueleto a bindear)."""
    if not cmds.objExists(root):
        raise RuntimeError(f"[proxy_skinning] no existe la raíz de esqueleto '{root}'.")
    kids = cmds.listRelatives(root, allDescendents=True, type="joint") or []
    return [root] + kids


def _uv_set(mesh):
    """UV set actual de la malla (para -uvSpace); None si no tiene."""
    try:
        return cmds.polyUVSet(mesh, q=True, currentUVSet=True)[0]
    except Exception:
        return None


def _gvb_bind(mesh, joints, max_influences, voxel_resolution=256):
    """
    Bind Geodesic Voxel de `mesh` a `joints`. Devuelve el skinCluster.
    GVB no cruza influencias (mide por el volumen), a diferencia del closest-joint.
    """
    sc = cmds.skinCluster(joints, mesh, toSelectedBones=True, bindMethod=3,
                          skinMethod=0, normalizeWeights=1,
                          maximumInfluences=max_influences, obeyMaxInfluences=True,
                          dropoffRate=4.0, name=f"{mesh.split('|')[-1]}_SKIN")[0]
    # Re-bind con resolución de vóxel controlada (partes finas/juntas piden más resolución).
    try:
        cmds.geomBind(sc, bindMethod=3, geodesicVoxelParams=(voxel_resolution, True),
                      maxInfluences=max_influences)
    except Exception as exc:
        cmds.warning(f"[proxy_skinning] geomBind (resolución) falló, se queda el bind base: {exc}")
    return sc


def skin_report(mesh, sc=None, threshold=1e-4):
    """Informe de eficiencia: nº de joints y máx/medio de influencias por vértice."""
    sc = sc or _skincluster(mesh)
    if not sc:
        return {"error": f"'{mesh}' no tiene skinCluster."}
    if not _HAS_OM:
        infl = cmds.skinCluster(sc, q=True, influence=True) or []
        return {"skinCluster": sc, "influences_total": len(infl)}
    sel = om.MSelectionList(); sel.add(sc)
    skfn = oma.MFnSkinCluster(sel.getDependNode(0))
    msel = om.MSelectionList()
    shp = cmds.listRelatives(mesh, s=True, ni=True, type="mesh")
    msel.add(shp[0] if shp else mesh)
    dag = msel.getDagPath(0)
    n_verts = om.MFnMesh(dag).numVertices
    comp_fn = om.MFnSingleIndexedComponent()
    comp = comp_fn.create(om.MFn.kMeshVertComponent)
    comp_fn.addElements(list(range(n_verts)))
    weights, n_w = skfn.getWeights(dag, comp)
    max_pv = total_pv = 0
    for vi in range(n_verts):
        c = sum(1 for j in range(n_w) if weights[vi * n_w + j] > threshold)
        max_pv = max(max_pv, c); total_pv += c
    return {"skinCluster": sc, "influences_total": len(skfn.influenceObjects()),
            "max_per_vertex": max_pv,
            "avg_per_vertex": round(total_pv / float(n_verts), 2) if n_verts else 0}


# --------------------------------------------------------------------------------------- #
# Transferencia proxy -> alta (copySkinWeights, NO auto_skin_transfer)
# --------------------------------------------------------------------------------------- #

def copy_weights(proxy, proxy_sc, high, high_sc, uv_space=False, use_labels=True):
    """
    Transfiere los pesos del proxy a la alta con `copySkinWeights` nativo.
      - uv_space=True  -> asociación por -uvSpace (dos superficies pegadas caen en UV distintas
                          -> no cruza). Requiere UV coherente en ambas mallas.
      - uv_space=False -> asociación por 'closestComponent' (mejor que closestPoint).
      - use_labels     -> influenceAssociation por 'label' (etiqueta de joint), con fallback a
                          'closestJoint'. Requiere labels puestos (Skin > Set Labels).
    """
    infl_assoc = ["label", "closestJoint"] if use_labels else ["closestJoint"]
    kwargs = dict(sourceSkin=proxy_sc, destinationSkin=high_sc,
                  noMirror=True, influenceAssociation=infl_assoc)
    if uv_space:
        src_uv, dst_uv = _uv_set(proxy), _uv_set(high)
        if src_uv and dst_uv:
            kwargs["uvSpace"] = (src_uv, dst_uv)
        else:
            cmds.warning("[proxy_skinning] falta UV set en proxy o alta; uso closestComponent.")
            kwargs["surfaceAssociation"] = "closestComponent"
    else:
        kwargs["surfaceAssociation"] = "closestComponent"
    cmds.copySkinWeights(**kwargs)


# --------------------------------------------------------------------------------------- #
# Cadena completa
# --------------------------------------------------------------------------------------- #

def proxy_skin(proxy, high, root_joint, max_influences=4, uv_space=False, use_labels=True,
               delta_mush=True, dm_iterations=10, bake=False, prune=0.005,
               dual_quaternion=False, voxel_resolution=256):
    """
    Ejecuta la cadena de proxy skinning: (GVB proxy) -> bind alta + copySkinWeights ->
    optimizar -> (Delta Mush) -> (bake a skin lineal). Devuelve un dict-informe.
    """
    for m in (proxy, high):
        if not cmds.objExists(m):
            raise RuntimeError(f"[proxy_skinning] no existe la malla '{m}'.")
    joints = _joint_chain(root_joint)

    # 1) proxy skinneado (usar el suyo o bindearlo GVB)
    proxy_sc = _skincluster(proxy) or _gvb_bind(proxy, joints, max_influences, voxel_resolution)

    # 2) bind de la alta a los mismos joints + transferir del proxy
    high_sc = _skincluster(high)
    if not high_sc:
        high_sc = _gvb_bind(high, joints, max_influences, voxel_resolution)
    copy_weights(proxy, proxy_sc, high, high_sc, uv_space=uv_space, use_labels=use_labels)

    # 3) optimizar (skin eficiente)
    cmds.skinPercent(high_sc, high, pruneWeights=prune, normalize=True)
    cmds.setAttr(high_sc + ".maxInfluences", max_influences)
    cmds.setAttr(high_sc + ".maintainMaxInfluences", True)
    cmds.setAttr(high_sc + ".skinningMethod", 1 if dual_quaternion else 0)

    # 4) refinar con Delta Mush (opcional)
    dm_node = None
    if delta_mush:
        dm_node = cmds.deltaMush(high, smoothingIterations=dm_iterations)[0]

    # 5) hornear Delta Mush -> skin lineal (opcional, deja un único skinCluster barato)
    baked = False
    if bake and dm_node:
        src = cmds.duplicate(high, name=f"{high}_dmSrc")[0]
        try:
            cmds.bakeDeformer(srcMeshName=src, dstMeshName=high,
                              srcSkeletonName=root_joint, dstSkeletonName=root_joint,
                              maxInfluences=max_influences)
            cmds.delete(dm_node)  # ya está horneado en el skin
            dm_node = None
            baked = True
        except Exception as exc:
            cmds.warning(f"[proxy_skinning] bakeDeformer falló, se conserva el Delta Mush: {exc}")
        finally:
            if cmds.objExists(src):
                cmds.delete(src)
        high_sc = _skincluster(high) or high_sc

    return {"proxy_skinCluster": proxy_sc, "high_skinCluster": high_sc,
            "delta_mush": dm_node, "baked": baked,
            "report": skin_report(high, sc=high_sc)}


# ======================================================================================= #
# PRUEBA Y AJUSTE (leer antes de darlo por bueno en Maya)
# ======================================================================================= #
#
# No se ha ejecutado en Maya aquí. Puntos a validar, por orden:
#
# 1) GEODESIC VOXEL desde script. `cmds.skinCluster(bindMethod=3)` + `cmds.geomBind(bindMethod=3,
#    geodesicVoxelParams=(res, True))` hacen GVB. La voxelización puede requerir contexto de
#    viewport/GPU: si corres en mayapy/headless puede fallar (ver hilo de Autodesk citado en la
#    skill) — en interactivo va bien. Sube voxel_resolution (256->512->1024) si dedos/axilas se
#    fusionan.
#
# 2) copySkinWeights: ambas mallas deben estar skinneadas a los MISMOS joints antes de copiar
#    (por eso se bindea la alta con GVB primero; la copia sobrescribe esos pesos). Para -uvSpace
#    hace falta UV coherente en proxy y alta. Para influenceAssociation 'label' hay que tener los
#    labels de joint puestos (Skin > Edit Influences > Set Labels); si no, cae a 'closestJoint'.
#
# 3) bakeDeformer muestrea la deformación moviendo el esqueleto: ten poses representativas antes
#    de hornear, o el Delta Mush horneado solo será fiel a la pose de bind.
#
# 4) VERIFICA la eficiencia con skin_report(high): objetivo max_per_vertex <= max_influences.
#
# Integra con tu SkinManager para versionar el .skc resultante, y valida con model_checker.
