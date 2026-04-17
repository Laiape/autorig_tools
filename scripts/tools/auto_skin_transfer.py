"""
auto_skin_transfer.py
=====================
Topology-independent skinning transfer using skeleton-relative UV projection.

Five modules + orchestrator:

  Module 1  UVMatchingModule      — temporary skeleton-relative / cylindrical /
                                    planar UVs on source and target.
  Module 2  SkinSamplingModule    — reads source skin, builds a queryable UV
                                    weight map (SkinUVMap).
  Module 3  JointMappingModule    — matches source ↔ target joints by name,
                                    spatial proximity or both.
  Module 4  WeightProjectionModule — transfers weights to target via KNN lookup
                                     in UV space with IDW blending.
  Module 5  RefinementModule      — smoothing, max-influence clamping, extra
                                     passes on critical flex zones.

  AutoSkinTransferSystem          — orchestrator with optional progress callback.

Quick usage
-----------
    from tools import auto_skin_transfer
    sys = auto_skin_transfer.AutoSkinTransferSystem()
    sys.transfer("source_mesh", "target_mesh")
"""

import math
import re
import os
import json

import maya.cmds as cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

_LOG  = om.MGlobal.displayInfo
_WARN = om.MGlobal.displayWarning
_ERR  = om.MGlobal.displayError


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 1 · UV MATCHING
# ─────────────────────────────────────────────────────────────────────────────

