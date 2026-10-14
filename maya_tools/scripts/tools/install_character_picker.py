"""Portable bundle installer. Drag into Maya 2024+; no AutoRig required."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys


def open_bundle(directory):
    path = Path(directory)/"character_picker_runtime.py"
    name = "character_picker_" + re.sub(r"\W", "_", str(directory))
    old = sys.modules.get(name)
    if old and getattr(old, "_WINDOW", None):
        try:
            old._WINDOW.close()
        except RuntimeError:
            # Maya can already have deleted the Qt child during a scene change.
            pass
        old._WINDOW = None
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.show()


def install(source=None):
    import maya.cmds as cmds
    import maya.mel as mel
    if cmds.about(batch=True) or int(cmds.about(apiVersion=True)) < 20240000:
        raise RuntimeError("Character Picker requires Maya 2024+ with a graphical interface.")
    source = Path(source or Path(__file__).parent)
    config = json.loads((source/"picker_config.json").read_text(encoding="utf-8"))
    character = config["character"]
    slug = re.sub(r"[^A-Za-z0-9_]", "_", character)
    files = ["character_picker_runtime.py", "character_picker_scene.py", "picker.json", "picker_config.json",
             "install_character_picker.py"] + [p["background"] for p in config["panels"]]
    for relative in files:
        path = (source/relative).resolve()
        if not path.is_relative_to(source.resolve()) or not path.is_file():
            raise ValueError("Invalid or missing bundle file: " + relative)
    scripts = Path(cmds.internalVar(userAppDir=True))/"scripts"
    destination = scripts/"character_picker_payloads"/slug
    for relative in files:
        target = destination/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if (source/relative).resolve() != target.resolve():
            shutil.copy2(source/relative, target)
    launcher_name = slug.lower()+"_character_picker_launcher"
    launcher = scripts/(launcher_name+".py")
    launcher.write_text(
        'import importlib.util\nfrom pathlib import Path\n'
        'def show():\n'
        '    root = Path(__file__).parent / '+repr("character_picker_payloads/"+slug)+'\n'
        '    spec = importlib.util.spec_from_file_location("portable_picker_installer", str(root / "install_character_picker.py"))\n'
        '    module = importlib.util.module_from_spec(spec)\n'
        '    spec.loader.exec_module(module)\n'
        '    return module.open_bundle(root)\n', encoding="utf-8")
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    shelf = mel.eval("$pickerShelf = $gShelfTopLevel")+"|AutoRig"
    if not cmds.shelfLayout(shelf, exists=True):
        shelf = cmds.shelfLayout("AutoRig", parent=shelf.rsplit("|", 1)[0])
    label = character+"Picker"
    for child in cmds.shelfLayout(shelf, query=True, childArray=True) or []:
        if cmds.objectTypeUI(child) == "shelfButton" and cmds.shelfButton(child, query=True, label=True) == label:
            cmds.deleteUI(child)
    cmds.shelfButton(slug+"_character_picker_button", parent=shelf, label=label,
                     annotation=character+" body and face picker", image="pickWalkUp.png",
                     imageOverlayLabel=character, sourceType="python",
                     command="import "+launcher_name+"; "+launcher_name+".show()")
    shelf_dir = Path(cmds.internalVar(userPrefDir=True))/"shelves"
    shelf_dir.mkdir(parents=True, exist_ok=True)
    cmds.saveShelf(shelf, str(shelf_dir/"shelf_AutoRig"))
    spec = importlib.util.spec_from_file_location("portable_picker_scene", str(destination/"character_picker_scene.py"))
    scene_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scene_module)
    roots = scene_module.matching_roots(character)
    for root in roots:
        scene_module.attach(destination, root)
    if roots:
        return scene_module._ar_picker_state()["window"]
    return open_bundle(destination)


def onMayaDroppedPythonFile(*_):
    return install()


if __name__ == "__main__":
    install()
