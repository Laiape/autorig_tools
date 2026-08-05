from utils import data_manager
import maya.cmds as cmds
from importlib import reload

from tools import skin_manager_api
from tools import model_checker
from ui import skin_transfer_UI
from utils import curve_tool
from utils import rig_manager
from utils import guides_manager
from utils import create_rig

reload(skin_manager_api)
reload(model_checker)
reload(curve_tool)
reload(rig_manager)
reload(guides_manager)
reload(create_rig)
reload(data_manager)

def create_custom_menu():
    menu_id = "autorig_menu"

    if cmds.menu(menu_id, exists=True):
        cmds.deleteUI(menu_id)

    cmds.menu(menu_id, label="AutoRig Tools", parent='MayaWindow', tearOff=True)

    cmds.menuItem(label="Reload UI", command=lambda x: rebuild_ui(), image="refresh.png")

    # ── PIPELINE ──────────────────────────────────────────────────────────────
    cmds.menuItem(divider=True, dividerLabel="PIPELINE")

    cmds.menuItem(label="Character Manager", command=lambda x: show_character_manager_ui(), image="fileOpen.png")

    # ── MODELING ──────────────────────────────────────────────────────────────
    cmds.menuItem(divider=True, dividerLabel="MODELING")

    cmds.menuItem(label="Model Checker", command=lambda x: open_model_checker(), image="polyCheckGeometry.png")

    # ── RIGGING ───────────────────────────────────────────────────────────────
    cmds.menuItem(divider=True, dividerLabel="RIGGING")

    cmds.menuItem(label="BUILD RIG", command=lambda x: rig(), boldFont=True, image="kinJoint.png")

    cmds.menuItem(label="Guides Manager", subMenu=True, tearOff=True, image="locator.png")
    cmds.menuItem(label="Create New Guides",  command=lambda x: create_new_guides(), image="confirm.png")
    cmds.menuItem(label="Import Guides",      command=lambda x: import_guides(),     image="move_M.png")
    cmds.menuItem(label="Export Guides",      command=lambda x: export_guides(),     image="copySelected.png")
    cmds.menuItem(label="Mirror Guides",      command=lambda x: mirror_guides(),     image="polyMirror.png")
    cmds.setParent('..', menu=True)

    cmds.menuItem(label="Controllers Manager", subMenu=True, tearOff=True, image="circle.png")
    cmds.menuItem(label="Export All Controllers", command=lambda x: export_all_controllers(), image="save.png")
    cmds.menuItem(label="Mirror Controllers",     command=lambda x: mirror_controllers(),      image="polyMirror.png")
    cmds.setParent('..', menu=True)

    # ── ANIMATION ─────────────────────────────────────────────────────────────
    cmds.menuItem(divider=True, dividerLabel="ANIMATION")

    cmds.menuItem(label="Test Rig", command=lambda x: open_pose_tester(), boldFont=True, image="setKeyframe.png")

    # ── CORRECTIVES ───────────────────────────────────────────────────────────
    cmds.menuItem(divider=True, dividerLabel="CORRECTIVES")

    cmds.menuItem(label="Corrective Blendshapes", subMenu=True, tearOff=True, image="blendShape.png")
    cmds.menuItem(label="Export Corrective Blendshapes", command=lambda x: export_corrective_blendshapes(), image="export.png")
    cmds.menuItem(label="Import Corrective Blendshapes", command=lambda x: import_corrective_blendshapes(), image="import.png")
    cmds.setParent('..', menu=True)

    cmds.menuItem(label="Corrective Skin — Setup / Localize",
                  command=lambda x: setup_corrective_skin(),
                  annotation="Selecciona la malla + joints correctivas: crea/actualiza el skin apilado "
                             "(pesos a 0, blendshape-like) y lo localiza. Rig en pose neutra.",
                  image="paintSkinWeights.png")

    # ── SKINNING ──────────────────────────────────────────────────────────────
    cmds.menuItem(divider=True, dividerLabel="SKINNING")

    cmds.menuItem(label="Skin Cluster Manager", subMenu=True, tearOff=True, image="paintSkinWeights.png")
    cmds.menuItem(label="Export Skin Cluster", command=lambda x: export_skin_cluster(), image="export.png")
    cmds.menuItem(label="Import Skin Cluster", command=lambda x: import_skin_cluster(), image="import.png")
    cmds.menuItem(label="Proxy Skinning", command=lambda x: proxy_skinning(), image="paintSkinWeights.png")
    cmds.setParent('..', menu=True)

    cmds.menuItem(label="Corrective Curve (Pose → Curve → Joints)",
                  command=lambda x: open_corrective_curve_ui(), image="kinJoint.png")
    cmds.menuItem(label="Auto Skin Transfer (Clothes)",
                  command=lambda x: open_skin_transfer_ui(), image="paintSkinWeights.png")

    # ── SIMULATION / ADONIS ───────────────────────────────────────────────────
    cmds.menuItem(divider=True, dividerLabel="SIMULATION")

    cmds.menuItem(label="AdonisFX Copy Weights", command=lambda x: open_adonis_copy_weights(), image="paintSkinWeights.png")


