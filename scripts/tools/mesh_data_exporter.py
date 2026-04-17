"""
mesh_data_exporter.py
=====================
Exports all data needed for automatic skin transfer from a source character.

Run this ONCE on the source character scene (with skin active).
The output files are stored in:
    assets/<char>/skin_clusters/<mesh>.skc      — sparse weights (via SkinManager)
    assets/<char>/skin_clusters/<mesh>.skinmap  — pre-computed UV weight map

At rig build time, AutoRig.import_weights() will find these files and run
the skin transfer to any new character automatically — the source mesh does
NOT need to be in the scene during the build.

Usage
-----
    from tools import mesh_data_exporter
    from importlib import reload
    reload(mesh_data_exporter)

    # Export everything skinned in the scene:
    mesh_data_exporter.SourceSkinExporter().export_all()

    # Export a single mesh explicitly:
    mesh_data_exporter.SourceSkinExporter().export_mesh("body_GEO")
"""

import os
import json

import maya.cmds as cmds
import maya.api.OpenMaya as om

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from tools import skin_manager_api
    from tools import auto_skin_transfer
    from utils import data_manager
    HAS_PIPELINE = True
except ImportError:
    HAS_PIPELINE = False

_LOG  = om.MGlobal.displayInfo
_WARN = om.MGlobal.displayWarning
_ERR  = om.MGlobal.displayError


# ─────────────────────────────────────────────────────────────────────────────