class UVMatchingModule:
    """
    Generates a temporary "skinTransfer_UV" set on both meshes.

    Three projection strategies are available:

    ``skeleton``   (default / recommended)
        Each vertex is projected onto its nearest bone segment.
        U = (joint_DFS_index + t_along_bone) / total_joints
        V = angle_around_bone_axis / 2π + 0.5
        Scale- and topology-independent. Works across different character sizes.

    ``cylindrical``
        Maya-native cylindrical projection along the skeleton's dominant axis.
        Fast but less accurate for highly asymmetric characters.

    ``planar``
        Maya-native planar (orthographic) projection along Y.
        Useful for flat meshes or quick tests.
    """

    UV_SET  = "skinTransfer_UV"
    METHODS = ("skeleton", "cylindrical", "planar")

    # ── public ──────────────────────────────────────────────────────────────

    def build(self, source_mesh, target_mesh, joint_data, method="skeleton"):
        """
        Builds skinTransfer_UV on both meshes.

        Args:
            source_mesh (str):        Maya transform.
            target_mesh (str):        Maya transform.
            joint_data  (list[dict]): Output of JointZoneAnalyzer.analyze().
            method      (str):        "skeleton" | "cylindrical" | "planar".

        Returns:
            bool: True on success.
        """
        for mesh in (source_mesh, target_mesh):
            if method == "skeleton":
                ok = self._project_skeleton(mesh, joint_data)
            elif method == "cylindrical":
                ok = self._project_cylindrical(mesh, joint_data)
            else:
                ok = self._project_planar(mesh, joint_data)

            if not ok:
                return False

        return True

    def get_uv_coords(self, mesh):
        """
        Returns (U, V) as (N,) float64 numpy arrays, indexed by vertex id.
        ``build`` must have been called first.
        """
        shape = self._get_shape(mesh)
        existing = cmds.polyUVSet(shape, q=True, allUVSets=True) or []
        if self.UV_SET not in existing:
            raise RuntimeError(f"'{self.UV_SET}' not found on '{mesh}' — call build() first")

        cmds.polyUVSet(shape, currentUVSet=True, uvSet=self.UV_SET)

        sel = om.MSelectionList()
        sel.add(shape)
        mf = om.MFnMesh(sel.getDagPath(0))

        us, vs         = mf.getUVs(self.UV_SET)
        _, fv_ids      = mf.getVertices()
        _, uv_ids      = mf.getAssignedUVs(self.UV_SET)

        n = mf.numVertices
        u_out = np.zeros(n, dtype=float)
        v_out = np.zeros(n, dtype=float)
        done  = np.zeros(n, dtype=bool)

        for i, vid in enumerate(fv_ids):
            if not done[vid]:
                uid      = uv_ids[i]
                u_out[vid] = float(us[uid])
                v_out[vid] = float(vs[uid])
                done[vid]  = True

        return u_out, v_out

    def cleanup(self, mesh):
        shape = self._get_shape(mesh)
        if not shape:
            return
        existing = cmds.polyUVSet(shape, q=True, allUVSets=True) or []
        if self.UV_SET in existing:
            cmds.polyUVSet(shape, delete=True, uvSet=self.UV_SET)

    # ── private ─────────────────────────────────────────────────────────────

    def _ensure_uv_set(self, shape):
        existing = cmds.polyUVSet(shape, q=True, allUVSets=True) or []
        if self.UV_SET not in existing:
            cmds.polyUVSet(shape, create=True, uvSet=self.UV_SET)
        cmds.polyUVSet(shape, currentUVSet=True, uvSet=self.UV_SET)

    def _project_skeleton(self, mesh, joint_data):
        """Vectorised skeleton-relative projection."""
        shape = self._get_shape(mesh)
        if not shape:
            _ERR(f"UVMatchingModule: no shape for '{mesh}'")
            return False

        self._ensure_uv_set(shape)

        sel = om.MSelectionList()
        sel.add(shape)
        dag = sel.getDagPath(0)
        mf  = om.MFnMesh(dag)
        pts = mf.getPoints(om.MSpace.kWorld)
        nv  = mf.numVertices

        vtx = np.array([[pts[i].x, pts[i].y, pts[i].z] for i in range(nv)], dtype=float)

        # Build bone table
        bones = []
        for jd in joint_data:
            if jd["parent_pos"] is None:
                continue
            s = np.array(jd["parent_pos"], dtype=float)
            e = np.array(jd["world_pos"],  dtype=float)
            v = e - s
            L = float(np.linalg.norm(v))
            if L < 1e-6:
                continue
            d = v / L
            cands = [np.array([0.,1.,0.]), np.array([1.,0.,0.]), np.array([0.,0.,1.])]
            up_c  = min(cands, key=lambda c: abs(float(np.dot(c, d))))
            right = np.cross(d, up_c); right /= np.linalg.norm(right)
            up    = np.cross(right, d)
            bones.append({
                "s": s, "d": d, "L": L, "r": right, "u": up,
                "j_idx": jd["index"], "N": jd["num_total"],
            })

        if not bones:
            # Single-influence fallback: mesh is pinned to one leaf joint
            # with no parent in the influence list.
            # Build a synthetic bone along the mesh's dominant axis so
            # the projection can still run.
            if joint_data:
                jd = joint_data[0]
                wp  = np.array(jd["world_pos"], dtype=float)
                # Use mesh bounding-box center as base and joint pos as tip
                bb  = cmds.xform(mesh, q=True, ws=True, bb=True)
                ctr = np.array([(bb[0]+bb[3])/2, bb[1], (bb[2]+bb[5])/2], dtype=float)
                vec = wp - ctr
                L   = float(np.linalg.norm(vec))
                if L < 1e-4:
                    vec = np.array([0., 1., 0.], dtype=float); L = 1.0
                d = vec / L
                cands = [np.array([0.,1.,0.]), np.array([1.,0.,0.]), np.array([0.,0.,1.])]
                up_c  = min(cands, key=lambda c: abs(float(np.dot(c, d))))
                right = np.cross(d, up_c); right /= np.linalg.norm(right)
                up    = np.cross(right, d)
                bones.append({"s": ctr, "d": d, "L": L, "r": right, "u": up,
                              "j_idx": 0, "N": 1})
                _WARN(f"UVMatchingModule: single-influence mesh '{mesh}' — "
                      f"using synthetic bone from bbox-base to '{jd['name']}'")
            else:
                _ERR(f"UVMatchingModule: no valid bones for '{mesh}'")
                return False

        best_d2 = np.full(nv, np.inf)
        best_u  = np.zeros(nv)
        best_v  = np.full(nv, 0.5)

        for b in bones:
            to_s = vtx - b["s"]
            t    = np.clip(np.dot(to_s, b["d"]) / b["L"], 0., 1.)
            cl   = b["s"] + t[:, None] * (b["d"] * b["L"])
            diff = vtx - cl
            d2   = np.einsum("ij,ij->i", diff, diff)
            mask = d2 < best_d2
            if not np.any(mask):
                continue

            span  = 1.0 / b["N"]
            u_new = b["j_idx"] / b["N"] + span * t

            perp  = diff - np.einsum("ij,j->i", diff, b["d"])[:, None] * b["d"]
            norms = np.linalg.norm(perp, axis=1)
            valid = norms > 1e-6
            px    = np.where(valid, np.einsum("ij,j->i", perp, b["r"]), 0.)
            py    = np.where(valid, np.einsum("ij,j->i", perp, b["u"]), 0.)
            v_new = np.where(valid, np.arctan2(py, px) / (2.*math.pi) + 0.5, 0.5)

            best_d2 = np.where(mask, d2,    best_d2)
            best_u  = np.where(mask, u_new, best_u)
            best_v  = np.where(mask, v_new, best_v)

        u_fa = om.MFloatArray(nv, 0.0)
        v_fa = om.MFloatArray(nv, 0.0)
        for i in range(nv):
            u_fa[i] = float(best_u[i]); v_fa[i] = float(best_v[i])

        mf.setUVs(u_fa, v_fa, self.UV_SET)
        fc, fv = mf.getVertices()
        uid_arr = om.MIntArray(len(fv), 0)
        for i, vid in enumerate(fv):
            uid_arr[i] = int(vid)
        mf.assignUVs(fc, uid_arr, self.UV_SET)
        _LOG(f"UVMatchingModule [skeleton]: '{mesh}' ({nv} verts, {len(bones)} bones)")
        return True

    def _project_cylindrical(self, mesh, joint_data):
        """Maya built-in cylindrical projection, normalised to 0-1."""
        shape = self._get_shape(mesh)
        if not shape:
            return False
        self._ensure_uv_set(shape)

        # Determine dominant axis from skeleton
        axis = self._dominant_axis(joint_data)
        bb   = cmds.xform(mesh, q=True, ws=True, bb=True)  # xmin,ymin,zmin,xmax,ymax,zmax
        cx   = (bb[0]+bb[3])/2; cy = (bb[1]+bb[4])/2; cz = (bb[2]+bb[5])/2

        cmds.select(mesh)
        cmds.polyProjection(
            shape + ".f[*]", type="Cylindrical",
            md=axis, uvSetName=self.UV_SET,
            ibd=True, kir=False
        )
        self._normalize_uvs(shape)
        cmds.select(clear=True)
        _LOG(f"UVMatchingModule [cylindrical/{axis}]: '{mesh}'")
        return True

    def _project_planar(self, mesh, joint_data):
        """Maya built-in planar projection, normalised to 0-1."""
        shape = self._get_shape(mesh)
        if not shape:
            return False
        self._ensure_uv_set(shape)
        axis = self._dominant_axis(joint_data)
        cmds.select(mesh)
        cmds.polyProjection(
            shape + ".f[*]", type="Planar",
            md=axis, uvSetName=self.UV_SET,
            ibd=True
        )
        self._normalize_uvs(shape)
        cmds.select(clear=True)
        _LOG(f"UVMatchingModule [planar/{axis}]: '{mesh}'")
        return True

    def _normalize_uvs(self, shape):
        """Rescales the current UV set to [0,1] × [0,1]."""
        sel = om.MSelectionList(); sel.add(shape)
        mf  = om.MFnMesh(sel.getDagPath(0))
        us, vs = mf.getUVs(self.UV_SET)
        u_arr = list(us); v_arr = list(vs)
        if not u_arr:
            return
        mn_u, mx_u = min(u_arr), max(u_arr)
        mn_v, mx_v = min(v_arr), max(v_arr)
        ru = (mx_u - mn_u) or 1.0
        rv = (mx_v - mn_v) or 1.0
        nu = om.MFloatArray([(u - mn_u) / ru for u in u_arr])
        nv = om.MFloatArray([(v - mn_v) / rv for v in v_arr])
        mf.setUVs(nu, nv, self.UV_SET)

    def _dominant_axis(self, joint_data):
        """Returns 'x'/'y'/'z' — the main elongation axis of the skeleton."""
        if not joint_data:
            return "y"
        positions = np.array([jd["world_pos"] for jd in joint_data], dtype=float)
        spread = positions.max(axis=0) - positions.min(axis=0)
        return ["x", "y", "z"][int(np.argmax(spread))]

    def _get_shape(self, node):
        shapes = cmds.listRelatives(node, shapes=True, fullPath=True) or []
        if shapes:
            return shapes[0]
        return node if cmds.nodeType(node) == "mesh" else None


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 2 · SKIN SAMPLING
# ─────────────────────────────────────────────────────────────────────────────

