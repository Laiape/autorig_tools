"""Summarize audited source and bounded capability evidence."""
import hashlib
import json
from pathlib import Path

root = Path("C:/proyectos/auto-rig/autorig_tools")
out = root / "maya_tools/docs/validation/ng_nurbs_bridge_20261016"
ng = Path("C:/ProgramData/Autodesk/ApplicationPlugins/ngskintools2/Contents")
sources = [
    ng / "scripts/ngSkinTools2" / name for name in (
        "api/target_info.py", "api/plugin.py", "api/events.py",
        "api/layers.py", "api/paint.py", "ui/mainwindow.py",
        "ui/targetui.py", "ui/actions.py", "ui/paintContextCallbacks.py",
        "pluginCallbacks.py", "operations/layers.py", "operations/paint.py")
]
sources += [ng / "plug-ins/2026/ngSkinTools2.mll"]
sources += [root / "maya_tools/scripts" / name for name in (
    "ui/skinning_tool_adapters.py", "ui/skinning_manager_UI.py", "framework/context.py")]
probe = json.loads((out / "probe.json").read_text())
summary = {
    "status": "design_pending_validation_no_runtime_implementation",
    "date": "2026-10-16",
    "maya": probe["maya"], "ng": probe["ng"],
    "source_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
    "cases": [{k: v for k, v in c.items() if k not in (
        "index_rows", "membership", "weightList_indices", "input_component_elements",
        "nonzero_weight_array_rows")} for c in probe["cases"]],
    "limits": ["No GUI brush or VP2 validation", "No performance measurement",
               "kClosed fixture did not retain kClosed",
               "Periodic and sparse-influence live transfer not validated",
               "Artist session queried read-only; fixtures created in separate mayapy"]
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="ascii")
print("Wrote audit summary and source hashes:", out / "summary.json")
