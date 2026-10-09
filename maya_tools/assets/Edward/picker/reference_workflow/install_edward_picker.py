"""Drag this file into Maya 2024+ to install/open Edward's native picker."""
import importlib
import importlib.util
from pathlib import Path
import shutil
import sys


def install():
    import maya.cmds as cmds
    import maya.mel as mel
    if int(cmds.about(apiVersion=True)) < 20240000:
        raise RuntimeError("Edward Picker requires Maya 2024 or later.")
    source = Path(__file__).resolve().parent
    scripts = Path(cmds.internalVar(userAppDir=True))/"scripts"
    destination = scripts/"edward_picker_payload"
    files = ["edward_maya_picker.py", "Edward_reference_picker.json",
             "backgrounds/body.png", "backgrounds/face.png", "edward_face_front_hd.png"]
    # Check the complete bundle before installing anything.
    for relative in files:
        if not (source/relative).is_file():
            raise FileNotFoundError("Incomplete Edward Picker bundle: " + relative)
    for relative in files:
        target = destination/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if (source/relative).resolve() != target.resolve():
            shutil.copy2(str(source/relative), str(target))
    launcher = scripts/"edward_picker_launcher.py"
    launcher.write_text(
        'import importlib.util\nfrom pathlib import Path\nimport sys\n\n'
        'def show():\n'
        '    path = Path(__file__).parent / "edward_picker_payload/edward_maya_picker.py"\n'
        '    name = "edward_maya_picker"\n'
        '    old = sys.modules.get(name)\n'
        '    if old is not None and getattr(old, "_WINDOW", None) is not None:\n'
        '        try:\n'
        '            old._WINDOW.close()\n'
        '        except RuntimeError:\n'
        '            pass\n'
        '    spec = importlib.util.spec_from_file_location(name, str(path))\n'
        '    module = importlib.util.module_from_spec(spec)\n'
        '    sys.modules[name] = module\n'
        '    spec.loader.exec_module(module)\n'
        '    return module.show()\n', encoding="utf-8")
    if str(scripts) not in sys.path:
        sys.path.insert(0,str(scripts))
    shelf_top = mel.eval("$temporaryEdwardShelf = $gShelfTopLevel")
    shelf = shelf_top+"|AutoRig"
    if not cmds.shelfLayout(shelf, exists=True):
        shelf = cmds.shelfLayout("AutoRig", parent=shelf_top)
    button = shelf+"|edward_picker_shelf_button"
    if cmds.shelfButton(button, exists=True):
        cmds.deleteUI(button)
    cmds.shelfButton("edward_picker_shelf_button", parent=shelf, label="EdwardPicker",
                     annotation="Edward body and face picker", image="pickWalkUp.png",
                     imageOverlayLabel="Edward", sourceType="python",
                     command="import edward_picker_launcher; edward_picker_launcher.show()")
    cmds.saveShelf(shelf, str(Path(cmds.internalVar(userShelfDir=True))/"shelf_AutoRig"))
    importlib.invalidate_caches()
    sys.modules.pop("edward_picker_launcher",None)
    launcher_module = importlib.import_module("edward_picker_launcher")
    launcher_module.show()
    return str(destination)


def onMayaDroppedPythonFile(*_):
    return install()


if __name__ == "__main__":
    install()
