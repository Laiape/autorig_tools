import maya.cmds as cmds
from importlib import reload

from biped.tools import skin_manager
from biped.utils import curve_tool
from biped.utils import rig_manager
from biped.utils import guides_manager
from biped.autorig import create_rig

reload(skin_manager)
reload(curve_tool)
reload(rig_manager)
reload(guides_manager)
reload(create_rig)

def create_custom_menu():
    menu_id = "autorig_menu"
    menu_label = "AutoRig Tools Laia"

    if cmds.menu(menu_id, exists=True):
        cmds.deleteUI(menu_id)

    # Creamos el menú principal
    cmds.menu(menu_id, label=menu_label, parent='MayaWindow', tearOff=True)

    # --- BOTÓN RELOAD ---
    # Icono de refrescar/flechas circulares
    cmds.menuItem(label="Reload UI", command=lambda x: rebuild_ui(), image="refresh.png")
    cmds.menuItem(divider=True)

    # --- ASSET MANAGER ---
    # Icono de carpeta o proyecto
    cmds.menuItem(label="Asset Manager", subMenu=True, tearOff=True, image="fileOpen.png")
    cmds.menuItem(label="Create New Asset", command=lambda x: create_new_asset(), image="newLayerEmpty.png")
    cmds.setParent('..', menu=True)

    # --- GUIDES MANAGER ---
    # Icono de ejes o locators
    cmds.menuItem(label="Guides Manager", subMenu=True, tearOff=True, image="locator.png")
    cmds.menuItem(label="Create New Guides", command=lambda x: create_new_guides(), image="confirm.png")
    cmds.menuItem(label="Import Guides", command=lambda x: import_guides(), image="move_M.png")
    cmds.menuItem(label="Export Guides", command=lambda x: export_guides(), image="copySelected.png")
    cmds.setParent('..', menu=True)

    # --- CONTROLLERS MANAGER ---
    # Icono de círculo/curva para el gestor de controles
    cmds.menuItem(label="Controllers Manager", subMenu=True, tearOff=True, image="circle.png")
    cmds.menuItem(label="Export All Controllers", command=lambda x: export_all_controllers(), image="save.png")
    cmds.menuItem(label="Mirror Controllers", command=lambda x: mirror_controllers(), image="polyMirror.png")
    cmds.menuItem(label="Library", command=lambda x: open_library(), image="tab_library.png")
    cmds.menuItem(label="Replace Shapes", command=lambda x: replace_shapes(), image="swap.png")
    cmds.setParent('..', menu=True)

    # --- SKIN CLUSTER MANAGER ---
    # Icono de pesos/skinning
    cmds.menuItem(label="Skin Cluster Manager", subMenu=True, tearOff=True, image="paintSkinWeights.png")
    cmds.menuItem(label="Export Skin Cluster", command=lambda x: export_skin_cluster(), image="export.png")
    cmds.menuItem(label="Import Skin Cluster", command=lambda x: import_skin_cluster(), image="import.png")
    cmds.setParent('..', menu=True)

    cmds.menuItem(divider=True)

    # --- BOTÓN RESALTADO: CREAR RIG ---
    cmds.menuItem(label="CREAR RIG", command=lambda x: rig(), boldFont=True, image="kinJoint.png")

def rebuild_ui():
    from biped.ui import auto_rig_UI
    reload(auto_rig_UI)
    auto_rig_UI.create_custom_menu()


def create_new_asset():
    from biped.utils import rig_manager
    reload(rig_manager)
    rig_manager.create_new_asset()
    cmds.inViewMessage(amg='New Asset Created.', pos='midCenter', fade=True)

def create_new_guides():
    guides_manager.create_new_guides()
    cmds.inViewMessage(amg='New Guides Created.', pos='midCenter', fade=True)

def import_guides():
    guides_manager.load_guides_info()

def export_guides():
    guides_manager.get_guides_info()
    cmds.inViewMessage(amg='Guides Exportados.', pos='midCenter', fade=True)

def export_all_controllers():
    curve_tool.get_all_ctl_curves_data()
    cmds.inViewMessage(amg='Controladores Exportados.', pos='midCenter', fade=True)

def mirror_controllers():
    curve_tool.mirror_curves()
    cmds.inViewMessage(amg='Controladores Espejados.', pos='midCenter', fade=True)

def open_library():
    print("Funcionalidad para abrir la librería de controladores.")

def replace_shapes():
    print("Funcionalidad para reemplazar formas de controladores.")

def export_skin_cluster():
    skinner = skin_manager.SkinManager()
    skinner.export_skins()
    cmds.inViewMessage(amg='Skins Exportadas.', pos='midCenter', fade=True)

def import_skin_cluster():
    skinner = skin_manager.SkinManager()
    skinner.import_skins()
    cmds.inViewMessage(amg='Skins Importadas y Reordenadas.', pos='midCenter', fade=True)

def rig():
    """Función para crear el rig bipedal"""
    from biped.autorig import create_rig
    reload(create_rig)
    cmds.file(new=True, force=True)
    rig = create_rig.AutoRig()
    rig.build()