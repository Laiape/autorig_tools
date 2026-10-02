# model_qc.py
# Modeling QC for the Character / Asset Manager.
# Workflow (option a):
#   setup_qc(model_path)  -> new scene, import the model, create editable landmark locators
#   run_qc(asset_dir)     -> tech checks + limb plane test + screenshots + PDF in models/feedback
#                            + versioned .ma in models (QC nodes removed before saving)
# All report text is English. Depends on reportlab (installed on demand with mayapy pip).

import os
import re
import sys
import json
import math
import time
import shutil
import subprocess
import collections

import maya.cmds as cmds
import maya.api.OpenMaya as om

try:
    import numpy as np
except ImportError:
    np = None

QC_GRP      = "QC_landmarks_GRP"
QC_TMP_GRP  = "QC_guides_GRP"
LANDMARKS   = ["hip", "knee", "ankle", "shoulder", "elbow", "wrist"]
CHAINS      = {"leg": ("hip", "knee", "ankle"), "arm": ("shoulder", "elbow", "wrist")}
MIN_GPU_VERTS = 2000
NAME_RE     = re.compile(r"^[clrCLR]_[A-Za-z0-9]+_(GEO|GRP)$")
DEFORM_EXCLUDE = re.compile(r"(sclera|pupil|specular|iris|cornea)", re.I)


# -- helpers -----------------------------------------------------------------

def _short(n):
    return n.split("|")[-1]


def _log(msg):
    print("[ModelQC] " + msg)


def _ensure_reportlab():
    try:
        import reportlab  # noqa
        return True
    except ImportError:
        pass
    import site
    mayapy = os.path.join(os.path.dirname(sys.executable), "mayapy.exe")
    if not os.path.exists(mayapy):
        mayapy = os.path.join(os.path.dirname(sys.executable), "mayapy")
    try:
        subprocess.run([mayapy, "-m", "pip", "install", "--user", "reportlab"],
                       capture_output=True, text=True, timeout=600)
    except Exception as e:
        _log("pip install reportlab failed: %s" % e)
    usp = site.getusersitepackages()
    if usp not in sys.path:
        sys.path.append(usp)
    try:
        import reportlab  # noqa
        return True
    except ImportError:
        return False


def find_body_mesh():
    """Transform of the main body mesh: *body_GEO first, else the biggest mesh."""
    meshes = cmds.ls(type="mesh", noIntermediate=True, long=True)
    best, best_n = None, -1
    for m in meshes:
        t = cmds.listRelatives(m, parent=True, fullPath=True)[0]
        if _short(t).lower().endswith("body_geo"):
            return t
        n = cmds.polyEvaluate(m, v=True)
        if n > best_n:
            best, best_n = t, n
    return best


def _mesh_points(transform):
    pts = cmds.xform(transform + ".vtx[*]", q=True, ws=True, t=True)
    return np.array(pts).reshape(-1, 3)


# -- SETUP -------------------------------------------------------------------

def guess_landmarks(body):
    """Approximate humanoid landmarks from the body mesh (user adjusts them after)."""
    P = _mesh_points(body)
    x0, y0, z0, x1, y1, z1 = cmds.exactWorldBoundingBox(body)
    h = y1 - y0
    lm = {}
    try:
        leg = P[(P[:, 0] > 0.02 * h) & (P[:, 0] < 0.16 * h) & (P[:, 1] < y0 + 0.55 * h)]

        def sec(pts, axis, lo, hi):
            s = pts[(pts[:, axis] >= lo) & (pts[:, axis] < hi)]
            return s.mean(axis=0) if len(s) >= 6 else None

        hip = sec(leg, 1, y0 + 0.44 * h, y0 + 0.49 * h)
        ankle = sec(leg, 1, y0 + 0.06 * h, y0 + 0.09 * h)
        knee = None
        if hip is not None and ankle is not None:
            axis = ankle - hip
            axis /= np.linalg.norm(axis)
            best = None
            for y in np.arange(y0 + 0.18 * h, y0 + 0.36 * h, h * 0.01):
                c = sec(leg, 1, y, y + h * 0.01)
                if c is None:
                    continue
                v = c - hip
                perp = v - np.dot(v, axis) * axis
                if best is None or perp[2] > best[0]:
                    best = (perp[2], c)
            knee = best[1] if best else None
        if hip is None or knee is None or ankle is None:
            raise ValueError
        lm["hip"], lm["knee"], lm["ankle"] = hip, knee, ankle

        arm = P[(P[:, 0] > 0.10 * h) & (P[:, 1] > y0 + 0.45 * h)]
        shoulder = sec(arm, 0, 0.10 * h, 0.115 * h)
        xs = arm[:, 0].max()
        wrist = sec(arm, 0, xs - 0.06 * h, xs - 0.05 * h)
        if shoulder is None or wrist is None:
            raise ValueError
        axis = wrist - shoulder
        L = np.linalg.norm(axis)
        axis /= L
        proj = np.dot(arm - shoulder, axis)
        best = None
        for t in np.arange(0.35 * L, 0.7 * L, 1.0):
            s = arm[(proj >= t) & (proj < t + 1.0)]
            if len(s) < 6:
                continue
            c = s.mean(axis=0)
            v = c - shoulder
            perp = v - np.dot(v, axis) * axis
            if best is None or -perp[2] > best[0]:
                best = (-perp[2], c)
        if best is None:
            raise ValueError
        lm["shoulder"], lm["elbow"], lm["wrist"] = shoulder, best[1], wrist
    except Exception:
        lm = {
            "hip":      np.array([0.09 * h, y0 + 0.47 * h, 0.0]),
            "knee":     np.array([0.09 * h, y0 + 0.27 * h, 0.02 * h]),
            "ankle":    np.array([0.09 * h, y0 + 0.07 * h, 0.0]),
            "shoulder": np.array([0.13 * h, y0 + 0.78 * h, 0.0]),
            "elbow":    np.array([0.24 * h, y0 + 0.66 * h, -0.02 * h]),
            "wrist":    np.array([0.36 * h, y0 + 0.55 * h, 0.0]),
        }
    return {k: [float(v) for v in val] for k, val in lm.items()}


