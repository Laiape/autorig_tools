"""
cloth_skin_transfer — transferencia de skin CUERPO -> PRENDA sin depender de UVs.

POR QUÉ (el fallo del copy por UVs)
-----------------------------------
`copySkinWeights -uvSpace` empareja cada vértice de la prenda con el punto del cuerpo que
tiene la MISMA coordenada UV. Eso solo funciona si cuerpo y prenda comparten layout de UVs
alineado — y en producción casi nunca lo comparten (cada asset tiene su propio unwrap). Con
layouts distintos, la correspondencia es basura: un vértice del vestido puede "caer" en el UV
del brazo. Resultado: el copy de la ropa "no funciona".

EL MÉTODO REFINADO (no necesita UVs)
------------------------------------
Estilo *Robust Skin Weights Transfer via Weight Inpainting* (Abdrashitov et al., Epic Games,
SIGGRAPH Asia 2023), implementable con nodos/API nativos:

  1. CLOSEST POINT: para cada vértice de la prenda, punto más cercano en la malla del cuerpo
     (en Maya: MMeshIntersector, C++ rápido) e interpolación BARICÉNTRICA de los pesos de los
     3 vértices del triángulo (no el vértice más cercano a pelo: interpola dentro de la cara).
  2. CONFIANZA: el match solo vale si está CERCA (dist <= max_dist) y las normales son
     compatibles (dot >= min_normal_dot). Un bajo de falda lejos de las piernas, o un pliegue
     que mira al lado contrario, NO tiene correspondencia fiable -> queda "sin asignar".
  3. INPAINTING: los vértices sin asignar se rellenan difundiendo los pesos de sus vecinos
     sobre la malla de la prenda (suavizado laplaciano iterativo con los asignados fijos).
     La falda "continúa" suavemente los pesos de la cadera/muslo hacia abajo, sin saltos.
  4. LIMPIEZA: clamp a max_influences por vértice + normalizado.

El NÚCLEO es Python puro (sin Maya, sin numpy) -> testeable headless (tests/ incluye pruebas
con mallas sintéticas que demuestran el fallo del emparejado por UV y validan este método).
El wrapper de Maya es fino (MMeshIntersector + MFnSkinCluster).

USO EN MAYA
-----------
    from tools import cloth_skin_transfer as cst
    reload(cst)
    result = cst.transfer("body_GEO", "dress_GEO", max_dist=2.0, max_influences=4)
    print(result)   # matched/inpainted counts

NOTA: el wrapper de Maya no se ha podido ejecutar aquí (sin Maya en el entorno); el núcleo sí
está probado (scripts/tools/tests/test_cloth_skin_transfer.py, corre con python3 a secas).
"""

# ======================================================================================= #
# NÚCLEO PURO (sin Maya) — testeable headless
# ======================================================================================= #

def _sub(a, b):  return (a[0] - b[0], a[1] - b[1], a[2] - b[2])
def _add(a, b):  return (a[0] + b[0], a[1] + b[1], a[2] + b[2])
def _mul(a, s):  return (a[0] * s, a[1] * s, a[2] * s)
def _dot(a, b):  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])
def _norm(a):
    import math
    l = math.sqrt(_dot(a, a))
    return (0.0, 0.0, 0.0) if l < 1e-12 else _mul(a, 1.0 / l)
def _dist(a, b):
    d = _sub(a, b)
    import math
    return math.sqrt(_dot(d, d))


def closest_point_on_triangle(p, a, b, c):
    """
    Punto más cercano a `p` en el triángulo (a,b,c) y sus baricéntricas (u,v,w) tales que
    point = u*a + v*b + w*c. Algoritmo de Ericson (Real-Time Collision Detection).
    """
    ab, ac, ap = _sub(b, a), _sub(c, a), _sub(p, a)
    d1, d2 = _dot(ab, ap), _dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return a, (1.0, 0.0, 0.0)
    bp = _sub(p, b)
    d3, d4 = _dot(ab, bp), _dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return b, (0.0, 1.0, 0.0)
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3)
        return _add(a, _mul(ab, v)), (1.0 - v, v, 0.0)
    cp = _sub(p, c)
    d5, d6 = _dot(ab, cp), _dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return c, (0.0, 0.0, 1.0)
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6)
        return _add(a, _mul(ac, w)), (1.0 - w, 0.0, w)
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return _add(b, _mul(_sub(c, b), w)), (0.0, 1.0 - w, w)
    denom = 1.0 / (va + vb + vc)
    v, w = vb * denom, vc * denom
    return _add(a, _add(_mul(ab, v), _mul(ac, w))), (1.0 - v - w, v, w)


