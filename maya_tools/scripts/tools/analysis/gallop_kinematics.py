"""
Cinematica de galope desde metraje -> los MISMOS angulos que mide el rig.

Convierte los landmarks 2D digitalizados de un video lateral de galope (uno por
articulacion y frame) en los angulos interiores codo / carpo / menudillo, para
comparar el caballo REAL contra los solvers del rig en las mismas unidades.

Los angulos se calculan igual que el test headless del rig:
    angulo interior en B = angulo entre (A-B) y (C-B)
asi el numero del video y el del rig son directamente comparables.

USO
  1) Digitaliza el video (Kinovea / DLTdv / a mano) y exporta un CSV con una
     fila por frame y estas columnas (pixeles, vista lateral):
         frame, sh_x, sh_y, el_x, el_y, ca_x, ca_y, fe_x, fe_y, ho_x, ho_y
     sh=hombro  el=codo  ca=carpo  fe=menudillo  ho=casco
  2) python gallop_kinematics.py  ruta/al/export.csv
  3) sin argumento corre el demo con datos sinteticos + autocomprobacion.

La Y de pixeles crece hacia ABAJO; el angulo interior es invariante al signo,
asi que no hace falta voltearla.
"""
import csv
import math
import sys

# Angulos de galope recogido que da el RIG (medido headless, pata delantera).
# Referencia para el print comparativo; no entra en el calculo del video.
RIG_GALOPE = {
    "spring":          {"codo": 78.8,  "carpo": 95.3},
    "rp":              {"codo": 161.2, "carpo": 170.7},
    "sc_rp_sc":        {"codo": 83.9,  "carpo": 180.0},
    "sc_rp_sc_carpus": {"codo": 121.1, "carpo": 65.7},
}

LANDMARKS = ["sh", "el", "ca", "fe", "ho"]  # hombro, codo, carpo, menudillo, casco
JOINTS = [  # (nombre, A, vertice B, C)  -> angulo interior en B
    ("codo",     "sh", "el", "ca"),
    ("carpo",    "el", "ca", "fe"),
    ("menudillo", "ca", "fe", "ho"),
]


def interior_angle(a, b, c):
    """Angulo interior (grados) en b entre los segmentos b->a y b->c. 2D."""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return float("nan")
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    cos = max(-1.0, min(1.0, cos))
    return math.degrees(math.acos(cos))


def read_frames(path):
    """Devuelve lista de dicts {frame, sh:(x,y), el:(x,y), ...}."""
    frames = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            rec = {"frame": int(float(row["frame"]))}
            for lm in LANDMARKS:
                rec[lm] = (float(row[f"{lm}_x"]), float(row[f"{lm}_y"]))
            frames.append(rec)
    frames.sort(key=lambda r: r["frame"])
    return frames


def joint_series(frames):
    """{joint: [(pct_stride, angulo), ...]} sobre el ciclo digitalizado."""
    n = len(frames)
    series = {name: [] for name, *_ in JOINTS}
    for i, rec in enumerate(frames):
        pct = 0.0 if n == 1 else round(100.0 * i / (n - 1), 1)
        for name, a, b, c in JOINTS:
            series[name].append((pct, round(interior_angle(rec[a], rec[b], rec[c]), 1)))
    return series


def summarize(series):
    """Por articulacion: pico de FLEXION (angulo minimo), su %stride, y ROM."""
    out = {}
    for name, pts in series.items():
        angs = [a for _, a in pts if a == a]  # descarta NaN
        if not angs:
            out[name] = None
            continue
        pk = min(pts, key=lambda p: p[1])
        out[name] = {
            "flexion_pico": pk[1],
            "en_pct_stride": pk[0],
            "extension_max": max(angs),
            "ROM": round(max(angs) - min(angs), 1),
        }
    return out


def report(summary):
    print("\n=== CINEMATICA DE GALOPE (medida del video) ===")
    print(f"{'articulacion':<12}{'flexion pico':>13}{'%stride':>9}{'ROM':>8}")
    for name, *_ in JOINTS:
        s = summary.get(name)
        if not s:
            print(f"{name:<12}{'sin datos':>13}")
            continue
        print(f"{name:<12}{s['flexion_pico']:>11}°{s['en_pct_stride']:>8}%{s['ROM']:>7}°")

    codo = summary.get("codo"); carpo = summary.get("carpo")
    if codo and carpo and codo["ROM"] > 0.5:
        ratio = round(carpo["ROM"] / codo["ROM"], 2)
        print(f"\nDominancia carpo/codo (ROM): {ratio}x")
        print("  -> valida 'el carpo domina' si es claramente > 1")
        if carpo["en_pct_stride"] < codo["en_pct_stride"]:
            print("  -> el carpo alcanza su pico ANTES que el codo (protraccion): coincide")

    print("\n=== RIG, galope recogido (para comparar, codo / carpo) ===")
    for solver, v in RIG_GALOPE.items():
        print(f"  {solver:<16} codo {v['codo']:>6}°   carpo {v['carpo']:>6}°")
    if carpo:
        print(f"\n  video: carpo flexion pico {carpo['flexion_pico']}°  "
              f"(el rig que mas se acerca gana la validacion)")


def demo():
    """Datos sinteticos de un cuarto de stride en vuelo + autocomprobacion.
    El carpo se pliega mucho (brazo distal recogido), el codo poco."""
    # posiciones aproximadas (px), 4 frames de protraccion a flexion maxima
    frames = [
        {"frame": 0, "sh": (100, 100), "el": (108, 160), "ca": (104, 220), "fe": (100, 278), "ho": (98, 330)},
        {"frame": 1, "sh": (100, 100), "el": (110, 160), "ca": (120, 214), "fe": (150, 232), "ho": (188, 250)},
        {"frame": 2, "sh": (100, 100), "el": (112, 160), "ca": (138, 206), "fe": (176, 190), "ho": (210, 165)},
        {"frame": 3, "sh": (100, 100), "el": (114, 160), "ca": (150, 200), "fe": (150, 156), "ho": (120, 150)},
    ]
    series = joint_series(frames)
    summary = summarize(series)
    report(summary)

    # el carpo debe DOMINAR: mucho mas ROM que el codo (la afirmacion a validar)
    assert summary["carpo"]["ROM"] > 2 * summary["codo"]["ROM"], "el carpo deberia dominar al codo"
    print("\n[demo OK] el carpo domina al codo (ROM %.0f vs %.0f), como debe."
          % (summary["carpo"]["ROM"], summary["codo"]["ROM"]))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        report(summarize(joint_series(read_frames(sys.argv[1]))))
    else:
        print("(sin CSV: corriendo demo con datos sinteticos)")
        demo()
