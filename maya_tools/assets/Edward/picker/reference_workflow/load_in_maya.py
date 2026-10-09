"""Load the separate Edward photo picker in DWPicker. Existing pickers are kept."""
import json
import os
from pathlib import Path


def load(namespace="", validate=True):
    import maya.cmds as cmds
    import dwpicker
    from dwpicker import scenedata
    root = Path(__file__).resolve().parent
    data = json.loads((root / "Edward_reference_picker.json").read_text())
    namespace = namespace.strip(":")
    for shape in data["shapes"]:
        if shape["image.path"]:
            path = root / "backgrounds" / Path(shape["image.path"]).name
            if not path.is_file():
                raise FileNotFoundError(str(path))
            shape["image.path"] = path.as_posix()
        if namespace:
            shape["action.targets"] = [namespace + ":" + name for name in shape["action.targets"]]
    targets = {name for s in data["shapes"] for name in s["action.targets"]}
    missing = sorted(name for name in targets if not cmds.objExists(name)) if validate else []
    if missing:
        cmds.warning("Edward picker: %s of %s targets are absent; verify rig and namespace." % (len(missing),len(targets)))
        print("Missing picker targets:\n" + "\n".join(missing))
    existing = scenedata.load_local_picker_data() or []
    existing = [p for p in existing if p["general"]["name"] != data["general"]["name"]]
    existing.append(data)
    scenedata.store_local_picker_data(existing)
    dwpicker.show()
    return {"targets":len(targets),"missing":missing,"file":str(root / "Edward_reference_picker.json")}


if __name__ == "__main__":
    load(namespace=os.environ.get("EDWARD_PICKER_NAMESPACE", ""))
