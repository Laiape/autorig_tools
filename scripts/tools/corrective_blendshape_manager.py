import copy
import csv
import io
import maya.cmds as cmds
import maya.api.OpenMaya as om
import os
import glob

try:
    from utils import data_manager
    from utils import rig_manager
    HAS_RIG_UTILS = True
except ImportError:
    HAS_RIG_UTILS = False


class CorrectiveBlendshapeManager:
    """
    Export / import / mirror pre-deformation corrective blendShapes with driven key connections.
    Targets are always placed before the skinCluster in the deformer stack.
    """

    # CSV suffix tokens — each export version produces 3 files sharing the same prefix
    _SFX_TARGETS = "_targets.csv"
    _SFX_DELTAS  = "_deltas.csv"
    _SFX_KEYS    = "_keys.csv"

    # Attributes whose driver value is negated when mirroring L→R or R→L.
    # Matches Maya's standard mirror convention for biped FK rigs.
    MIRROR_NEGATE_ATTRS = {"translateX", "tx", "rotateY", "ry", "rotateZ", "rz"}

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def __init__(self):
        self.asset_name = self._resolve_asset_name()
        self.folder_path = self._resolve_folder_path()

    def _resolve_asset_name(self):
        if HAS_RIG_UTILS:
            try:
                name = data_manager.DataExportBiped().get_data("basic_structure", "character_name")
                if name:
                    return name
            except Exception:
                pass
        assemblies = cmds.ls(assemblies=True) or []
        valid = [a for a in assemblies if not cmds.listRelatives(a, type="camera")]
        return valid[-1] if valid else "asset"

    def _resolve_folder_path(self):
        if HAS_RIG_UTILS:
            try:
                return rig_manager.asset_path(self.asset_name, "corrective_blendshapes")
            except Exception:
                pass
        script_dir = os.path.dirname(os.path.realpath(__file__))
        root = script_dir
        for _ in range(3):
            root = os.path.dirname(root)
        return os.path.normpath(
            os.path.join(root, "assets", self.asset_name, "corrective_blendshapes")
        )

    def _versioned_prefix(self, version):
        """Return the base path prefix shared by the 3 CSV files for a given version."""
        return os.path.join(self.folder_path, f"{self.asset_name}_v{version:03d}")

    def _csv_paths(self, prefix):
        return (prefix + self._SFX_TARGETS,
                prefix + self._SFX_DELTAS,
                prefix + self._SFX_KEYS)

    def _get_next_export_prefix(self):
        os.makedirs(self.folder_path, exist_ok=True)
        pattern = os.path.join(self.folder_path, f"{self.asset_name}_v*{self._SFX_TARGETS}")
        highest = 0
        for f in glob.glob(pattern):
            try:
                ver = int(os.path.basename(f).split("_v")[-1].split(self._SFX_TARGETS)[0])
                highest = max(highest, ver)
            except ValueError:
                pass
        return self._versioned_prefix(highest + 1)

    def _get_latest_import_prefix(self):
        if not os.path.isdir(self.folder_path):
            return None
        pattern = os.path.join(self.folder_path, f"{self.asset_name}_v*{self._SFX_TARGETS}")
        highest, latest = -1, None
        for f in glob.glob(pattern):
            try:
                ver = int(os.path.basename(f).split("_v")[-1].split(self._SFX_TARGETS)[0])
                if ver > highest:
                    highest, latest = ver, self._versioned_prefix(ver)
            except ValueError:
                pass
        return latest

    # ------------------------------------------------------------------
    # Scene scanning
    # ------------------------------------------------------------------

    def _history(self, mesh_shape):
        return cmds.listHistory(mesh_shape, pruneDagObjects=True, interestLevel=1) or []

    def _is_pre_deformation(self, bs_node, mesh_shape):
        """
        True when bs_node is deeper in the deformer chain than any skinCluster,
        meaning it evaluates BEFORE the skinCluster (pre-deformation).
        listHistory returns output→input, so pre-deform nodes have higher indices.
        """
        hist = self._history(mesh_shape)
        try:
            bs_idx = hist.index(bs_node)
        except ValueError:
            return False
        skin_idxs = [i for i, n in enumerate(hist) if cmds.nodeType(n) == "skinCluster"]
        return bs_idx > max(skin_idxs) if skin_idxs else True

    def _collect_pre_deform_blendshapes(self):
        """Return {mesh_transform: [bs_node, ...]} for all pre-deformation blendShapes."""
        result = {}
        for shape in cmds.ls(type="mesh"):
            if cmds.getAttr(f"{shape}.intermediateObject"):
                continue
            hist = self._history(shape)
            pre_bs = [n for n in hist
                      if cmds.nodeType(n) == "blendShape"
                      and self._is_pre_deformation(n, shape)]
            if not pre_bs:
                continue
            parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            if parents:
                mesh_name = parents[0].split("|")[-1]
                existing = result.setdefault(mesh_name, [])
                for bs in pre_bs:
                    if bs not in existing:
                        existing.append(bs)
        return result

    # ------------------------------------------------------------------
    # Delta extraction  (inputPointsTarget stores per-vertex deltas)
    # ------------------------------------------------------------------

    def _parse_components(self, comp_list):
        """Expand ['vtx[0]', 'vtx[3:5]', ...] → flat list of int indices."""
        indices = []
        for c in comp_list:
            inner = c.strip()[4:-1]  # strip 'vtx[' and ']'
            if ":" in inner:
                a, b = inner.split(":")
                indices.extend(range(int(a), int(b) + 1))
            else:
                indices.append(int(inner))
        return indices

    def _get_target_deltas(self, bs_node, target_index):
        """
        Return sparse vertex deltas [[vtx_idx, dx, dy, dz], ...] for a blendShape target.
        inputPointsTarget stores (dx, dy, dz, w) offsets from the base mesh.
        """
        base = (f"{bs_node}.inputTarget[0]"
                f".inputTargetGroup[{target_index}]"
                f".inputTargetItem[6000]")
        try:
            points = cmds.getAttr(f"{base}.inputPointsTarget") or []
            components = cmds.getAttr(f"{base}.inputComponentsTarget") or []
        except Exception as e:
            om.MGlobal.displayWarning(f"[CBS] Cannot read deltas {bs_node}[{target_index}]: {e}")
            return []

        if not points or not components:
            return []

        vtx_indices = self._parse_components(components)
        deltas = []
        for i, vtx_idx in enumerate(vtx_indices):
            if i >= len(points):
                break
            dx, dy, dz = points[i][0], points[i][1], points[i][2]
            if abs(dx) > 1e-6 or abs(dy) > 1e-6 or abs(dz) > 1e-6:
                deltas.append([vtx_idx, round(dx, 6), round(dy, 6), round(dz, 6)])
        return deltas

    # ------------------------------------------------------------------
    # Driven key extraction
    # ------------------------------------------------------------------

    _ANIM_CURVE_TYPES = {"animCurveUA", "animCurveUL", "animCurveUT", "animCurveUU"}

    def _get_driven_key(self, bs_node, weight_index):
        """Return driven key data dict for weight[weight_index], or None."""
        weight_plug = f"{bs_node}.weight[{weight_index}]"
        connected = (cmds.listConnections(weight_plug, source=True, plugs=True,
                                          skipConversionNodes=True) or [])
        curve = next(
            (conn.split(".")[0] for conn in connected
             if cmds.nodeType(conn.split(".")[0]) in self._ANIM_CURVE_TYPES),
            None
        )
        if not curve:
            return None

        driver_conns = cmds.listConnections(f"{curve}.input", source=True, plugs=True) or []
        if not driver_conns:
            return None

        num_keys = cmds.keyframe(curve, query=True, keyframeCount=True) or 0
        keys = []
        for i in range(num_keys):
            t_r = cmds.keyframe(curve, q=True, index=(i, i), floatChange=True)
            v_r = cmds.keyframe(curve, q=True, index=(i, i), valueChange=True)
            if not t_r or not v_r:
                continue
            it = (cmds.keyTangent(curve, q=True, index=(i, i), inTangentType=True)  or ["linear"])[0]
            ot = (cmds.keyTangent(curve, q=True, index=(i, i), outTangentType=True) or ["linear"])[0]
            ia = (cmds.keyTangent(curve, q=True, index=(i, i), inAngle=True)        or [0.0])[0]
            oa = (cmds.keyTangent(curve, q=True, index=(i, i), outAngle=True)       or [0.0])[0]
            iw = (cmds.keyTangent(curve, q=True, index=(i, i), inWeight=True)       or [1.0])[0]
            ow = (cmds.keyTangent(curve, q=True, index=(i, i), outWeight=True)      or [1.0])[0]
            keys.append({"t": round(t_r[0], 6), "v": round(v_r[0], 6),
                         "it": it, "ot": ot,
                         "ia": round(ia, 4), "oa": round(oa, 4),
                         "iw": round(iw, 4), "ow": round(ow, 4)})

        pre_inf  = (cmds.setInfinity(curve, q=True, preInfinite=True)  or ["constant"])[0]
        post_inf = (cmds.setInfinity(curve, q=True, postInfinite=True) or ["constant"])[0]

        return {
            "driver":     driver_conns[0],
            "curve_name": curve,
            "curve_type": cmds.nodeType(curve),
            "pre_inf":    pre_inf,
            "post_inf":   post_inf,
            "keys":       keys,
        }

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export(self, path=None):
        """
        Export all pre-deformation blendShapes + driven keys to three CSV files:
          <prefix>_targets.csv  — one row per target (metadata + driver info)
          <prefix>_deltas.csv   — one row per non-zero vertex delta
          <prefix>_keys.csv     — one row per driven-key keyframe
        """
        prefix  = path or self._get_next_export_prefix()
        bs_map  = self._collect_pre_deform_blendshapes()

        if not bs_map:
            om.MGlobal.displayWarning("[CBS] No pre-deformation blendShapes found.")
            return None

        target_rows, delta_rows, key_rows = [], [], []

        for mesh_name, bs_nodes in bs_map.items():
            for bs_node in bs_nodes:
                aliases_flat = cmds.aliasAttr(bs_node, query=True) or []
                idx_to_name = {
                    int(aliases_flat[i + 1].split("[")[1].rstrip("]")): aliases_flat[i]
                    for i in range(0, len(aliases_flat), 2)
                }

                for w_idx, t_name in idx_to_name.items():
                    deltas = self._get_target_deltas(bs_node, w_idx)
                    dk     = self._get_driven_key(bs_node, w_idx)

                    target_rows.append({
                        "mesh":       mesh_name,
                        "bs_node":    bs_node,
                        "target":     t_name,
                        "w_idx":      w_idx,
                        "driver":     dk["driver"]     if dk else "",
                        "curve_name": dk["curve_name"] if dk else "",
                        "curve_type": dk["curve_type"] if dk else "",
                        "pre_inf":    dk["pre_inf"]    if dk else "",
                        "post_inf":   dk["post_inf"]   if dk else "",
                    })

                    for vtx_idx, dx, dy, dz in deltas:
                        delta_rows.append({
                            "mesh":    mesh_name,
                            "bs_node": bs_node,
                            "target":  t_name,
                            "vtx_idx": vtx_idx,
                            "dx":      dx,
                            "dy":      dy,
                            "dz":      dz,
                        })

                    if dk:
                        for ki, kd in enumerate(dk["keys"]):
                            key_rows.append({
                                "mesh":    mesh_name,
                                "bs_node": bs_node,
                                "target":  t_name,
                                "key_idx": ki,
                                "t":       kd["t"],
                                "v":       kd["v"],
                                "it":      kd["it"],
                                "ot":      kd["ot"],
                                "ia":      kd["ia"],
                                "oa":      kd["oa"],
                                "iw":      kd["iw"],
                                "ow":      kd["ow"],
                            })

        os.makedirs(self.folder_path, exist_ok=True)
        p_targets, p_deltas, p_keys = self._csv_paths(prefix)

        self._write_csv(p_targets, ["mesh","bs_node","target","w_idx",
                                    "driver","curve_name","curve_type","pre_inf","post_inf"],
                        target_rows)
        self._write_csv(p_deltas,  ["mesh","bs_node","target","vtx_idx","dx","dy","dz"],
                        delta_rows)
        self._write_csv(p_keys,    ["mesh","bs_node","target","key_idx",
                                    "t","v","it","ot","ia","oa","iw","ow"],
                        key_rows)

        total_bs = sum(len(v) for v in bs_map.values())
        om.MGlobal.displayInfo(
            f"[CBS] Exported {total_bs} blendShape(s) → {prefix}_*.csv"
        )
        return prefix

    @staticmethod
    def _write_csv(filepath, fieldnames, rows):
        with io.open(filepath, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_from(self, path=None):
        """
        Import corrective blendShapes from the three CSV files produced by export().
        Pass the shared version prefix (same value returned by export()), or leave
        None to auto-pick the latest version in the configured folder.
        """
        prefix = path or self._get_latest_import_prefix()
        if not prefix:
            om.MGlobal.displayWarning("[CBS] No CSV export found, skipping.")
            return

        p_targets, p_deltas, p_keys = self._csv_paths(prefix)
        for p in (p_targets, p_deltas, p_keys):
            if not os.path.exists(p):
                om.MGlobal.displayWarning(f"[CBS] Missing file: {p}")
                return

        om.MGlobal.displayInfo(f"[CBS] Importing from {prefix}_*.csv")

        # ── build delta lookup: (mesh, bs_node, target) → [[vtx,dx,dy,dz],...]
        delta_map = {}
        for row in self._read_csv(p_deltas):
            key = (row["mesh"], row["bs_node"], row["target"])
            delta_map.setdefault(key, []).append(
                [int(row["vtx_idx"]),
                 float(row["dx"]), float(row["dy"]), float(row["dz"])]
            )

        # ── build key lookup: (mesh, bs_node, target) → [key_dict,...]
        key_map = {}
        for row in self._read_csv(p_keys):
            key = (row["mesh"], row["bs_node"], row["target"])
            key_map.setdefault(key, []).append({
                "t":  float(row["t"]),
                "v":  float(row["v"]),
                "it": row["it"],
                "ot": row["ot"],
                "ia": float(row["ia"]),
                "oa": float(row["oa"]),
                "iw": float(row["iw"]),
                "ow": float(row["ow"]),
            })

        # ── reconstruct the nested data structure expected by _recreate_blendshape
        # Group target rows by mesh → bs_node, preserving w_idx order
        mesh_data = {}
        for row in self._read_csv(p_targets):
            mesh    = row["mesh"]
            bs_node = row["bs_node"]
            target  = row["target"]
            w_idx   = int(row["w_idx"])
            key     = (mesh, bs_node, target)

            bs_entry = mesh_data.setdefault(mesh, {}).setdefault(bs_node, {
                "targets": {}, "driven_keys": {}
            })
            bs_entry["targets"][target] = {
                "w_idx":  w_idx,
                "deltas": delta_map.get(key, []),
            }
            if row["driver"]:
                bs_entry["driven_keys"][target] = {
                    "driver":     row["driver"],
                    "curve_name": row["curve_name"],
                    "curve_type": row["curve_type"],
                    "pre_inf":    row["pre_inf"],
                    "post_inf":   row["post_inf"],
                    "keys":       key_map.get(key, []),
                }

        for mesh_name, bs_map in mesh_data.items():
            if not cmds.objExists(mesh_name):
                om.MGlobal.displayWarning(f"[CBS] Mesh not found: {mesh_name}")
                continue
            shapes = cmds.listRelatives(mesh_name, shapes=True, noIntermediate=True) or []
            if not shapes:
                continue
            for bs_name, bs_data in bs_map.items():
                self._recreate_blendshape(mesh_name, shapes[0], bs_name, bs_data)

        om.MGlobal.displayInfo("[CBS] Import complete.")

    @staticmethod
    def _read_csv(filepath):
        with io.open(filepath, "r", newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def _duplicate_base_mesh(self, mesh_name, mesh_shape, temp_name):
        """Duplicate the mesh at its base (pre-deformation) pose."""
        deformers = self._history(mesh_shape)
        saved = {}
        for d in deformers:
            if cmds.attributeQuery("envelope", node=d, exists=True):
                saved[d] = cmds.getAttr(f"{d}.envelope")
                cmds.setAttr(f"{d}.envelope", 0)

        dup = cmds.duplicate(mesh_name, name=temp_name)[0]

        for d, env in saved.items():
            cmds.setAttr(f"{d}.envelope", env)

        return dup

    def _recreate_blendshape(self, mesh_name, mesh_shape, bs_name, bs_data):
        targets_data = bs_data.get("targets", {})
        driven_keys  = bs_data.get("driven_keys", {})

        if not targets_data:
            return

        if cmds.objExists(bs_name) and cmds.nodeType(bs_name) == "blendShape":
            cmds.delete(bs_name)

        target_names = sorted(targets_data, key=lambda n: targets_data[n]["w_idx"])
        temp_meshes  = []

        for t_name in target_names:
            deltas = targets_data[t_name].get("deltas", [])
            dup = self._duplicate_base_mesh(mesh_name, mesh_shape, f"cbsTmp_{t_name}")
            cmds.setAttr(f"{dup}.visibility", 0)

            for vtx_idx, dx, dy, dz in deltas:
                vtx = f"{dup}.vtx[{vtx_idx}]"
                pos = cmds.xform(vtx, q=True, os=True, t=True)
                cmds.xform(vtx, os=True, t=[pos[0] + dx, pos[1] + dy, pos[2] + dz])

            temp_meshes.append(dup)

        if not temp_meshes:
            return

        # Disable all deformers so Maya cannot compute automatic initial weights
        # by comparing targets against the currently deformed mesh shape.
        saved_env = {}
        for d in self._history(mesh_shape):
            if cmds.attributeQuery("envelope", node=d, exists=True):
                saved_env[d] = cmds.getAttr(f"{d}.envelope")
                cmds.setAttr(f"{d}.envelope", 0)

        # frontOfChain=True places the blendShape before the skinCluster (pre-deformation)
        new_bs = cmds.blendShape(
            temp_meshes + [mesh_name],
            name=bs_name,
            frontOfChain=True,
            origin="local"
        )[0]

        # Restore deformers
        for d, env in saved_env.items():
            cmds.setAttr(f"{d}.envelope", env)

        cmds.delete(temp_meshes)

        # Force all weights to 0 — safety in case Maya set any non-zero during creation
        for i in range(len(target_names)):
            try:
                cmds.setAttr(f"{new_bs}.weight[{i}]", 0)
            except Exception:
                pass

        # Rename weight aliases to the stored target names (Maya auto-names from mesh names)
        for i, t_name in enumerate(target_names):
            try:
                cmds.aliasAttr(t_name, f"{new_bs}.weight[{i}]")
            except Exception:
                pass

        # Safety: verify and enforce pre-deformation position
        if not self._is_pre_deformation(new_bs, mesh_shape):
            self._push_before_skin(new_bs, mesh_shape, mesh_name)

        for t_name, dk_data in driven_keys.items():
            self._restore_driven_key(new_bs, t_name, dk_data)

        om.MGlobal.displayInfo(f"[CBS] Recreated {bs_name} on {mesh_name}")

    def _push_before_skin(self, bs_node, mesh_shape, mesh_name):
        """Move bs_node before the deepest skinCluster using reorderDeformers."""
        hist = self._history(mesh_shape)
        skin_nodes = [n for n in hist if cmds.nodeType(n) == "skinCluster"]
        if not skin_nodes:
            return
        # skin_nodes[-1] = deepest in evaluation order (first to evaluate)
        try:
            cmds.reorderDeformers(bs_node, skin_nodes[-1], mesh_name)
            om.MGlobal.displayInfo(f"[CBS] Moved {bs_node} to pre-deform position.")
        except Exception as e:
            om.MGlobal.displayWarning(f"[CBS] reorderDeformers failed for {bs_node}: {e}")

    # ------------------------------------------------------------------
    # Driven key restore
    # ------------------------------------------------------------------

    def _restore_driven_key(self, bs_node, target_name, dk_data):
        """Recreate setDrivenKeyframe connections for one blendShape target."""
        driver_attr = dk_data.get("driver")
        keys        = dk_data.get("keys", [])

        if not driver_attr or not keys:
            return

        driver_node = driver_attr.split(".")[0]
        if not cmds.objExists(driver_node):
            om.MGlobal.displayWarning(
                f"[CBS] Driver not found: {driver_node}, skipping DK for {target_name}."
            )
            return

        # Resolve weight plug from alias
        aliases_flat = cmds.aliasAttr(bs_node, query=True) or []
        weight_plug  = None
        for i in range(0, len(aliases_flat), 2):
            if aliases_flat[i] == target_name:
                weight_plug = f"{bs_node}.{aliases_flat[i + 1]}"
                break

        if not weight_plug:
            om.MGlobal.displayWarning(f"[CBS] Weight plug not found for {target_name}")
            return

        # Preserve driver value to avoid permanently moving the rig
        try:
            orig_val = cmds.getAttr(driver_attr)
        except Exception:
            orig_val = None

        for key_data in keys:
            try:
                cmds.setDrivenKeyframe(
                    weight_plug,
                    currentDriver=driver_attr,
                    driverValue=key_data["t"],
                    value=key_data["v"],
                )
            except Exception as e:
                om.MGlobal.displayWarning(f"[CBS] setDrivenKeyframe failed: {e}")

        if orig_val is not None:
            try:
                cmds.setAttr(driver_attr, orig_val)
            except Exception:
                pass

        # Apply tangent and infinity settings to the created animCurve
        curve_conns = (cmds.listConnections(weight_plug, source=True, plugs=False,
                                            type="animCurve") or [])
        if not curve_conns:
            return

        dk_curve = curve_conns[0]

        for i, kd in enumerate(keys):
            try:
                cmds.keyTangent(dk_curve, index=(i, i),
                                inTangentType=kd.get("it", "linear"),
                                outTangentType=kd.get("ot", "linear"))
                if kd.get("it") in ("fixed", "clamped"):
                    cmds.keyTangent(dk_curve, index=(i, i), lock=False,
                                    inAngle=kd["ia"], inWeight=kd["iw"])
                if kd.get("ot") in ("fixed", "clamped"):
                    cmds.keyTangent(dk_curve, index=(i, i), lock=False,
                                    outAngle=kd["oa"], outWeight=kd["ow"])
            except Exception:
                pass

        try:
            cmds.setInfinity(dk_curve,
                             preInfinite=dk_data.get("pre_inf", "constant"),
                             postInfinite=dk_data.get("post_inf", "constant"))
        except Exception:
            pass

        stored_name = dk_data.get("curve_name")
        if stored_name and stored_name != dk_curve:
            try:
                cmds.rename(dk_curve, stored_name)
            except Exception:
                pass

    # ==================================================================
    # MIRROR
    # ==================================================================

    def _mirror_name(self, name):
        """
        Swap L_ ↔ R_ (and l_ ↔ r_) in a node name or 'node.attr' string.
        Works on full driver strings like 'L_arm_CTL.rotateZ' or 'l_arm_CTL.rotateZ'.
        """
        if not name:
            return name
        node, _, attr = name.partition(".")
        suffix = f".{attr}" if attr else ""

        if node.startswith("L_"):
            return "R_" + node[2:] + suffix
        if node.startswith("R_"):
            return "L_" + node[2:] + suffix
        if node.startswith("l_"):
            return "r_" + node[2:] + suffix
        if node.startswith("r_"):
            return "l_" + node[2:] + suffix
        if "_L_" in node:
            return node.replace("_L_", "_R_", 1) + suffix
        if "_R_" in node:
            return node.replace("_R_", "_L_", 1) + suffix
        if "_l_" in node:
            return node.replace("_l_", "_r_", 1) + suffix
        if "_r_" in node:
            return node.replace("_r_", "_l_", 1) + suffix
        return name

    def _mirror_driver_value(self, driver_attr, value):
        """
        Negate the driver key value for attributes that represent lateral motion
        (translateX, rotateY, rotateZ). Keeps all other axes unchanged.
        """
        short_attr = driver_attr.split(".")[-1] if "." in driver_attr else driver_attr
        return -value if short_attr in self.MIRROR_NEGATE_ATTRS else value

    def _mirror_deltas(self, deltas, mirror_table):
        """
        Return mirrored deltas for the opposite side vertices.
        YZ-plane mirror: negate X component of the delta, find the vertex at (-x, y, z).
        """
        mirrored = []
        for vtx_idx, dx, dy, dz in deltas:
            mirror_vtx = mirror_table.get(vtx_idx)
            if mirror_vtx is not None:
                mirrored.append([mirror_vtx, round(-dx, 6), round(dy, 6), round(dz, 6)])
        return mirrored

    def _mirror_dk_data(self, dk_data):
        """Return a deep copy of dk_data with driver name and key values mirrored."""
        m = copy.deepcopy(dk_data)
        m["driver"]     = self._mirror_name(dk_data["driver"])
        m["curve_name"] = self._mirror_name(dk_data.get("curve_name", ""))
        m["keys"] = [
            dict(kd, t=self._mirror_driver_value(dk_data["driver"], kd["t"]))
            for kd in dk_data["keys"]
        ]
        return m

    def _build_mirror_vertex_table(self, mesh_name):
        """
        Build {vtx_idx: mirror_vtx_idx} for a YZ-plane symmetric mesh.
        Matches each vertex at (x, y, z) to the vertex nearest (-x, y, z).
        Vertices on the centre seam (x ≈ 0) map to themselves.
        """
        vtx_count = cmds.polyEvaluate(mesh_name, vertex=True)

        # Round to 3 dp (≈ 1 mm tolerance) for reliable dict lookup
        pos_to_idx = {}
        for i in range(vtx_count):
            px, py, pz = cmds.xform(f"{mesh_name}.vtx[{i}]", q=True, os=True, t=True)
            key = (round(px, 3), round(py, 3), round(pz, 3))
            pos_to_idx[key] = i

        mirror_table = {}
        for i in range(vtx_count):
            px, py, pz = cmds.xform(f"{mesh_name}.vtx[{i}]", q=True, os=True, t=True)
            mirror_key = (round(-px, 3), round(py, 3), round(pz, 3))
            if mirror_key in pos_to_idx:
                mirror_table[i] = pos_to_idx[mirror_key]

        return mirror_table

    def mirror_in_scene(self):
        """
        For every pre-deformation blendShape whose name starts with L_ or R_,
        create a mirrored blendShape on the opposite side if it doesn't exist yet.

        - Geometry: vertex deltas are reflected across the YZ plane.
        - Driven keys: driver node name is mirrored (L_→R_), key driver values are
          negated for translateX / rotateY / rotateZ (standard biped convention).
        """
        bs_map = self._collect_pre_deform_blendshapes()
        if not bs_map:
            om.MGlobal.displayWarning("[CBS] No pre-deformation blendShapes found to mirror.")
            return

        created = 0

        for mesh_name, bs_nodes in bs_map.items():
            shapes = cmds.listRelatives(mesh_name, shapes=True, noIntermediate=True) or []
            if not shapes:
                continue
            mesh_shape = shapes[0]

            mirror_table = None  # built lazily once per mesh

            for bs_node in bs_nodes:
                mirror_bs_name = self._mirror_name(bs_node)
                if mirror_bs_name == bs_node:
                    om.MGlobal.displayWarning(
                        f"[CBS] {bs_node} has no L_/R_ side — skipping mirror."
                    )
                    continue

                if cmds.objExists(mirror_bs_name):
                    om.MGlobal.displayInfo(
                        f"[CBS] Mirror {mirror_bs_name} already exists, skipping."
                    )
                    continue

                if mirror_table is None:
                    om.MGlobal.displayInfo(f"[CBS] Building mirror vertex table for {mesh_name}…")
                    mirror_table = self._build_mirror_vertex_table(mesh_name)

                self._create_mirror_blendshape(
                    bs_node, mirror_bs_name, mesh_name, mesh_shape, mirror_table
                )
                created += 1

        if created:
            om.MGlobal.displayInfo(f"[CBS] Mirror complete — {created} blendShape(s) created.")
        else:
            om.MGlobal.displayInfo("[CBS] No new mirrors needed.")

    def _create_mirror_blendshape(self, src_bs, mirror_bs_name, mesh_name, mesh_shape, mirror_table):
        """Create one mirrored blendShape node from src_bs."""
        aliases_flat = cmds.aliasAttr(src_bs, query=True) or []
        idx_to_name = {
            int(aliases_flat[i + 1].split("[")[1].rstrip("]")): aliases_flat[i]
            for i in range(0, len(aliases_flat), 2)
        }

        sorted_indices = sorted(idx_to_name)
        temp_meshes    = []
        ordered_names  = []

        for w_idx in sorted_indices:
            t_name        = idx_to_name[w_idx]
            mirror_t_name = self._mirror_name(t_name)
            deltas        = self._get_target_deltas(src_bs, w_idx)
            mirror_deltas = self._mirror_deltas(deltas, mirror_table)

            dup = self._duplicate_base_mesh(mesh_name, mesh_shape, f"cbsTmp_{mirror_t_name}")
            cmds.setAttr(f"{dup}.visibility", 0)

            for vtx_idx, dx, dy, dz in mirror_deltas:
                vtx = f"{dup}.vtx[{vtx_idx}]"
                pos = cmds.xform(vtx, q=True, os=True, t=True)
                cmds.xform(vtx, os=True, t=[pos[0] + dx, pos[1] + dy, pos[2] + dz])

            temp_meshes.append(dup)
            ordered_names.append(mirror_t_name)

        if not temp_meshes:
            return

        new_bs = cmds.blendShape(
            temp_meshes + [mesh_name],
            name=mirror_bs_name,
            frontOfChain=True,
            origin="local"
        )[0]

        cmds.delete(temp_meshes)

        # Rename aliases to the correct mirrored target names
        for i, mirror_t_name in enumerate(ordered_names):
            try:
                cmds.aliasAttr(mirror_t_name, f"{new_bs}.weight[{i}]")
            except Exception:
                pass

        # Enforce pre-deformation
        if not self._is_pre_deformation(new_bs, mesh_shape):
            self._push_before_skin(new_bs, mesh_shape, mesh_name)

        # Restore driven keys with mirrored driver + values
        for w_idx, mirror_t_name in zip(sorted_indices, ordered_names):
            dk = self._get_driven_key(src_bs, w_idx)
            if dk:
                mirror_dk = self._mirror_dk_data(dk)
                self._restore_driven_key(new_bs, mirror_t_name, mirror_dk)

        om.MGlobal.displayInfo(f"[CBS] Created mirror: {mirror_bs_name} on {mesh_name}")

    # ==================================================================
    # MIRROR TARGETS (within the same blendShape node)
    # ==================================================================

    def mirror_targets(self):
        """
        For every pre-deformation blendShape target whose name contains L_/R_,
        create the mirrored target INSIDE THE SAME blendShape node if it doesn't exist.

        - Geometry: vertex deltas reflected across the YZ plane.
        - Driver: the mirrored controller (L_→R_) is connected via setDrivenKeyframe
          with negated driver values for translateX / rotateY / rotateZ.
        """
        bs_map = self._collect_pre_deform_blendshapes()
        if not bs_map:
            om.MGlobal.displayWarning("[CBS] No pre-deformation blendShapes found.")
            return

        created = 0

        for mesh_name, bs_nodes in bs_map.items():
            shapes = cmds.listRelatives(mesh_name, shapes=True, noIntermediate=True) or []
            if not shapes:
                continue
            mesh_shape  = shapes[0]
            mirror_table = None  # built lazily once per mesh

            for bs_node in bs_nodes:
                aliases_flat = cmds.aliasAttr(bs_node, query=True) or []
                idx_to_name  = {
                    int(aliases_flat[i + 1].split("[")[1].rstrip("]")): aliases_flat[i]
                    for i in range(0, len(aliases_flat), 2)
                }
                existing_names = set(idx_to_name.values())
                next_idx       = (max(idx_to_name) + 1) if idx_to_name else 0

                for w_idx in sorted(idx_to_name):
                    t_name      = idx_to_name[w_idx]
                    mirror_name = self._mirror_name(t_name)

                    if mirror_name == t_name:
                        continue  # no L_/R_ in name — nothing to mirror
                    if mirror_name in existing_names:
                        continue  # target already exists

                    if mirror_table is None:
                        om.MGlobal.displayInfo(
                            f"[CBS] Building mirror vertex table for {mesh_name}…"
                        )
                        mirror_table = self._build_mirror_vertex_table(mesh_name)

                    deltas        = self._get_target_deltas(bs_node, w_idx)
                    mirror_deltas = self._mirror_deltas(deltas, mirror_table)

                    # Build target mesh with mirrored shape
                    dup = self._duplicate_base_mesh(
                        mesh_name, mesh_shape, f"cbsTmp_{mirror_name}"
                    )
                    cmds.setAttr(f"{dup}.visibility", 0)
                    for vtx_idx, dx, dy, dz in mirror_deltas:
                        vtx = f"{dup}.vtx[{vtx_idx}]"
                        pos = cmds.xform(vtx, q=True, os=True, t=True)
                        cmds.xform(vtx, os=True,
                                   t=[pos[0] + dx, pos[1] + dy, pos[2] + dz])

                    # Disable deformers so Maya cannot bias the initial weight
                    saved_env = {}
                    for d in self._history(mesh_shape):
                        if cmds.attributeQuery("envelope", node=d, exists=True):
                            saved_env[d] = cmds.getAttr(f"{d}.envelope")
                            cmds.setAttr(f"{d}.envelope", 0)

                    # Add target to the existing blendShape node at next_idx
                    cmds.blendShape(bs_node, edit=True,
                                    target=[mesh_name, next_idx, dup, 1.0])

                    for d, env in saved_env.items():
                        cmds.setAttr(f"{d}.envelope", env)

                    cmds.delete(dup)

                    # Name the new alias and ensure weight starts at 0
                    try:
                        cmds.aliasAttr(mirror_name, f"{bs_node}.weight[{next_idx}]")
                    except Exception:
                        pass
                    try:
                        cmds.setAttr(f"{bs_node}.weight[{next_idx}]", 0)
                    except Exception:
                        pass

                    # Connect to mirrored driver via driven key
                    dk = self._get_driven_key(bs_node, w_idx)
                    if dk:
                        mirror_dk = self._mirror_dk_data(dk)
                        mirror_driver = mirror_dk["driver"].split(".")[0]
                        if cmds.objExists(mirror_driver):
                            self._restore_driven_key(bs_node, mirror_name, mirror_dk)
                        else:
                            om.MGlobal.displayWarning(
                                f"[CBS] Mirror driver not found: {mirror_driver} "
                                f"— {mirror_name} created without driven key."
                            )

                    existing_names.add(mirror_name)
                    idx_to_name[next_idx] = mirror_name
                    next_idx += 1
                    created += 1
                    om.MGlobal.displayInfo(
                        f"[CBS] Created mirror target: {mirror_name} in {bs_node}"
                    )

        if created:
            om.MGlobal.displayInfo(
                f"[CBS] Mirror targets complete — {created} target(s) created."
            )
        else:
            om.MGlobal.displayInfo("[CBS] No new mirror targets needed.")
