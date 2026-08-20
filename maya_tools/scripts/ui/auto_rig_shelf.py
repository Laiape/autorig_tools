import maya.cmds as cmds
import maya.mel as mel

SHELF_NAME = "AutoRig"

# (etiqueta, icono, anotación, comando python)
# Para añadir un botón nuevo: una fila más aquí. Los iconos viven en
# maya_tools/icons (el .mod la añade al XBMLANGPATH, basta el nombre).
SHELF_BUTTONS = [
    ("AssetMgr", "myLogo.png", "Character / Asset Manager",
     "from maya_tools.scripts.ui import auto_rig_UI\n"
     "auto_rig_UI.show_character_manager_ui()"),
]


def create_shelf():
    """Crea (o regenera) el shelf AutoRig con los botones custom."""
    if cmds.about(batch=True):
        return None

    top = mel.eval("$tmp = $gShelfTopLevel")
    if cmds.shelfLayout(SHELF_NAME, exists=True):
        cmds.deleteUI(SHELF_NAME, layout=True)

    shelf = cmds.shelfLayout(SHELF_NAME, parent=top)
    for label, icon, annotation, command in SHELF_BUTTONS:
        cmds.shelfButton(
            parent=shelf,
            label=label,
            annotation=annotation,
            image=icon,
            image1=icon,
            style="iconOnly",
            sourceType="python",
            command=command,
        )
    return shelf
