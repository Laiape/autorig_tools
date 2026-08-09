"""
Tests headless del núcleo de cloth_skin_transfer (sin Maya, sin numpy).

    python3 scripts/tools/tests/test_cloth_skin_transfer.py

Escenario sintético: un "cuerpo" con dos piernas (tubos) skinneadas rígidas a L/R, y una
"falda" elíptica que envuelve ambas piernas y cuelga por debajo (el bajo no tiene cuerpo
cerca -> inpainting). Cuerpo y falda tienen TOPOLOGÍAS Y UVs DISTINTOS, como en producción.

Cubre:
  1. closest_point_on_triangle correcto (vs muestreo por fuerza bruta).
  2. El transfer por closest point + baricéntricas NO cruza pesos entre piernas.
  3. El bajo sin correspondencia se rellena por inpainting: suave, normalizado y coherente
     por lado (izquierda sigue L, derecha sigue R).
  4. DEMO DEL FALLO POR UVs: con layouts de UV distintos (lo normal entre cuerpo y prenda),
     el emparejado por UV asigna un % alto de vértices a la pierna EQUIVOCADA; el closest
     point, cero. (La hipótesis del usuario, reproducida numéricamente.)
"""

import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from maya.scripts.tools.cloth_skin_transfer import (closest_point_on_triangle, closest_on_mesh,  # noqa: E402
                                 transfer_core, inpaint_weights, clamp_and_normalize,
                                 adjacency_from_tris, _dist)


# ---------------------------------------------------------------------------------------- #
# Generadores de malla sintética
# ---------------------------------------------------------------------------------------- #

def make_tube(cx, cz, radius_x, radius_z, y_top, y_bottom, rings, segs, u_offset=0.0,
              u_scale=1.0):
    """Tubo elíptico triangulado. Devuelve (verts, tris, uvs) — uvs por vértice (u,v)."""
    verts, uvs = [], []
    for r in range(rings):
        t = r / float(rings - 1)
        y = y_top + (y_bottom - y_top) * t
        for s in range(segs):
            ang = 2.0 * math.pi * s / segs
            verts.append((cx + radius_x * math.cos(ang), y, cz + radius_z * math.sin(ang)))
            uvs.append((u_offset + u_scale * (s / float(segs)), t))
    tris = []
    for r in range(rings - 1):
        for s in range(segs):
            a = r * segs + s
            b = r * segs + (s + 1) % segs
            c = (r + 1) * segs + s
            d = (r + 1) * segs + (s + 1) % segs
            tris.append((a, b, c)); tris.append((b, d, c))
    return verts, tris, uvs


def make_body():
    """
    Dos piernas: L en x=-3, R en x=+3, radio 1, de y=0 a y=-10. Cada una skinneada rígida a
    su joint (0=L, 1=R). UVs de producción del cuerpo: cada pierna en su franja de U
    (L: [0,0.45], R: [0.55,1.0]).
    """
    lv, lt, luv = make_tube(-3.0, 0.0, 1.0, 1.0, 0.0, -10.0, rings=12, segs=12,
                            u_offset=0.0, u_scale=0.45)
    rv, rt, ruv = make_tube(+3.0, 0.0, 1.0, 1.0, 0.0, -10.0, rings=12, segs=12,
                            u_offset=0.55, u_scale=0.45)
    verts = lv + rv
    off = len(lv)
    tris = lt + [(a + off, b + off, c + off) for a, b, c in rt]
    uvs = luv + ruv
    weights = [{0: 1.0}] * len(lv) + [{1: 1.0}] * len(rv)
    return verts, tris, uvs, weights


def make_skirt():
    """
    Falda elíptica que envuelve ambas piernas (rx=5.5, rz=2.5) de y=0 a y=-14: el tramo por
    debajo de y=-10 no tiene cuerpo cerca. Topología distinta (más segmentos) y UVs propios
    con layout DISTINTO al del cuerpo (unwrap completo [0,1] con seam rotado).
    """
    return make_tube(0.0, 0.0, 5.5, 2.5, 0.0, -14.0, rings=15, segs=24,
                     u_offset=0.31, u_scale=1.0)  # layout propio: ni franjas ni misma escala


# ---------------------------------------------------------------------------------------- #
# Tests
# ---------------------------------------------------------------------------------------- #