def closest_on_mesh(p, verts, tris):
    """
    Punto más cercano a `p` sobre una malla triangulada (fuerza bruta, para tests/mallas
    pequeñas; en Maya esto lo hace MMeshIntersector). Devuelve (dist, point, tri_index, bary).
    """
    best = None
    for ti, (i0, i1, i2) in enumerate(tris):
        pt, bary = closest_point_on_triangle(p, verts[i0], verts[i1], verts[i2])
        d = _dist(p, pt)
        if best is None or d < best[0]:
            best = (d, pt, ti, bary)
    return best


def face_normal(verts, tri):
    i0, i1, i2 = tri
    return _norm(_cross(_sub(verts[i1], verts[i0]), _sub(verts[i2], verts[i0])))


def interpolate_weights(bary, w0, w1, w2):
    """Combina 3 dicts {joint: peso} por baricéntricas. Devuelve dict normalizado."""
    out = {}
    for bar, wd in zip(bary, (w0, w1, w2)):
        if bar <= 0.0:
            continue
        for j, w in wd.items():
            out[j] = out.get(j, 0.0) + bar * w
    s = sum(out.values())
    return {j: w / s for j, w in out.items()} if s > 1e-12 else {}


def transfer_core(src_verts, src_tris, src_weights, dst_verts,
                  max_dist=None, min_normal_dot=None, dst_normals=None,
                  closest_fn=None):
    """
    Paso 1+2: closest point + baricéntricas + filtro de confianza.

    Args:
        src_weights: lista de dicts {joint: peso} por vértice del cuerpo.
        max_dist: distancia máxima para dar el match por bueno (None = sin filtro).
        min_normal_dot: dot mínimo entre la normal del vértice de la prenda y la de la cara
            del cuerpo (None = sin filtro). Requiere dst_normals.
        closest_fn: override del closest point (en Maya, MMeshIntersector); firma
            closest_fn(p) -> (dist, point, tri_index, bary).

    Returns:
        (weights, matched): lista de dicts (vacíos donde no hay match) y máscara booleana.
    """
    closest = closest_fn or (lambda p: closest_on_mesh(p, src_verts, src_tris))
    weights, matched = [], []
    for vi, p in enumerate(dst_verts):
        d, _pt, ti, bary = closest(p)
        ok = True
        if max_dist is not None and d > max_dist:
            ok = False
        if ok and min_normal_dot is not None and dst_normals is not None:
            if _dot(dst_normals[vi], face_normal(src_verts, src_tris[ti])) < min_normal_dot:
                ok = False
        if ok:
            i0, i1, i2 = src_tris[ti]
            weights.append(interpolate_weights(bary, src_weights[i0], src_weights[i1], src_weights[i2]))
            matched.append(True)
        else:
            weights.append({})
            matched.append(False)
    return weights, matched


def inpaint_weights(weights, matched, adjacency, iterations=300, tol=1e-6):
    """
    Paso 3: rellena los vértices sin match difundiendo desde los vecinos (Jacobi laplaciano,
    matched fijos). Converge a una interpolación armónica sobre la malla de la prenda: el bajo
    de la falda continúa suavemente los pesos de arriba, sin usar UVs ni distancia al cuerpo.
    """
    n = len(weights)
    todo = [i for i in range(n) if not matched[i]]
    if not todo:
        return weights
    cur = [dict(w) for w in weights]
    for _ in range(iterations):
        delta = 0.0
        new = {}
        for i in todo:
            acc, cnt = {}, 0
            for nb in adjacency[i]:
                wnb = cur[nb]
                if not wnb:
                    continue
                cnt += 1
                for j, w in wnb.items():
                    acc[j] = acc.get(j, 0.0) + w
            if not cnt:
                continue
            s = sum(acc.values())
            nw = {j: w / s for j, w in acc.items()} if s > 1e-12 else {}
            old = cur[i]
            keys = set(nw) | set(old)
            delta = max(delta, max((abs(nw.get(k, 0.0) - old.get(k, 0.0)) for k in keys), default=0.0))
            new[i] = nw
        for i, w in new.items():
            cur[i] = w
        if delta < tol:
            break
    return cur


