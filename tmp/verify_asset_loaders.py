"""Read migrated dependencies in a disposable Maya process."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "maya_tools/scripts"))
os.environ["MAYA_SKIP_USERSETUP_PY"] = "1"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["MAYA_APP_DIR"] = str(ROOT / "tmp/maya_asset_validation")

import maya.standalone
maya.standalone.initialize(name="python")
import maya.cmds as cmds
from maya_tools.scripts.utils import guides_manager, rig_manager
from maya_tools.scripts.tools.mesh_data_exporter import SourceSkinExporter

result = {"guides": {}, "models": {}}
for asset in sorted((ROOT / "maya_tools/assets").iterdir()):
    if not (asset / "guides").is_dir():
        continue
    data = guides_manager.read_guides_info(asset.name.lower())
    assert data, asset.name
    result["guides"][asset.name] = len(data)
    assert Path(rig_manager.asset_path(asset.name.lower(), "guides")).name == "guides"

source = Path(SourceSkinExporter._skin_clusters_folder("source"))
assert source.parent.name == "Source"
assert source.is_dir()
for character in ["Horse", "Thaiz"]:
    model = next((ROOT / "maya_tools/assets" / character / "models").glob("*.ma"))
    cmds.file(str(model), open=True, force=True, prompt=False, ignoreVersion=True,
              executeScriptNodes=False, loadReferenceDepth="none")
    assert cmds.objExists(character), character
    assert not cmds.objExists(character.lower()), character
    shapes = cmds.ls(type="mesh") or []
    assert shapes, character
    result["models"][character] = {"meshes": len(shapes), "model": model.name}

cmds.optionVar(sv=("currentAssetRigName", "thaiz"))
assert rig_manager.get_character_name_from_build() == "Thaiz"
assert rig_manager.get_character_name_from_scene() == "Thaiz"
(ROOT / "tmp/asset_loader_validation.json").write_text(json.dumps(result, indent=2))
print("ASSET_LOADERS_OK " + json.dumps(result))
sys.stdout.flush()
sys.stderr.flush()
if os.name == "nt":
    import ctypes
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    kernel.TerminateProcess(kernel.GetCurrentProcess(), 0)
else:
    os._exit(0)