def rebuild_ui():
    from ui import auto_rig_UI
    reload(auto_rig_UI)
    auto_rig_UI.create_custom_menu()


def create_new_asset():
    from utils import rig_manager
    reload(rig_manager)
    rig_manager.create_new_asset()
    cmds.inViewMessage(amg='New Asset Created.', pos='midCenter', fade=True)

def create_new_guides():
    reload(guides_manager)
    guides_manager.create_new_guides()
    cmds.inViewMessage(amg='New Guides Created.', pos='midCenter', fade=True)

def import_guides():
    reload(guides_manager)
    guides_manager.load_guides_info()

def export_guides():
    reload(guides_manager)
    guides_manager.get_guides_info()
    cmds.inViewMessage(amg='Guides Exportados.', pos='midCenter', fade=True)

def mirror_guides():
    reload(guides_manager)
    guides_manager.mirror_guides()
    cmds.inViewMessage(amg='Guides Espejados.', pos='midCenter', fade=True)

def export_all_controllers():
    reload(curve_tool)
    curve_tool.get_all_ctl_curves_data()
    cmds.inViewMessage(amg='Controladores Exportados.', pos='midCenter', fade=True)

def mirror_controllers():
    reload(curve_tool)
    curve_tool.mirror_curves()
    cmds.inViewMessage(amg='Controladores Espejados.', pos='midCenter', fade=True)

def open_library():
    print("Funcionalidad para abrir la librería de controladores.")

def replace_shapes():
    print("Funcionalidad para reemplazar formas de controladores.")

def tag_scene_curves():
    reload(curve_tool)
    curve_tool.tag_scene_curves()
    cmds.inViewMessage(amg='Curves Taggeadas.', pos='midCenter', fade=True)

def export_corrective_blendshapes():
    from tools import corrective_blendshape_manager
    reload(corrective_blendshape_manager)
    path = corrective_blendshape_manager.CorrectiveBlendshapeManager().export()
    if path:
        cmds.inViewMessage(amg='Corrective Blendshapes Exportados.', pos='midCenter', fade=True)

def import_corrective_blendshapes():
    from tools import corrective_blendshape_manager
    reload(corrective_blendshape_manager)
    corrective_blendshape_manager.CorrectiveBlendshapeManager().import_from()
    cmds.inViewMessage(amg='Corrective Blendshapes Importados.', pos='midCenter', fade=True)

def mirror_corrective_blendshapes():
    from tools import corrective_blendshape_manager
    reload(corrective_blendshape_manager)
    corrective_blendshape_manager.CorrectiveBlendshapeManager().mirror_in_scene()
    cmds.inViewMessage(amg='Corrective Blendshapes Espejados.', pos='midCenter', fade=True)

def mirror_corrective_blendshape_targets():
    from tools import corrective_blendshape_manager
    reload(corrective_blendshape_manager)
    corrective_blendshape_manager.CorrectiveBlendshapeManager().mirror_targets()
    cmds.inViewMessage(amg='Targets Espejados.', pos='midCenter', fade=True)

def export_skin_cluster():
    reload(skin_manager_api)
    skinner = skin_manager_api.SkinManager()
    skinner.export_skins()
    cmds.inViewMessage(amg='Skins Exportadas.', pos='midCenter', fade=True)

def import_skin_cluster():
    skinner = skin_manager_api.SkinManager()
    reload(skin_manager_api)
    skinner.import_skins()
    cmds.inViewMessage(amg='Skins Importadas y Reordenadas.', pos='midCenter', fade=True)

def copy_skin_cluster():
    skinner = skin_manager_api.SkinManager()
    reload(skin_manager_api)
    skinner.copy_skin_cluster()
    cmds.inViewMessage(amg='Skin Cluster Copiado.', pos='midCenter', fade=True)

def open_skin_transfer_ui():
    from ui import skin_transfer_UI
    reload(skin_transfer_UI)
    skin_transfer_UI.show()

