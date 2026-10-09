"""Interactive Proximity Wrap bake using an existing animated range of motion."""
import os
import re
from importlib import reload
import maya.cmds as cmds
from tools import proximity_bake


def show():
    reload(proximity_bake)
    window = "proximityBakeUI"
    if cmds.window(window, exists=True):
        cmds.deleteUI(window)
    cmds.window(window, title="Bake Proximity Wrap to Skin", widthHeight=(530, 410), sizeable=True)
    cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
    cmds.text(label="Selecciona meshes con Proximity Wrap o nodos _PRX.", align="left")
    cmds.text(label="Anima poses variadas en el rango indicado antes de hacer bake.", align="left")
    start = cmds.floatFieldGrp(label="Inicio / Fin / Paso", numberOfFields=3,
                               value1=cmds.playbackOptions(query=True, minTime=True),
                               value2=cmds.playbackOptions(query=True, maxTime=True), value3=1)
    bind = cmds.floatFieldGrp(label="Frame de bind", numberOfFields=1,
                              value1=cmds.currentTime(query=True))
    influences = cmds.intFieldGrp(label="Max. influencias / vertice", numberOfFields=1, value1=8)
    cmds.separator(height=10)
    cmds.text(label="Crea copias <mesh>_BAKED con skin. Conserva los originales.", align="left")
    save = cmds.checkBox(label="Guardar siguiente SKC para rebuild", value=False)
    path = cmds.textFieldButtonGrp(label="Archivo SKC", buttonLabel="Elegir...", text="")

    def choose(*unused):
        from tools.skin_manager_api import SkinManager
        manager = SkinManager()
        latest = manager.get_latest_version_path()
        match = re.search(r"_v(\d+)\.skc$", latest)
        version = int(match.group(1)) + 1 if match and os.path.isfile(latest) else 1
        suggested = os.path.join(manager.folder_path, "{}_v{:03d}.skc".format(manager.asset_name, version))
        paths = cmds.fileDialog2(fileMode=0, caption="Guardar nuevo SKC de bake",
                                fileFilter="Skin Cluster (*.skc)", startingDirectory=suggested)
        if paths:
            cmds.textFieldButtonGrp(path, edit=True, text=paths[0])
            cmds.checkBox(save, edit=True, value=True)

    cmds.textFieldButtonGrp(path, edit=True, buttonCommand=choose)
    cmds.text(label="El SKC sustituye los wraps seleccionados por skins; incluye el resto de la escena.", align="left")
    cmds.text(label="Los pesos aproximan las poses muestreadas. Revisa el error en Script Editor.", align="left")

    def bake(*unused):
        try:
            output = None
            if cmds.checkBox(save, query=True, value=True):
                output = cmds.textFieldButtonGrp(path, query=True, text=True).strip()
                if not output:
                    raise RuntimeError("Elige el archivo SKC de destino.")
                if not output.lower().endswith(".skc"):
                    output += ".skc"
            result = proximity_bake.bake_selected(
                cmds.floatFieldGrp(start, query=True, value1=True),
                cmds.floatFieldGrp(start, query=True, value2=True),
                cmds.floatFieldGrp(start, query=True, value3=True),
                cmds.floatFieldGrp(bind, query=True, value1=True),
                cmds.intFieldGrp(influences, query=True, value1=True), export_path=output)
            cmds.text(status, edit=True, label="Bake de {} meshes completado.{}".format(
                len(result["records"]), " SKC: " + output if output else ""))
        except Exception as exc:
            cmds.warning(str(exc))
            cmds.text(status, edit=True, label=str(exc))

    cmds.button(label="Bake de seleccion a Skin", height=36, command=bake)
    status = cmds.text(label="Listo.", align="left", wordWrap=True)
    cmds.showWindow(window)