def test_closest_point_on_triangle():
    random.seed(7)
    for _ in range(300):
        a = tuple(random.uniform(-5, 5) for _ in range(3))
        b = tuple(random.uniform(-5, 5) for _ in range(3))
        c = tuple(random.uniform(-5, 5) for _ in range(3))
        p = tuple(random.uniform(-8, 8) for _ in range(3))
        pt, bary = closest_point_on_triangle(p, a, b, c)
        # baricéntricas válidas y consistentes con el punto
        assert all(-1e-9 <= x <= 1.0 + 1e-9 for x in bary), bary
        assert abs(sum(bary) - 1.0) < 1e-6, bary
        recon = tuple(bary[0] * a[i] + bary[1] * b[i] + bary[2] * c[i] for i in range(3))
        assert _dist(pt, recon) < 1e-6
        # ningún punto muestreado del triángulo está más cerca que el devuelto
        d_best = _dist(p, pt)
        for _s in range(60):
            u = random.random(); v = random.random() * (1.0 - u)
            w = 1.0 - u - v
            q = tuple(u * a[i] + v * b[i] + w * c[i] for i in range(3))
            assert _dist(p, q) >= d_best - 1e-6
    print("ok  1. closest_point_on_triangle (300 triángulos aleatorios vs fuerza bruta)")


def test_no_crossing_and_inpainting():
    bv, bt, _buv, bw = make_body()
    sv, st, _suv = make_skirt()
    MAX_DIST = 2.6   # el bajo (y < -10) queda a > 2.6 de las piernas -> sin match

    weights, matched = transfer_core(bv, bt, bw, sv, max_dist=MAX_DIST)
    n_matched = sum(matched)
    assert 0 < n_matched < len(sv), (n_matched, len(sv))

    # 2) sin cruce: en la zona con match, izquierda pura L (joint 0), derecha pura R (joint 1)
    for i, (v, m) in enumerate(zip(sv, matched)):
        if not m:
            continue
        if v[0] < -1.0:
            assert weights[i].get(1, 0.0) < 1e-9, (i, v, weights[i])
        if v[0] > 1.0:
            assert weights[i].get(0, 0.0) < 1e-9, (i, v, weights[i])
    print(f"ok  2. sin cruce de piernas en {n_matched} vértices con match")

    # 3) inpainting del bajo: normalizado, y el lado izquierdo sigue dominado por L
    adj = adjacency_from_tris(len(sv), st)
    full = inpaint_weights(weights, matched, adj, iterations=800)
    full = clamp_and_normalize(full, max_influences=4)
    n_inpainted = len(matched) - n_matched
    for i, (v, m) in enumerate(zip(sv, matched)):
        assert full[i], f"vértice {i} sin pesos tras inpainting"
        assert abs(sum(full[i].values()) - 1.0) < 1e-6
        assert len(full[i]) <= 4
        if not m and v[0] < -5.0:      # extremo izquierdo del bajo (rx=5.5)
            assert full[i].get(0, 0.0) > 0.9, (i, v, full[i])
        if not m and v[0] > 5.0:       # extremo derecho del bajo
            assert full[i].get(1, 0.0) > 0.9, (i, v, full[i])
    print(f"ok  3. inpainting de {n_inpainted} vértices del bajo: normalizado y coherente por lado")


def test_uv_copy_fails_with_mismatched_layouts():
    """Simula copySkinWeights -uvSpace: nearest neighbour en espacio UV. Con layouts
    distintos (cuerpo por franjas, falda unwrap propio), la correspondencia es basura."""
    bv, bt, buv, bw = make_body()
    sv, _st, suv = make_skirt()

    wrong_uv, considered = 0, 0
    for i, (v, uv) in enumerate(zip(sv, suv)):
        if abs(v[0]) < 1.0 or v[1] < -10.0:   # ignora midline y bajo (sin lado claro)
            continue
        considered += 1
        # nearest neighbour en UV contra los vértices del cuerpo (lo que hace -uvSpace)
        j = min(range(len(buv)),
                key=lambda k: (buv[k][0] - uv[0]) ** 2 + (buv[k][1] - uv[1]) ** 2)
        got = bw[j]
        expected_joint = 0 if v[0] < 0 else 1
        if got.get(expected_joint, 0.0) < 0.5:
            wrong_uv += 1

    frac_wrong = wrong_uv / float(considered)
    # el closest point 3D en la misma zona: 0 errores (probado arriba); por UV, muchos
    assert frac_wrong > 0.25, f"esperaba fallo masivo del UV-copy, salió {frac_wrong:.1%}"
    print(f"ok  4. UV-copy con layouts distintos asigna la pierna equivocada en "
          f"{frac_wrong:.1%} de los vértices laterales (closest point 3D: 0%)")


if __name__ == "__main__":
    test_closest_point_on_triangle()
    test_no_crossing_and_inpainting()
    test_uv_copy_fails_with_mismatched_layouts()
    print("\nTodos los tests del núcleo pasan.")