class SkinUVMap:
    """
    Queryable weight map indexed by UV position.
    Supports save/load so a map can be reused across sessions.
    """

    VERSION = 1

    def __init__(self, uv_array, weight_matrix, influence_names):
        """
        Args:
            uv_array       (np.ndarray): (N, 2) — UV coords of source vertices.
            weight_matrix  (np.ndarray): (N, J) — weights per vertex per joint.
            influence_names (list[str]): J joint names.
        """
        self._uv      = uv_array        # (N, 2)
        self._weights = weight_matrix   # (N, J)
        self._infs    = influence_names # [str × J]

    @property
    def influence_names(self):
        return list(self._infs)

    # ── query ────────────────────────────────────────────────────────────────

    def query_batch(self, query_uvs, k=4):
        """
        IDW (inverse-distance weighting) lookup in UV space.

        Args:
            query_uvs (np.ndarray): (M, 2) query UV coordinates.
            k         (int):        K nearest neighbours to blend.

        Returns:
            np.ndarray: (M, J) blended weight matrix, each row sums to 1.
        """
        M    = len(query_uvs)
        J    = len(self._infs)
        out  = np.zeros((M, J), dtype=float)
        k    = min(k, len(self._uv))
        CHUNK = 2000  # process in batches to limit RAM

        for start in range(0, M, CHUNK):
            end   = min(start + CHUNK, M)
            q     = query_uvs[start:end]         # (C, 2)
            diffs = self._uv[None, :, :] - q[:, None, :]   # (C, N, 2)
            d2    = np.einsum("cnj,cnj->cn", diffs, diffs)  # (C, N)

            for ci in range(end - start):
                ids  = np.argpartition(d2[ci], k)[:k]
                dist = d2[ci][ids]
                if np.all(dist < 1e-12):
                    inv = np.ones(k) / k
                else:
                    inv = 1.0 / (dist + 1e-8)
                    inv /= inv.sum()
                blended = (self._weights[ids] * inv[:, None]).sum(axis=0)
                total   = blended.sum()
                if total > 1e-6:
                    blended /= total
                out[start + ci] = blended

        return out

    # ── persistence ─────────────────────────────────────────────────────────

    def save(self, path):
        data = {
            "version":    self.VERSION,
            "influences": self._infs,
            "uv_coords":  self._uv.tolist(),
            "weights":    self._weights.tolist(),
        }
        with open(path, "w") as f:
            json.dump(data, f, separators=(",", ":"))
        _LOG(f"SkinUVMap: saved → {path}")

    @classmethod
    def load(cls, path):
        with open(path, "r") as f:
            data = json.load(f)
        return cls(
            uv_array       = np.array(data["uv_coords"], dtype=float),
            weight_matrix  = np.array(data["weights"],   dtype=float),
            influence_names= data["influences"],
        )