def setup_qc(model_path=None):
    """New scene, import the model, create the landmark locators. Returns body mesh."""
    if model_path:
        cmds.file(new=True, force=True)
        ext = os.path.splitext(model_path)[1].lower()
        if ext == ".fbx":
            cmds.loadPlugin("fbxmaya", quiet=True)
            cmds.file(model_path, i=True, type="FBX", ignoreVersion=True, ra=True,
                      mergeNamespacesOnClash=False, namespace=":", options="fbx", pr=True)
        else:
            cmds.file(model_path, i=True, ignoreVersion=True, ra=True,
                      mergeNamespacesOnClash=False, namespace=":", pr=True)
        cmds.optionVar(sv=("modelQC_sourceFile", model_path))
    else:
        cmds.optionVar(sv=("modelQC_sourceFile", cmds.file(q=True, sn=True) or "current scene"))

    if cmds.objExists(QC_GRP):
        cmds.delete(QC_GRP)
    body = find_body_mesh()
    if not body:
        raise RuntimeError("No mesh found in the scene.")
    lm = guess_landmarks(body)
    grp = cmds.group(empty=True, name=QC_GRP)
    x0, y0, z0, x1, y1, z1 = cmds.exactWorldBoundingBox(body)
    ls = max(0.5, (y1 - y0) * 0.012)
    for n in LANDMARKS:
        loc = cmds.spaceLocator(name="L_%s_QC_LOC" % n)[0]
        cmds.xform(loc, ws=True, t=lm[n])
        cmds.setAttr(loc + ".localScale", ls, ls, ls)
        cmds.setAttr(loc + ".overrideEnabled", 1)
        cmds.setAttr(loc + ".overrideColor", 13)
        cmds.parent(loc, grp)
    cmds.select(clear=True)
    cmds.inViewMessage(amg="<hl>Model QC</hl> adjust the 6 landmark locators, then press QC RUN",
                       pos="midCenter", fade=True, fadeStayTime=4000)
    return body


def read_landmarks():
    if not cmds.objExists(QC_GRP):
        return None
    lm = {}
    for n in LANDMARKS:
        loc = "L_%s_QC_LOC" % n
        if not cmds.objExists(loc):
            return None
        lm[n] = cmds.xform(loc, q=True, ws=True, t=True)
    return lm


# -- CHECKS ------------------------------------------------------------------

def _is_deforming(name):
    return not DEFORM_EXCLUDE.search(name)