def proxy_skinning():
    """
    Proxy skinning del cuerpo con la cadena recomendada (Geodesic Voxel Binding -> transferir
    con copySkinWeights -> optimizar -> Delta Mush). No usa auto_skin_transfer.

    Selección esperada (en cualquier orden): la malla PROXY, la malla de ALTA y la RAÍZ del
    esqueleto (joint). El PRIMER mesh seleccionado es el proxy; el segundo, la alta.
    """
    from tools import proxy_skinning as ps
    reload(ps)

    # orderedSelection preserva el orden en que se seleccionó (proxy primero, alta después)
    sel = cmds.ls(sl=True, orderedSelection=True) or []
    meshes, joints, seen = [], [], set()
    for node in sel:
        nt = cmds.nodeType(node)
        if nt == "joint":
            if node not in seen:
                seen.add(node); joints.append(node)
            continue
        # normaliza a transform tanto si se seleccionó la malla como su shape
        xform = None
        if nt == "mesh":
            par = cmds.listRelatives(node, parent=True, type="transform")
            xform = par[0] if par else None
        elif cmds.listRelatives(node, shapes=True, type="mesh"):
            xform = node
        if xform and xform not in seen:
            seen.add(xform); meshes.append(xform)

    if len(meshes) != 2 or len(joints) != 1:
        cmds.inViewMessage(
            amg="Proxy Skinning: selecciona <hl>PROXY</hl>, <hl>ALTA</hl> y la <hl>raíz del "
                "esqueleto</hl> en ese orden (2 mallas + 1 joint).",
            pos='midCenter', fade=True, fadeStayTime=2500)
        return

    proxy, high, root = meshes[0], meshes[1], joints[0]
    cmds.undoInfo(openChunk=True)
    try:
        res = ps.proxy_skin(proxy, high, root, max_influences=4, uv_space=False,
                            use_labels=True, delta_mush=True, bake=False)
    finally:
        cmds.undoInfo(closeChunk=True)

    rep = res.get("report", {})
    cmds.inViewMessage(
        amg=f"Proxy Skinning: proxy <hl>{proxy}</hl> → alta <hl>{high}</hl> · máx "
            f"influencias/vértice: <hl>{rep.get('max_per_vertex', '?')}</hl>.",
        pos='midCenter', fade=True, fadeStayTime=2500)

def export_source_skin_data():
    from tools import mesh_data_exporter
    reload(mesh_data_exporter)
    exported = mesh_data_exporter.SourceSkinExporter().export_all()
    n = len(exported)
    cmds.inViewMessage(
        amg=f"Source skin data exported: <hl>{n}</hl> mesh(es).",
        pos="midCenter", fade=True
    )
    
def rig():
    """Función para crear el rig bipedal"""
    cmds.file(new=True, force=True)
    data_manager.DataExportBiped().new_build()
    reload(create_rig)
    rig = create_rig.AutoRig()
    rig.build()

def open_model_checker():
    from tools import model_checker
    reload(model_checker)
    model_checker.show()

def show_character_manager_ui():
    from utils import character_manager
    reload(character_manager)
    pro_asset_manager = character_manager.AssetManagerUI()
    pro_asset_manager.show()

def show_curve_library():
    from tools import curve_library
    reload(curve_library)
    curve_library.show()

def show_rig_tools():
    from tools import rig_tools
    reload(rig_tools)
    rig_tools.show()

def open_adonis_copy_weights():
    from adonis import copyWeightsAdonis
    reload(copyWeightsAdonis)
    copyWeightsAdonis.show()


def open_corrective_curve_ui():
    from ui import corrective_curve_UI
    reload(corrective_curve_UI)
    corrective_curve_UI.show()


def setup_corrective_skin():
    from utils import correctives
    reload(correctives)
    sel = cmds.ls(selection=True) or []
    meshes = [s for s in sel
              if (cmds.listRelatives(s, shapes=True, noIntermediate=True) or [])
              and cmds.nodeType((cmds.listRelatives(s, shapes=True, noIntermediate=True))[0]) == "mesh"]
    joints = [s for s in sel if cmds.nodeType(s) == "joint"]
    if not meshes:
        cmds.inViewMessage(amg="Selecciona la MALLA (+ joints correctivas).", pos='midCenter', fade=True)
        return
    result = correctives.corrective_skin_setup(meshes[0], joints)
    cmds.inViewMessage(
        amg=f"Corrective skin <hl>{result['skin']}</hl>: {len(result['added'])} nuevas, "
            f"{result['localized']} localizadas.",
        pos='midCenter', fade=True)


def open_pose_tester():
    from tools import pose_tester
    reload(pose_tester)
    from ui import pose_tester_UI
    reload(pose_tester_UI)
    pose_tester_UI.show()