class SkinSamplingModule:
    """
    Builds a SkinUVMap from either a live skinCluster or a .skc export file.

    .skc format (produced by SkinManager.export_skins):
        {
          "mesh_name": [
            {
              "name": "skinCluster1",
              "vertex_count": 1234,
              "influences": ["joint1", "joint2", ...],
              "sparse_weights": {
                "joint1": {"ix": [v_idx, ...], "vw": [weight, ...]},
                ...
              }
            }
          ]
        }
    """

    def build_map(self, source_mesh, source_skin, u_coords, v_coords):
        """
        Builds a SkinUVMap from a **live skinCluster** in the scene.

        Args:
            source_mesh (str):        Maya transform.
            source_skin (str):        skinCluster node name.
            u_coords    (np.ndarray): (N,) U values indexed by vertex.
            v_coords    (np.ndarray): (N,) V values indexed by vertex.

        Returns:
            SkinUVMap | None
        """
        weights, infs = self._read_weights(source_mesh, source_skin)
        if weights is None:
            return None
        uv = np.column_stack([u_coords, v_coords])
        return SkinUVMap(uv, weights, infs)

    def build_map_from_skc(self, skc_path, source_mesh, u_coords, v_coords):
        """
        Builds a SkinUVMap from a **.skc export file** — no skinCluster needed in scene.
        The source mesh only needs to be present for UV projection (can be unbound).

        If the file contains multiple meshes, it tries to match by name;
        falls back to the first entry.

        Args:
            skc_path    (str):        Path to the .skc file.
            source_mesh (str):        Maya transform (used only for name matching).
            u_coords    (np.ndarray): (N,) U values indexed by vertex.
            v_coords    (np.ndarray): (N,) V values indexed by vertex.

        Returns:
            SkinUVMap | None
        """
        if not os.path.exists(skc_path):
            _ERR(f"SkinSamplingModule: .skc not found: {skc_path}")
            return None

        try:
            with open(skc_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            _ERR(f"SkinSamplingModule: cannot read .skc: {e}")
            return None

        skin_entry = self._find_skc_entry(data, source_mesh)
        if skin_entry is None:
            return None

        weights, infs = self._parse_skc_entry(skin_entry, len(u_coords))
        if weights is None:
            return None

        uv = np.column_stack([u_coords, v_coords])
        _LOG(f"SkinSamplingModule: built map from .skc "
             f"({len(infs)} influences, {weights.shape[0]} verts)")
        return SkinUVMap(uv, weights, infs)

    # ── .skc helpers ─────────────────────────────────────────────────────────

    def _find_skc_entry(self, data, source_mesh):
        """
        Returns the first skin dict for the best-matching mesh in the .skc file.
        Priority: exact name → suffix match → first entry.
        """
        short = source_mesh.split("|")[-1].split(":")[-1]

        # 1. exact match
        if short in data and data[short]:
            return data[short][0]

        # 2. ends-with match  (handles namespace prefix differences)
        for key, skins in data.items():
            if skins and (key.endswith(short) or short.endswith(key)):
                _LOG(f"SkinSamplingModule: matched '{short}' → '{key}' in .skc")
                return skins[0]

        # 3. fallback to first entry
        first_key = next(iter(data), None)
        if first_key and data[first_key]:
            _WARN(f"SkinSamplingModule: '{short}' not found in .skc, "
                  f"using first entry '{first_key}'")
            return data[first_key][0]

        _ERR(f"SkinSamplingModule: .skc file is empty or invalid")
        return None

    def _parse_skc_entry(self, entry, expected_vtx_count):
        """
        Reconstructs a dense (V × J) weight matrix from the sparse .skc format.

        Returns:
            (np.ndarray, list[str]) or (None, None)
        """
        infs        = entry.get("influences", [])
        skc_vtx_cnt = entry.get("vertex_count", 0)
        sparse      = entry.get("sparse_weights", {})

        if not infs:
            _ERR("SkinSamplingModule._parse_skc_entry: no influences in entry")
            return None, None

        # Vertex count mismatch → warn but continue; UV count takes priority.
        nv = expected_vtx_count
        if skc_vtx_cnt and skc_vtx_cnt != nv:
            _WARN(f"SkinSamplingModule: .skc vertex count ({skc_vtx_cnt}) != "
                  f"mesh vertex count ({nv}). Using mesh count.")

        arr = np.zeros((nv, len(infs)), dtype=float)
        for ji, jname in enumerate(infs):
            block = sparse.get(jname)
            if not block:
                continue
            for vi, wv in zip(block["ix"], block["vw"]):
                if vi < nv:
                    arr[vi, ji] = float(wv)

        return arr, infs

    def influences_from_skc(self, skc_path, source_mesh):
        """
        Returns just the influence (joint) list from a .skc file.
        Used by the orchestrator to create the target skinCluster without
        needing a live source skin.
        """
        if not os.path.exists(skc_path):
            return []
        try:
            with open(skc_path, "r") as f:
                data = json.load(f)
        except Exception:
            return []
        entry = self._find_skc_entry(data, source_mesh)
        return entry.get("influences", []) if entry else []

    def _read_weights(self, mesh, skin_cluster):
        try:
            sel = om.MSelectionList()
            sel.add(skin_cluster)
            fn_skin = oma.MFnSkinCluster(sel.getDependNode(0))

            sel2 = om.MSelectionList()
            sel2.add(mesh)
            dag = sel2.getDagPath(0)
            dag.extendToShape()
            nv = om.MFnMesh(dag).numVertices

            comp = om.MFnSingleIndexedComponent()
            vc   = comp.create(om.MFn.kMeshVertComponent)
            comp.setCompleteData(nv)

            wm, ni = fn_skin.getWeights(dag, vc)
            arr    = np.array(list(wm), dtype=float).reshape(nv, int(ni))
            infs   = [p.partialPathName() for p in fn_skin.influenceObjects()]
            return arr, infs
        except Exception as e:
            _ERR(f"SkinSamplingModule._read_weights: {e}")
            return None, None


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 3 · JOINT MAPPING
# ─────────────────────────────────────────────────────────────────────────────

class JointMappingModule:
    """
    Maps source skeleton joints to target skeleton joints.

    Strategies:
      ``name``      — normalised name matching (strips suffixes, side tokens).
      ``proximity`` — closest world-space joint.
      ``auto``      — name first, proximity fallback for unmatched joints.
    """

    _STRIP_SUFFIXES = ["_JNT","_jnt","_Jnt","_J","_joint","_Joint","_BIND","_bind","_Bind","_SKN","_skn"]
    _STRIP_PREFIXES = ["jnt_","JNT_","joint_","Joint_","bind_","Bind_","DEF_","def_"]
    _SIDE_MAP = {
        r"\bL\b": "L", r"\bLeft\b": "L", r"\bleft\b": "L",
        r"\bR\b": "R", r"\bRight\b": "R", r"\bright\b": "R",
    }

    def map(self, source_joints, target_joints, strategy="auto"):
        """
        Args:
            source_joints (list[str]): Joint names from source skinCluster.
            target_joints (list[str]): Available joints in target skeleton.
            strategy      (str):      "name" | "proximity" | "auto".

        Returns:
            dict[str, str | None]: {source_joint: target_joint or None}
        """
        result = {j: None for j in source_joints}

        if strategy in ("name", "auto"):
            matched = self._match_by_name(source_joints, target_joints)
            result.update(matched)

        if strategy in ("proximity", "auto"):
            unmatched_src = [j for j, v in result.items() if v is None]
            used_tgt      = set(result.values()) - {None}
            avail_tgt     = [j for j in target_joints if j not in used_tgt]
            prox          = self._match_by_proximity(unmatched_src, avail_tgt)
            for k, v in prox.items():
                if result[k] is None:
                    result[k] = v

        matched = sum(1 for v in result.values() if v is not None)
        _LOG(f"JointMappingModule: {matched}/{len(source_joints)} joints mapped")
        unmapped = [j for j, v in result.items() if v is None]
        if unmapped:
            _WARN(f"  Unmapped: {unmapped}")
        return result

    def _match_by_name(self, src, tgt):
        tgt_norm = {self._normalize(j): j for j in tgt}
        result   = {}
        for j in src:
            n = self._normalize(j)
            if n in tgt_norm:
                result[j] = tgt_norm[n]
            else:
                # Fuzzy: best Jaccard score above threshold
                best_score, best_match = 0.0, None
                for tn, tj in tgt_norm.items():
                    score = self._jaccard(n, tn)
                    if score > best_score:
                        best_score, best_match = score, tj
                if best_score > 0.6:
                    result[j] = best_match
        return result

    def _match_by_proximity(self, src, tgt):
        if not src or not tgt:
            return {}
        result = {}
        tgt_pos = {}
        for j in tgt:
            try:
                p = cmds.xform(j, q=True, ws=True, t=True)
                tgt_pos[j] = np.array(p, dtype=float)
            except Exception:
                pass

        for j in src:
            try:
                sp = np.array(cmds.xform(j, q=True, ws=True, t=True), dtype=float)
            except Exception:
                continue
            best_d, best_j = np.inf, None
            for tj, tp in tgt_pos.items():
                d = float(np.linalg.norm(sp - tp))
                if d < best_d:
                    best_d, best_j = d, tj
            if best_j is not None:
                result[j] = best_j
        return result

    def _normalize(self, name):
        n = name.split(":")[-1].split("|")[-1]
        for sfx in self._STRIP_SUFFIXES:
            if n.endswith(sfx):
                n = n[:-len(sfx)]; break
        for pfx in self._STRIP_PREFIXES:
            if n.startswith(pfx):
                n = n[len(pfx):]; break
        return n.lower()

    def _jaccard(self, a, b):
        ta = set(re.split(r"[_\-\.\s]+", a))
        tb = set(re.split(r"[_\-\.\s]+", b))
        if not ta or not tb:
            return 0.0
        return len(ta & tb) / len(ta | tb)


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 4 · WEIGHT PROJECTION
# ─────────────────────────────────────────────────────────────────────────────

class WeightProjectionModule:
    """
    Creates a skinCluster on the target mesh and fills its weights
    by querying the SkinUVMap at each target vertex's UV coordinate.
    """

    def setup_skin(self, source_mesh, target_mesh, source_skin,
                   influences_override=None):
        """
        Creates a new skinCluster on *target_mesh*.

        Influences are taken from *source_skin* (live scene) unless
        *influences_override* is provided — used when working from a .skc file
        and the source mesh has no active skinCluster.

        Args:
            source_mesh        (str):       Source mesh (for skinning method).
            target_mesh        (str):       Target mesh.
            source_skin        (str|None):  Live skinCluster name, or None.
            influences_override(list[str]): Joint list from .skc; overrides source_skin query.

        Returns:
            str | None: new skinCluster name.
        """
        if influences_override is not None:
            infs = influences_override
        elif source_skin:
            infs = cmds.skinCluster(source_skin, q=True, influence=True) or []
        else:
            _ERR("WeightProjectionModule: no source skin and no influences_override")
            return None

        valid_infs = [j for j in infs if cmds.objExists(j)]
        if not valid_infs:
            _ERR("WeightProjectionModule: no valid influences found in scene")
            return None

        tgt_shape = (cmds.listRelatives(target_mesh, shapes=True) or [target_mesh])[0]
        hist      = cmds.listHistory(tgt_shape, pruneDagObjects=True) or []
        for old in [n for n in hist if cmds.nodeType(n) == "skinCluster"]:
            cmds.delete(old)

        new_skin = cmds.skinCluster(
            valid_infs, target_mesh,
            toSelectedBones=False, bindMethod=0,
            normalizeWeights=1, weightDistribution=0,
            mi=4, omi=False, dr=4.0,
        )[0]

        method = cmds.getAttr(f"{source_skin}.skinningMethod")
        cmds.setAttr(f"{new_skin}.skinningMethod", method)
        _LOG(f"WeightProjectionModule: created '{new_skin}' ({len(valid_infs)} infs)")
        return new_skin

    def project(self, target_mesh, target_skin, target_uvs,
                skin_map, joint_map, progress_cb=None):
        """
        Transfers weights from *skin_map* to *target_skin*.

        Args:
            target_uvs (tuple):    (U_array, V_array) for target.
            skin_map   (SkinUVMap): queryable source weight map.
            joint_map  (dict):     {source_joint: target_joint | None}.
            progress_cb(callable): optional fn(percent:int, msg:str).

        Returns:
            bool
        """
        tgt_u, tgt_v  = target_uvs
        query_uv      = np.column_stack([tgt_u, tgt_v])
        nv            = len(tgt_u)

        if progress_cb:
            progress_cb(10, "Querying UV weight map…")

        src_blended = skin_map.query_batch(query_uv, k=4)   # (nv, J_src)

        if progress_cb:
            progress_cb(50, "Remapping influences…")

        # Build influence remap: src index → target skin index
        tgt_infs    = cmds.skinCluster(target_skin, q=True, influence=True) or []
        tgt_inf_map = {name: i for i, name in enumerate(tgt_infs)}
        src_infs    = skin_map.influence_names
        src_to_tgt  = {}
        for si, sname in enumerate(src_infs):
            tgt_name = joint_map.get(sname)
            if tgt_name and tgt_name in tgt_inf_map:
                src_to_tgt[si] = tgt_inf_map[tgt_name]
            elif sname in tgt_inf_map:  # direct name match fallback
                src_to_tgt[si] = tgt_inf_map[sname]

        ni_tgt = len(tgt_infs)
        out    = np.zeros((nv, ni_tgt), dtype=float)

        for si, ti in src_to_tgt.items():
            out[:, ti] += src_blended[:, si]

        # Renormalize
        totals = out.sum(axis=1, keepdims=True)
        out    = np.where(totals > 1e-6, out / totals, out)

        if progress_cb:
            progress_cb(80, "Applying weights…")

        return self._apply_weights(target_mesh, target_skin, out)

    def _apply_weights(self, mesh, skin_cluster, weights_np):
        try:
            sel = om.MSelectionList(); sel.add(skin_cluster)
            fn  = oma.MFnSkinCluster(sel.getDependNode(0))

            sel2 = om.MSelectionList(); sel2.add(mesh)
            dag  = sel2.getDagPath(0); dag.extendToShape()
            nv   = om.MFnMesh(dag).numVertices

            comp = om.MFnSingleIndexedComponent()
            vc   = comp.create(om.MFn.kMeshVertComponent)
            comp.setCompleteData(nv)

            ni        = weights_np.shape[1]
            m_weights = om.MDoubleArray(weights_np.flatten().tolist())
            m_idxs    = om.MIntArray(list(range(ni)))

            prev = cmds.getAttr(f"{skin_cluster}.normalizeWeights")
            cmds.setAttr(f"{skin_cluster}.normalizeWeights", 0)
            try:
                fn.setWeights(dag, vc, m_idxs, m_weights, False)
            finally:
                cmds.setAttr(f"{skin_cluster}.normalizeWeights", prev)
            return True
        except Exception as e:
            _ERR(f"WeightProjectionModule._apply_weights: {e}")
            return False


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 5 · REFINEMENT
# ─────────────────────────────────────────────────────────────────────────────

class RefinementModule:
    """
    Post-transfer weight quality pass:

    1. Limit the number of active influences per vertex.
    2. Smooth weights globally or in targeted regions.
    3. Extra smooth iterations near critical flex zones (elbows, knees).
    """

    def limit_influences(self, mesh, skin_cluster, max_infs=4):
        """
        Prunes each vertex to at most *max_infs* influences (keeps the heaviest),
        then renormalizes.
        """
        sel = om.MSelectionList(); sel.add(skin_cluster)
        fn  = oma.MFnSkinCluster(sel.getDependNode(0))

        sel2 = om.MSelectionList(); sel2.add(mesh)
        dag  = sel2.getDagPath(0); dag.extendToShape()
        nv   = om.MFnMesh(dag).numVertices

        comp = om.MFnSingleIndexedComponent()
        vc   = comp.create(om.MFn.kMeshVertComponent)
        comp.setCompleteData(nv)

        wm, ni = fn.getWeights(dag, vc)
        arr    = np.array(list(wm), dtype=float).reshape(nv, int(ni))

        for vi in range(nv):
            row = arr[vi]
            if (row > 0).sum() <= max_infs:
                continue
            threshold_idx = np.argpartition(row, -max_infs)[-max_infs:]
            mask = np.zeros(int(ni), dtype=bool)
            mask[threshold_idx] = True
            row[~mask] = 0.0
            total = row.sum()
            if total > 1e-6:
                row /= total
            arr[vi] = row

        m_weights = om.MDoubleArray(arr.flatten().tolist())
        m_idxs    = om.MIntArray(list(range(int(ni))))
        prev      = cmds.getAttr(f"{skin_cluster}.normalizeWeights")
        cmds.setAttr(f"{skin_cluster}.normalizeWeights", 0)
        try:
            fn.setWeights(dag, vc, m_idxs, m_weights, False)
        finally:
            cmds.setAttr(f"{skin_cluster}.normalizeWeights", prev)
        _LOG(f"RefinementModule: influences clamped to {max_infs} on '{mesh}'")

    def smooth(self, mesh, skin_cluster, iterations=3, grow_rings=0):
        """
        Global smooth of all weights using Maya's skinPercent smooth.

        Args:
            iterations (int): number of smooth passes.
            grow_rings (int): selection grow before smoothing (0 = all verts).
        """
        nv = cmds.polyEvaluate(mesh, vertex=True)
        all_verts = [f"{mesh}.vtx[{i}]" for i in range(nv)]
        cmds.select(all_verts)
        for _ in range(iterations):
            try:
                cmds.skinPercent(skin_cluster, all_verts, normalize=True, smooth=True)
            except Exception as e:
                _WARN(f"RefinementModule.smooth: {e}"); break
        cmds.select(clear=True)
        _LOG(f"RefinementModule: smoothed {iterations}× on '{mesh}'")

    def boost_critical_zones(self, mesh, skin_cluster, joint_data,
                              flex_smooth_iter=3, grow_rings=2):
        """
        Applies extra smooth iterations around flex-zone joints
        (elbows, knees, shoulders).
        """
        flex_joints = [jd["name"] for jd in joint_data if jd.get("is_flex")]
        if not flex_joints:
            return

        for jnt in flex_joints:
            try:
                cmds.select(clear=True)
                cmds.skinCluster(skin_cluster, e=True, selectInfluenceVerts=jnt)
                affected = cmds.ls(sl=True, flatten=True)
                if not affected:
                    continue
                for _ in range(grow_rings):
                    cmds.GrowPolygonSelectionRegion()
                grown = cmds.ls(sl=True, flatten=True) or affected
                for _ in range(flex_smooth_iter):
                    cmds.skinPercent(skin_cluster, grown, normalize=True, smooth=True)
            except Exception as e:
                _WARN(f"RefinementModule.boost_critical_zones: skipped '{jnt}': {e}")
            finally:
                cmds.select(clear=True)

        _LOG(f"RefinementModule: critical zones boosted ({len(flex_joints)} joints)")


# ─────────────────────────────────────────────────────────────────────────────
#  JOINT ZONE ANALYZER  (skeleton parser — shared with UV module)
# ─────────────────────────────────────────────────────────────────────────────

class JointZoneAnalyzer:
    """
    Walks the joint hierarchy and returns structured data per joint.
    Used by UVMatchingModule (skeleton projection) and RefinementModule (flex zones).
    """

    FLEX_PREFER_ANGLE = 20.0

    def analyze(self, root_joint):
        all_j      = self._collect(root_joint)
        if not all_j:
            _ERR(f"JointZoneAnalyzer: no joints under '{root_joint}'")
            return []

        pmap      = self._parent_map(all_j)
        ordered   = self._dfs(root_joint, all_j, pmap)
        chain_map = self._chains(ordered, pmap)

        chain_local = {}; chain_totals = {}
        for j in ordered:
            cid = chain_map[j]
            chain_totals[cid] = chain_totals.get(cid, 0) + 1

        result = []
        for idx, j in enumerate(ordered):
            wp  = list(cmds.xform(j, q=True, ws=True, t=True))
            par = pmap[j]
            pp  = list(cmds.xform(par, q=True, ws=True, t=True)) if par else None
            bd  = self._bone_dir(wp, pp)
            cid = chain_map[j]
            li  = chain_local.get(cid, 0); chain_local[cid] = li + 1
            t   = li / max(chain_totals.get(cid, 1), 1)

            result.append({
                "name":       j,
                "index":      idx,
                "chain_id":   cid,
                "t":          t,
                "is_flex":    self._is_flex(j, pmap, wp, pp),
                "world_pos":  wp,
                "parent_pos": pp,
                "bone_dir":   bd,
                "num_total":  len(ordered),
            })

        _LOG(f"JointZoneAnalyzer: {len(result)} joints, "
             f"{sum(1 for d in result if d['is_flex'])} flex")
        return result

    def _collect(self, root):
        desc = cmds.listRelatives(root, allDescendents=True, type="joint") or []
        return [root] + desc

    def _parent_map(self, joints):
        pmap = {}
        for j in joints:
            p = cmds.listRelatives(j, parent=True, type="joint")
            pmap[j] = p[0] if p else None
        return pmap

    def _dfs(self, root, all_j, pmap):
        cmap = {j: [] for j in all_j}
        for j in all_j:
            p = pmap[j]
            if p and p in cmap:
                cmap[p].append(j)
        order = []; stack = [root]
        while stack:
            j = stack.pop(); order.append(j)
            for c in reversed(cmap.get(j, [])): stack.append(c)
        return order

    def _chains(self, ordered, pmap):
        cmap = {}; counter = [0]
        def dfs(j, cid):
            cmap[j] = cid
            kids = [x for x in ordered if pmap.get(x) == j]
            if len(kids) > 1:
                for kid in kids:
                    counter[0] += 1; dfs(kid, counter[0])
            elif len(kids) == 1:
                dfs(kids[0], cid)
        if ordered:
            dfs(ordered[0], 0)
        return cmap

    def _bone_dir(self, wp, pp):
        if not pp:
            return [0., 1., 0.]
        d = [wp[i] - pp[i] for i in range(3)]
        L = math.sqrt(sum(x*x for x in d))
        return [x / L if L > 1e-6 else 0. for x in d]

    def _is_flex(self, joint, pmap, wp, pp):
        kids = cmds.listRelatives(joint, children=True, type="joint") or []
        for ax in "XYZ":
            try:
                if abs(cmds.getAttr(f"{joint}.preferAngle{ax}")) > self.FLEX_PREFER_ANGLE:
                    return True
            except Exception:
                pass
        if pp and len(kids) == 1:
            diff = [wp[i] - pp[i] for i in range(3)]
            if math.sqrt(sum(d*d for d in diff)) > 0.5:
                return True
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  ORCHESTRATOR
# ─────────────────────────────────────────────────────────────────────────────

class AutoSkinTransferSystem:
    """
    Orchestrates all five modules.

    Args to ``transfer``
    --------------------
    source_mesh    (str)  : source mesh (must be in scene; skin not required if skc given).
    target_mesh    (str)  : mesh that will receive the skinning.
    root_joint     (str)  : root of the shared skeleton; auto-detected if None.
    uv_method      (str)  : "skeleton" | "cylindrical" | "planar".
    joint_strategy (str)  : "auto" | "name" | "proximity".
    smooth_iter    (int)  : global smoothing passes (0 = skip).
    max_infs       (int)  : max influences per vertex (0 = skip).
    boost_critical (bool) : extra smooth on flex zones.
    cleanup_uvs    (bool) : delete temp UV sets when done.
    skin_map_path  (str)  : if given, save map to this path (or load from it).
    source_skc_path(str)  : path to a .skc export from SkinManager.export_skins().
                            When provided, weights are read from file — the source
                            mesh can be unbound (no active skinCluster needed).
    progress_cb    (fn)   : optional callback(percent:int, msg:str).

    Returns the new skinCluster name, or None on failure.
    """

    def __init__(self):
        self.uv_mod       = UVMatchingModule()
        self.sample_mod   = SkinSamplingModule()
        self.joint_mod    = JointMappingModule()
        self.project_mod  = WeightProjectionModule()
        self.refine_mod   = RefinementModule()
        self.zone_analyzer= JointZoneAnalyzer()

    # ── main entry ───────────────────────────────────────────────────────────

    def transfer(self, source_mesh, target_mesh,
                 root_joint=None, uv_method="skeleton",
                 joint_strategy="auto", smooth_iter=3,
                 max_infs=4, boost_critical=True,
                 cleanup_uvs=True, skin_map_path=None,
                 source_skc_path=None, progress_cb=None):

        def _p(pct, msg):
            _LOG(f"  [{pct:3d}%] {msg}")
            if progress_cb:
                progress_cb(pct, msg)

        if not HAS_NUMPY:
            _ERR("AutoSkinTransferSystem requires numpy. "
                 "Run install_numpy() from userSetup.py and restart Maya.")
            return None

        _LOG(f"=== AutoSkinTransfer  '{source_mesh}' → '{target_mesh}' ===")
        using_skc = bool(source_skc_path and os.path.exists(source_skc_path))
        if using_skc:
            _LOG(f"  Mode: .skc file  ({source_skc_path})")

        for m in (source_mesh, target_mesh):
            if not cmds.objExists(m):
                _ERR(f"'{m}' not found"); return None

        # ── Source skin (optional when .skc is provided) ──────────────
        source_skin = self._find_skin(source_mesh)
        if source_skin:
            _LOG(f"  Source skin: {source_skin}")
        elif not using_skc:
            _ERR(f"No skinCluster on '{source_mesh}' and no .skc file provided")
            return None
        else:
            _LOG("  Source skin: none in scene — will use .skc file")

        # ── Root joint ────────────────────────────────────────────────
        if not root_joint:
            if source_skin:
                root_joint = self._find_root_joint(source_skin)
            elif using_skc:
                root_joint = self._find_root_joint_from_skc(source_skc_path, source_mesh)
        if not root_joint:
            _ERR("Cannot determine root joint — pass root_joint explicitly")
            return None
        _LOG(f"  Root joint:  {root_joint}")

        # ── 1. Analyze skeleton ───────────────────────────────────────
        _p(5, "Analyzing skeleton…")
        joint_data = self.zone_analyzer.analyze(root_joint)
        if not joint_data:
            return None

        # ── 2. Build transfer UVs ─────────────────────────────────────
        _p(15, f"Building UV projection [{uv_method}]…")
        if not self.uv_mod.build(source_mesh, target_mesh, joint_data, uv_method):
            return None

        # ── 3. Read UV coords ─────────────────────────────────────────
        _p(25, "Reading UV coordinates…")
        try:
            src_uvs = self.uv_mod.get_uv_coords(source_mesh)
            tgt_uvs = self.uv_mod.get_uv_coords(target_mesh)
        except Exception as e:
            _ERR(f"UV read failed: {e}")
            if cleanup_uvs:
                self.uv_mod.cleanup(source_mesh)
                self.uv_mod.cleanup(target_mesh)
            return None

        # ── 4. Build / load skin UV map ───────────────────────────────
        _p(30, "Building skin UV map…")
        if skin_map_path and os.path.exists(skin_map_path):
            _LOG(f"  Loading existing .skinmap: {skin_map_path}")
            skin_map = SkinUVMap.load(skin_map_path)
        elif using_skc:
            _LOG(f"  Reading weights from .skc…")
            skin_map = self.sample_mod.build_map_from_skc(
                source_skc_path, source_mesh, *src_uvs
            )
            if skin_map is None:
                if cleanup_uvs:
                    self.uv_mod.cleanup(source_mesh)
                    self.uv_mod.cleanup(target_mesh)
                return None
            if skin_map_path:
                os.makedirs(os.path.dirname(os.path.abspath(skin_map_path)), exist_ok=True)
                skin_map.save(skin_map_path)
        else:
            skin_map = self.sample_mod.build_map(source_mesh, source_skin, *src_uvs)
            if skin_map is None:
                if cleanup_uvs:
                    self.uv_mod.cleanup(source_mesh)
                    self.uv_mod.cleanup(target_mesh)
                return None
            if skin_map_path:
                os.makedirs(os.path.dirname(os.path.abspath(skin_map_path)), exist_ok=True)
                skin_map.save(skin_map_path)

        # ── 5. Map joints ─────────────────────────────────────────────
        _p(40, "Mapping joints…")
        src_joints = skin_map.influence_names
        tgt_joints = cmds.listRelatives(root_joint, allDescendents=True, type="joint") or []
        tgt_joints = [root_joint] + tgt_joints
        joint_map  = self.joint_mod.map(src_joints, tgt_joints, joint_strategy)

        # ── 6. Setup target skin ──────────────────────────────────────
        _p(45, "Creating target skinCluster…")
        # When using .skc, pass influences directly (source may be unbound)
        infs_override = skin_map.influence_names if (using_skc and not source_skin) else None
        target_skin = self.project_mod.setup_skin(
            source_mesh, target_mesh, source_skin,
            influences_override=infs_override,
        )
        if not target_skin:
            if cleanup_uvs:
                self.uv_mod.cleanup(source_mesh)
                self.uv_mod.cleanup(target_mesh)
            return None

        # ── 7. Project weights ────────────────────────────────────────
        _p(50, "Projecting weights via UV space…")
        ok = self.project_mod.project(
            target_mesh, target_skin, tgt_uvs,
            skin_map, joint_map,
            progress_cb=lambda p, m: _p(50 + int(p * 0.3), m),
        )

        # ── 8. Cleanup temp UVs ───────────────────────────────────────
        if cleanup_uvs:
            self.uv_mod.cleanup(source_mesh)
            self.uv_mod.cleanup(target_mesh)

        if not ok:
            _ERR("Weight projection failed"); return None

        # ── 9. Refinement ─────────────────────────────────────────────
        if max_infs > 0:
            _p(82, f"Limiting influences (max={max_infs})…")
            self.refine_mod.limit_influences(target_mesh, target_skin, max_infs)

        if smooth_iter > 0:
            _p(88, f"Smoothing weights ({smooth_iter}×)…")
            self.refine_mod.smooth(target_mesh, target_skin, smooth_iter)

        if boost_critical:
            _p(94, "Boosting critical flex zones…")
            self.refine_mod.boost_critical_zones(target_mesh, target_skin, joint_data)

        _p(100, "Done.")
        _LOG(f"=== COMPLETE  skin: '{target_skin}' on '{target_mesh}' ===")
        return target_skin

    # ── helpers ──────────────────────────────────────────────────────────────

    def _find_skin(self, mesh):
        shape = (cmds.listRelatives(mesh, shapes=True) or [mesh])[0]
        hist  = cmds.listHistory(shape, pruneDagObjects=True, interestLevel=1) or []
        skins = [n for n in hist if cmds.nodeType(n) == "skinCluster"]
        return skins[-1] if skins else None

    def _find_root_joint(self, skin_cluster):
        infs    = cmds.skinCluster(skin_cluster, q=True, influence=True) or []
        inf_set = set(infs)
        for j in infs:
            p = cmds.listRelatives(j, parent=True, type="joint")
            if not p or p[0] not in inf_set:
                return j
        return infs[0] if infs else None

    def _find_root_joint_from_skc(self, skc_path, source_mesh):
        """
        Reads the influence list from a .skc file and finds the root joint
        by walking the scene hierarchy — the joint with no joint parent
        inside the influence set.
        """
        infs = self.sample_mod.influences_from_skc(skc_path, source_mesh)
        if not infs:
            return None
        # Filter to joints that actually exist in the scene
        scene_infs = [j for j in infs if cmds.objExists(j)]
        if not scene_infs:
            _WARN("_find_root_joint_from_skc: none of the .skc joints exist in scene")
            return None
        inf_set = set(scene_infs)
        for j in scene_infs:
            p = cmds.listRelatives(j, parent=True, type="joint")
            if not p or p[0] not in inf_set:
                return j
        return scene_infs[0]