def check_meshes(model_root=None):
    meshes = cmds.ls(type="mesh", noIntermediate=True, long=True)
    rep = collections.OrderedDict()
    for m in meshes:
        t = cmds.listRelatives(m, parent=True, fullPath=True)[0]
        if model_root and not t.startswith(model_root):
            continue
        s = _short(t)
        d = {"transform": t, "shape": m}
        d["verts"] = cmds.polyEvaluate(m, v=True)
        d["faces"] = cmds.polyEvaluate(m, f=True)
        cmds.select(m, r=True)
        cmds.polySelectConstraint(mode=3, type=0x0008, size=3)
        ng = [f for f in cmds.ls(sl=True, fl=True) if ".f[" in f]
        cmds.polySelectConstraint(disable=True)
        cmds.select(m, r=True)
        cmds.polySelectConstraint(mode=3, type=0x0008, size=1)
        tr = [f for f in cmds.ls(sl=True, fl=True) if ".f[" in f]
        cmds.polySelectConstraint(disable=True)
        cmds.select(clear=True)
        d["ngons"] = len(ng)
        d["ngon_pos"] = [[round(v, 1) for v in cmds.xform(f, q=True, ws=True, t=True)[:3]] for f in ng[:6]]
        d["tris"] = len(tr)
        d["nonmanifold"] = len(cmds.polyInfo(m, nonManifoldEdges=True) or []) + \
                           len(cmds.polyInfo(m, nonManifoldVertices=True) or [])
        d["lamina"] = len(cmds.polyInfo(m, laminaFaces=True) or [])
        hist = [h for h in (cmds.listHistory(m, pruneDagObjects=True) or [])
                if cmds.nodeType(h) not in ("mesh", "shadingEngine", "groupId")]
        d["history"] = sorted(set(cmds.nodeType(h) for h in hist))
        try:
            pn = cmds.getAttr(m + ".pnts[:]")
            d["tweaks"] = sum(1 for p in pn if any(abs(x) > 1e-5 for x in p))
        except Exception:
            d["tweaks"] = 0
        pts = cmds.xform(m + ".vtx[*]", q=True, ws=True, t=True)
        seen = collections.defaultdict(list)
        for i in range(0, len(pts), 3):
            seen[(round(pts[i], 3), round(pts[i + 1], 3), round(pts[i + 2], 3))].append(i // 3)
        ov = {k: v for k, v in seen.items() if len(v) > 1}
        d["overlap"] = sum(len(v) - 1 for v in ov.values())
        d["overlap_pos"] = [list(k) for k in list(ov.keys())[:6]]
        d["minY"] = round(min(pts[1::3]), 3)
        d["SG"] = sorted(set(cmds.listConnections(m, type="shadingEngine") or []))
        d["uvsets"] = cmds.polyUVSet(m, q=True, allUVSets=True) or []
        try:
            fr = cmds.polyNormalPerVertex(m + ".vtx[0]", q=True, freezeNormal=True)
            d["locked_normals"] = bool(fr and fr[0])
        except Exception:
            d["locked_normals"] = False
        tt = cmds.xform(t, q=True, ws=False, t=True)
        rr = cmds.xform(t, q=True, ws=False, ro=True)
        ss = cmds.xform(t, q=True, r=True, s=True)
        pv = cmds.xform(t, q=True, ws=True, rp=True)
        d["t"], d["r"], d["s"], d["pivot"] = [round(v, 2) for v in tt], [round(v, 2) for v in rr], \
                                             [round(v, 3) for v in ss], [round(v, 2) for v in pv]
        d["unfrozen"] = any(abs(v) > 1e-3 for v in tt) or any(abs(v) > 1e-3 for v in rr) or \
                        any(abs(v - 1) > 1e-3 for v in ss)
        d["pivot_off"] = any(abs(v) > 1e-2 for v in pv)
        d["name_ok"] = bool(NAME_RE.match(s)) and s.endswith("_GEO")
        d["deforming"] = _is_deforming(s)
        rep[s] = d
    return rep


def check_groups(model_root):
    out = []
    for t in cmds.ls(model_root, dag=True, long=True, type="transform"):
        if cmds.listRelatives(t, shapes=True):
            continue
        s = _short(t)
        tt = cmds.xform(t, q=True, ws=False, t=True)
        rr = cmds.xform(t, q=True, ws=False, ro=True)
        ss = cmds.xform(t, q=True, r=True, s=True)
        unfrozen = any(abs(v) > 1e-3 for v in tt) or any(abs(v) > 1e-3 for v in rr) or \
                   any(abs(v - 1) > 1e-3 for v in ss)
        name_ok = bool(NAME_RE.match(s)) and s.endswith("_GRP")
        if t == model_root:
            name_ok = True
        out.append({"name": s, "t": [round(v, 2) for v in tt], "r": [round(v, 2) for v in rr],
                    "s": [round(v, 3) for v in ss], "unfrozen": unfrozen, "name_ok": name_ok,
                    "named_geo": s.endswith("_GEO")})
    return out


def check_scene(model_root):
    d = {}
    allt = cmds.ls(model_root, dag=True, long=True)
    cnt = collections.Counter(_short(n) for n in allt)
    d["dup_names"] = sorted(k for k, c in cnt.items() if c > 1)
    d["intermediate"] = [_short(m) for m in cmds.ls(type="mesh", intermediateObjects=True)]
    d["cameras"] = [c for c in cmds.ls(type="camera") if not cmds.camera(c, q=True, startupCamera=True)]
    d["unknown"] = cmds.ls(type="unknown") or []
    d["namespaces"] = [n for n in cmds.namespaceInfo(lon=True, r=True) if n not in ("UI", "shared")]
    sgs = cmds.ls(type="shadingEngine")
    d["unused_SG"] = [s for s in sgs if s not in ("initialShadingGroup", "initialParticleSE")
                      and not cmds.sets(s, q=True)]
    d["n_SG"] = len(sgs)
    d["groupIds"] = cmds.ls(type="groupId") or []
    d["layers"] = [l for l in cmds.ls(type="displayLayer") if l != "defaultLayer"]
    d["sets"] = [s for s in cmds.ls(type="objectSet") if cmds.nodeType(s) == "objectSet"
                 and s not in ("defaultLightSet", "defaultObjectSet")]
    d["mesh_under_mesh"] = []
    for m in cmds.ls(type="mesh", long=True):
        t = cmds.listRelatives(m, parent=True, fullPath=True)[0]
        for anc in t.split("|")[1:-1]:
            if cmds.listRelatives(anc, shapes=True, type="mesh"):
                d["mesh_under_mesh"].append(_short(t))
                break
    d["multi_shape"] = [_short(t) for t in cmds.ls(type="transform", long=True)
                        if len(cmds.listRelatives(t, shapes=True, noIntermediate=True) or []) > 1]
    return d


def check_symmetry(body):
    P = _mesh_points(body)
    L = P[P[:, 0] > 0.05]
    R = P[P[:, 0] < -0.05]
    C = P[np.abs(P[:, 0]) <= 0.05]
    if len(L) == 0 or len(R) == 0:
        return {"symmetric": False, "nL": len(L), "nR": len(R), "nC": len(C), "max": None, "bad": 0}
    Rm = R.copy()
    Rm[:, 0] *= -1
    d = np.empty(len(L))
    for i in range(0, len(L), 400):
        blk = L[i:i + 400]
        dd = np.sqrt(((blk[:, None, :] - Rm[None, :, :]) ** 2).sum(-1))
        d[i:i + 400] = dd.min(axis=1)
    bad = int((d > 0.01).sum())
    return {"symmetric": len(L) == len(R) and bad == 0, "nL": int(len(L)), "nR": int(len(R)),
            "nC": int(len(C)), "max": round(float(d.max()), 3), "bad": bad,
            "bad_sample": [[round(float(v), 2) for v in L[i]] for i in np.where(d > 0.1)[0][:6]]}


def check_poles(body, lm):
    sel = om.MSelectionList()
    sel.add(body)
    it = om.MItMeshVertex(sel.getDagPath(0))
    pts, val = [], []
    while not it.isDone():
        p = it.position(om.MSpace.kWorld)
        pts.append((p.x, p.y, p.z))
        val.append(it.numConnectedEdges())
        it.next()
    pts = np.array(pts)
    val = np.array(val)
    poles = np.where(val != 4)[0]
    x0, y0, z0, x1, y1, z1 = cmds.exactWorldBoundingBox(body)
    rad = (y1 - y0) * 0.05
    out = {"radius": round(rad, 1)}
    for n in ("knee", "elbow", "shoulder", "wrist", "hip"):
        c = np.array(lm[n])
        d = np.linalg.norm(pts[poles] - c, axis=1)
        near = poles[d < rad]
        out[n] = {"count": int(len(near)),
                  "sample": [[int(val[i])] + [round(float(v), 1) for v in pts[i]] for i in near[:4]]}
    return out


def _end_radius(body, point, axis_from):
    """Mean radius of the limb cross-section at `point`, measured around the mid->end axis."""
    P = _mesh_points(body)
    point = np.array(point)
    u = point - np.array(axis_from)
    L = np.linalg.norm(u)
    u /= (L or 1.0)
    rel = P - point
    proj = np.dot(rel, u)
    slab = (np.abs(proj) < max(0.5, 0.04 * L)) & (np.linalg.norm(rel, axis=1) < 0.3 * L)
    if slab.sum() < 6:
        return float(np.sort(np.linalg.norm(rel, axis=1))[:12].mean())
    radial = np.linalg.norm(rel[slab] - np.outer(proj[slab], u), axis=1)
    return float(radial.mean())


def _sao_from_normal(n):
    k = int(np.argmax(np.abs(n)))
    return "xyz"[k] + ("up" if n[k] > 0 else "down")


def limb_plane_test(lm, body, mirror=True):
    """Build 3-joint chains, orient, zero minor axes on the middle joint, measure drift."""
    if cmds.objExists(QC_TMP_GRP):
        cmds.delete(QC_TMP_GRP)
    grp = cmds.group(empty=True, name=QC_TMP_GRP)
    results = {}
    sides = [("L", 1)] + ([("R", -1)] if mirror else [])
    for cname, names in CHAINS.items():
        a, b, c = (np.array(lm[n]) for n in names)
        n_plane = np.cross(b - a, c - b)
        n_plane /= (np.linalg.norm(n_plane) or 1.0)
        ac = c - a
        u = ac / np.linalg.norm(ac)
        pole = (b - a) - np.dot(b - a, u) * u
        pole_len = float(np.linalg.norm(pole))
        # secondary axis: leg -> plane normal (world X-ish); arm -> pole direction (world -Z-ish)
        sao = _sao_from_normal(n_plane if cname == "leg" else pole)
        for side, sign in sides:
            cmds.select(clear=True)
            js = []
            for n in names:
                p = list(lm[n])
                p[0] *= sign
                js.append(cmds.joint(name="%s_%s_QC_JNT" % (side, n), p=p, radius=2.0))
            cmds.parent(js[0], grp)
            cmds.joint(js[0], e=True, oj="xyz", sao=sao, ch=True, zso=True)
            jo = list(cmds.getAttr(js[1] + ".jointOrient")[0])
            k = max(range(3), key=lambda i: abs(jo[i]))
            end_before = np.array(cmds.xform(js[2], q=True, ws=True, t=True))
            clean = [jo[i] if i == k else 0.0 for i in range(3)]
            cmds.setAttr(js[1] + ".jointOrient", *clean)
            end_after = np.array(cmds.xform(js[2], q=True, ws=True, t=True))
            drift = end_after - end_before
            loc = cmds.spaceLocator(name="%s_%s_target_LOC" % (side, names[2]))[0]
            cmds.xform(loc, ws=True, t=list(end_before))
            cmds.setAttr(loc + ".localScale", 2, 2, 2)
            cmds.setAttr(loc + ".overrideEnabled", 1)
            cmds.setAttr(loc + ".overrideColor", 13)
            cmds.parent(loc, grp)
            if side == "L":
                radius = _end_radius(body, end_before, b)
                residual = [abs(jo[i]) for i in range(3) if i != k]
                dl = float(np.linalg.norm(drift))
                verdict = "PASS" if dl <= 0.15 * radius and max(residual) <= 1.0 else \
                          ("PASS, small deviation" if dl <= 0.6 * radius else "FAIL")
                bend_angle = math.degrees(math.acos(np.clip(np.dot((b - a) / np.linalg.norm(b - a),
                                                                    (c - b) / np.linalg.norm(c - b)), -1, 1)))
                results[cname] = {
                    "joints": js, "sao": sao,
                    "orient": [round(v, 2) for v in jo],
                    "orient_clean": [round(v, 2) for v in clean],
                    "bend_axis": "XYZ"[k],
                    "residual": [round(v, 2) for v in residual],
                    "drift": [round(float(v), 2) for v in drift],
                    "drift_len": round(dl, 2),
                    "end_radius": round(radius, 1),
                    "prebend_deg": round(bend_angle, 1),
                    "pole_dir": [round(float(v), 2) for v in (pole / pole_len if pole_len else pole)],
                    "pole_len": round(pole_len, 2),
                    "plane_normal": [round(float(v), 3) for v in n_plane],
                    "verdict": verdict,
                }
    cmds.select(clear=True)
    return results


# -- SCREENSHOTS -------------------------------------------------------------

def _panel():
    for p in cmds.getPanel(type="modelPanel"):
        if cmds.modelPanel(p, q=True, exists=True):
            try:
                cmds.setFocus(p)
                return p
            except Exception:
                continue
    return None


def _shot(panel, cam, path, fit_objs=None, center=None, width=None, size=640, fit=0.9):
    cmds.lookThru(panel, cam)
    if fit_objs:
        cmds.select(fit_objs, r=True)
        cmds.viewFit(cam, f=fit)
    elif center is not None:
        loc = cmds.spaceLocator(name="tmpfit_LOC")[0]
        cmds.xform(loc, ws=True, t=center)
        cmds.select(loc)
        cmds.viewFit(cam, f=1.0)
        cmds.delete(loc)
    if width and cmds.getAttr(cam + ".orthographic"):
        cmds.setAttr(cam + ".orthographicWidth", width)
    cmds.select(clear=True)
    cmds.playblast(frame=cmds.currentTime(q=True), format="image", compression="jpg",
                   completeFilename=path, widthHeight=(size, size), percent=100,
                   forceOverwrite=True, showOrnaments=False, viewer=False, quality=75)
    return path


def take_screenshots(outdir, model_root, body, lm, plane):
    panel = _panel()
    shots = {}
    if not panel:
        return shots
    state = {k: cmds.modelEditor(panel, q=True, **{k: True}) for k in
             ("displayAppearance", "wireframeOnShaded", "jointXray", "grid", "hud", "locators", "joints")}
    cmds.modelEditor(panel, e=True, displayAppearance="smoothShaded", wireframeOnShaded=False,
                     jointXray=True, grid=False, hud=False, locators=True, joints=True, polymeshes=True)
    if cmds.objExists(QC_TMP_GRP):
        cmds.hide(QC_TMP_GRP)
    if cmds.objExists(QC_GRP):
        cmds.hide(QC_GRP)
    for cam in ("front", "side", "persp"):
        shots[cam] = _shot(panel, cam, os.path.join(outdir, "model_%s.jpg" % cam), fit_objs=[model_root], fit=0.95)
    x0, y0, z0, x1, y1, z1 = cmds.exactWorldBoundingBox(body)
    h = y1 - y0
    shots["face"] = _shot(panel, "front", os.path.join(outdir, "face_front.jpg"),
                          center=[0, y1 - 0.08 * h, z1], width=0.25 * h)
    if cmds.objExists(QC_TMP_GRP):
        cmds.showHidden(QC_TMP_GRP)
        others = [t for t in cmds.listRelatives(model_root, children=True, fullPath=True) or []
                  if not t.endswith(_short(body))]
        hidden = []
        for t in others:
            if cmds.getAttr(t + ".visibility"):
                cmds.hide(t)
                hidden.append(t)
        shots["body_guides"] = _shot(panel, "front", os.path.join(outdir, "body_guides_front.jpg"),
                                     fit_objs=[body], fit=0.95)
        leg = plane.get("leg")
        arm = plane.get("arm")
        if leg:
            c = np.mean([lm["hip"], lm["ankle"]], axis=0)
            w = float(np.linalg.norm(np.array(lm["hip"]) - lm["ankle"])) * 1.3
            shots["leg_side"] = _shot(panel, "side", os.path.join(outdir, "leg_side.jpg"), center=list(c), width=w)
            shots["leg_front"] = _shot(panel, "front", os.path.join(outdir, "leg_front.jpg"), center=list(c), width=w)
        if arm:
            c = np.mean([lm["shoulder"], lm["wrist"]], axis=0)
            w = float(np.linalg.norm(np.array(lm["shoulder"]) - lm["wrist"])) * 1.4
            shots["arm_top"] = _shot(panel, "top", os.path.join(outdir, "arm_top.jpg"), center=list(c), width=w)
            shots["arm_front"] = _shot(panel, "front", os.path.join(outdir, "arm_front.jpg"), center=list(c), width=w)
        for t in hidden:
            cmds.showHidden(t)
    cmds.lookThru(panel, "persp")
    try:
        cmds.modelEditor(panel, e=True, **state)
    except Exception:
        cmds.modelEditor(panel, e=True, displayAppearance="smoothShaded", jointXray=False, grid=True)
    return shots


# -- REPORT ------------------------------------------------------------------

def build_findings(asset, source, meshes, groups, scene, sym, poles, plane, body):
    blockers, recs, passed = [], [], []
    ngon = [(k, d["ngons"], d["ngon_pos"]) for k, d in meshes.items() if d["ngons"] and d["deforming"]]
    if ngon:
        blockers.append(("N-gons on deforming meshes",
                         "; ".join("%s: %d n-gons near %s" % (k, n, p[:3]) for k, n, p in ngon) +
                         ". Rebuild as quads."))
    else:
        passed.append(("N-gons", "None on deforming meshes."))
    ov = [(k, d["overlap"], d["overlap_pos"]) for k, d in meshes.items() if d["overlap"]]
    if ov:
        blockers.append(("Vertices in the same position (unmerged seams)",
                         "; ".join("%s: %d pairs near %s" % (k, n, p[:3]) for k, n, p in ov) +
                         ". Merge the vertices (usually the mirror seam)."))
    else:
        passed.append(("Duplicate vertices", "None."))
    nm = [k for k, d in meshes.items() if d["nonmanifold"] or d["lamina"]]
    if nm:
        blockers.append(("Non-manifold or lamina geometry", ", ".join(nm)))
    else:
        passed.append(("Non-manifold, lamina faces", "None on any mesh."))
    hist = [(k, d["history"]) for k, d in meshes.items() if d["history"]]
    if hist:
        blockers.append(("Construction history", "; ".join("%s: %s" % (k, ", ".join(h)) for k, h in hist) + ". Delete history."))
    else:
        passed.append(("Construction history", "None."))
    if scene["intermediate"]:
        blockers.append(("Intermediate shapes", ", ".join(scene["intermediate"])))
    tw = [k for k, d in meshes.items() if d["tweaks"]]
    if tw:
        blockers.append(("Vertex tweaks (pnts)", ", ".join(tw) + ". Freeze or delete history."))
    else:
        passed.append(("Vertex tweaks (pnts)", "All zero."))
    unf = [("%s" % k, d["t"], d["r"], d["s"]) for k, d in meshes.items() if d["unfrozen"]] + \
          [(g["name"] + " (group)", g["t"], g["r"], g["s"]) for g in groups if g["unfrozen"]]
    piv = [k for k, d in meshes.items() if d["pivot_off"]]
    if unf or piv:
        txt = ""
        if unf:
            txt += "Unfrozen: " + "; ".join("%s t=%s r=%s s=%s" % u for u in unf) + ". "
        if piv:
            txt += "Pivot not at the origin: %d meshes (e.g. %s). " % (len(piv), ", ".join(piv[:4]))
        blockers.append(("Transforms not frozen, pivots not at the origin",
                         txt + "Freeze translate, rotate and scale and put every pivot at (0, 0, 0)."))
    else:
        passed.append(("Frozen transforms and pivots at origin", "OK."))
    bad_names = [k for k, d in meshes.items() if not d["name_ok"]] + \
                [g["name"] for g in groups if not g["name_ok"]]
    prefixes = set(k.split("_")[0] for k in list(meshes.keys()) + [g["name"] for g in groups] if "_" in k)
    mixed = len(set(p.lower() for p in prefixes)) != len(prefixes)
    if bad_names or mixed:
        txt = ""
        if bad_names:
            txt += "Not matching side_name_GEO / side_name_GRP: " + ", ".join(bad_names) + ". "
        if mixed:
            txt += "Mixed-case side prefixes (%s): pick one case for the whole asset." % ", ".join(sorted(prefixes))
        blockers.append(("Naming convention", txt))
    else:
        passed.append(("Naming convention", "All nodes follow side_name_GEO / side_name_GRP."))
    ln = [k for k, d in meshes.items() if d["locked_normals"]]
    if ln:
        blockers.append(("Locked vertex normals", "%d of %d meshes (%s). Locked normals do not update on deformation. "
                         "Unlock them (Mesh Display > Unlock Normals). FBX export locks normals; deliver a Maya scene." %
                         (len(ln), len(meshes), ", ".join(ln[:5]) + ("..." if len(ln) > 5 else ""))))
    else:
        passed.append(("Vertex normals", "Unlocked on every mesh."))
    if scene["dup_names"]:
        blockers.append(("Duplicate node names", ", ".join(scene["dup_names"])))
    else:
        passed.append(("Duplicate names", "None."))
    if scene["namespaces"] or scene["unknown"]:
        blockers.append(("Namespaces or unknown nodes", "namespaces: %s; unknown: %s" % (scene["namespaces"], scene["unknown"])))
    else:
        passed.append(("Namespaces, unknown nodes", "None."))
    if scene["mesh_under_mesh"] or scene["multi_shape"]:
        blockers.append(("Hierarchy", "mesh under mesh: %s; several shapes on one transform: %s" %
                         (scene["mesh_under_mesh"], scene["multi_shape"])))
    else:
        passed.append(("One shape per transform, no mesh under a mesh", "OK."))
    if sym["max"] is None:
        recs.append(("Symmetry", "Body mesh has no left/right split; not checked."))
    elif sym["symmetric"]:
        passed.append(("Body symmetry", "%d vertices per side, %d on the center line, max deviation %.3f cm." %
                       (sym["nL"], sym["nC"], sym["max"])))
    else:
        blockers.append(("Body symmetry", "L=%d R=%d, %d vertices deviate more than 0.01 cm (max %.3f), e.g. %s. Mirror the body." %
                         (sym["nL"], sym["nR"], sym["bad"], sym["max"], sym.get("bad_sample", [])[:3])))
    if source and source.lower().endswith(".fbx"):
        blockers.append(("Delivery format", "Only an FBX was delivered. Deliver a Maya ASCII (.ma) scene."))
    tris = [(k, d["tris"]) for k, d in meshes.items() if d["tris"] and d["deforming"]]
    if tris:
        recs.append(("Triangles on deforming meshes", "; ".join("%s: %d" % t for t in tris) + ". Convert to quads where the mesh deforms."))
    else:
        passed.append(("Triangles", "None on deforming meshes."))
    small = [k for k, d in meshes.items() if d["verts"] < MIN_GPU_VERTS]
    if small:
        recs.append(("Meshes under %d vertices" % MIN_GPU_VERTS, "%d of %d meshes. Deformers on these run on the CPU. Combine meshes that deform together (e.g. %s)." %
                     (len(small), len(meshes), ", ".join(small[:5]))))
    miny = min(d["minY"] for d in meshes.values())
    if abs(miny) > 0.1:
        recs.append(("Ground contact", "Lowest point at Y = %.3f. Snap the sole to Y = 0." % miny))
    else:
        passed.append(("Ground contact", "Lowest point at Y = %.3f." % miny))
    multi = [(k, len(d["SG"])) for k, d in meshes.items() if len(d["SG"]) > 1]
    if multi or scene["groupIds"]:
        recs.append(("Per-face material assignment", "%s; %d groupId nodes. One material per mesh unless lookdev needs the split." %
                     ("; ".join("%s: %d shading groups" % m for m in multi), len(scene["groupIds"]))))
    if scene["unused_SG"] or scene["cameras"] or scene["layers"] or scene["sets"]:
        recs.append(("Extra nodes", "unused shaders: %s; cameras: %s; layers: %s; sets: %s. Clean up." %
                     (scene["unused_SG"], scene["cameras"], scene["layers"], scene["sets"])))
    else:
        passed.append(("Unused shaders, extra cameras, layers, sets", "None (%d shading groups, all assigned)." % scene["n_SG"]))
    pole_txt = []
    for n in ("knee", "elbow", "shoulder", "wrist", "hip"):
        if poles[n]["count"]:
            pole_txt.append("%s: %d poles within %.0f cm (valence, x, y, z: %s)" %
                            (n, poles[n]["count"], poles["radius"], poles[n]["sample"][:2]))
    if pole_txt:
        recs.append(("Poles near deformation areas", "; ".join(pole_txt) + ". Keep poles off the fold loops."))
    else:
        passed.append(("Poles near knees, elbows, shoulders, wrists", "None within %.0f cm." % poles["radius"]))
    for cname, r in plane.items():
        if r["verdict"] == "FAIL":
            blockers.append(("Limb plane: %s" % cname, "Middle joint keeps %s deg on the minor axes; end guide drifts %.2f cm (limb radius %.1f cm). "
                             "Realign the %s so the bend happens in one plane." % (r["residual"], r["drift_len"], r["end_radius"], cname)))
        elif r["verdict"].startswith("PASS, small"):
            recs.append(("Limb plane alignment: %s" % cname, "Passes with a small deviation: %s deg on the minor axes, end guide drifts %.2f cm "
                         "(limb radius %.1f cm). Optional: move the %s so the three landmarks share one plane." %
                         (r["residual"], r["drift_len"], r["end_radius"], cname)))
        if r["prebend_deg"] > 20:
            recs.append(("Pre-bend: %s" % cname, "%.1f degrees. 5 to 10 degrees is enough for the IK solver." % r["prebend_deg"]))
    passed.append(("Neutral expression, feet direction, cloth/body elbow match", "Visual check by the reviewer. See screenshots."))
    return blockers, recs, passed


def write_pdf(path, asset, source, version, blockers, recs, passed, plane, meshes, shots, body_name):
    if not _ensure_reportlab():
        raise RuntimeError("reportlab is not available and could not be installed.")
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image

    ss = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=15, spaceAfter=6, spaceBefore=10)
    H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12, spaceAfter=4, spaceBefore=8)
    B = ParagraphStyle("B", parent=ss["Normal"], fontSize=9.5, leading=13)
    SM = ParagraphStyle("SM", parent=B, fontSize=8, leading=10, textColor=colors.HexColor("#444444"))
    CAP = ParagraphStyle("CAP", parent=SM, alignment=1)

    def esc(t):
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def P(t, s=B):
        return Paragraph(esc(t), s)

    def tbl(data, widths, header=True, font=8.5):
        cs = ParagraphStyle("cell", parent=B, fontSize=font, leading=font + 2.5)
        hs = ParagraphStyle("hcell", parent=cs, fontName="Helvetica-Bold")
        rows = [[Paragraph(esc(c).replace("\n", "<br/>"), hs if (header and r == 0) else cs) for c in row]
                for r, row in enumerate(data)]
        t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
        st = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#999999")),
              ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
        if header:
            st.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6e6e6")))
        t.setStyle(TableStyle(st))
        return t

    def img(key, w=80 * mm):
        p = shots.get(key)
        return Image(p, width=w, height=w) if p and os.path.exists(p) else Spacer(w, w)

    def pair(a, ca, b, cb, w=80 * mm):
        t = Table([[img(a, w), img(b, w)], [P(ca, CAP), P(cb, CAP)]], colWidths=[w + 4 * mm, w + 4 * mm])
        t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    status = "NOT APPROVED. Fix the items in section 2 and resubmit. Items in section 3 are recommended." \
        if blockers else "APPROVED for rigging. Items in section 3 are recommended."
    nverts = sum(d["verts"] for d in meshes.values())
    S = [P("%s. Modeling QC Feedback" % asset, ss["Title"]),
         tbl([["Asset", asset], ["Reviewed file", "%s (%d meshes, %s vertices)" % (source, len(meshes), format(nverts, ","))],
              ["Body mesh used for symmetry and limb tests", body_name],
              ["Reference", "Modeling QC Checklist (Topology/Model design checks, Tech checks)"],
              ["Reviewed by", "Rigging department (automated Model QC v%s)" % version], ["Date", time.strftime("%d %B %Y")],
              ["Status", status]], [35 * mm, 139 * mm], header=False, font=9),
         Spacer(1, 6), P("1. Summary", H1),
         P("%d blocking issues, %d recommendations, %d checks passed. Blocking issues must be fixed before rigging starts." %
           (len(blockers), len(recs), len(passed))),
         pair("front", "Front view.", "side", "Side view. The character should face +Z."),
         P("2. Must fix (blockers)", H1)]
    if blockers:
        for i, (t, d) in enumerate(blockers, 1):
            S.append(P("2.%d %s" % (i, t), H2))
            S.append(P(d))
    else:
        S.append(P("None."))
    S.append(P("3. Should fix (recommended)", H1))
    if recs:
        for i, (t, d) in enumerate(recs, 1):
            S.append(P("3.%d %s" % (i, t), H2))
            S.append(P(d))
    else:
        S.append(P("None."))
    S.append(PageBreak())
    S.append(P("4. Limb plane check (single rotation axis)", H1))
    S.append(P("Method: a 3-joint chain is placed on each limb (hip, knee, ankle and shoulder, elbow, wrist) on the landmark "
               "locators. The chain is oriented with Orient Joint (primary X down the chain, secondary axis toward the bending "
               "plane). A limb is in one plane when the middle joint carries rotation on one axis only. The root can have any "
               "orientation. The two minor axes of the middle joint are then set to 0 and the drift of the end guide is measured. "
               "Pass: the end guide stays approximately in place, inside the limb volume and close to its center."))
    rows = [["Chain", "Middle joint orient (X, Y, Z) after Orient Joint", "Orient with the other axes at 0", "Residual removed",
             "End guide drift after zeroing", "Pass"]]
    for cname in ("leg", "arm"):
        r = plane.get(cname)
        if not r:
            continue
        mid = CHAINS[cname][1]
        end = CHAINS[cname][2]
        rows.append([cname.capitalize(), "%s: %s" % (mid, ", ".join(str(v) for v in r["orient"])),
                     "%s: %s (%s only)" % (mid, ", ".join(str(v) for v in r["orient_clean"]), r["bend_axis"]),
                     ", ".join("%.2f deg" % v for v in r["residual"]),
                     "%s moves %.2f cm (%s); %s radius about %.1f cm" % (end, r["drift_len"], r["drift"], end, r["end_radius"]),
                     "YES" if r["verdict"] == "PASS" else ("YES, small deviation" if r["verdict"].startswith("PASS") else "NO")])
    S.append(tbl(rows, [20 * mm, 38 * mm, 34 * mm, 28 * mm, 34 * mm, 20 * mm], font=7.5))
    for cname in ("leg", "arm"):
        r = plane.get(cname)
        if r:
            S.append(P("%s: bend axis %s, pre-bend %.1f degrees, pole direction %s (offset %.2f cm), plane normal %s, secondary axis %s. Verdict: %s." %
                       (cname.capitalize(), r["bend_axis"], r["prebend_deg"], r["pole_dir"], r["pole_len"], r["plane_normal"], r["sao"], r["verdict"]), SM))
    S.append(Spacer(1, 4))
    S.append(pair("leg_side", "Leg chain, side view. Red locator: ankle landmark.", "leg_front", "Leg chain, front view, after zeroing the minor axes."))
    S.append(pair("arm_top", "Arm chain, top view. Red locator: wrist landmark.", "arm_front", "Arm chain, front view, after zeroing the minor axes."))
    S.append(PageBreak())
    S.append(P("5. Checks passed", H1))
    S.append(tbl([["Check", "Result"]] + [[t, d] for t, d in passed], [72 * mm, 102 * mm]))
    S.append(pair("body_guides", "Body mesh with the guide chains.", "face", "Face, expression check."))
    S.append(P("6. Per-mesh summary", H1))
    rows = [["Mesh", "Verts", "Flags"]]
    for k, d in meshes.items():
        fl = []
        if d["ngons"]: fl.append("%d n-gons" % d["ngons"])
        if d["tris"]: fl.append("%d tris" % d["tris"])
        if d["overlap"]: fl.append("%d duplicate verts" % d["overlap"])
        if d["nonmanifold"]: fl.append("non-manifold")
        if d["lamina"]: fl.append("lamina")
        if d["history"]: fl.append("history")
        if d["tweaks"]: fl.append("tweaks")
        if d["unfrozen"]: fl.append("unfrozen")
        if d["pivot_off"]: fl.append("pivot off origin")
        if not d["name_ok"]: fl.append("name")
        if d["locked_normals"]: fl.append("locked normals")
        if len(d["SG"]) > 1: fl.append("%d materials" % len(d["SG"]))
        rows.append([k, str(d["verts"]), ", ".join(fl) or "clean"])
    S.append(tbl(rows, [58 * mm, 18 * mm, 98 * mm], font=7.5))
    S.append(Spacer(1, 8))
    S.append(P("Resubmission: deliver the asset as a Maya ASCII scene with section 2 fixed. Rigging will re-run this check before starting the rig."))
    SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                      title="%s Modeling QC Feedback v%s" % (asset, version), author="Rigging").build(S)
    return path