class SourceSkinExporter:
    """
    Exports the source character's skin data in two formats:

    .skc       Sparse skin weights, joint names, vertex count.
               Compatible with SkinManager.import_skins().

    .skinmap   Pre-computed SkinUVMap: UV coordinates projected relative to
               the skeleton + weight matrix. The transfer tool uses this to
               apply skinning to new characters without the source in scene.
    """

    UV_METHOD = "skeleton"   # UV projection method for the skinmap

    def __init__(self):
        self._system = auto_skin_transfer.AutoSkinTransferSystem() if HAS_PIPELINE else None

    # ── public ──────────────────────────────────────────────────────────────

    # Body-mesh keywords — meshes whose short name contains any of these
    # will be included when body_only=True (default).
    BODY_KEYWORDS = ("body",)

    def export_all(self, uv_method=None, force=False, body_only=True):
        """
        Finds skinned meshes in the scene and exports .skc + .skinmap to
        assets/source/skin_clusters/ (always, regardless of scene context).

        Args:
            uv_method  (str):  "skeleton" | "cylindrical" | "planar".
            force      (bool): Overwrite existing .skinmap files.
            body_only  (bool): Only export meshes whose name contains a body
                               keyword (default True).  Set False to export all.

        Returns:
            list[str]: Paths of exported .skinmap files.
        """
        if not HAS_NUMPY:
            _ERR("SourceSkinExporter requires numpy.")
            return []

        all_meshes = self._find_skinned_meshes()
        if not all_meshes:
            _WARN("SourceSkinExporter.export_all: no skinned meshes found.")
            return []

        if body_only:
            meshes = [
                m for m in all_meshes
                if any(kw in m.lower() for kw in self.BODY_KEYWORDS)
            ]
            if not meshes:
                _WARN(
                    f"SourceSkinExporter: no body mesh found among {all_meshes}. "
                    "Pass body_only=False to export all."
                )
                return []
        else:
            meshes = all_meshes

        _LOG(f"SourceSkinExporter: exporting {len(meshes)} mesh(es) → {meshes}")
        results = []
        for mesh in meshes:
            path = self.export_mesh(mesh, uv_method=uv_method, force=force)
            if path:
                results.append(path)

        _LOG(f"=== SourceSkinExporter: exported {len(results)}/{len(meshes)} meshes ===")
        return results

    def export_mesh(self, mesh, root_joint=None, uv_method=None, force=False):
        """
        Exports one mesh's skin data.

        Steps
        -----
        1. Resolve paths (character name → skin_clusters folder).
        2. Export .skc via SkinManager (skip if already up to date).
        3. Project skeleton-relative UVs onto the mesh.
        4. Build SkinUVMap and save as .skinmap.
        5. Cleanup temp UV set.

        Args:
            mesh       (str):  Maya transform name.
            root_joint (str):  Skeleton root; auto-detected if None.
            uv_method  (str):  UV projection method.
            force      (bool): Overwrite existing .skinmap.

        Returns:
            str | None: Path to the .skinmap file, or None on failure.
        """
        if not HAS_NUMPY:
            _ERR("SourceSkinExporter requires numpy.")
            return None

        if not cmds.objExists(mesh):
            _ERR(f"SourceSkinExporter: '{mesh}' not in scene.")
            return None

        method = uv_method or self.UV_METHOD
        _LOG(f"--- SourceSkinExporter: exporting '{mesh}' [{method}] ---")

        # ── 1. Resolve paths — always write to assets/source/ ─────────
        folder     = self._skin_clusters_folder("source")
        mesh_short = mesh.split("|")[-1].split(":")[-1]
        skinmap_path = os.path.join(folder, f"{mesh_short}.skinmap")
        skc_path     = os.path.join(folder, "source_v001.skc")

        if os.path.exists(skinmap_path) and not force:
            _LOG(f"  .skinmap already exists (use force=True to overwrite): {skinmap_path}")
            return skinmap_path

        os.makedirs(folder, exist_ok=True)

        # ── 2. Find skin cluster ──────────────────────────────────────
        skin_cluster = self._find_skin(mesh)
        if not skin_cluster:
            _WARN(f"  No skinCluster on '{mesh}', skipping.")
            return None

        # ── 3. Export .skc (SkinManager) ─────────────────────────────
        self._export_skc(skc_path)

        # ── 4. Find root joint ────────────────────────────────────────
        if not root_joint:
            root_joint = self._system._find_root_joint(skin_cluster)
        if not root_joint:
            _ERR(f"  Cannot determine root joint for '{mesh}'.")
            return None
        _LOG(f"  Root joint: {root_joint}")

        # ── 5. Analyze skeleton ───────────────────────────────────────
        joint_data = self._system.zone_analyzer.analyze(root_joint)
        if not joint_data:
            return None

        # ── 6. Build UV projection on source mesh ─────────────────────
        uv_mod = self._system.uv_mod
        _LOG(f"  Projecting UVs [{method}]…")

        # build() normally projects on source+target; here source == target,
        # so we call the per-mesh method directly (avoids double projection).
        if method == "skeleton":
            ok = uv_mod._project_skeleton(mesh, joint_data)
        elif method == "cylindrical":
            ok = uv_mod._project_cylindrical(mesh, joint_data)
        else:
            ok = uv_mod._project_planar(mesh, joint_data)

        if not ok:
            _ERR(f"  UV projection failed on '{mesh}'.")
            uv_mod.cleanup(mesh)
            return None

        try:
            u_coords, v_coords = uv_mod.get_uv_coords(mesh)
        except Exception as e:
            _ERR(f"  UV read failed: {e}")
            uv_mod.cleanup(mesh)
            return None

        # ── 7. Build SkinUVMap ────────────────────────────────────────
        _LOG("  Building SkinUVMap…")
        skin_map = self._system.sample_mod.build_map(mesh, skin_cluster, u_coords, v_coords)
        if skin_map is None:
            uv_mod.cleanup(mesh)
            return None

        # ── 8. Save .skinmap ──────────────────────────────────────────
        skin_map.save(skinmap_path)
        _LOG(f"  .skinmap saved → {skinmap_path}")

        # ── 9. Cleanup ────────────────────────────────────────────────
        uv_mod.cleanup(mesh)

        return skinmap_path

    # ── static query helpers ─────────────────────────────────────────────────

    @staticmethod
    def find_skinmaps_for_char(source_char="source"):
        """
        Returns a dict  {mesh_short_name: skinmap_path}
        by scanning the source character's skin_clusters folder.
        """
        folder  = SourceSkinExporter._skin_clusters_folder(source_char)
        if not os.path.exists(folder):
            return {}
        result = {}
        for fname in os.listdir(folder):
            if fname.endswith(".skinmap"):
                mesh_name = fname[:-len(".skinmap")]
                result[mesh_name] = os.path.normpath(os.path.join(folder, fname))
        return result

    @staticmethod
    def find_skc_for_char(source_char="source"):
        """Returns the latest .skc path for the source character, or None."""
        folder = SourceSkinExporter._skin_clusters_folder(source_char)
        if not os.path.exists(folder):
            return None
        skc_files = [
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.endswith(".skc")
        ]
        return max(skc_files, key=os.path.getmtime) if skc_files else None

    # ── private ──────────────────────────────────────────────────────────────

    def _find_skinned_meshes(self):
        """Returns transforms of all meshes that have a skinCluster."""
        results = []
        seen    = set()
        it = om.MItDependencyNodes(om.MFn.kSkinClusterFilter)
        while not it.isDone():
            fn = om.MFnDependencyNode(it.thisNode())
            plug = fn.findPlug("outputGeometry", False)
            for i in range(plug.numElements()):
                try:
                    dst = plug.elementByPhysicalIndex(i).destinations()
                    for d in dst:
                        node = d.node()
                        if node.hasFn(om.MFn.kMesh):
                            dag = om.MFnDagNode(node)
                            if not dag.isIntermediateObject:
                                parent = om.MFnDagNode(dag.parent(0))
                                name   = parent.name()
                                if name not in seen:
                                    seen.add(name)
                                    results.append(name)
                except Exception:
                    pass
            it.next()
        return results

    def _find_skin(self, mesh):
        shape = (cmds.listRelatives(mesh, shapes=True) or [mesh])[0]
        hist  = cmds.listHistory(shape, pruneDagObjects=True, interestLevel=1) or []
        skins = [n for n in hist if cmds.nodeType(n) == "skinCluster"]
        return skins[-1] if skins else None

    def _export_skc(self, skc_path):
        """Delegates .skc export to SkinManager."""
        if not HAS_PIPELINE:
            return
        try:
            from tools import skin_manager_api
            skinner = skin_manager_api.SkinManager()
            skinner.export_skins(in_path=skc_path)
        except Exception as e:
            _WARN(f"  .skc export failed (non-critical): {e}")

    @staticmethod
    def _get_char_name():
        """
        Detects the character name for EXPORT context.

        Priority
        --------
        1. Scene assemblies (most reliable when the source scene is open).
        2. Build cache (fallback, may point to a different character being rigged).
        3. Literal "source".

        The build cache is intentionally checked LAST because during export the
        user has the source scene open, not a rig build scene.
        """
        # 1. First non-camera root transform in the scene
        assemblies = cmds.ls(assemblies=True, transforms=True) or []
        for a in assemblies:
            if not cmds.listRelatives(a, type="camera"):
                return a

        # 2. Build cache fallback
        if HAS_PIPELINE:
            try:
                name = data_manager.DataExportBiped().get_data(
                    "basic_structure", "character_name"
                )
                if name:
                    return name
            except Exception:
                pass

        return "source"

    @staticmethod
    def _skin_clusters_folder(char_name):
        """Resolves  <repo_root>/assets/<char_name>/skin_clusters/"""
        script_path = os.path.realpath(__file__)
        # scripts/tools/mesh_data_exporter.py → go up 3 levels to repo root
        repo_root = os.path.dirname(
            os.path.dirname(os.path.dirname(script_path))
        )
        return os.path.normpath(
            os.path.join(repo_root, "assets", char_name, "skin_clusters")
        )