def clamp_and_normalize(weights, max_influences=4, prune=1e-3):
    """Paso 4: por vértice, poda pesos ínfimos, conserva las N mayores influencias y normaliza."""
    out = []
    for wd in weights:
        items = sorted(((w, j) for j, w in wd.items() if w > prune), reverse=True)[:max_influences]
        s = sum(w for w, _ in items)
        out.append({j: w / s for w, j in items} if s > 1e-12 else {})
    return out


def adjacency_from_tris(n_verts, tris):
    """Vecindad vértice->vértices desde triángulos (para el inpainting)."""
    adj = [set() for _ in range(n_verts)]
    for i0, i1, i2 in tris:
        adj[i0].update((i1, i2)); adj[i1].update((i0, i2)); adj[i2].update((i0, i1))
    return [sorted(s) for s in adj]


# ======================================================================================= #
# WRAPPER DE MAYA (fino; no ejecutado aquí — validar en escena)
# ======================================================================================= #

def transfer(body, cloth, max_dist=2.0, min_normal_dot=0.0, max_influences=4,
             prune=1e-3, inpaint_iterations=300):
    """
    Transfiere el skin del cuerpo a la prenda SIN UVs: closest point (MMeshIntersector) +
    baricéntricas + confianza + inpainting. Crea/usa un skinCluster en la prenda con las
    mismas influencias que el cuerpo y escribe los pesos de una vez.
    """
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma

    def _shape(mesh):
        shapes = cmds.listRelatives(mesh, s=True, ni=True, type="mesh") or []
        if not shapes:
            raise RuntimeError(f"[cloth_skin_transfer] '{mesh}' no tiene shape de malla.")
        return shapes[0]

    def _skincluster(mesh):
        for n in (cmds.listHistory(mesh, pruneDagObjects=True) or []):
            if cmds.nodeType(n) == "skinCluster":
                return n
        return None

    body_sc = _skincluster(body)
    if not body_sc:
        raise RuntimeError(f"[cloth_skin_transfer] '{body}' no tiene skinCluster.")

    # --- lee el cuerpo: puntos, triángulos y pesos por vértice
    sel = om.MSelectionList(); sel.add(_shape(body)); sel.add(body_sc)
    body_dag = sel.getDagPath(0)
    skfn = oma.MFnSkinCluster(sel.getDependNode(1))
    body_fn = om.MFnMesh(body_dag)

    infl_paths = skfn.influenceObjects()
    influences = [p.partialPathName() for p in infl_paths]
    n_body = body_fn.numVertices

    comp_fn = om.MFnSingleIndexedComponent()
    comp = comp_fn.create(om.MFn.kMeshVertComponent)
    comp_fn.addElements(list(range(n_body)))
    flat, n_infl = skfn.getWeights(body_dag, comp)
    src_weights = []
    for vi in range(n_body):
        base = vi * n_infl
        src_weights.append({j: flat[base + j] for j in range(n_infl) if flat[base + j] > 1e-6})

    body_pts = [(p.x, p.y, p.z) for p in body_fn.getPoints(om.MSpace.kWorld)]
    tri_counts, tri_verts = body_fn.getTriangles()
    src_tris, it = [], iter(tri_verts)
    for _ in range(len(tri_verts) // 3):
        src_tris.append((next(it), next(it), next(it)))

    # --- closest point acelerado con MMeshIntersector (espacio local del cuerpo)
    intersector = om.MMeshIntersector()
    intersector.create(body_dag.node(), body_dag.inclusiveMatrix())
    inv = body_dag.inclusiveMatrix().inverse()

    # triángulos por (cara, triángulo) para mapear el hit del intersector a src_tris
    face_tri_index = {}
    running = 0
    for face, cnt in enumerate(tri_counts):
        for t in range(cnt):
            face_tri_index[(face, t)] = running
            running += 1

    def closest_fn(p):
        mp = om.MPoint(p[0], p[1], p[2]) * inv          # a espacio local del intersector
        hit = intersector.getClosestPoint(mp)
        ti = face_tri_index[(hit.face, hit.triangle)]
        i0, i1, i2 = src_tris[ti]
        pt, bary = closest_point_on_triangle(p, body_pts[i0], body_pts[i1], body_pts[i2])
        return _dist(p, pt), pt, ti, bary

    # --- lee la prenda: puntos, normales, adyacencia
    csel = om.MSelectionList(); csel.add(_shape(cloth))
    cloth_dag = csel.getDagPath(0)
    cloth_fn = om.MFnMesh(cloth_dag)
    dst_verts = [(p.x, p.y, p.z) for p in cloth_fn.getPoints(om.MSpace.kWorld)]
    dst_normals = None
    if min_normal_dot is not None and min_normal_dot > -1.0:
        dst_normals = [(_n.x, _n.y, _n.z) for _n in cloth_fn.getVertexNormals(False, om.MSpace.kWorld)]
    c_counts, c_verts_flat = cloth_fn.getTriangles()
    dst_tris, it = [], iter(c_verts_flat)
    for _ in range(len(c_verts_flat) // 3):
        dst_tris.append((next(it), next(it), next(it)))
    adjacency = adjacency_from_tris(len(dst_verts), dst_tris)

    # --- núcleo: transfer + inpaint + clamp
    weights, matched = transfer_core(body_pts, src_tris, src_weights, dst_verts,
                                     max_dist=max_dist, min_normal_dot=min_normal_dot,
                                     dst_normals=dst_normals, closest_fn=closest_fn)
    weights = inpaint_weights(weights, matched, adjacency, iterations=inpaint_iterations)
    weights = clamp_and_normalize(weights, max_influences=max_influences, prune=prune)

    # --- skinCluster en la prenda con las mismas influencias, y escribir pesos de una vez
    cloth_sc = _skincluster(cloth)
    if not cloth_sc:
        cloth_sc = cmds.skinCluster(influences, cloth, toSelectedBones=True,
                                    maximumInfluences=max_influences, obeyMaxInfluences=True,
                                    normalizeWeights=1,
                                    name=f"{cloth.split('|')[-1]}_SKIN")[0]
    ssel = om.MSelectionList(); ssel.add(cloth_sc)
    cloth_skfn = oma.MFnSkinCluster(ssel.getDependNode(0))
    # mapa influencia->índice físico del skinCluster de la prenda
    cloth_infl = {p.partialPathName(): cloth_skfn.indexForInfluenceObject(p)
                  for p in cloth_skfn.influenceObjects()}
    order = [cloth_infl.get(name) for name in influences]
    if any(i is None for i in order):
        missing = [influences[k] for k, i in enumerate(order) if i is None]
        raise RuntimeError(f"[cloth_skin_transfer] influencias del cuerpo ausentes en el skin "
                           f"de la prenda: {missing[:5]}")

    n_dst = len(dst_verts)
    n_cloth_infl = len(cloth_infl)
    flat_out = om.MDoubleArray(n_dst * n_cloth_infl, 0.0)
    for vi, wd in enumerate(weights):
        base = vi * n_cloth_infl
        for j, w in wd.items():
            flat_out[base + order[j]] = w
    ccomp_fn = om.MFnSingleIndexedComponent()
    ccomp = ccomp_fn.create(om.MFn.kMeshVertComponent)
    ccomp_fn.addElements(list(range(n_dst)))
    cloth_skfn.setWeights(cloth_dag, ccomp,
                          om.MIntArray(list(range(n_cloth_infl))), flat_out, False)

    cmds.setAttr(cloth_sc + ".maxInfluences", max_influences)
    cmds.setAttr(cloth_sc + ".maintainMaxInfluences", True)

    n_matched = sum(1 for m in matched if m)
    return {"skinCluster": cloth_sc, "matched": n_matched,
            "inpainted": len(matched) - n_matched, "influences": len(influences)}


# ======================================================================================= #
# PRUEBA Y AJUSTE (en Maya)
# ======================================================================================= #
#
# El núcleo está testeado headless (tests/test_cloth_skin_transfer.py). Al validar en escena:
#
# 1) max_dist es EN UNIDADES DE ESCENA (cm por defecto): la distancia prenda-cuerpo típica.
#    Para una camiseta pegada, 1-3 cm; para falda vaporosa sube el umbral o deja que el bajo
#    caiga en inpainting (que es lo deseable).
# 2) min_normal_dot=0.0 descarta matches con normal opuesta (interior de pliegues). Si la
#    prenda tiene normales invertidas, ponlo a None o corrige normales antes.
# 3) El hit de MMeshIntersector (hit.face, hit.triangle) se mapea a índice global de triángulo;
#    si tu versión de la API cambia esos nombres (face/triangle), verifica en el Script Editor.
# 4) Valida el resultado con skin_report de tools.proxy_skinning y con model_checker.