# -- MAIN --------------------------------------------------------------------

def _next_version(models_dir, asset):
    files = [f for f in os.listdir(models_dir) if f.endswith(".ma")]
    ver = 1
    if files:
        files.sort()
        try:
            ver = int(files[-1].split("_v")[-1].split(".")[0]) + 1
        except Exception:
            pass
    return ver


def run_qc(asset_dir, save_model=True):
    if np is None:
        raise RuntimeError("numpy is required (ships with Maya 2022+).")
    lm = read_landmarks()
    if not lm:
        raise RuntimeError("Landmark locators not found. Run QC SETUP first.")
    asset = os.path.basename(asset_dir.rstrip("/\\"))
    models_dir = os.path.join(asset_dir, "models")
    fb_dir = os.path.join(models_dir, "feedback")
    os.makedirs(fb_dir, exist_ok=True)
    ver = _next_version(models_dir, asset)
    tmp = os.path.join(fb_dir, "_shots_v%03d" % ver)
    os.makedirs(tmp, exist_ok=True)
    source = cmds.optionVar(q="modelQC_sourceFile") or (cmds.file(q=True, sn=True) or "current scene")

    body = find_body_mesh()
    roots = [t for t in cmds.ls(assemblies=True, long=True)
             if t not in ("|persp", "|top", "|front", "|side") and t != "|" + QC_GRP and t != "|" + QC_TMP_GRP]
    model_root = roots[0] if len(roots) == 1 else None
    if model_root is None:
        model_root = "|" + body.split("|")[1]

    _log("checking meshes")
    meshes = check_meshes(model_root)
    groups = check_groups(model_root)
    scene = check_scene(model_root)
    sym = check_symmetry(body)
    poles = check_poles(body, lm)
    _log("limb plane test")
    plane = limb_plane_test(lm, body)
    _log("screenshots")
    shots = take_screenshots(tmp, model_root, body, lm, plane)
    blockers, recs, passed = build_findings(asset, source, meshes, groups, scene, sym, poles, plane, body)
    if len(roots) > 1:
        blockers.insert(0, ("Several top groups", "The model must live under a single top group. Found: %s" % ", ".join(_short(r) for r in roots)))
    pdf = os.path.join(fb_dir, "%s_QC_v%03d.pdf" % (asset, ver))
    _log("writing pdf")
    write_pdf(pdf, asset, source, "%03d" % ver, blockers, recs, passed, plane, meshes, shots, _short(body))
    json.dump({"landmarks": lm, "plane": {k: {kk: vv for kk, vv in v.items() if kk != "joints"} for k, v in plane.items()},
               "blockers": blockers, "recommended": recs, "passed": passed},
              open(os.path.join(fb_dir, "%s_QC_v%03d.json" % (asset, ver)), "w"), indent=1)
    for g in (QC_TMP_GRP, QC_GRP):
        if cmds.objExists(g):
            cmds.delete(g)
    ma = None
    if save_model:
        ma = os.path.join(models_dir, "%s_v%03d.ma" % (asset, ver)).replace("\\", "/")
        cmds.file(rename=ma)
        cmds.file(save=True, type="mayaAscii", force=True)
    cmds.inViewMessage(amg="<hl>Model QC</hl> %s  |  %d blockers, %d recommendations" % (os.path.basename(pdf), len(blockers), len(recs)),
                       pos="midCenter", fade=True, fadeStayTime=5000)
    return {"pdf": pdf, "ma": ma, "blockers": blockers, "recommended": recs, "passed": passed, "plane": plane}
